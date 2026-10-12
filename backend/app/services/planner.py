"""ArtifactPlanner —— 设计规格 §6.1 阶段 2 的真实实现。

═══════════════════════════════════════════════════════════════════
以前是写死的
═══════════════════════════════════════════════════════════════════
阶段 2 原本把章节硬编码成 `["概念导入", "核心机制", "动手示例"]`。
现在改成让模型按「主题 + 受众 + 课时 + 学习目标」产出章节骨架。

═══════════════════════════════════════════════════════════════════
为什么必须有兜底
═══════════════════════════════════════════════════════════════════
模型可能:返回的不是 JSON / JSON 缺字段 / 时长加起来不对。
**大纲失败不能让整次生成失败** —— 否则教师改个字就白等一分钟。

所以 `plan_outline()` 的策略是:

    能解析 + 校验通过  → 用模型的
    任何一步失败        → 退回默认骨架,并在 rationale 里说明

这叫「优雅降级」,对应 §14 的失败隔离原则。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.llm.client import ChatClient

#: 兜底骨架。模型出不来东西时用这个,保证流程不中断。
DEFAULT_SECTIONS: tuple[str, ...] = ("概念导入", "核心机制", "动手示例")
DEFAULT_OBJECTIVES: tuple[str, ...] = ("理解核心概念", "能动手应用")

#: 单节的合理时长范围,用来挡掉模型给的离谱数值
MIN_SECTION_MINUTES = 3
MAX_SECTION_MINUTES = 60


class PlannedSection(BaseModel):
    """大纲里的一节。"""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="ignore"
    )

    title: str
    minutes: int = Field(gt=0)
    objective_ids: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    """阶段 2 的产出:章节骨架 + 学习目标。"""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="ignore"
    )

    objectives: list[str]
    sections: list[PlannedSection]
    #: 为什么这么安排 —— 展示给教师,也便于排查模型在想什么
    rationale: str = ""
    #: 是否退回了兜底骨架
    used_fallback: bool = False


@dataclass
class PlannerRequest:
    topic: str
    audience: str
    duration_min: int
    requested_objectives: list[str] = field(default_factory=list)
    language: str = "zh-HK"


PLANNER_PROMPT = """你是课程设计助手。为下面的迷你课程设计章节骨架。

只输出一个 JSON 对象,不要任何解释文字、不要 Markdown 围栏。格式:

{
  "objectives": ["学习目标1", "学习目标2"],
  "sections": [
    {"title": "章节标题", "minutes": 15, "objectiveIds": ["LO1"]},
    {"title": "章节标题", "minutes": 15, "objectiveIds": ["LO2"]}
  ],
  "rationale": "一句话说明为什么这样安排章节顺序"
}

硬性要求:
1. 学习目标用 id 表示时必须与 objectives 数组的顺序对应:第一个是 LO1,第二个是 LO2,以此类推。
2. 所有 sections 的 minutes 之和必须**恰好等于**给定课时。
3. 章节数量 2–6 节,每节 3–60 分钟。
4. 面向非专业学习者时,先讲「为什么」再讲「怎么做」。
5. 章节标题要具体,不要「第一章」这种。
"""


def extract_json(text: str) -> dict[str, Any] | None:
    """从模型回复里抠出 JSON 对象。

    模型很爱加 ```json 围栏,或者在前后写一句「好的,以下是…」。
    所以先剥围栏,再取第一个 `{` 到最后一个 `}`。
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")[1:]                       # 去掉首行围栏
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_minutes(sections: list[PlannedSection], duration: int) -> list[PlannedSection]:
    """把各节时长调整到总和等于课时。

    **为什么要归一化而不是直接丢弃:** 模型算错总时长是常态
    (比如给 45 分钟的课配了 100+100+100)。但它的**比例**往往是对的 ——
    三节一样长。直接丢掉等于白扔一份可用的大纲。
    按比例缩放后,大纲的价值(有哪些节、什么顺序)完全保留。

    **顺序很重要:先归一化,再校验。** 反过来会把这类大纲误杀。
    """
    n = len(sections)
    total = sum(s.minutes for s in sections)
    if n == 0 or total <= 0:
        return sections
    if total == duration:
        return sections

    minutes = [
        min(MAX_SECTION_MINUTES, max(MIN_SECTION_MINUTES, round(s.minutes * duration / total)))
        for s in sections
    ]

    # 取整 + 限幅会留下误差,一分钟一分钟地补到还有余量的节上。
    # 循环上限保证不会死循环。
    for _ in range(abs(duration - sum(minutes)) + n + 1):
        diff = duration - sum(minutes)
        if diff == 0:
            break
        moved = False
        for i in sorted(range(n), key=lambda k: -minutes[k]):   # 从最长的那节开始调
            if diff > 0 and minutes[i] < MAX_SECTION_MINUTES:
                minutes[i] += 1
                moved = True
                break
            if diff < 0 and minutes[i] > MIN_SECTION_MINUTES:
                minutes[i] -= 1
                moved = True
                break
        if not moved:
            break       # 怎么调都到不了目标,交给上层判定

    return [s.model_copy(update={"minutes": m}) for s, m in zip(sections, minutes)]


def _fallback(req: PlannerRequest, reason: str) -> Outline:
    """兜底骨架。**永远不抛异常** —— 这是它的全部意义。"""
    objectives = list(req.requested_objectives) or list(DEFAULT_OBJECTIVES)
    per = max(MIN_SECTION_MINUTES, req.duration_min // len(DEFAULT_SECTIONS))
    return Outline(
        objectives=objectives,
        sections=[
            PlannedSection(title=t, minutes=per, objective_ids=[])
            for t in DEFAULT_SECTIONS
        ],
        rationale=f"退回默认骨架:{reason}",
        used_fallback=True,
    )


async def plan_outline(
    req: PlannerRequest, *, client: ChatClient, model: str, temperature: float = 0.4
) -> Outline:
    """让模型产出章节骨架。**失败一律降级,不抛异常。**"""
    objectives_hint = (
        "教师指定的学习目标:" + "、".join(req.requested_objectives)
        if req.requested_objectives
        else "教师没指定学习目标,请你根据主题拟定 2–3 条。"
    )
    user = (
        f"课程主题:{req.topic}\n"
        f"学习者:{req.audience}\n"
        f"课时:{req.duration_min} 分钟\n"
        f"语言:{req.language}\n"
        f"{objectives_hint}"
    )

    try:
        reply = await client.complete(
            model=model,
            messages=[
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        return _fallback(req, f"模型调用失败({type(exc).__name__})")

    data = extract_json(reply.content)
    if data is None:
        return _fallback(req, "模型没有返回可解析的 JSON")

    try:
        outline = Outline.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return _fallback(req, f"大纲结构不合法({type(exc).__name__})")

    if not outline.sections:
        return _fallback(req, "模型给出的章节为空")

    # 先归一化,再校验 —— 顺序不能反。
    # 模型给的原始时长可能整体偏大(单位理解错了),但比例是对的;
    # 按比例缩放后再看是否落在合理区间,才不会误杀可用的大纲。
    outline.sections = _normalize_minutes(outline.sections, req.duration_min)

    total = sum(s.minutes for s in outline.sections)
    if total != req.duration_min:
        return _fallback(req, f"无法把章节时长调整到 {req.duration_min} 分钟(得到 {total})")
    for s in outline.sections:
        if not (MIN_SECTION_MINUTES <= s.minutes <= MAX_SECTION_MINUTES):
            return _fallback(req, f"章节时长不合理({s.title} {s.minutes} 分钟)")
    if not outline.objectives:
        outline.objectives = list(req.requested_objectives) or list(DEFAULT_OBJECTIVES)
    if req.requested_objectives:
        # 教师给的目标优先 —— 他们比模型更清楚要教什么
        outline.objectives = list(req.requested_objectives)
    return outline
