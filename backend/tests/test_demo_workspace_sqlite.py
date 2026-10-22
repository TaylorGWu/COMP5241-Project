from __future__ import annotations

import httpx
import pytest

from app.api.routes import demo
from app.main import app
from app.services.patches import artifact_id_of


async def _request(method: str, path: str, body: dict | None = None) -> httpx.Response:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.request(method, path, json=body)


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
    assert demo.STATE.package is not None
    assert demo.STATE.store is not None
    proposed = demo.STATE.store.propose(
        artifact_id=artifact_id_of(demo.STATE.package),
        kind="slide",
        target_id=demo.STATE.package.slide_deck.slides[0].id,
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
