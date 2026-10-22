from __future__ import annotations

from app.services.patches import SQLitePatchStore


def test_sqlite_patch_store_reopens_proposed_patch_without_applying_it(tmp_path):
    """Restarting must preserve the review gate, not apply an AI patch early."""
    path = tmp_path / "teacher-workspace.db"
    proposed = SQLitePatchStore(path, scope_id="course-1:chapter-1").propose(
        artifact_id="a-slides",
        kind="slide",
        target_id="s1",
        payload={"title": "Reviewed title"},
        reason="Clearer wording",
        diff="- old\n+ new",
    )

    restored = SQLitePatchStore(path, scope_id="course-1:chapter-1").get(proposed.id)

    assert restored.status == "proposed"
    assert restored.payload == {"title": "Reviewed title"}


def test_sqlite_patch_store_keeps_chapter_review_histories_separate(tmp_path):
    """Equal IR artifact ids from two chapters must not show each other's patches."""
    path = tmp_path / "teacher-workspace.db"
    first = SQLitePatchStore(path, scope_id="course-1:chapter-1")
    second = SQLitePatchStore(path, scope_id="course-1:chapter-2")
    first.propose(
        artifact_id="a-slides", kind="slide", target_id="s1", payload={"title": "One"},
        reason="First chapter", diff="...",
    )
    second.propose(
        artifact_id="a-slides", kind="slide", target_id="s1", payload={"title": "Two"},
        reason="Second chapter", diff="...",
    )

    assert [patch.payload["title"] for patch in first.list("a-slides")] == ["One"]
    assert [patch.payload["title"] for patch in second.list("a-slides")] == ["Two"]
