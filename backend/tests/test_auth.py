"""Accounts and qualification review use only the isolated workspace fixture."""
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import demo

ORIGIN = "http://localhost:3000"
PASSWORD = "a long example password"
PDF = b"%PDF-1.7\nqualification\n%%EOF"


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def headers(client):
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrfToken"]}


def register(client, role="student", email="learner@example.test", **extra):
    fields = dict(name="Test Learner", email=email, password=PASSWORD, role=role)
    fields.update(extra)
    files = {"qualification": ("qualification.pdf", PDF, "application/pdf")} if role == "instructor" else None
    return client.post("/api/auth/register", data=fields, files=files, headers=headers(client))


def test_student_registration_normalization_cookie_persistence_and_logout(client):
    response = register(client, email="  LEARNER@Example.test ")
    assert response.status_code == 201
    user = response.json()["user"]
    assert user == dict(id=user["id"], name="Test Learner", email="learner@example.test", role="student", status="active", reviewReason=None)
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["user"] == user
    assert register(client).status_code == 409
    token = client.get("/api/auth/me").json()["csrfToken"]
    cookie = client.cookies.get("coursework_session")
    assert client.post("/api/auth/logout", headers={"Origin": ORIGIN, "X-CSRF-Token": token}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("coursework_session", cookie)
    assert client.get("/api/auth/me").status_code == 401


def test_public_roles_fields_password_and_required_qualification(client):
    assert register(client, role="admin").status_code == 422
    assert register(client, active="true").status_code == 422
    assert register(client, password="short").status_code == 422
    response = client.post("/api/auth/register", data=dict(name="Tutor", email="t@example.test", password=PASSWORD, role="instructor"), headers=headers(client))
    assert response.status_code == 422
    assert client.get("/api/admin/applications").status_code == 401


def test_origin_csrf_and_json_only_login(client):
    assert client.post("/api/auth/login", json={"email":"x", "password":PASSWORD}).status_code == 403
    valid = headers(client)
    assert client.post("/api/auth/login", json={"email":"x", "password":PASSWORD}, headers={**valid,"Origin":"null"}).status_code == 403
    assert client.post("/api/auth/login", json={"email":"x", "password":PASSWORD}, headers={**valid,"Origin":"https://evil.test"}).status_code == 403
    assert client.post("/api/auth/login", data={"email":"x", "password":PASSWORD}, headers=valid).status_code == 415


def test_login_rotation_generic_failure_expiry_disabled_and_throttle(client):
    register(client)
    old = client.cookies.get("coursework_session")
    response = client.post("/api/auth/login", json={"email":"learner@example.test", "password":PASSWORD}, headers=headers(client))
    assert response.status_code == 200
    assert old != client.cookies.get("coursework_session")
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("UPDATE users SET active=0")
    assert client.get("/api/auth/me").status_code == 401
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("UPDATE users SET active=1")
        db.execute("UPDATE sessions SET expires_at=?", (time.time()-1,))
    assert client.get("/api/auth/me").status_code == 401
    responses = [client.post("/api/auth/login", json={"email":"missing@example.test", "password":PASSWORD}, headers=headers(client)) for _ in range(7)]
    assert responses[0].status_code == 401
    assert responses[-1].status_code == 429
    assert "password" not in response.json()["user"]


def test_instructor_review_rejection_resubmission_approval_and_private_files(client):
    from app.services.auth import get_auth_store
    response = register(client, role="instructor")
    assert response.status_code == 201
    applicant = response.json()["user"]
    assert applicant["status"] == "pending"
    assert client.get("/api/admin/applications").status_code == 403
    assert client.get("/api/auth/qualification").content == PDF
    admin = get_auth_store().create_user(name="Reviewer", email="admin@example.test", password=PASSWORD, role="admin")
    with TestClient(app) as reviewer:
        login = reviewer.post("/api/auth/login", json=dict(email=admin["email"], password=PASSWORD), headers=headers(reviewer))
        assert login.status_code == 200
        entries = reviewer.get("/api/admin/applications").json()["applications"]
        assert entries[0]["qualificationFilename"] == "qualification.pdf"
        assert reviewer.get(f"/api/admin/applications/{applicant['id']}/qualification").content == PDF
        path = f"/api/admin/applications/{applicant['id']}/review"
        assert reviewer.post(path,json=dict(decision="rejected",reason=""),headers=headers(reviewer)).status_code == 422
        assert reviewer.post(path,json=dict(decision="rejected",reason="Please include your teaching role"),headers=headers(reviewer)).status_code == 200
        assert client.get("/api/auth/me").json()["user"]["status"] == "rejected"
        assert client.post("/api/auth/qualification", files={"qualification": ("updated.pdf", PDF, "application/pdf")},headers=headers(client)).json()["user"]["status"] == "pending"
        assert reviewer.post(path,json=dict(decision="approved",reason="Reviewed document"),headers=headers(reviewer)).status_code == 200
        assert client.get("/api/auth/me").json()["user"]["status"] == "approved"
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        assert db.execute("SELECT count(*) FROM qualification_reviews").fetchone()[0] == 2
    with TestClient(app) as other:
        register(other, email="other@example.test")
        assert other.get("/api/auth/qualification").status_code == 403
        assert other.get(f"/api/admin/applications/{applicant['id']}/qualification").status_code == 403
    download = client.get("/api/auth/qualification")
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("filename,data,mime", [("fake.pdf",b"hello","application/pdf"),("a.svg",b"<svg/>","image/svg+xml"),("big.pdf",b"%PDF-"+b"x"*(5*1024*1024),"application/pdf")])
def test_bad_qualifications_fail_without_creating_account(client,filename,data,mime):
    response=client.post("/api/auth/register",data=dict(name="Tutor",email="t@example.test",password=PASSWORD,role="instructor"),files={"qualification":(filename,data,mime)},headers=headers(client))
    assert response.status_code in (413,422)
    assert client.get("/api/auth/me").status_code == 401


def test_course_assignment_is_explicit_and_never_reassigns(client):
    from app.services.auth import get_auth_store
    store=get_auth_store()
    first=store.create_user(name="One",email="one@example.test",password=PASSWORD,role="instructor",qualification=("q.pdf","application/pdf",PDF))
    second=store.create_user(name="Two",email="two@example.test",password=PASSWORD,role="instructor",qualification=("q.pdf","application/pdf",PDF))
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("INSERT INTO courses(id,payload_json) VALUES ('legacy','{}')")
        assert db.execute("SELECT count(*) FROM course_owners").fetchone()[0]==0
    assert store.claim_unowned(first["email"],["legacy"]) == ["legacy"]
    with pytest.raises(ValueError):
        store.claim_unowned(second["email"],["legacy"])
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        assert db.execute("SELECT instructor_id FROM course_owners").fetchone()[0]==first["id"]
        assert db.execute("SELECT payload_json FROM courses WHERE id='legacy'").fetchone()[0]=='{}'


def test_migration_backup_preserves_legacy_and_does_not_repeat(tmp_path):
    from app.services.auth import AuthStore
    path=tmp_path/"legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE courses(id TEXT PRIMARY KEY,payload_json TEXT NOT NULL)")
        db.execute("INSERT INTO courses VALUES('old','unchanged')")
    AuthStore(path)
    backups=list(tmp_path.glob("*.bak"))
    assert len(backups)==1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute("SELECT payload_json FROM courses").fetchone()[0]=="unchanged"
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone()
    AuthStore(path)
    assert len(list(tmp_path.glob("*.bak")))==1
    assert path.stat().st_mode & 0o777 == 0o600


def test_password_and_session_secrets_are_hashed_and_old_cookie_is_revoked(client):
    from app.services.auth import AuthStore, digest
    result=register(client)
    old=client.cookies.get("coursework_session")
    csrf=result.json()["csrfToken"]
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        stored=db.execute("SELECT password_hash FROM users").fetchone()[0]
        assert stored.startswith("$argon2id$") and PASSWORD not in stored
        assert db.execute("SELECT token_digest,csrf_digest FROM sessions").fetchone()==(digest(old),digest(csrf))
    login=client.post("/api/auth/login",json=dict(email="learner@example.test",password=PASSWORD),headers=headers(client))
    assert login.status_code==200
    assert AuthStore(demo.TEACHER_WORKSPACE_DB).session(old) is None
    assert client.post("/api/auth/logout",headers={"Origin":ORIGIN,"X-CSRF-Token":csrf}).status_code==403
    assert client.get("/api/auth/csrf").json()["csrfToken"]==login.json()["csrfToken"]


def test_qualification_headers_safe_for_unicode_and_windows_paths(client):
    result=client.post("/api/auth/register",data=dict(name="Tutor",email="t@example.test",password=PASSWORD,role="instructor"),files={"qualification":("C:\\private\\教師.pdf",PDF,"application/pdf")},headers=headers(client))
    assert result.status_code==201
    downloaded=client.get("/api/auth/qualification")
    assert "private" not in downloaded.headers["content-disposition"]
    assert "%E6%95%99" in downloaded.headers["content-disposition"]


def test_dependency_requires_approved_instructor_and_fresh_status(client):
    from fastapi import Depends, FastAPI
    from app.services.auth import approved_instructor, get_auth_store
    protected=FastAPI()
    @protected.get("/protected")
    async def route(user=Depends(approved_instructor)):
        return {"id":user["id"]}
    register(client,role="instructor")
    token=client.cookies.get("coursework_session")
    with TestClient(protected) as private:
        assert private.get("/protected").status_code==401
        private.cookies.set("coursework_session",token)
        assert private.get("/protected").status_code==403
        with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
            db.execute("UPDATE users SET status='approved'")
        assert private.get("/protected").status_code==200
        with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
            db.execute("UPDATE users SET status='rejected'")
        assert private.get("/protected").status_code==403


def test_expired_challenge_and_account_throttle_persist_across_store_instances(client):
    from app.services.auth import AuthStore
    valid=headers(client)
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("UPDATE auth_challenges SET expires_at=0")
    assert client.post("/api/auth/login",json=dict(email="missing@example.test",password=PASSWORD),headers=valid).status_code==403
    for _ in range(6):
        AuthStore(demo.TEACHER_WORKSPACE_DB).throttle("one-ip","same@example.test")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        AuthStore(demo.TEACHER_WORKSPACE_DB).throttle("different-ip"," SAME@EXAMPLE.TEST ")
    assert error.value.status_code==429


def test_cli_password_is_hidden_and_assignment_is_all_or_nothing(monkeypatch,client,capsys):
    from app import auth_cli
    from app.services.auth import get_auth_store
    prompts=[]
    def hidden(prompt):
        prompts.append(prompt)
        return PASSWORD
    monkeypatch.setattr(auth_cli.getpass,"getpass",hidden)
    auth_cli.main(["create-admin","--email","admin@example.test","--name","Local Admin"])
    assert len(prompts)==2
    assert PASSWORD not in capsys.readouterr().out
    assert get_auth_store().authenticate("admin@example.test",PASSWORD)["role"]=="admin"
    user=get_auth_store().create_user(name="Tutor",email="t@example.test",password=PASSWORD,role="instructor",qualification=("q.pdf","application/pdf",PDF))
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("INSERT INTO courses VALUES('first','{}')")
    with pytest.raises(ValueError):
        get_auth_store().claim_unowned(user["email"],["first","missing"])
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        assert db.execute("SELECT count(*) FROM course_owners").fetchone()[0]==0


@pytest.mark.parametrize("value", ["https://evil.test/courses","//evil.test/courses","/admin","/courses-other","/courses/\\evil", "/%2f%2fevil.test"])
def test_redirects_only_allow_role_destination(value):
    from app.services.auth import safe_next
    assert safe_next(value,{"role":"instructor","status":"approved"})=="/courses"


def test_production_uses_secure_cookies_and_wildcard_origins_are_rejected(monkeypatch):
    from app.services.auth import secure_cookie
    from app.config import Settings, settings
    monkeypatch.setattr(settings,"app_env","production")
    assert secure_cookie()
    with pytest.raises(ValueError):
        Settings(cors_origins=["*"])


def test_login_generic_failures_and_invalid_images(client):
    register(client)
    missing=client.post("/api/auth/login",json=dict(email="missing@example.test",password=PASSWORD),headers=headers(client))
    wrong=client.post("/api/auth/login",json=dict(email="learner@example.test",password="incorrect long password"),headers=headers(client))
    assert missing.status_code==wrong.status_code==401
    assert missing.json()==wrong.json()
    invalid=client.post("/api/auth/register",data=dict(name="Tutor",email="t@example.test",password=PASSWORD,role="instructor"),files={"qualification":("broken.png",b"\x89PNG\r\n\x1a\ninvalid","image/png")},headers=headers(client))
    assert invalid.status_code==422


def test_truncated_jpeg_is_not_accepted_as_a_qualification(client):
    from io import BytesIO
    from PIL import Image
    output=BytesIO()
    Image.new("RGB",(8,8),"white").save(output,format="JPEG")
    response=client.post("/api/auth/register",data=dict(name="Tutor",email="t@example.test",password=PASSWORD,role="instructor"),files={"qualification":("broken.jpg",output.getvalue()[:-2],"image/jpeg")},headers=headers(client))
    assert response.status_code==422


def test_bounded_json_body_and_invalid_session_do_not_reach_credentials(client):
    valid=headers(client)
    response=client.post("/api/auth/login",content=b"x"*17000,headers={**valid,"Content-Type":"application/json"})
    assert response.status_code==413
    client.cookies.set("coursework_session","attacker-selected-session",domain="testserver.local")
    response=register(client)
    assert response.status_code==201
    assert client.cookies.get("coursework_session")!="attacker-selected-session"


def test_file_resubmission_denies_pending_and_approved_accounts(client):
    register(client,role="instructor")
    response=client.post("/api/auth/qualification",files={"qualification":("q.pdf",PDF,"application/pdf")},headers=headers(client))
    assert response.status_code==409
    with sqlite3.connect(demo.TEACHER_WORKSPACE_DB) as db:
        db.execute("UPDATE users SET status='approved'")
    response=client.post("/api/auth/qualification",files={"qualification":("q.pdf",PDF,"application/pdf")},headers=headers(client))
    assert response.status_code==409
