"""教师手动编辑 —— 不走 AI,但**仍然走 patch 机制**。

═══════════════════════════════════════════════════════════════════
这组测试在守什么
═══════════════════════════════════════════════════════════════════
「教师自己改」听起来该是最直接的路径。但如果它直接写产物,
`apply_patch()` 就不再是唯一能改编产物的函数 —— 那条核心不变式
(未确认的改动不得改变产物)当场失效,所有断言它的测试和文档
都变成假话。

所以手动编辑也生成 patch,只是 `author="teacher"`,并立刻 apply。
下面这几条测试就是钉死这件事的。
"""

from __future__ import annotations

import pytest

from app.services.patches import (
    InMemoryPatchStore,
    apply_patch,
    current_values,
    manual_edit,
    reject_patch,
)


@pytest.fixture
def package(pipeline_result):
    """跑一遍流水线,拿一个真实产物。"""
    return pipeline_result.package


@pytest.fixture
def store(package):
    return InMemoryPatchStore()


# ═══════════════════════════════════════════════════════════
# ★ 教师改动同样是 patch
# ═══════════════════════════════════════════════════════════


def test_manual_edit_leaves_a_patch_record(package, store):
    """手动改也留下 patch —— 这是可审计、可回退的前提。"""
    patch, _ = manual_edit(
        package, store,
        kind="slide", target_id="s1",
        payload={"title": "教师自己写的标题"},
        note="标题太学术了,改口语一点",
    )

    assert patch.author == "teacher"
    assert patch.status == "applied"
    assert patch.reason == "标题太学术了,改口语一点"
    assert patch.payload == {"title": "教师自己写的标题"}
    # 记录留在历史里
    assert [p.id for p in store.list(patch.artifact_id)] == [patch.id]


def test_manual_edit_actually_changes_the_package(package, store):
    """当然要真的改到 —— 走了 patch 不等于没生效。"""
    manual_edit(package, store, kind="slide", target_id="s1",
                payload={"title": "新标题"})
    assert package.slide_deck.slides[0].title == "新标题"


def test_manual_edit_is_immediate_not_pending(package, store):
    """教师点保存就是确认 —— 不该再留一条 pending 让教师点第二次。"""
    manual_edit(package, store, kind="slide", target_id="s1", payload={"title": "X"})
    assert store.list(package.slide_deck.artifact_id, status="proposed") == []


def test_manual_edit_diff_shows_only_what_changed(package, store):
    """diff 只列真正改的字段,而且要显示改前改后。"""
    patch, _ = manual_edit(package, store, kind="slide", target_id="s1",
                           payload={"title": "改过的标题"})
    assert "title" in patch.diff
    assert "改过的标题" in patch.diff


def test_manual_edit_records_only_changed_fields(package, store):
    """传了一堆没变的字段,不该全记进去 —— diff 会变成噪音。"""
    before = current_values(package, "slide", "s1")
    patch, _ = manual_edit(
        package, store, kind="slide", target_id="s1",
        payload={"title": "变了", "layout": before["layout"]},   # layout 没变
    )
    assert set(patch.payload) == {"title"}


def test_no_change_is_rejected(package, store):
    """什么都没改就别生成 patch。"""
    before = current_values(package, "slide", "s1")
    with pytest.raises(ValueError, match="没有任何字段发生变化"):
        manual_edit(package, store, kind="slide", target_id="s1",
                    payload={"title": before["title"]})
    assert store.list(package.slide_deck.artifact_id) == []


# ═══════════════════════════════════════════════════════════
# ★ 手动改也不能绕过校验
# ═══════════════════════════════════════════════════════════


def test_manual_edit_still_runs_schema_validation(package, store):
    """教师手滑填了非法值,一样要被挡住。

    「是人改的」不能成为绕过 schema 的理由 —— 否则产物会出现
    连导出器都处理不了的数据。
    """
    with pytest.raises(Exception):
        manual_edit(package, store, kind="slide", target_id="s1",
                    payload={"order": "不是数字"})
    # 产物没变
    assert package.slide_deck.slides[0].order == 1


def test_failed_manual_edit_does_not_leave_a_pending_patch(package, store):
    """校验没过就别在「待确认」里留一条 —— 教师已经看到报错了。"""
    with pytest.raises(Exception):
        manual_edit(package, store, kind="slide", target_id="s1",
                    payload={"order": "不是数字"})

    pending = store.list(package.slide_deck.artifact_id, status="proposed")
    assert pending == []


def test_unknown_target_raises(package, store):
    with pytest.raises(KeyError):
        manual_edit(package, store, kind="slide", target_id="s999",
                    payload={"title": "X"})


# ═══════════════════════════════════════════════════════════
# 教案环节也能手动改
# ═══════════════════════════════════════════════════════════


def test_manual_edit_of_a_timeline_entry(package, store):
    """改教案的某一环节,只动那一条,别的环节不受影响。"""
    entry_id = package.lesson_plan.timeline[0].id
    others = [
        (t.id, t.teacher_action) for t in package.lesson_plan.timeline[1:]
    ]

    manual_edit(package, store, kind="timeline", target_id=entry_id,
                payload={"teacherAction": "教师自己写的讲法"})

    assert package.lesson_plan.timeline[0].teacher_action == "教师自己写的讲法"
    assert [(t.id, t.teacher_action) for t in package.lesson_plan.timeline[1:]] == others


def test_timeline_edit_is_precise(package, store):
    """diff 里不该出现别人的字段 —— 说明是精确定位,不是整份替换。"""
    entry_id = package.lesson_plan.timeline[0].id
    patch, _ = manual_edit(package, store, kind="timeline", target_id=entry_id,
                           payload={"minutes": 99})
    assert set(patch.payload) == {"minutes"}


# ═══════════════════════════════════════════════════════════
# 和 AI 提议的 patch 并存时互不干扰
# ═══════════════════════════════════════════════════════════


def test_teacher_and_ai_patches_are_distinguishable(package, store):
    """审计要能分清「这页是 AI 改的还是教师改的」。"""
    # AI 提议(不 apply)
    ai = store.propose(
        artifact_id=package.slide_deck.artifact_id,
        kind="slide", target_id="s2", payload={"title": "AI 想改成这个"},
        reason="教师说太难了", diff="", author="ai",
    )
    assert ai.is_pending

    # 教师手动改(立刻 apply)
    teacher, _ = manual_edit(package, store, kind="slide", target_id="s1",
                             payload={"title": "教师改的"})

    assert ai.author == "ai" and ai.is_pending
    assert teacher.author == "teacher" and teacher.status == "applied"
    # AI 的提议还挂着,没被手动编辑影响
    assert store.get(ai.id).is_pending
