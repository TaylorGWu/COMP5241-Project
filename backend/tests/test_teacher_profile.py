"""Teacher profiles are private account data, not an approval mechanism."""
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.auth import AuthStore, get_auth_store

PASSWORD = "a long profile test password"
ORIGIN = "http://localhost:3000"


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


def headers(client):
    return {"Origin": ORIGIN, "X-CSRF-Token": client.get("/api/auth/csrf").json()["csrfToken"]}


def login(client, role="instructor", email="profile@example.test"):
    user = get_auth_store().create_user(name="Teacher", email=email, password=PASSWORD, role=role)
    result = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}, headers=headers(client))
    assert result.status_code == 200
    return user


def photo():
    buffer = BytesIO()
    Image.new("RGB", (800, 600), (40, 90, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_teacher_profile_persists_without_changing_review_status(client):
    user = login(client)
    result = client.get("/api/auth/profile")
    assert result.status_code == 200
    assert result.json()["profile"]["name"] == "Teacher"
    values = dict(name="陳老師", bio="I teach testing.", institution="Example College", independent=False,
                  position="Lecturer", university="Example University", degree="master", experience="3-5",
                  subjects=["software-engineering", "databases"], otherSubject="")
    result = client.put("/api/auth/profile", json=values, headers=headers(client))
    assert result.status_code == 200
    assert all(result.json()["profile"][key] == value for key, value in values.items())
    assert client.get("/api/auth/me").json()["user"]["status"] == "pending"
    assert client.get("/api/auth/me").json()["user"]["name"] == "陳老師"
    # Reopen the store, rather than trusting an in-memory echo.
    assert AuthStore(get_auth_store().path).profile(user["id"])["university"] == "Example University"
    assert client.get("/api/demo/courses").status_code == 403


@pytest.mark.parametrize("changes", [
    {"name": ""}, {"degree": "fake"}, {"experience": "fake"}, {"subjects": ["fake"]},
    {"subjects": ["databases", "databases"]}, {"bio": "x" * 1001},
    {"status": "approved"}, {"independent": "yes"}, {"subjects": "databases"},
    {"subjects": ["other"], "otherSubject": ""},
])
def test_invalid_profile_is_rejected_atomically(client, changes):
    login(client)
    before = client.get("/api/auth/profile").json()
    response = client.put("/api/auth/profile", json={"name": "Changed", **changes}, headers=headers(client))
    assert response.status_code == 422
    assert client.get("/api/auth/profile").json() == before


def test_private_profile_role_and_csrf_boundaries(client):
    assert client.get("/api/auth/profile").status_code == 401
    login(client, role="student")
    assert client.get("/api/auth/profile").status_code == 403
    assert client.put("/api/auth/profile", json={"name": "Changed"}, headers=headers(client)).status_code == 403
    client.post("/api/auth/logout", headers=headers(client))
    login(client, email="teacher2@example.test")
    assert client.put("/api/auth/profile", json={"name": "Changed"}).status_code == 403
    assert client.get("/api/admin/applications/unknown/profile").status_code == 403


def test_avatar_is_private_sanitized_replaceable_and_removable(client):
    user = login(client)
    assert client.get("/api/auth/avatar").status_code == 404
    upload = client.put("/api/auth/avatar", files={"avatar": ("photo.png", photo(), "image/png")}, headers=headers(client))
    assert upload.status_code == 200
    assert upload.json()["profile"]["hasAvatar"] is True
    image = client.get("/api/auth/avatar")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "no-store"
    assert image.headers["x-content-type-options"] == "nosniff"
    with Image.open(BytesIO(image.content)) as clean:
        assert clean.size == (512, 384)
        assert not clean.getexif()
    client.post("/api/auth/logout", headers=headers(client))
    login(client, email="other@example.test")
    assert client.get("/api/auth/avatar").status_code == 404
    assert client.get(f"/api/admin/applications/{user['id']}/avatar").status_code == 403
    assert client.get("/api/auth/profile").json()["profile"]["university"] == ""
    client.post("/api/auth/logout", headers=headers(client))
    client.post("/api/auth/login", json={"email": user["email"], "password": PASSWORD}, headers=headers(client))
    assert client.delete("/api/auth/avatar").status_code == 403
    assert client.delete("/api/auth/avatar", headers=headers(client)).status_code == 200
    assert client.get("/api/auth/avatar").status_code == 404
    assert client.get("/api/auth/profile").json()["profile"]["hasAvatar"] is False


@pytest.mark.parametrize("filename,content,mime", [
    ("photo.svg", b"<svg></svg>", "image/svg+xml"),
    ("photo.jpg", b"not an image", "image/jpeg"),
    ("photo.png", b"", "image/png"),
    ("photo.png", b"x" * (5 * 1024 * 1024 + 1), "image/png"),
])
def test_invalid_avatar_does_not_replace_existing_photo(client, filename, content, mime):
    login(client)
    assert client.put("/api/auth/avatar", files={"avatar": ("photo.png", photo(), "image/png")}, headers=headers(client)).status_code == 200
    before = client.get("/api/auth/avatar").content
    response = client.put("/api/auth/avatar", files={"avatar": (filename, content, mime)}, headers=headers(client))
    assert response.status_code in (413, 422)
    assert client.get("/api/auth/avatar").content == before


def test_admin_can_read_submitted_applicant_profile_only(client):
    user = login(client)
    client.put("/api/auth/profile", json={"name": "Teacher", "university": "Example University"}, headers=headers(client))
    client.put("/api/auth/avatar", files={"avatar": ("photo.png", photo(), "image/png")}, headers=headers(client))
    client.post("/api/auth/qualification", files={"qualification": ("proof.pdf", b"%PDF-1.7\nproof\n%%EOF", "application/pdf")}, headers=headers(client))
    client.post("/api/auth/logout", headers=headers(client))
    login(client, role="admin", email="admin@example.test")
    result = client.get(f"/api/admin/applications/{user['id']}/profile")
    assert result.status_code == 200
    assert result.json()["profile"]["university"] == "Example University"
    assert client.get(f"/api/admin/applications/{user['id']}/avatar").status_code == 200
    assert client.get("/api/admin/applications/missing/profile").status_code == 404
