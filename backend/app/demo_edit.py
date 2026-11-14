"""L2 编辑演示 —— 先跑 L1 生成一份课件,再让 agent 改它。

    cd backend && ../.venv/bin/python -m app.demo_edit

全程不需要 API key(规则版假模型)。

═══════════════════════════════════════════════════════════════════
重点看这三行
═══════════════════════════════════════════════════════════════════
    agent 提议了改动 → patch 状态 = proposed
    产物是否已被改动? 否     ← ★ 这是整个设计的核心
    教师确认(apply)…
    产物是否已被改动? 是     ← 这时才真的变了

如果第一句就显示「是」,说明「AI 不能直接改内容」这条失效了。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.demo_pipeline import (
    FakeSectionModel,
    fake_illustration,
    fake_make_diagram,
    fake_search,
)
from app.llm.client import ChatMessage, ToolCall
from app.services.edit import edit_artifact
from app.services.patches import InMemoryPatchStore, apply_patch, reject_patch
from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course


class FakeEditModel:
    """规则版假编辑模型:看自己这条对话线走到第几步。

    真实模型的行为目标是:
        第 1 步  先读要改的那一页(read_slide)
        第 2 步  提出改动(patch_slide),并说明理由
        第 3 步  不再调工具,用一句话收尾

    `delay` 同 `FakeSectionModel`:只给演示用,默认 0,测试里必须保持 0。
    """


    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        """假编辑模型:决定下一步。"""
        if self.delay:
            await asyncio.sleep(self.delay)
        return self._decide(messages)

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    def _decide(self, messages: list[dict[str, Any]]) -> ChatMessage:
        """纯决策:先读、再改、然后收尾。不 await,行为确定。"""

        done = sum(1 for m in messages if m.get("role") == "tool")
        target = _parse_revision_target(messages)
        slide_id = _parse_slide_id(messages)

        if target == "slides" and _is_animation_request(messages):
            if done == 0:
                return ChatMessage(
                    tool_calls=[ToolCall(id="animation-read", name="read_slide", arguments={"slide_id": slide_id})],
                )
            if done == 1:
                return ChatMessage(
                    tool_calls=[ToolCall(
                        id="animation-patch",
                        name="patch_slide",
                        arguments={
                            "slide_id": slide_id,
                            "patch": {"animation": {"autoplay": True, "steps": _animation_steps(messages)}},
                            "reason": "依照教師要求，把既有內容排成短暫的逐步講解；沒有改動任何教學文字或視覺。",
                        },
                    )],
                )
            return ChatMessage(content="已準備這一頁的動畫建議，等待教師確認。")

        if target == "questions":
            question_id = _parse_question_id(messages)
            if done == 0:
                return ChatMessage(tool_calls=[ToolCall(id="q1", name="read_question", arguments={"question_id": question_id})])
            if done == 1:
                return ChatMessage(tool_calls=[ToolCall(id="q2", name="patch_question", arguments={
                    "question_id": question_id,
                    "patch": {
                        "stem": "用自己的话说明：为什么功能分支不会直接影响主干？",
                        "explanation": "题干先给出具体情境，帮助初学者把分支理解成安全的独立工作线。",
                    },
                    "reason": "教师希望题目更清晰，因此将抽象措辞改为具体的协作场景。",
                })])
            return ChatMessage(content="我已将这道题改成更具体的协作情境，改动待你确认。")

        if target == "paper":
            if done == 0:
                return ChatMessage(tool_calls=[ToolCall(id="p1", name="read_paper", arguments={})])
            if done == 1:
                return ChatMessage(tool_calls=[ToolCall(id="p2", name="patch_paper", arguments={
                    "patch": {"answerKey": False},
                    "reason": "教师要求准备学生版试卷，因此隐藏答案键。",
                })])
            return ChatMessage(content="我已准备学生版试卷，答案键的改动待你确认。")

        # 第 1 步:先读 —— 不许对没读过的页瞎改
        if done == 0:
            return ChatMessage(
                tool_calls=[ToolCall(id="e1", name="read_slide", arguments={"slide_id": slide_id})],
            )

        # 第 2 步:提出改动。只暂存,不落库。
        if done == 1:
            return ChatMessage(
                tool_calls=[
                    ToolCall(
                        id="e2",
                        name="patch_slide",
                        arguments={
                            "slide_id": slide_id,
                            "patch": {
                                "title": "分支是什么(入门版)",
                                "bullets": [
                                    "用自己的分支改代码,不会影响别人",
                                    "改完确认没问题,再合并回主干",
                                ],
                                "speakerNotes": "先问学生:如果两个人同时改同一行,会怎样?",
                            },
                            "reason": "教师反馈这一页太难。去掉 rebase / cherry-pick 等术语,改用日常说法,并补一个引导提问。",
                        },
                    )
                ]
            )

        # 第 3 步:不再调工具,收尾
        return ChatMessage(
            content="已把这一页降到入门水平:去掉了两个高级术语,改成日常说法,并补了一个引导提问。改动待你确认。",
        )


def _parse_slide_id(messages: list[dict[str, Any]]) -> str:
    """从教师的话里取页码，兼容中文与教师端默认的英文提示。"""
    for m in messages:
        if m.get("role") == "user":
            hit = re.search(
                r"(?:第\s*(\d+)\s*页|slide\s*#?\s*(\d+))",
                m.get("content", ""),
                flags=re.IGNORECASE,
            )
            if hit:
                return f"s{next(group for group in hit.groups() if group is not None)}"
    return "s1"


def _is_animation_request(messages: list[dict[str, Any]]) -> bool:
    return any(
        message.get("role") == "user" and "animation" in str(message.get("content", "")).lower()
        for message in messages
    )


def _animation_steps(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a valid deterministic sequence from the page returned by read_slide."""
    slide: dict[str, Any] = {}
    for message in reversed(messages):
        if message.get("role") != "tool":
            continue
        try:
            candidate = json.loads(str(message.get("content", "{}")))
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "title" in candidate:
            slide = candidate
            break

    steps: list[dict[str, Any]] = [{"kind": "reveal", "target": "title", "atMs": 0}]
    bullets = slide.get("bullets")
    if isinstance(bullets, list) and bullets:
        steps.append({"kind": "reveal", "target": "bullet:0", "atMs": 700})
    visuals = slide.get("visuals")
    if isinstance(visuals, list) and visuals and isinstance(visuals[0], dict) and isinstance(visuals[0].get("id"), str):
        steps.append({"kind": "sequence", "target": f"visual:{visuals[0]['id']}", "atMs": 1_400})
    return steps


def _parse_question_id(messages: list[dict[str, Any]]) -> str:
    for m in messages:
        if m.get("role") == "tool" and m.get("name") == "read_question":
            # The fake model only needs a stable, valid demo target.
            break
    return "q1"


def _parse_revision_target(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "user":
            content = str(message.get("content", ""))
            hit = re.search(r"revision target:\s*(slides|questions|paper)", content, flags=re.I)
            if hit:
                return hit.group(1).lower()
    return "slides"


async def main() -> None:
    """L1 生成 → L2 编辑 → 确认。全程不需要 key。"""

    # ── 第一步:用 L1 生成一份课件 + 教案 ────────────────────────
    print("═" * 66)
    print("第 1 步:L1 生成")
    print("═" * 66)

    l1 = await generate_course(
        GenerationRequest(
            topic="Git 分支管理",
            audience="非计算机专业初学者",
            duration_min=45,
            objectives=["解释分支与主干的关系", "完成一次安全的合并"],
        ),
        PipelineDeps(
            client=FakeSectionModel(),
            model="fake-l1",
            search_materials=fake_search,
            make_diagram=fake_make_diagram,
            request_illustration=fake_illustration,
        ),
    )
    package = l1.package
    deck = package.slide_deck
    assert deck is not None
    print(f"  产出:课件 {len(deck.slides)} 页 + 教案 {len(package.lesson_plan.timeline)} 环节")
    for s in deck.slides:
        print(f"    · {s.id} {s.title}")

    # ── 第二步:L2 编辑 ─────────────────────────────────────────
    print()
    print("═" * 66)
    print("第 2 步:L2 编辑")
    print("═" * 66)

    instruction = "第 3 页太难了,给非 CS 背景的学生降一档。"
    print(f"  教师:{instruction}")

    store = InMemoryPatchStore()
    snapshot_before = package.model_dump_json()      # 留个快照用来比对

    result = await edit_artifact(
        client=FakeEditModel(),
        model="fake-l2",
        package=package,
        message=instruction,
        store=store,
    )

    print()
    print("  Agent 的工具调用序列:")
    for call in result.agent.calls if result.agent else []:
        print(f"    {call.turn}. {call.name}")

    print()
    print("  产生的待确认改动:")
    for p in result.proposed:
        print(f"    [{p.id}] {p.kind} → {p.target_id}  状态={p.status}")
        print(f"      理由:{p.reason}")
        print("      差异:")
        print(p.diff)

    # ★ 核心断言:提议了改动,但产物一字未变
    unchanged = package.model_dump_json() == snapshot_before
    print()
    print(f"  ★ 产物是否已被改动? {'否 ✅(改动只在暂存区)' if unchanged else '是 ❌ 设计被破坏了!'}")

    # ── 第三步:教师确认 ────────────────────────────────────────
    print()
    print("═" * 66)
    print("第 3 步:教师确认(apply)")
    print("═" * 66)

    patch_id = result.proposed[0].id
    apply_patch(package, store, patch_id)
    changed = package.model_dump_json() != snapshot_before
    print(f"  已 apply {patch_id}")
    print(f"  ★ 产物是否已被改动? {'是 ✅' if changed else '否 ❌'}")

    edited = next(s for s in package.slide_deck.slides if s.id == "s3")
    print()
    print("  改动后第 3 页:")
    print(f"    标题:{edited.title}")
    for b in edited.bullets:
        print(f"    · {b}")
    print(f"    讲稿:{edited.speaker_notes}")

    print()
    print("  最终状态:")
    for p in store.list(deck.artifact_id):
        print(f"    [{p.id}] {p.status}")

    print()
    print("═" * 66)
    print("对照:reject 的路径")
    print("═" * 66)
    store2 = InMemoryPatchStore()
    snap2 = package.model_dump_json()
    r2 = await edit_artifact(
        client=FakeEditModel(), model="fake-l2", package=package,
        message="第 3 页太难了,降一档。", store=store2,
    )
    if r2.proposed:
        reject_patch(store2, r2.proposed[0].id)
        print(f"  已驳回 {r2.proposed[0].id}")
        print(f"  产物是否被改动? {'否 ✅(驳回不改内容)' if package.model_dump_json() == snap2 else '是 ❌'}")


if __name__ == "__main__":
    asyncio.run(main())
