"""L2 编辑测试 —— 对应设计规格 §7.2 与 §7.3。

**这里最重要的一条是「未确认的 patch 不得落库」。**
它是 NFR-04 在编辑路径上的落点:AI 可以提议,但不能自己生效。
这条不变式一旦被破坏,「教师审核」就退化成事后补救了。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.llm.client import ChatMessage, ScriptedChatClient, ToolCall
from app.services.edit import EditDeps, edit_artifact
from app.services.patches import (
    InMemoryPatchStore,
    PatchAlreadyDecided,
    apply_patch,
    make_diff,
    reject_patch,
)
from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course


async def _package():
    """跑一遍 L1 拿一份真实的课件 + 教案。"""
    result = await generate_course(
        GenerationRequest(
            topic="Git 分支管理",
            audience="初学者",
            duration_min=45,
            objectives=["解释分支", "完成合并"],
        ),
        PipelineDeps(
            client=FakeSectionModel(),
            model="fake",
            search_materials=fake_search,
            make_diagram=fake_make_diagram,
            request_illustration=fake_illustration,
        ),
    )
    assert result.integrity_issues == []
    return result.package


def _edit_script(slide_id: str = "s3") -> list[ChatMessage]:
    """造一段「先读、再改」的假模型脚本。"""

    return [
        ChatMessage(tool_calls=[ToolCall(id="e1", name="read_slide", arguments={"slide_id": slide_id})]),
        ChatMessage(
            tool_calls=[
                ToolCall(
                    id="e2",
                    name="patch_slide",
                    arguments={
                        "slide_id": slide_id,
                        "patch": {"title": "入门版标题"},
                        "reason": "教师说太难",
                    },
                )
            ]
        ),
        ChatMessage(content="改好了,待确认。"),
    ]


# ═══════════════════════════════════════════════════════════
# ★ 核心不变式:未确认的 patch 不得改变产物
# ═══════════════════════════════════════════════════════════


async def test_proposed_patch_does_not_change_the_package():
    """agent 提议了改动,产物必须**一字未变**。"""
    package = await _package()
    before = package.model_dump_json()

    store = InMemoryPatchStore()
    result = await edit_artifact(
        client=ScriptedChatClient(_edit_script()),
        model="fake", package=package, message="第 3 页太难了", store=store,
    )

    assert result.proposed, "应该产生了一个待确认的 patch"
    assert result.proposed[0].status == "proposed"
    assert package.model_dump_json() == before, "提议阶段产物就被改了 —— 设计被破坏"


async def test_apply_is_the_only_way_to_change_the_package():
    """只有 apply 之后产物才变 —— 证明上一条不是「什么都没做」。"""
    package = await _package()
    before = package.model_dump_json()

    store = InMemoryPatchStore()
    result = await edit_artifact(
        client=ScriptedChatClient(_edit_script()),
        model="fake", package=package, message="第 3 页太难了", store=store,
    )
    assert package.model_dump_json() == before

    apply_patch(package, store, result.proposed[0].id)

    assert package.model_dump_json() != before, "apply 之后必须真的变了"
    edited = next(s for s in package.slide_deck.slides if s.id == "s3")
    assert edited.title == "入门版标题"
    assert store.get(result.proposed[0].id).status == "applied"


async def test_reject_leaves_the_package_untouched():
    """驳回只改 patch 状态,一个字都不该动产物。"""

    package = await _package()
    before = package.model_dump_json()

    store = InMemoryPatchStore()
    result = await edit_artifact(
        client=ScriptedChatClient(_edit_script()),
        model="fake", package=package, message="第 3 页太难了", store=store,
    )
    reject_patch(store, result.proposed[0].id)

    assert package.model_dump_json() == before
    assert store.get(result.proposed[0].id).status == "rejected"


async def test_patch_cannot_be_decided_twice():
    """已确认或已驳回的 patch 不能再操作一次。"""

    package = await _package()
    store = InMemoryPatchStore()
    result = await edit_artifact(
        client=ScriptedChatClient(_edit_script()),
        model="fake", package=package, message="改一下", store=store,
    )
    pid = result.proposed[0].id
    apply_patch(package, store, pid)

    with pytest.raises(PatchAlreadyDecided):
        apply_patch(package, store, pid)
    with pytest.raises(PatchAlreadyDecided):
        reject_patch(store, pid)


# ═══════════════════════════════════════════════════════════
# 行为约束
# ═══════════════════════════════════════════════════════════


async def test_agent_reads_before_patching():
    """先读再改 —— 不许对没看过的页动手。"""
    package = await _package()
    result = await edit_artifact(
        client=ScriptedChatClient(_edit_script()),
        model="fake", package=package, message="改第 3 页", store=InMemoryPatchStore(),
    )
    assert result.agent is not None
    assert result.agent.index_of("read_slide") < result.agent.index_of("patch_slide")


async def test_diff_uses_the_real_previous_value_for_camel_case_fields():
    """回归测试:曾经 before 用 snake_case 取值、payload 用 camelCase,
    导致 `speakerNotes` 这种字段的「改动前」被显示成 None ——
    教师会以为原来没有讲稿,其实有。

    这类 bug 不会让测试挂,只会让 diff 骗人。
    """
    package = await _package()
    before_slide = package.slide_deck.slides[2]
    assert before_slide.speaker_notes, "前提:这一页原本有讲稿"

    store = InMemoryPatchStore()
    script = [
        ChatMessage(tool_calls=[ToolCall(id="d1", name="patch_slide", arguments={
            "slide_id": "s3",
            "patch": {"speakerNotes": "新的讲稿"},
            "reason": "换个问法",
        })]),
        ChatMessage(content="提好了"),
    ]
    result = await edit_artifact(
        client=ScriptedChatClient(script), model="fake",
        package=package, message="换讲稿", store=store,
    )
    diff = result.proposed[0].diff

    assert "None" not in diff, f"diff 里出现了 None,说明改前值没取到:\n{diff}"
    assert before_slide.speaker_notes in diff, "diff 必须显示真实的改前讲稿"


async def test_patch_carries_reason_and_diff():
    """每个改动都要留下「为什么」和「改了什么」。"""
    package = await _package()
    result = await edit_artifact(
        client=ScriptedChatClient(_edit_script()),
        model="fake", package=package, message="改第 3 页", store=InMemoryPatchStore(),
    )
    patch = result.proposed[0]
    assert patch.reason == "教师说太难"
    assert "入门版标题" in patch.diff
    assert patch.target_id == "s3"


async def test_apply_revalidates_the_payload():
    """一个会让产物非法的 patch,必须在 apply 时被挡住。

    这条守的是:「AI 输出必须过 schema」在编辑路径上同样成立 ——
    不能因为「是教师确认的」就跳过校验。
    """
    package = await _package()
    store = InMemoryPatchStore()
    script = [
        ChatMessage(tool_calls=[ToolCall(id="x1", name="patch_slide", arguments={
            "slide_id": "s3",
            "patch": {"layout": "carousel"},        # 不在允许的枚举里
            "reason": "随便试试",
        })]),
        ChatMessage(content="提好了"),
    ]
    result = await edit_artifact(
        client=ScriptedChatClient(script), model="fake",
        package=package, message="换个版式", store=store,
    )
    # 提议阶段允许(它只是个 dict),apply 时才校验
    with pytest.raises(ValidationError):
        apply_patch(package, store, result.proposed[0].id)


async def test_patch_plan_updates_the_lesson_plan():
    """教案也能改,而且同样先暂存后生效。"""
    package = await _package()
    before = package.model_dump_json()
    store = InMemoryPatchStore()
    script = [
        ChatMessage(tool_calls=[ToolCall(id="p1", name="patch_plan", arguments={
            "patch": {"overview": "改过的教案概述"},
            "reason": "原来的概述太笼统",
        })]),
        ChatMessage(content="提好了"),
    ]
    result = await edit_artifact(
        client=ScriptedChatClient(script), model="fake",
        package=package, message="改教案概述", store=store,
    )
    assert package.model_dump_json() == before          # 暂存阶段不变
    apply_patch(package, store, result.proposed[0].id)
    assert package.lesson_plan.overview == "改过的教案概述"


async def test_read_only_tools_work():
    """三个只读工具(读页 / 查时长 / 查覆盖)能正常返回。"""

    package = await _package()
    deps = EditDeps(package=package, store=InMemoryPatchStore())

    timing = await deps.estimate_timing()
    assert timing["limit_min"] == 45 and timing["total_min"] == 45

    coverage = await deps.check_coverage()
    assert coverage["gaps"] == []

    slide = await deps.read_slide("s1")
    assert slide["id"] == "s1"
    assert "speakerNotes" in slide          # 对模型输出 camelCase


# ═══════════════════════════════════════════════════════════
# diff 工具本身
# ═══════════════════════════════════════════════════════════


def test_make_diff_shows_changed_fields():
    """普通字段用 -/+ 展示。"""

    diff = make_diff({"title": "旧"}, {"title": "新"})
    assert "- title: '旧'" in diff and "+ title: '新'" in diff


def test_make_diff_handles_lists_line_by_line():
    """列表字段(如 bullets)逐行对比,而不是整块替换。"""

    diff = make_diff({"bullets": ["a", "b"]}, {"bullets": ["a", "c"]})
    assert "-b" in diff.replace(" ", "") and "+c" in diff.replace(" ", "")


def test_make_diff_reports_no_change():
    """没变化时要说「无实际变化」,而不是空白。"""

    assert "无实际变化" in make_diff({"title": "同"}, {"title": "同"})
