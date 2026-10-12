"""可运行的流水线演示 —— **不需要 API key**。

    cd backend && ../.venv/bin/python -m app.demo_pipeline

它替换掉了两处「需要外部资源」的东西:
  · 模型     → FakeSectionModel(规则版假模型,看对话走到第几步决定下一步)
  · 检索/画图 → 内存里的假实现

真实实现只要替换这两处即可,agent 与 pipeline 的代码一行都不用改 ——
这就是依赖注入的意义。

关键观察点(跑的时候留意):
  1. 六段进度条按阶段推进
  2. 三节是**并发**跑的(进度会跳着报)
  3. 每节的 agent 自己决定调了哪几个工具、调了几次
  4. 最后跑 §6.4 的交叉引用校验
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from app.llm.client import ChatMessage, ToolCall
from app.services.ingest import IngestDeps
from app.services.pipeline import GenerationRequest, PipelineDeps, generate_course


class FakeSectionModel:
    """规则版假模型:看**自己这条对话线**走到第几步,决定下一步调什么工具。

    要点:它只看自己收到的 `messages`,不共享任何全局状态。
    所以即使三节并发跑,每一节的推进也是独立且确定的 ——
    这正是"可测试"的关键:行为可复现,才能断言。

    `delay` 是**只给演示用的**人为延迟,默认 0。测试里必须保持 0,
    否则整个测试套件会慢到没人愿意跑。演示时给一点延迟的原因:
    假模型是瞬间跑完的 —— 六段进度条和动作流会在一帧之内全部闪过去,
    那样「看得见过程」这件事就完全没法验收。
    """


    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        """假模型:决定下一步调什么。"""
        if self.delay:
            await asyncio.sleep(self.delay)
        return self._decide(messages, tools)

    def __init__(self, delay: float = 0.0) -> None:
        self.delay = delay

    def _decide(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None
    ) -> ChatMessage:
        """纯决策:看自己这条对话线走到第几步,决定下一步调什么。

        **不发网络请求,也不 await** —— 所以三节并发跑时行为完全确定。
        这正是「可以断言工具调用序列」的前提。
        """

        # 数一数这条对话线里已经有几个工具执行结果
        # 没有工具 = 这是阶段 2 的「出大纲」调用,不是分节生成。
        # 真实现见 services/planner.py;这里的假实现只是让离线 demo 能跑通。
        if not tools:
            return ChatMessage(
                content=json.dumps(_fake_outline(messages), ensure_ascii=False),
            )

        done = sum(1 for m in messages if m.get("role") == "tool")

        index, title = _parse_section(messages)

        # 第 1 步:先查讲义 —— 模型自己判断该检索
        if done == 0:
            return ChatMessage(
                tool_calls=[ToolCall(id="c1", name="search_materials", arguments={"query": title})]
            )

        # 第 2 步:要给这页配一张示意图 —— 走 Mermaid,不走生图
        if done == 1:
            return ChatMessage(
                tool_calls=[
                    ToolCall(
                        id="c2",
                        name="make_diagram",
                        arguments={"mermaid": f"graph LR; A[{title}]-->B[应用]"},
                    )
                ]
            )

        # 第 3 步:先写教案环节(它要引用即将创建的幻灯片 id)
        if done == 2:
            return ChatMessage(
                tool_calls=[
                    ToolCall(
                        id="c3",
                        name="write_plan_entry",
                        arguments={
                            "entry": {
                                "id": f"T{index}",
                                "phase": title,
                                "minutes": _parse_minutes(messages),
                                "teacherAction": f"讲解{title},并抛出一个常见误解",
                                "studentAction": "说出自己的理解",
                                "objectiveIds": ["LO1"] if index == 1 else ["LO2"],
                                "slideIds": [f"s{index}"],
                                "checkUnderstanding": f"能否用自己的话解释{title}",
                            }
                        },
                    )
                ]
            )

        # 第 4 步:写完提交。write_section 是终止工具,循环到此结束。
        # 注意:assetId 是从上一轮的工具结果里取的 —— 真实模型也是这么做的。
        # make_diagram 返回什么,它就写进幻灯片。这样引用不会对不上。
        if done == 3:
            asset_id = _last_asset_id(messages) or "as-unknown"
            return ChatMessage(
                tool_calls=[
                    ToolCall(
                        id="c4",
                        name="write_section",
                        arguments={"slides": [_fake_slide(index, title, asset_id)]},
                    )
                ]
            )

        return ChatMessage(content="(不应到达)")


def _fake_outline(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """假大纲:三节,时长恰好等于课时。真实现见 services/planner.py。"""
    duration = 45
    objectives: list[str] = []
    for m in messages:
        text = m.get("content") or ""
        if not isinstance(text, str):
            continue
        if hit := re.search(r"课时:(\d+) 分钟", text):
            duration = int(hit.group(1))
        if hit := re.search(r"教师指定的学习目标:([^\n]+)", text):
            objectives = [t.strip() for t in hit.group(1).split("、") if t.strip()]
    if not objectives:
        objectives = ["理解核心概念", "能动手应用"]

    titles = ["概念导入", "核心机制", "动手示例"]
    per = max(3, duration // len(titles))
    return {
        "objectives": objectives,
        "sections": [
            {
                "title": t,
                "minutes": per,
                "objectiveIds": [f"LO{min(i + 1, len(objectives))}"],
            }
            for i, t in enumerate(titles)
        ],
        "rationale": "先建立直觉,再看机制,最后动手 —— 对非专业初学者更友好。",
    }


def _parse_minutes(messages: list[dict[str, Any]], default: int = 15) -> int:
    """从用户消息里取「建议时长 N 分钟」—— 教案时长必须跟大纲一致。"""
    for m in messages:
        text = m.get("content") or ""
        if isinstance(text, str) and (hit := re.search(r"建议时长 (\d+) 分钟", text)):
            return int(hit.group(1))
    return default


def _parse_section(messages: list[dict[str, Any]]) -> tuple[int, str]:
    """从用户消息里取出「第 N 节:标题」。"""
    for m in messages:
        if m.get("role") == "user":
            hit = re.search(r"写第 (\d+) 节:([^。]+)", m.get("content", ""))
            if hit:
                return int(hit.group(1)), hit.group(2).strip()
    return 1, "本节"


def _last_asset_id(messages: list[dict[str, Any]]) -> str | None:
    """从工具执行结果里取出 assetId(倒着找最近一个)。"""
    for m in reversed(messages):
        if m.get("role") == "tool":
            try:
                payload = json.loads(m.get("content") or "{}")
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("asset_id"):
                return str(payload["asset_id"])
    return None


def _fake_slide(index: int, title: str, asset_id: str) -> dict[str, Any]:
    """一节一页幻灯片。字段名用 camelCase,与设计规格 §5.1 一致。"""
    return {
        "id": f"s{index}",
        "order": index,
        "layout": "diagram",
        "title": title,
        "bullets": [f"{title}:要点一", f"{title}:要点二"],
        "speakerNotes": f"先问学生:{title} 解决了什么问题?",
        "visuals": [
            {
                "id": f"v{index}",
                "kind": "diagram",
                "spec": {"engine": "mermaid", "code": f"graph LR; A[{title}]-->B[应用]"},
                "assetId": asset_id,
            }
        ],
        "objectiveIds": ["LO1"] if index == 1 else ["LO2"],
        "sourceRefs": [{"materialId": "m1", "page": 10 + index}],
        "origin": "sourced",
    }


# ── 假的检索与渲染:真实实现见 §6.1 / §8.2 ─────────────────


async def fake_search(query: str) -> list[dict[str, Any]]:
    """假检索:返回两条带页码的片段。真实现见 §6.1 MaterialIngestor。"""

    return [
        {"materialId": "m1", "page": 12, "text": f"关于「{query}」的讲义片段…"},
        {"materialId": "m1", "page": 14, "text": f"「{query}」的常见误解…"},
    ]


async def fake_make_diagram(mermaid: str) -> str:
    """假渲染:用内容哈希做 assetId,模拟 §8.6 的按 hash 去重。"""

    # 用内容哈希做 id:同一个 Mermaid 源码 → 同一个 assetId。
    # 这就是 §8.6「按 hash 去重」的最小形态。
    digest = hashlib.sha256(mermaid.encode()).hexdigest()[:8]
    return f"as-{digest}"


async def fake_illustration(prompt: str) -> str:
    """假生图:返回固定 id。真实现要接 ImageProvider。"""

    return "as-illus-1"


async def fake_ocr(image_bytes: bytes) -> str:
    """假 OCR:回显图片大小,证明真的走到了 OCR 这条路。"""

    return f"OCR 识别结果(输入图 {len(image_bytes) // 1024} KB):分支隔离改动,主干保持可用。"


async def main() -> None:
    """跑一遍完整流水线并打印结果。"""

    print("═" * 64)
    print("L1 生成流水线演示(假模型,无需 API key)")
    print("═" * 64)

    # 造一份讲义当材料 —— 阶段 1 会真的读它,并用它的 chunk 做检索。
    # 用 mkdtemp 而不是 with,免得把 main 的整个主体重新缩进一遍。
    material = Path(tempfile.mkdtemp()) / "Git讲义.md"
    material.write_text(
        "# Git 分支管理\n\n"
        "分支让不同人的改动互相隔离,主干始终保持可用。\n"
        "合并之前先确认改动可审查,并让至少一位同伴看过。\n"
        "冲突发生在两个人改了同一文件的同一行时,先拉取最新代码再手动决定保留哪一份。\n",
        encoding="utf-8",
    )

    req = GenerationRequest(
        topic="Git 分支管理",
        audience="非计算机专业初学者",
        duration_min=45,
        objectives=["解释分支与主干的关系", "完成一次安全的合并"],
        material_paths=[material],          # ← 给了材料,阶段 1 就真干活
    )
    deps = PipelineDeps(
        client=FakeSectionModel(),
        model="fake-model",
        search_materials=fake_search,
        make_diagram=fake_make_diagram,
        request_illustration=fake_illustration,
        section_concurrency=3,
        ingest_deps=IngestDeps(ocr_image=fake_ocr),
    )

    result = await generate_course(req, deps, on_event=lambda ev: print("  " + str(ev)))

    print()
    print("═" * 64)
    print("每个 SectionAgent 干了什么(这就是「工具调用序列」)")
    print("═" * 64)
    for i, agent in enumerate(result.agents, 1):
        print(f"  第 {i} 节: {agent.call_names}")
        print(f"          轮数 {agent.turns} · 结束原因 {agent.stopped_by}")

    pkg = result.package
    print()
    print("═" * 64)
    print("产出的 IR")
    print("═" * 64)
    print(f"  项目       : {pkg.project.meta.title}(受众 {pkg.project.meta.audience})")
    print(f"  学习目标   : {[o.id for o in pkg.project.learning_objectives]}")
    print(f"  幻灯片     : {len(pkg.slide_deck.slides)} 页")
    for s in pkg.slide_deck.slides:
        print(f"     · {s.id} [{s.layout}] {s.title}  来源={s.origin} {s.source_refs}")

    print()
    print("═" * 64)
    print("材料摄取报告(阶段 1)")
    print("═" * 64)
    for m in result.materials:
        print("  " + m.summary())
    if result.failed_materials:
        print(f"  ⚠️  {len(result.failed_materials)} 份材料没读到字 —— 但不影响产物生成")

    print()
    print("═" * 64)
    print("§6.4 交叉引用校验")
    print("═" * 64)
    issues = result.integrity_issues
    if issues:
        for i in issues:
            print(f"  ❌ {i}")
    else:
        print("  ✅ 通过")

    print()
    print("═" * 64)
    print("导出为 JSON 时是 camelCase(与 spec §5.1 一致)")
    print("═" * 64)
    one = pkg.slide_deck.slides[0].model_dump(by_alias=True)
    print("  " + str({k: one[k] for k in ("id", "layout", "speakerNotes", "objectiveIds", "sourceRefs")}))


if __name__ == "__main__":
    asyncio.run(main())
