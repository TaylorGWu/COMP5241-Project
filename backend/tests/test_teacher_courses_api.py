from __future__ import annotations

import httpx
import pytest

from app.api.routes import demo
from app.main import app


@pytest.fixture(autouse=True)
def reset_courses():
    demo.reset_course_workspace()


async def request(method: str, path: str, body: dict | None = None):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, json=body)


async def create_course(title: str = "Git basics") -> dict:
    response = await request("POST", "/api/demo/courses", {"title": title, "description": "Short course", "audience": "Beginners", "durationMin": 45})
    assert response.status_code == 201, response.text
    return response.json()


async def test_course_api_creates_draft_with_first_chapter_and_lists_it():
    course = await create_course()

    listed = await request("GET", "/api/demo/courses")

    assert course["status"] == "draft"
    assert len(course["chapterIds"]) == 1
    assert listed.json()["courses"][0]["id"] == course["id"]


async def test_chapter_routes_keep_order_and_course_ownership():
    first = await create_course("Git")
    second = await create_course("AI")
    first_chapter = first["chapterIds"][0]

    added = await request("POST", f"/api/demo/courses/{first['id']}/chapters", {"title": "Branching"})
    reordered = await request("POST", f"/api/demo/courses/{first['id']}/chapters/reorder", {"chapterIds": [added.json()["id"], first_chapter]})
    cross_course = await request("GET", f"/api/demo/courses/{second['id']}/chapters/{first_chapter}")

    assert [chapter["order"] for chapter in reordered.json()["chapters"]] == [1, 2]
    assert cross_course.status_code == 404


async def test_publish_requires_ready_chapter_then_can_be_withdrawn():
    course = await create_course()
    chapter_id = course["chapterIds"][0]

    blocked = await request("POST", f"/api/demo/courses/{course['id']}/publish")
    prepared = await request("PATCH", f"/api/demo/courses/{course['id']}/chapters/{chapter_id}", {"status": "ready", "package": {"slides": []}})
    published = await request("POST", f"/api/demo/courses/{course['id']}/publish")
    withdrawn = await request("POST", f"/api/demo/courses/{course['id']}/unpublish")

    assert blocked.status_code == 409
    assert prepared.status_code == 200
    assert published.json()["status"] == "published"
    assert withdrawn.json()["status"] == "draft"


async def test_generating_a_chapter_does_not_replace_another_chapter_package(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    first_id = course["chapterIds"][0]
    second = await request("POST", f"/api/demo/courses/{course['id']}/chapters", {"title": "Branching"})
    await request("PATCH", f"/api/demo/courses/{course['id']}/chapters/{first_id}", {"status": "ready", "package": {"marker": "keep"}})

    generated = await request("POST", f"/api/demo/courses/{course['id']}/chapters/{second.json()['id']}/generate", {"topic": "Git branches", "audience": "Beginners", "duration_min": 30})
    first = await request("GET", f"/api/demo/courses/{course['id']}/chapters/{first_id}")

    assert generated.status_code == 200, generated.text
    assert generated.json()["chapter"]["status"] == "ready"
    assert first.json()["package"] == {"marker": "keep"}


async def test_activating_a_chapter_makes_its_ir_available_to_teacher_tools(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    chapter_id = course["chapterIds"][0]
    generated = await request(
        "POST",
        f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/generate",
        {"topic": "Git branches", "audience": "Beginners", "duration_min": 30},
    )
    assert generated.status_code == 200

    activated = await request("POST", f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/activate")
    questions = await request("POST", "/api/demo/questions", {"use_real_model": False})

    assert activated.status_code == 200
    assert questions.status_code == 200
    assert questions.json()["package"]["questionSet"]["questions"]


async def test_teacher_can_import_students_create_an_invite_and_view_actionable_analytics():
    course = await create_course()
    course_id = course["id"]

    imported = await request(
        "POST",
        f"/api/demo/courses/{course_id}/students/import",
        {"rows": [
            {"row": 2, "name": "Ada Lovelace", "email": "ada@example.com"},
            {"row": 3, "name": "", "email": "missing-name@example.com"},
        ]},
    )
    invite = await request("POST", f"/api/demo/courses/{course_id}/invites")
    analytics = await request("GET", f"/api/demo/courses/{course_id}/analytics")

    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    assert imported.json()["errors"] == [{"row": 3, "message": "name is required"}]
    assert invite.status_code == 201
    assert invite.json()["code"].startswith(f"invite-{course_id}-")
    assert analytics.status_code == 200
    assert analytics.json()["enrolledCount"] == 1
    assert analytics.json()["averageScore"] == 0


async def test_teacher_can_attach_a_syllabus_when_setting_up_a_course():
    course = await create_course("Software engineering foundations")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        uploaded = await client.post(
            f"/api/demo/courses/{course['id']}/syllabus",
            content=b"Course outcomes\n- Explain version control\n- Review a pull request",
            headers={"content-type": "application/octet-stream", "x-filename": "course-syllabus.md"},
        )

    assert uploaded.status_code == 200, uploaded.text
    payload = uploaded.json()
    assert payload["syllabusFilename"] == "course-syllabus.md"
    assert payload["syllabusChars"] > 20
    assert payload["syllabusStatus"] == "ok"
    assert "syllabusText" not in payload
