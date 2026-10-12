"""大纲规划测试 —— 对应设计规格 §6.1 阶段 2。

**重点不是「模型给对了怎么办」,而是「模型给错了怎么办」。**
大纲失败不能让整次生成失败 —— 所以这里大部分测试都在验证降级。
"""

from __future__ import annotations

import json

import pytest

from app.llm.client import ChatMessage, ScriptedChatClient
from app.services.planner import (
    DEFAULT_SECTIONS,
    PlannerRequest,
    extract_json,
    plan_outline,
)


def _req(**overrides) -> PlannerRequest:
    base = dict(topic="Git 分支", audience="初学者", duration_min=45)
    base.update(overrides)
    return PlannerRequest(**base)


def _valid_outline_json(minutes=(20, 15, 10)) -> str:
    return json.dumps(
        {
            "objectives": ["解释分支", "完成合并"],
            "sections": [
                {"title": f"第 {i} 节", "minutes": m, "objectiveIds": []}
                for i, m in enumerate(minutes, start=1)
            ],
            "rationale": "先直觉后机制",
        },
        ensure_ascii=False,
    )


# ═══════════════════════════════════════════════════════════
# extract_json:模型爱加围栏
# ═══════════════════════════════════════════════════════════


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_ignores_leading_prose():
    assert extract_json('好的,以下是结果:\n{"a": 1}\n希望有帮助') == {"a": 1}


@pytest.mark.parametrize("bad", ["", "没有 JSON", "{不是合法 JSON}", "[1,2,3]"])
def test_extract_json_returns_none_for_junk(bad):
    assert extract_json(bad) is None


# ═══════════════════════════════════════════════════════════
# 正常路径
# ═══════════════════════════════════════════════════════════


async def test_valid_outline_is_used():
    client = ScriptedChatClient([ChatMessage(content=_valid_outline_json())])
    outline = await plan_outline(_req(), client=client, model="m")

    assert outline.used_fallback is False
    assert len(outline.sections) == 3
    assert sum(s.minutes for s in outline.sections) == 45
    assert outline.rationale == "先直觉后机制"


async def test_teacher_objectives_win_over_model():
    """教师给的学习目标优先 —— 他们比模型更清楚要教什么。"""
    client = ScriptedChatClient([ChatMessage(content=_valid_outline_json())])
    outline = await plan_outline(
        _req(requested_objectives=["教师定的目标"]), client=client, model="m"
    )
    assert outline.objectives == ["教师定的目标"]


# ═══════════════════════════════════════════════════════════
# ★ 降级:模型出问题不能让流程挂
# ═══════════════════════════════════════════════════════════


async def test_non_json_reply_falls_back():
    client = ScriptedChatClient([ChatMessage(content="我觉得应该分三章讲,先讲基础。")])
    outline = await plan_outline(_req(), client=client, model="m")
    assert outline.used_fallback is True
    assert [s.title for s in outline.sections] == list(DEFAULT_SECTIONS)
    assert "没有返回可解析的 JSON" in outline.rationale


async def test_wrong_shape_falls_back():
    client = ScriptedChatClient([ChatMessage(content='{"sections": "不是数组"}')])
    outline = await plan_outline(_req(), client=client, model="m")
    assert outline.used_fallback is True


async def test_empty_sections_falls_back():
    client = ScriptedChatClient([ChatMessage(content='{"objectives": [], "sections": []}')])
    outline = await plan_outline(_req(), client=client, model="m")
    assert outline.used_fallback is True
    assert "章节为空" in outline.rationale


async def test_model_exception_falls_back():
    class Boom:
        async def complete(self, **kwargs):
            raise RuntimeError("上游 503")

    outline = await plan_outline(_req(), client=Boom(), model="m")
    assert outline.used_fallback is True
    assert "模型调用失败" in outline.rationale


async def test_unreachable_duration_falls_back():
    """2 节最多 120 分钟,却要求 300 分钟 —— 怎么调都到不了,只能兜底。"""
    client = ScriptedChatClient([ChatMessage(content=_valid_outline_json((10, 10)))])
    outline = await plan_outline(_req(duration_min=300), client=client, model="m")
    assert outline.used_fallback is True
    assert "无法把章节时长调整到" in outline.rationale


async def test_overlong_sections_are_scaled_not_discarded():
    """模型把单位搞错(100+100+100 分钟)但比例对 —— 缩放保留,别丢。"""
    client = ScriptedChatClient([ChatMessage(content=_valid_outline_json((100, 100, 100)))])
    outline = await plan_outline(_req(duration_min=45), client=client, model="m")

    assert outline.used_fallback is False
    assert len(outline.sections) == 3
    assert sum(s.minutes for s in outline.sections) == 45


async def test_fallback_still_sums_to_the_requested_duration():
    """降级也要保证时长对得上,否则后面的交叉引用校验会失败。"""
    client = ScriptedChatClient([ChatMessage(content="乱七八糟")])
    outline = await plan_outline(_req(duration_min=30), client=client, model="m")
    assert sum(s.minutes for s in outline.sections) == 30


# ═══════════════════════════════════════════════════════════
# 时长归一化
# ═══════════════════════════════════════════════════════════


async def test_minutes_are_scaled_to_match_duration():
    """模型算错总时长是常态 —— 按比例缩放,而不是整份丢掉。"""
    client = ScriptedChatClient([ChatMessage(content=_valid_outline_json((100, 100, 100)))])
    outline = await plan_outline(_req(duration_min=45), client=client, model="m")

    assert outline.used_fallback is False          # 大纲本身可用
    assert sum(s.minutes for s in outline.sections) == 45


async def test_scaling_keeps_section_order():
    client = ScriptedChatClient([ChatMessage(content=_valid_outline_json((30, 10)))])
    outline = await plan_outline(_req(duration_min=60), client=client, model="m")
    assert [s.title for s in outline.sections] == ["第 1 节", "第 2 节"]
