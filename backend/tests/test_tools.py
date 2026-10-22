"""工具 schema 测试 —— 盯住「模型看到的」和「代码要求的」不能漂移。

═══════════════════════════════════════════════════════════════════
这组测试为什么必须存在
═══════════════════════════════════════════════════════════════════
**模型只能看到工具 schema。** schema 里没写的字段,它只能猜。

`write_plan_entry` 原来的 schema 是个空壳:

    {"type": "object",
     "properties": {"entry": {"type": "object",
                              "description": "字段见设计规格 §5.1 的 TimelineEntry"}}}

问题是 —— **模型看不到设计规格**。它于是自己猜出了
`{"start": 0, "duration": 45, ...}`,直到装配阶段才炸 ValidationError,
那时 token 已经烧完了。

而假模型「恰好」传对了字段,所以相关测试全绿。
真模型第一次跑就把这个坑踩出来了。

结论:**凡是「人照着文档填」的 schema,都必须有一条测试盯着它和
IR 模型一一对应。** 否则文档改了、模型字段改了,schema 不会跟着改。
"""

from __future__ import annotations

import pytest

from app.schemas.ir import Slide, TimelineEntry
from app.services.tools import PLAN_ENTRY_SCHEMA, SLIDE_SCHEMA, SectionDeps, build_section_tools


def _aliases(model: type) -> set[str]:
    """取模型对外暴露的字段名。

    IR 用 `alias_generator=to_camel`,所以 `teacher_action` 对外是
    `teacherAction` —— 比对时必须用别名,不能直接比 `model_fields` 的键。
    """
    return {f.alias or name for name, f in model.model_fields.items()}


def _assert_schema_matches_model(schema: dict, model: type) -> None:
    """schema 既不能凭空造字段,也不能漏掉模型的必填字段。"""
    schema_fields = set(schema["properties"])
    model_fields = _aliases(model)

    invented = schema_fields - model_fields
    assert not invented, f"{model.__name__} 的 schema 里有模型不认识的字段:{invented}"

    required = {
        (f.alias or name) for name, f in model.model_fields.items() if f.is_required()
    }
    missing = required - schema_fields
    assert not missing, f"{model.__name__} 要求必填但 schema 没告诉模型:{missing}"


# ═══════════════════════════════════════════════════════════
# ★ 防漂移:两套 schema 各盯一个模型
# ═══════════════════════════════════════════════════════════


def test_plan_entry_schema_matches_timeline_entry():
    """教案环节的 schema 必须和 TimelineEntry 对齐。

    这条测试如果早写一天,真模型那次「装配阶段 ValidationError」就不会发生。
    """
    _assert_schema_matches_model(PLAN_ENTRY_SCHEMA, TimelineEntry)


def test_slide_schema_matches_slide():
    """幻灯片 schema 同理。它本来就写得对,加这条是防以后改坏。"""
    _assert_schema_matches_model(SLIDE_SCHEMA, Slide)


def test_slide_schema_exposes_instructional_semantics():
    """生成模型必须看到教学角色与视觉用途，否则只能猜。"""
    assert {"teachingRole", "visualPurpose"} <= set(SLIDE_SCHEMA["properties"])


def test_schema_says_more_than_just_object():
    """schema 必须有实打实的字段定义 —— 空壳等于让模型猜。"""
    for schema in (PLAN_ENTRY_SCHEMA, SLIDE_SCHEMA):
        assert schema.get("properties"), "schema 不能没有 properties"
        assert schema.get("required"), "schema 必须声明哪些字段必填"


def test_the_shape_the_real_model_invented_is_gone():
    """真模型曾猜出 `start` / `duration` —— 现在 schema 里只有正确字段。"""
    props = set(PLAN_ENTRY_SCHEMA["properties"])
    assert "start" not in props and "duration" not in props
    assert {"id", "phase", "minutes", "teacherAction"} <= props


@pytest.mark.parametrize("schema", [PLAN_ENTRY_SCHEMA, SLIDE_SCHEMA])
def test_every_field_has_a_description(schema):
    """每个字段都要有说明 —— 模型的填写质量直接取决于这句话。"""
    for name, spec in schema["properties"].items():
        assert spec.get("description"), f"字段 {name} 没有 description"


# ═══════════════════════════════════════════════════════════
# 工具集本身
# ═══════════════════════════════════════════════════════════


def test_write_plan_entry_actually_embeds_the_schema():
    """build_section_tools 造出来的工具里,必须真的带上这份 schema。"""

    class _Noop:  # 这个测试只关心 schema,不关心依赖
        pass

    tools = build_section_tools(_Noop())  # type: ignore[arg-type]
    by_name = {t.name: t for t in tools}

    entry_schema = by_name["write_plan_entry"].parameters["properties"]["entry"]
    assert set(entry_schema["properties"]) == set(PLAN_ENTRY_SCHEMA["properties"])

    slide_items = by_name["write_section"].parameters["properties"]["slides"]["items"]
    assert set(slide_items["properties"]) == set(SLIDE_SCHEMA["properties"])


def test_write_section_is_the_only_terminal_tool():
    """终止工具只能有一个 —— 多了一定是搞错了。"""

    class _Noop:
        pass

    tools = build_section_tools(_Noop())  # type: ignore[arg-type]
    assert [t.name for t in tools if t.terminal] == ["write_section"]


async def test_make_diagram_normalizes_model_escaped_newlines_before_registering_asset():
    """A model may double-escape JSON newlines; the renderer must receive real lines."""
    received: list[str] = []

    async def make_diagram(code: str) -> str:
        received.append(code)
        return "asset-1"

    async def unused(_value: str):
        return []

    deps = SectionDeps(search_materials=unused, make_diagram=make_diagram, request_illustration=unused)
    tool = next(tool for tool in build_section_tools(deps) if tool.name == "make_diagram")

    await tool.fn({"mermaid": 'graph LR\\n  A["main"] --> B["feature branch"]'})

    expected = 'graph LR\n  A["main"] --> B["feature branch"]'
    assert received == [expected]
    assert deps.assets[0]["spec"]["code"] == expected
