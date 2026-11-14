"""术语白话化与无障碍 —— 设计规格 §9.4。

═══════════════════════════════════════════════════════════════════
这个文件守什么
═══════════════════════════════════════════════════════════════════
两件不同的事,分开测:

    build_glossary   课件里的专业词 → 一句白话解释
    describe_visuals 每张图 → 一段替代文本

分开的理由:合成一次调用的话,schema 会长出一个
「要么有 term 要么有 assetId」的形状,而那正是模型最容易填错的结构。
分开之后降级也各自发生 —— 术语解释失败不影响替代文本。

═══════════════════════════════════════════════════════════════════
§9.4 的两条硬要求只能靠 prompt,所以测 prompt
═══════════════════════════════════════════════════════════════════
· 白话解释**不得引入新的未解释术语**
· 替代文本**要描述这张图在讲什么,而不是罗列图中元素**

这两条没法自动判定「做到了没有」—— 只能测 prompt 里写了这两条要求。
这不是敷衍:模型看不到设计规格,它只看得到 prompt。要求没写进去,
就等于没要求。
"""

from __future__ import annotations

import json
from typing import Any

from app.llm.client import ChatMessage, ScriptedChatClient
from app.schemas.ir import GlossaryEntry, LearningObjective, Visual
from app.services.glossary import (
    ALT_TEXT_SCHEMA,
    GLOSSARY_ENTRY_SCHEMA,
    GlossaryRequest,
    VisualRequest,
    build_glossary,
    describe_visuals,
)

OBJECTIVES = [
    LearningObjective(id="LO1", text="解释分支与主干的关系"),
    LearningObjective(id="LO2", text="完成一次安全的合并"),
]


def _glossary_req(**overrides: Any) -> GlossaryRequest:
    base: dict[str, Any] = {
        "content": "分支是一条独立的开发线。合并冲突发生在两个人改了同一行的时候。",
        "objectives": OBJECTIVES,
        "language": "zh-HK",
    }
    base.update(overrides)
    return GlossaryRequest(**base)


def _entry(term: str = "分支", plain: str = "一条独立的开发线,改动不会影响别人") -> dict[str, Any]:
    return {"term": term, "plain": plain, "objectiveIds": ["LO1"]}


def _client(payload: Any) -> ScriptedChatClient:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return ScriptedChatClient([ChatMessage(content=text)])


def _aliases(model: type) -> set[str]:
    return {f.alias or name for name, f in model.model_fields.items()}


# ═══════════════════════════════════════════════════════════════
# 契约:语言必须进 prompt
# ═══════════════════════════════════════════════════════════════


async def test_the_glossary_prompt_states_the_language():
    client = _client({"glossary": [_entry()]})
    await build_glossary(_glossary_req(language="en"), client=client, model="fake")

    assert "en" in client.requests[0]["messages"][-1]["content"]


async def test_every_language_reaches_the_glossary_prompt():
    for lang in ("en", "zh-HK", "zh-CN"):
        client = _client({"glossary": [_entry()]})
        await build_glossary(_glossary_req(language=lang), client=client, model="fake")
        assert lang in client.requests[0]["messages"][-1]["content"], lang


async def test_the_alt_text_prompt_states_the_language():
    client = _client({"descriptions": [{"assetId": "as-1", "altText": "分支"}]})
    req = VisualRequest(visuals=[Visual(id="v1", kind="diagram", asset_id="as-1")], language="en")
    await describe_visuals(req, client=client, model="fake")

    assert "en" in client.requests[0]["messages"][-1]["content"]


async def test_the_glossary_prompt_carries_the_course_content():
    """模型得看到内容才挑得出词。"""
    client = _client({"glossary": [_entry()]})
    await build_glossary(_glossary_req(), client=client, model="fake")

    body = client.requests[0]["messages"][-1]["content"]
    assert "合并冲突" in body


async def test_the_glossary_prompt_carries_the_objective_ids():
    """模型要能标 objectiveIds —— 只给文字它就会自己编号。"""
    client = _client({"glossary": [_entry()]})
    await build_glossary(_glossary_req(), client=client, model="fake")

    body = client.requests[0]["messages"][-1]["content"]
    for objective in OBJECTIVES:
        assert objective.id in body


# ═══════════════════════════════════════════════════════════════
# 契约:§9.4 的两条要求必须写进 prompt
# ═══════════════════════════════════════════════════════════════


async def test_the_glossary_prompt_forbids_new_jargon():
    """「用不认识的词解释不认识的词」等于没解释 —— 这条得明文写出来。"""
    client = _client({"glossary": [_entry()]})
    await build_glossary(_glossary_req(), client=client, model="fake")

    system = client.requests[0]["messages"][0]["content"]
    assert "不能出现别的没解释过的专业术语" in system


async def test_the_alt_text_prompt_forbids_enumerating_elements():
    """替代文本最容易写成「左边一个圆、右边一个方框」—— 那对读屏用户没用。"""
    client = _client({"descriptions": [{"assetId": "as-1", "altText": "分支"}]})
    req = VisualRequest(visuals=[Visual(id="v1", kind="diagram", asset_id="as-1")])
    await describe_visuals(req, client=client, model="fake")

    system = client.requests[0]["messages"][0]["content"]
    assert "罗列图中元素" in system


# ═══════════════════════════════════════════════════════════════
# 契约:schema 不能和 IR 漂移
# ═══════════════════════════════════════════════════════════════


def test_the_glossary_schema_covers_every_ir_field():
    assert set(GLOSSARY_ENTRY_SCHEMA["properties"]) == _aliases(GlossaryEntry)


def test_both_schemas_describe_every_field():
    """没有 description 的字段等于没写 —— 模型看不懂英文缩写。"""
    for name, schema in (
        ("GLOSSARY_ENTRY_SCHEMA", GLOSSARY_ENTRY_SCHEMA),
        ("ALT_TEXT_SCHEMA", ALT_TEXT_SCHEMA),
    ):
        missing = [k for k, v in schema["properties"].items() if not v.get("description")]
        assert missing == [], f"{name} 里这些字段没有 description:{missing}"


def test_the_schemas_are_valid_json():
    for schema in (GLOSSARY_ENTRY_SCHEMA, ALT_TEXT_SCHEMA):
        assert "properties" in json.loads(json.dumps(schema, ensure_ascii=False))


# ═══════════════════════════════════════════════════════════════
# 正常路径
# ═══════════════════════════════════════════════════════════════


async def test_valid_entries_become_a_glossary():
    client = _client({"glossary": [_entry("分支"), _entry("合并冲突", "两个人都改了同一行")]})
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert result.used_fallback is False
    assert [e.term for e in result.glossary] == ["分支", "合并冲突"]
    assert result.glossary[0].plain


async def test_the_glossary_tolerates_code_fences():
    fenced = "```json\n" + json.dumps({"glossary": [_entry()]}, ensure_ascii=False) + "\n```"
    client = _client(fenced)
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert result.used_fallback is False
    assert len(result.glossary) == 1


async def test_valid_descriptions_become_a_mapping():
    visual = Visual(id="v1", kind="diagram", asset_id="as-1")
    client = _client({"descriptions": [{"assetId": "as-1", "altText": "改动在分支上进行"}]})
    result = await describe_visuals(VisualRequest(visuals=[visual]), client=client, model="fake")

    assert result.used_fallback is False
    assert result.alt_texts == {"as-1": "改动在分支上进行"}


async def test_the_visual_spec_reaches_the_alt_text_prompt():
    """模型要看到图是怎么画的,才写得出「这张图在讲什么」。"""
    visual = Visual(
        id="v1",
        kind="diagram",
        asset_id="as-1",
        spec={"engine": "mermaid", "code": "graph LR; 分支-->主干"},
    )
    client = _client({"descriptions": [{"assetId": "as-1", "altText": "x"}]})
    await describe_visuals(VisualRequest(visuals=[visual]), client=client, model="fake")

    assert "分支-->主干" in client.requests[0]["messages"][-1]["content"]


# ═══════════════════════════════════════════════════════════════
# 逐条校验
# ═══════════════════════════════════════════════════════════════


async def test_an_entry_without_an_explanation_is_dropped():
    """没有解释的词条等于没写 —— 留着只会在界面上占一行。"""
    client = _client({"glossary": [_entry("分支", ""), _entry("合并冲突", "两个人改了同一行")]})
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert [e.term for e in result.glossary] == ["合并冲突"]
    assert "分支" in result.reason


async def test_duplicate_terms_keep_only_the_first():
    """同一个词解释两遍,界面上会出现两条一模一样的。"""
    client = _client({"glossary": [_entry("分支", "第一条"), _entry("分支", "第二条")]})
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert [e.term for e in result.glossary] == ["分支"]
    assert result.glossary[0].plain == "第一条"


async def test_an_invented_objective_id_is_stripped_from_the_entry():
    """编一个不存在的目标 id 会污染覆盖率统计 —— 剥掉,但词条留着。"""
    client = _client({"glossary": [_entry() | {"objectiveIds": ["LO1", "LO9"]}]})
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert result.glossary[0].objective_ids == ["LO1"]


async def test_a_description_for_an_asset_that_does_not_exist_is_dropped():
    """编了一个 assetId 挂不上去 —— 丢掉,不能污染资产池。"""
    visual = Visual(id="v1", kind="diagram", asset_id="as-1")
    client = _client(
        {
            "descriptions": [
                {"assetId": "as-999", "altText": "编的"},
                {"assetId": "as-1", "altText": "真的"},
            ]
        }
    )
    result = await describe_visuals(VisualRequest(visuals=[visual]), client=client, model="fake")

    assert result.alt_texts == {"as-1": "真的"}
    assert "as-999" in result.reason


async def test_an_empty_description_is_dropped():
    visual = Visual(id="v1", kind="diagram", asset_id="as-1")
    client = _client({"descriptions": [{"assetId": "as-1", "altText": "   "}]})
    result = await describe_visuals(VisualRequest(visuals=[visual]), client=client, model="fake")

    assert result.used_fallback is True
    assert result.alt_texts == {}


async def test_a_visual_without_an_asset_id_is_not_sent_to_the_model():
    """还没渲染的图没有 assetId,替代文本没地方挂 —— 不该浪费一次调用。"""
    visuals = [
        Visual(id="v1", kind="diagram", spec={"code": "graph LR; A-->B"}),
        Visual(id="v2", kind="diagram", asset_id="as-1"),
    ]
    client = _client({"descriptions": [{"assetId": "as-1", "altText": "x"}]})
    await describe_visuals(VisualRequest(visuals=visuals), client=client, model="fake")

    body = client.requests[0]["messages"][-1]["content"]
    assert "assetId=as-1" in body
    assert "assetId=None" not in body


# ═══════════════════════════════════════════════════════════════
# 降级 —— 都不许抛异常(§14)
# ═══════════════════════════════════════════════════════════════


class _Boom:
    async def complete(self, **_kwargs: Any) -> ChatMessage:
        raise ConnectionError("模拟网络抖动")


async def test_a_glossary_model_failure_returns_empty_not_raises():
    result = await build_glossary(_glossary_req(), client=_Boom(), model="fake")

    assert result.used_fallback is True
    assert result.glossary == []
    assert "ConnectionError" in result.reason


async def test_an_alt_text_model_failure_returns_empty_not_raises():
    visual = Visual(id="v1", kind="diagram", asset_id="as-1")
    result = await describe_visuals(VisualRequest(visuals=[visual]), client=_Boom(), model="fake")

    assert result.used_fallback is True
    assert result.alt_texts == {}
    assert "ConnectionError" in result.reason


async def test_unparseable_glossary_output_returns_empty():
    client = _client("这些词我就不解释了。")
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert result.used_fallback is True
    assert "JSON" in result.reason


async def test_a_wrong_shaped_glossary_payload_returns_empty():
    client = _client({"glossary": {"分支": "一条独立的开发线"}})
    result = await build_glossary(_glossary_req(), client=client, model="fake")

    assert result.used_fallback is True
    assert result.glossary == []


async def test_empty_content_is_not_sent_to_the_model():
    """没有内容可挑词,不该浪费一次调用。"""
    client = _client({"glossary": []})
    result = await build_glossary(_glossary_req(content="   "), client=client, model="fake")

    assert result.used_fallback is True
    assert client.requests == []
