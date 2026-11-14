from __future__ import annotations

import httpx
import pytest

from app.api.routes import demo
from app.main import app
from app.services.patches import artifact_id_of, SQLitePatchStore
from app.schemas.ir import CoursePackage


async def _request(method: str, path: str, body: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, json=body)


async def test_inserted_slide_scope_survives_plan_and_edit_routes(pipeline_result, monkeypatch):
    from app.llm.client import ChatMessage, ScriptedChatClient, ToolCall
    created = (await _request("POST", "/api/demo/courses", {"title": "Scope regression"})).json()
    root = f"/api/demo/courses/{created['id']}/chapters/{created['chapterIds'][0]}"
    package = pipeline_result.package
    package.slide_deck.slides[2].id = "s-inserted-uuid"
    await _request("PATCH", root, {"package": package.model_dump(by_alias=True)})
    body = {"message": "Improve this page", "slide_id": "s-inserted-uuid"}
    plan = await _request("POST", root + "/edit/plan", body)
    assert plan.status_code == 200
    assert {a["target_id"] for a in plan.json()["actions"]} == {"s-inserted-uuid"}
    assert plan.json()["slide_id"] == "s-inserted-uuid"
    for path in ["/edit/plan", "/edit", "/edit/stream"]:
        missing = await _request("POST", root + path, {**body, "slide_id": "deleted"})
        assert missing.status_code == 404
    script = [ChatMessage(tool_calls=[ToolCall(id="read", name="read_slide", arguments={"slide_id": "s-inserted-uuid"})]),
              ChatMessage(tool_calls=[ToolCall(id="write", name="patch_slide", arguments={"slide_id": "s-inserted-uuid", "patch": {"title": "Selected page only"}, "reason": "Teacher request"})]),
              ChatMessage(content="Proposed")]
    monkeypatch.setattr(demo, "_build_model", lambda *a: (ScriptedChatClient(script), "fake", None, "fake"))
    response = await _request("POST", root + "/edit", body)
    assert response.status_code == 200, response.text
    assert response.json()["call_names"] == ["read_slide", "patch_slide"]
    assert {p["target_id"] for p in response.json()["patches"]} == {"s-inserted-uuid"}
    assert (await _request("GET", root)).json()["package"] == package.model_dump(by_alias=True)


@pytest.mark.parametrize("slide_count, expected", [(0, "failed"), (4, "draft"), (12, "ready")])
async def test_generation_does_not_mark_missing_slides_ready(pipeline_result, monkeypatch, slide_count, expected):
    result = pipeline_result
    result.package.slide_deck.slides = result.package.slide_deck.slides[:slide_count]
    if slide_count == 4:
        result.agents[1].stopped_by = "max_turns"

    async def generate(*args, **kwargs):
        return result, "fake"

    monkeypatch.setattr(demo, "_run_generation", generate)
    course = (await _request("POST", "/api/demo/courses", {
        "title": "Regression", "audience": "Beginners", "durationMin": 45,
    })).json()
    chapter_id = course["chapterIds"][0]
    response = await _request("POST", f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/generate", {
        "topic": "Regression", "audience": "Beginners",
    })
    assert response.status_code == 200, response.text
    assert response.json()["chapter"]["status"] == expected
    # A recoverable draft is retained, never automatically published.
    assert response.json()["package"]["slideDeck"] is not None
    assert (await _request("GET", f"/api/demo/courses/{course['id']}")).json()["status"] == "draft"


async def test_course_and_chapter_ir_survive_workspace_reopen(tmp_path, monkeypatch):
    """The running teacher routes must reopen the local SQLite workspace."""
    monkeypatch.setattr(demo, "TEACHER_WORKSPACE_DB", tmp_path / "workspace.db")
    demo.reset_course_workspace()
    created = await _request(
        "POST",
        "/api/demo/courses",
        {"title": "Git collaboration", "description": "Short", "audience": "Beginners", "durationMin": 45},
    )
    assert created.status_code == 201, created.text
    course = created.json()
    chapter_id = course["chapterIds"][0]
    changed = await _request(
        "PATCH",
        f"/api/demo/courses/{course['id']}/chapters/{chapter_id}",
        {"status": "ready", "package": {"slideDeck": {"slides": [{"id": "s1"}]}}},
    )
    assert changed.status_code == 200, changed.text

    demo.reload_course_workspace()
    reloaded = await _request("GET", f"/api/demo/courses/{course['id']}/chapters/{chapter_id}")

    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["package"] == {"slideDeck": {"slides": [{"id": "s1"}]}}


def test_default_workspace_path_is_local_and_credential_free(monkeypatch):
    monkeypatch.delenv("TEACHER_WORKSPACE_DB", raising=False)

    path = demo.resolve_teacher_workspace_path()

    assert path.as_posix().endswith("backend/.local/teacher-workspace.db")


async def test_pending_chapter_patch_is_visible_after_workspace_reopen(tmp_path, monkeypatch):
    """A restart keeps reviewable AI work separate from the chapter IR."""
    monkeypatch.setattr(demo, "TEACHER_WORKSPACE_DB", tmp_path / "workspace.db")
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    demo.reset_course_workspace()
    created = await _request(
        "POST",
        "/api/demo/courses",
        {"title": "Git collaboration", "description": "Short", "audience": "Beginners", "durationMin": 45},
    )
    course = created.json()
    chapter_id = course["chapterIds"][0]
    generated = await _request(
        "POST",
        f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/generate",
        {"topic": "Git branching", "audience": "Beginners", "duration_min": 30},
    )
    assert generated.status_code == 200, generated.text
    package = CoursePackage.model_validate(generated.json()["package"])
    store = SQLitePatchStore(demo.TEACHER_WORKSPACE_DB, scope_id=f"{course['id']}:{chapter_id}")
    proposed = store.propose(
        artifact_id=artifact_id_of(package),
        kind="slide",
        target_id=package.slide_deck.slides[0].id,
        payload={"title": "Review this wording"},
        reason="More direct for beginners",
        diff="- old\n+ new",
    )

    demo.reload_course_workspace()
    activated = await _request(
        "POST", f"/api/demo/courses/{course['id']}/chapters/{chapter_id}/activate"
    )

    assert activated.status_code == 200, activated.text
    assert [(patch["id"], patch["status"]) for patch in activated.json()["patches"]] == [
        (proposed.id, "proposed")
    ]


async def test_slide_insertion_deletion_preserves_ids_references_and_history(monkeypatch):
    monkeypatch.setattr(demo, "FAKE_MODEL_DELAY", 0.0)
    course = (await _request("POST", "/api/demo/courses", {"title": "Slides", "audience": "Beginners"})).json()
    cid, chapter = course["id"], course["chapterIds"][0]
    root = f"/api/demo/courses/{cid}/chapters/{chapter}"
    original = (await _request("POST", root + "/generate", {"topic": "Git", "audience": "Beginners"})).json()["package"]
    ids = [s["id"] for s in original["slideDeck"]["slides"]]
    for action, anchor, expected_index in [("before", ids[0], 0), ("after", ids[-1], len(ids) + 1)]:
        response = await _request("POST", root + "/slides", {"action": action, "anchor_id": anchor, "title": "New slide"})
        assert response.status_code == 200, response.text
        result = response.json()
        slides = result["package"]["slideDeck"]["slides"]
        assert slides[expected_index]["id"] == result["selected_slide_id"]
        assert slides[expected_index]["origin"] == "teacher"
        assert [s["id"] for s in slides if s["id"] in ids] == ids
        assert [s["order"] for s in slides] == list(range(1, len(slides) + 1))
        assert result["patch"]["author"] == "teacher" and result["patch"]["status"] == "applied"
    deleted = await _request("POST", root + "/slides", {"action": "delete", "anchor_id": ids[0]})
    assert deleted.status_code == 200, deleted.text
    package = deleted.json()["package"]
    assert ids[0] not in [s["id"] for s in package["slideDeck"]["slides"]]
    assert all(ids[0] not in entry["slideIds"] for entry in package["lessonPlan"]["timeline"])
    demo.reload_course_workspace()
    assert (await _request("GET", root)).json()["package"] == package
    invalid = await _request("POST", root + "/slides", {"action": "after", "anchor_id": "foreign-slide"})
    assert invalid.status_code == 404
    assert (await _request("GET", root)).json()["package"] == package
    for slide in package["slideDeck"]["slides"]:
        response = await _request("POST", root + "/slides", {"action": "delete", "anchor_id": slide["id"]})
        assert response.status_code == 200, response.text
    assert response.json()["selected_slide_id"] is None
    assert response.json()["package"]["slideDeck"]["slides"] == []
    restored = await _request("POST", root + "/slides", {"action": "after", "title": "Start again"})
    assert restored.status_code == 200, restored.text
    assert restored.json()["package"]["slideDeck"]["slides"][0]["order"] == 1
