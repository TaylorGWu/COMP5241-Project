"""出题 —— 按学习目标生成题目。

═══════════════════════════════════════════════════════════════════
这个文件守的两条契约,都是踩过坑才加的
═══════════════════════════════════════════════════════════════════
1. **语言必须进 prompt。**「教材语言」那个开关曾经是假的:前端传了、
   API 收了、大纲阶段用上了,但真正写内容的 agent 一个字都没提。
   所有单元测试都是绿的。

2. **prompt 里的 JSON schema 必须和 IR 一一对应。**`write_plan_entry`
   的 schema 曾经是个空壳,description 里写「字段见设计规格 §5.1」——
   但**模型看不到设计规格**,于是自己猜出了 `start` / `duration` 之类的字段,
   直到装配阶段才炸。假模型「恰好」传对了,所以测试全绿。

**原则:模型能看到的契约 —— schema 或 prompt —— 必须有测试守着。**

═══════════════════════════════════════════════════════════════════
其余测的是降级行为(§14)
═══════════════════════════════════════════════════════════════════
出题是流水线里的一个可选步骤。它失败**不能让整包失败** ——
课件和教案还在,教师不该因为出题失败就丢掉整次生成。

所以策略和 planner.py 一致:能解析 + 校验通过就用模型的,
任何一步失败就返回空题库并说明原因,**永远不抛异常**。
"""

from __future__ import annotations

import json
from typing import Any

from app.llm.client import ChatMessage, ScriptedChatClient
from app.schemas.ir import LearningObjective, Question, QuestionSet
from app.services.questions import (
    QUESTION_SCHEMA,
    QuestionRequest,
    generate_questions,
)

OBJECTIVES = [
    LearningObjective(id="LO1", text="解释分支与主干的关系"),
    LearningObjective(id="LO2", text="完成一次安全的合并"),
]


def _req(**overrides: Any) -> QuestionRequest:
    base: dict[str, Any] = {
        "objectives": OBJECTIVES,
        "audience": "非计算机专业初学者",
        "language": "zh-HK",
    }
    base.update(overrides)
    return QuestionRequest(**base)


def _question(qid: str = "q1", objective: str = "LO1", **overrides: Any) -> dict[str, Any]:
    """一道合法的题。字段名用 camelCase,与 §5.1 一致。"""
    base: dict[str, Any] = {
        "id": qid,
        "type": "mcq",
        "stem": "分支的作用是什么?",
        "options": [
            {"id": "A", "text": "让改动互相隔离"},
            {"id": "B", "text": "加快编译"},
        ],
        "answer": "A",
        "explanation": "分支让不同人的改动互不影响。",
        "difficulty": 2,
        "objectiveIds": [objective],
        "points": 5,
    }
    base.update(overrides)
    return base


def _client(payload: Any, *, as_text: bool = True) -> ScriptedChatClient:
    """假模型:把 payload 序列化成一条回复。"""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return ScriptedChatClient([ChatMessage(content=text)])


async def _run(payload: Any, req: QuestionRequest | None = None):
    client = _client(payload)
    result = await generate_questions(req or _req(), client=client, model="fake")
    return result, client


# ═══════════════════════════════════════════════════════════════
# 契约一:语言必须进 prompt(§11.7 那类 bug)
# ═══════════════════════════════════════════════════════════════


async def test_the_prompt_states_the_content_language():
    """选的语言必须真的送到模型面前 —— 否则那个开关就是假的。"""
    _, client = await _run({"questions": [_question()]}, _req(language="en"))

    user_message = client.requests[0]["messages"][-1]["content"]
    assert "en" in user_message


async def test_every_supported_language_reaches_the_prompt():
    for lang in ("en", "zh-HK", "zh-CN"):
        _, client = await _run({"questions": [_question()]}, _req(language=lang))
        assert lang in client.requests[0]["messages"][-1]["content"], lang


async def test_changing_the_language_changes_the_prompt():
    _, a = await _run({"questions": [_question()]}, _req(language="en"))
    _, b = await _run({"questions": [_question()]}, _req(language="zh-CN"))

    assert a.requests[0]["messages"][-1] != b.requests[0]["messages"][-1]


async def test_the_prompt_carries_every_objective_with_its_id():
    """模型必须知道目标 id,否则它标不出 objectiveIds。

    只给文字、不给 id 的话,它会自己编号(q1、O1、LO-1…),
    对不上大纲,覆盖率检查就永远算不对。
    """
    _, client = await _run({"questions": [_question()]})

    prompt = client.requests[0]["messages"][-1]["content"]
    for objective in OBJECTIVES:
        assert objective.id in prompt
        assert objective.text in prompt


async def test_the_prompt_states_the_audience():
    _, client = await _run({"questions": [_question()]})
    assert "非计算机专业初学者" in client.requests[0]["messages"][-1]["content"]


# ═══════════════════════════════════════════════════════════════
# 契约二:prompt 里的 schema 不能和 IR 漂移
# ═══════════════════════════════════════════════════════════════


def _aliases(model: type) -> set[str]:
    """IR 用 alias_generator=to_camel,所以要比别名而不是字段名。"""
    return {f.alias or name for name, f in model.model_fields.items()}


def test_the_schema_in_the_prompt_covers_every_ir_field():
    """schema 里少写一个字段,模型就只能猜 —— 猜错要到装配时才炸。"""
    assert set(QUESTION_SCHEMA["properties"]) == _aliases(Question)


def test_the_schema_marks_the_required_fields():
    """哪些字段是必须的,必须写清楚。

    `stem` / `type` 少了就不是一道题;`answer` 少了就没法评分。
    """
    required = set(QUESTION_SCHEMA.get("required", []))
    assert {"id", "type", "stem"} <= required


def test_the_schema_is_valid_json_schema():
    """schema 本身要能序列化 —— 它会被塞进 prompt。"""
    encoded = json.dumps(QUESTION_SCHEMA, ensure_ascii=False)
    assert "properties" in json.loads(encoded)


def test_every_schema_property_has_a_description():
    """没有 description 的字段等于没写 —— 模型看不懂英文缩写。

    这条是 `write_plan_entry` 那个坑的直接产物。
    """
    missing = [k for k, v in QUESTION_SCHEMA["properties"].items() if not v.get("description")]
    assert missing == [], f"这些字段没有 description:{missing}"


# ═══════════════════════════════════════════════════════════════
# 正常路径
# ═══════════════════════════════════════════════════════════════


async def test_a_valid_response_becomes_a_question_set():
    result, _ = await _run({"questions": [_question("q1", "LO1"), _question("q2", "LO2")]})

    assert result.used_fallback is False
    assert isinstance(result.question_set, QuestionSet)
    assert [q.id for q in result.question_set.questions] == ["q1", "q2"]
    assert result.question_set.questions[0].options[0].id == "A"
    assert result.question_set.questions[0].objective_ids == ["LO1"]


async def test_a_code_fence_around_the_json_is_tolerated():
    """模型很爱加 ```json 围栏 —— 这不是错误,不该降级。"""
    fenced = "```json\n" + json.dumps({"questions": [_question()]}, ensure_ascii=False) + "\n```"
    result, _ = await _run(fenced)

    assert result.used_fallback is False
    assert len(result.question_set.questions) == 1


async def test_chatter_around_the_json_is_tolerated():
    noisy = "好的,以下是题目:\n" + json.dumps({"questions": [_question()]}, ensure_ascii=False) + "\n希望有帮助。"
    result, _ = await _run(noisy)

    assert result.used_fallback is False
    assert len(result.question_set.questions) == 1


async def test_the_count_per_objective_reaches_the_prompt():
    """教师想要每个目标几道题,这个数得让模型知道。"""
    _, client = await _run({"questions": [_question()]}, _req(count_per_objective=3))

    assert "3" in client.requests[0]["messages"][-1]["content"]


async def test_material_context_reaches_the_prompt_when_given():
    _, client = await _run(
        {"questions": [_question()]},
        _req(material_context="讲义第 3 页:分支让改动互相隔离。"),
    )

    assert "分支让改动互相隔离" in client.requests[0]["messages"][-1]["content"]


# ═══════════════════════════════════════════════════════════════
# 降级:任何一步失败都不能抛异常(§14)
# ═══════════════════════════════════════════════════════════════


async def test_a_model_failure_returns_an_empty_set_instead_of_raising():
    """上游抖一下不能让整次生成白跑 —— 课件和教案还在。"""

    class _Boom:
        async def complete(self, **_kwargs: Any) -> ChatMessage:
            raise ConnectionError("模拟网络抖动")

    result = await generate_questions(_req(), client=_Boom(), model="fake")

    assert result.used_fallback is True
    assert result.question_set.questions == []
    assert "ConnectionError" in result.reason


async def test_unparseable_output_returns_an_empty_set():
    result, _ = await _run("我觉得还是不要出题了。")

    assert result.used_fallback is True
    assert result.question_set.questions == []
    assert "JSON" in result.reason


async def test_a_wrong_shaped_payload_returns_an_empty_set():
    """questions 应该是数组,给个对象就是结构不合法。"""
    result, _ = await _run({"questions": {"q1": _question()}})

    assert result.used_fallback is True
    assert result.question_set.questions == []


async def test_an_empty_question_list_is_a_fallback():
    """模型返回了合法 JSON 但一道题都没有 —— 那也算没出出来。"""
    result, _ = await _run({"questions": []})

    assert result.used_fallback is True
    assert result.question_set.questions == []


# ═══════════════════════════════════════════════════════════════
# 逐题校验:坏的那道丢掉,好的留下
# ═══════════════════════════════════════════════════════════════


async def test_a_malformed_question_is_dropped_and_the_rest_survive():
    """一道题不合规不该毁掉整批 —— 和教案环节的处理方式一致。"""
    payload = {"questions": [_question("q1"), {"id": "q2"}, _question("q3", "LO2")]}
    result, _ = await _run(payload)

    assert [q.id for q in result.question_set.questions] == ["q1", "q3"]
    assert result.used_fallback is False
    assert "q2" in result.reason or "跳过" in result.reason


async def test_an_mcq_without_options_is_dropped():
    """没有选项的选择题是废的 —— 学生没法作答。"""
    payload = {"questions": [_question("q1", options=[]), _question("q2", "LO2")]}
    result, _ = await _run(payload)

    assert [q.id for q in result.question_set.questions] == ["q2"]


async def test_an_answer_pointing_at_a_missing_option_is_dropped():
    """答案说选 C,但只有 A 和 B —— 这种题会把学生逼疯。"""
    payload = {"questions": [_question("q1", answer="C"), _question("q2", "LO2")]}
    result, _ = await _run(payload)

    assert [q.id for q in result.question_set.questions] == ["q2"]


async def test_an_objective_id_the_model_invented_is_dropped_from_the_question():
    """模型偶尔会编一个不存在的目标 id。

    直接丢掉整道题太狠(题干本身可能是好的),但**不能留着** ——
    留着会让覆盖率检查把一个不存在的目标算成已覆盖。
    """
    payload = {"questions": [_question("q1", "LO1", objectiveIds=["LO1", "LO9"])]}
    result, _ = await _run(payload)

    assert result.question_set.questions[0].objective_ids == ["LO1"]


async def test_a_question_with_no_valid_objective_left_is_dropped():
    """标的目标全都对不上,那这道题没法进覆盖率统计。"""
    payload = {"questions": [_question("q1", objective="LO9"), _question("q2", "LO2")]}
    result, _ = await _run(payload)

    assert [q.id for q in result.question_set.questions] == ["q2"]


async def test_duplicate_question_ids_are_made_unique():
    """模型会重复用同一个 id —— 不修的话组卷会选中同一道题两次。"""
    payload = {"questions": [_question("q1"), _question("q1", "LO2")]}
    result, _ = await _run(payload)

    ids = [q.id for q in result.question_set.questions]
    assert len(ids) == len(set(ids)), f"id 重复了:{ids}"


async def test_difficulty_out_of_range_is_clamped_not_dropped():
    """难度 7 是模型手滑,不是结构错误 —— 夹到 5 比丢掉一整道题划算。"""
    payload = {"questions": [_question("q1", difficulty=7)]}
    result, _ = await _run(payload)

    assert result.question_set.questions[0].difficulty == 5
