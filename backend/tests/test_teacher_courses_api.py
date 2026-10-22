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


def test_demo_workspace_is_isolated_from_the_development_server(tmp_path):
    """A test run must never write to the local teacher demo database."""
    assert demo.TEACHER_WORKSPACE_DB.parent == tmp_path


async def test_course_api_creates_draft_with_first_chapter_and_lists_it():
    course = await create_course()

    listed = await request("GET", "/api/demo/courses")

    assert course["status"] == "draft"
    assert len(course["chapterIds"]) == 1
    assert listed.json()["courses"][0]["id"] == course["id"]


async def test_course_creation_keeps_a_catalogue_ready_teaching_blueprint():
    response = await request(
        "POST",
        "/api/demo/courses",
        {
            "title": "Git collaboration",
            "description": "A reviewed collaboration mini-course",
            "audience": "University beginners",
            "durationMin": 90,
            "courseCode": "SE-101",
            "subject": "Software Engineering",
            "level": "Undergraduate",
            "learningObjectives": ["Explain branch isolation", "Review a pull request before merging"],
        },
    )

    assert response.status_code == 201, response.text
    course = response.json()
    assert course["courseCode"] == "SE-101"
    assert course["subject"] == "Software Engineering"
    assert course["level"] == "Undergraduate"
    assert course["learningObjectives"] == [
        {"id": "LO1", "text": "Explain branch isolation"},
        {"id": "LO2", "text": "Review a pull request before merging"},
    ]


async def test_course_blueprint_edits_and_publication_leave_an_audit_trail():
    course = await create_course("Git collaboration")
    course_id = course["id"]
    chapter_id = course["chapterIds"][0]

    updated = await request(
        "PATCH",
        f"/api/demo/courses/{course_id}",
        {
            "courseCode": "SE-101",
            "subject": "Software Engineering",
            "level": "Undergraduate",
            "learningObjectives": [{"id": "LO1", "text": "Explain branch isolation"}],
        },
    )
    await request(
        "PATCH",
        f"/api/demo/courses/{course_id}/chapters/{chapter_id}",
        {"status": "ready", "package": {"slides": []}},
    )
    published = await request("POST", f"/api/demo/courses/{course_id}/publish")
    activity = await request("GET", f"/api/demo/courses/{course_id}/activity")

    assert updated.status_code == 200, updated.text
    assert updated.json()["courseCode"] == "SE-101"
    assert published.status_code == 200, published.text
    # The UI intentionally shows the newest review event first.
    assert [item["kind"] for item in activity.json()["activity"]] == ["publish", "course-update"]
    assert activity.json()["activity"][1]["changedFields"] == [
        "course_code", "subject", "level", "learning_objectives"
    ]


async def test_course_coverage_explains_which_outcomes_are_taught_and_assessed():
    course = await request(
        "POST",
        "/api/demo/courses",
        {
            "title": "Git collaboration",
            "description": "Short course",
            "audience": "Beginners",
            "durationMin": 45,
            "learningObjectives": ["Explain branch isolation", "Review a pull request"],
        },
    )
    course_id = course.json()["id"]
    chapter_id = course.json()["chapterIds"][0]
    await request(
        "PATCH",
        f"/api/demo/courses/{course_id}/chapters/{chapter_id}",
        {
            "status": "ready",
            "package": {
                "slideDeck": {"slides": [{"id": "slide-1", "objectiveIds": ["LO1"]}]},
                "questionSet": {"questions": [{"id": "question-1", "objectiveIds": ["LO1"]}]},
            },
        },
    )

    coverage = await request("GET", f"/api/demo/courses/{course_id}/coverage")

    assert coverage.status_code == 200, coverage.text
    assert coverage.json()["outcomes"] == [
        {"id": "LO1", "text": "Explain branch isolation", "slideCount": 1, "questionCount": 1, "status": "covered"},
        {"id": "LO2", "text": "Review a pull request", "slideCount": 0, "questionCount": 0, "status": "missing"},
    ]


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


async def test_chapter_generation_uses_course_learning_objectives_by_default(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    created = await request(
        "POST", "/api/demo/courses",
        {"title": "Git collaboration", "learningObjectives": ["Explain branch isolation", "Review a pull request"]},
    )
    course = created.json()
    chapter_id = course["chapterIds"][0]

    generated = await request(
        "POST", f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/generate",
        {"topic": "Git collaboration", "use_real_model": False},
    )

    assert generated.status_code == 200, generated.text
    assert generated.json()["package"]["project"]["learningObjectives"] == course["learningObjectives"]


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


async def test_reactivated_json_chapter_can_be_edited_and_the_change_persists(monkeypatch):
    """Browser refresh stores JSON; activation must restore a validated IR object."""
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    chapter_id = course["chapterIds"][0]
    path = f"/api/demo/courses/{course['id']}/chapters/{chapter_id}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    assert generated.status_code == 200, generated.text
    package = generated.json()["package"]
    slide_id = package["slideDeck"]["slides"][0]["id"]
    saved = await request("PATCH", path, {"package": package, "status": "ready"})
    assert saved.status_code == 200, saved.text

    activated = await request("POST", f"{path}/activate")
    # The browser used to send a second JSON save after activation, severing
    # the repository object's reference to STATE.package.
    await request("PATCH", path, {"package": package, "status": "ready"})
    changed = await request(
        "POST", "/api/demo/manual-edit",
        {"kind": "slide", "target_id": slide_id, "payload": {"title": "Teacher-reviewed title"}},
    )
    reloaded = await request("GET", path)

    assert activated.status_code == 200, activated.text
    assert changed.status_code == 200, changed.text
    assert changed.json()["package"]["slideDeck"]["slides"][0]["title"] == "Teacher-reviewed title"
    assert reloaded.json()["package"]["slideDeck"]["slides"][0]["title"] == "Teacher-reviewed title"


async def test_ai_change_after_chapter_refresh_waits_for_teacher_approval(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    package = generated.json()["package"]
    original_title = package["slideDeck"]["slides"][1]["title"]
    await request("PATCH", path, {"package": package, "status": "ready"})
    await request("POST", f"{path}/activate")
    await request("PATCH", path, {"package": package, "status": "ready"})

    proposed = await request("POST", "/api/demo/edit", {"message": "Make slide 2 easier", "use_real_model": False})
    before_approval = await request("GET", path)
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["call_names"][:2] == ["read_slide", "patch_slide"]
    assert before_approval.json()["package"]["slideDeck"]["slides"][1]["title"] == original_title

    patch_id = proposed.json()["patches"][0]["id"]
    applied = await request("POST", "/api/demo/apply", {"patch_id": patch_id})
    after_approval = await request("GET", path)
    assert applied.status_code == 200, applied.text
    assert after_approval.json()["package"]["slideDeck"]["slides"][1]["title"] == "分支是什么(入门版)"


async def test_reactivating_a_chapter_keeps_pending_field_reviews(monkeypatch):
    """The workspace activates on page load; doing so must not erase a review."""
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    assert generated.status_code == 200, generated.text

    proposed = await request(
        "POST",
        f"{path}/edit",
        {"message": "Make slide 2 easier", "use_real_model": False, "target": "slides"},
    )
    assert proposed.status_code == 200, proposed.text
    proposal_ids = {patch["id"] for patch in proposed.json()["patches"]}

    activated = await request("POST", f"{path}/activate")
    state = await request("GET", "/api/demo/state")

    assert activated.status_code == 200, activated.text
    assert proposal_ids <= {patch["id"] for patch in activated.json()["patches"] if patch["status"] == "proposed"}
    assert proposal_ids <= {patch["id"] for patch in state.json()["patches"] if patch["status"] == "proposed"}


async def test_course_scoped_edit_stream_loads_the_chapter_without_legacy_activation(monkeypatch):
    """A deep-linked chapter editor must not depend on the old singleton being primed."""
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    assert generated.status_code == 200, generated.text

    demo.STATE.package = None
    demo.STATE.store = None
    demo.STATE.active_course_id = None
    demo.STATE.active_chapter_id = None

    changed = await request(
        "POST", f"{path}/edit/stream",
        {"message": "Make slide 2 easier", "use_real_model": False},
    )

    assert changed.status_code == 200, changed.text
    assert "event: result" in changed.text
    assert '"read_slide"' in changed.text
    assert '"patch_slide"' in changed.text


async def test_course_scoped_edit_stream_accepts_a_multi_action_plan_prompt(monkeypatch):
    """Several approved plan actions are combined before the Agent executes them."""
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request(
        "POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False},
    )
    assert generated.status_code == 200, generated.text

    multi_action_prompt = "Teacher request: improve this lesson.\n\nRun only these approved actions:\n" + "\n\n".join(
        f"{index}. Inspect the selected material, add a concrete teaching cue, and keep the proposed patch reviewable."
        for index in range(1, 8)
    )
    assert len(multi_action_prompt) > 500

    changed = await request(
        "POST", f"{path}/edit/stream",
        {"message": multi_action_prompt, "use_real_model": False, "target": "slides", "images": []},
    )

    assert changed.status_code == 200, changed.text
    assert "event: result" in changed.text


async def test_course_scoped_questions_load_and_save_the_named_chapter(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    assert generated.status_code == 200, generated.text

    demo.STATE.package = None
    demo.STATE.store = None
    demo.STATE.active_course_id = None
    demo.STATE.active_chapter_id = None
    questions = await request("POST", f"{path}/questions", {"use_real_model": False})
    reloaded = await request("GET", path)

    assert questions.status_code == 200, questions.text
    assert questions.json()["package"]["questionSet"]["questions"]
    assert reloaded.json()["package"]["questionSet"]["questions"]


async def test_ai_revision_can_propose_question_and_paper_patches(monkeypatch):
    """Every teacher artifact can be revised without bypassing approval."""
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    assert generated.status_code == 200, generated.text
    questions = await request("POST", f"{path}/questions", {"use_real_model": False})
    assert questions.status_code == 200, questions.text
    paper = await request("POST", f"{path}/paper", {"total_points": 10, "duration_min": 15})
    assert paper.status_code == 200, paper.text

    question_before = questions.json()["package"]["questionSet"]["questions"][0]["stem"]
    question_edit = await request(
        "POST", f"{path}/edit",
        {"message": "Make the first question clearer", "target": "questions", "use_real_model": False},
    )
    assert question_edit.status_code == 200, question_edit.text
    assert question_edit.json()["call_names"][:2] == ["read_question", "patch_question"]
    assert question_edit.json()["package"]["questionSet"]["questions"][0]["stem"] == question_before

    question_patch = question_edit.json()["patches"][0]["id"]
    question_applied = await request("POST", f"{path}/apply", {"patch_id": question_patch})
    assert question_applied.status_code == 200, question_applied.text
    assert question_applied.json()["package"]["questionSet"]["questions"][0]["stem"] != question_before

    paper_before = paper.json()["package"]["examPaper"]["answerKey"]
    paper_edit = await request(
        "POST", f"{path}/edit",
        {"message": "Prepare a student copy", "target": "paper", "use_real_model": False},
    )
    assert paper_edit.status_code == 200, paper_edit.text
    assert paper_edit.json()["call_names"][:2] == ["read_paper", "patch_paper"]
    assert paper_edit.json()["package"]["examPaper"]["answerKey"] == paper_before

    paper_patch = paper_edit.json()["patches"][0]["id"]
    paper_applied = await request("POST", f"{path}/apply", {"patch_id": paper_patch})
    assert paper_applied.status_code == 200, paper_applied.text
    assert paper_applied.json()["package"]["examPaper"]["answerKey"] is False


async def test_generated_questions_are_saved_under_the_active_chapter(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course()
    path = f"/api/demo/courses/{course['id']}/chapters/{course['chapterIds'][0]}"
    generated = await request("POST", f"{path}/generate", {"topic": "Git branches", "use_real_model": False})
    await request("PATCH", path, {"package": generated.json()["package"], "status": "ready"})
    await request("POST", f"{path}/activate")

    questions = await request("POST", "/api/demo/questions", {"use_real_model": False})
    chapter = await request("GET", path)

    assert questions.status_code == 200, questions.text
    assert chapter.json()["package"]["questionSet"]["questions"]


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


async def test_chapter_generation_stream_uses_the_course_syllabus(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = await create_course("Software engineering foundations")
    chapter_id = course["chapterIds"][0]
    syllabus = "Course outcome: explain pull-request review before merging."

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        attached = await client.post(
            f"/api/demo/courses/{course['id']}/syllabus",
            content=syllabus.encode(),
            headers={"content-type": "application/octet-stream", "x-filename": "syllabus.md"},
        )
        streamed = await client.post(
            f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/generate/stream",
            json={"topic": "Git review", "audience": "Beginners", "duration_min": 30, "use_real_model": False},
        )

    assert attached.status_code == 200
    assert streamed.status_code == 200, streamed.text
    assert "event: result" in streamed.text
    assert syllabus in streamed.text
