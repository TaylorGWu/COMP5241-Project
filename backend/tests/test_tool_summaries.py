"""工具摘要 —— 设计规格 §6.1.2「动作流」里那句给人看的话。

═══════════════════════════════════════════════════════════════════
这组测试守的是什么
═══════════════════════════════════════════════════════════════════
进度界面上要显示的是:

    ✓ 检索「分支合并」→ 命中 4 段
    ✓ 画示意图(Mermaid)
    ✓ 提交 3 页课件
    ✗ search_materials / make_diagram / write_section

函数名对教师没有意义。所以摘要必须**由工具自己提供** ——
只有它知道 `{"query": "分支合并"}` 里哪个字段是重点。

而「每个工具都有摘要器」这件事很容易在加新工具时被忘掉:
忘了不会报错,只会让界面上多出一行 `new_tool_name`,没人发现。
所以要有测试逐个数。

═══════════════════════════════════════════════════════════════════
为什么还要测「摘要别太长」
═══════════════════════════════════════════════════════════════════
摘要会进 SSE 事件、进浏览器。`write_section` 的参数里是**整页课件内容**,
`make_diagram` 的参数里是**整段 Mermaid 源码**。摘要器如果直接
`str(args)`,一条事件可能就是几十 KB,而且是每轮都发。

所以这里用「敌意参数」测:给最长的输入,断言摘要仍然很短。
"""

from __future__ import annotations

from typing import Any

from app.services.tools import build_edit_tools, build_section_tools

#: 界面上一条摘要超过这个长度就没有意义了(要换行、要挤掉别的信息)
MAX_SUMMARY = 120


def _section_tools() -> dict[str, Any]:
    """造一套 L1 工具。摘要测试不碰依赖,所以传 None 就够。"""
    return {t.name: t for t in build_section_tools(None)}  # type: ignore[arg-type]


def _edit_tools() -> dict[str, Any]:
    return {t.name: t for t in build_edit_tools(None)}  # type: ignore[arg-type]


def _summary(tool: Any, args: dict[str, Any]) -> str:
    """取摘要。没有摘要器就直接失败 —— 这正是要守的东西。"""
    assert tool.summarize is not None, f"{tool.name} 没有 summarize,界面上会显示函数名"
    return tool.summarize(args)


# ═══════════════════════════════════════════════════════════════
# 完整性:一个都不能漏
# ═══════════════════════════════════════════════════════════════


def test_every_section_tool_provides_a_summary():
    missing = [name for name, t in _section_tools().items() if t.summarize is None]
    assert missing == [], f"这些 L1 工具缺摘要器:{missing}"


def test_every_edit_tool_provides_a_summary():
    missing = [name for name, t in _edit_tools().items() if t.summarize is None]
    assert missing == [], f"这些 L2 工具缺摘要器:{missing}"


# ═══════════════════════════════════════════════════════════════
# 内容:摘要要真的来自参数
# ═══════════════════════════════════════════════════════════════


def test_search_summary_shows_the_query():
    tool = _section_tools()["search_materials"]
    assert "分支合并" in _summary(tool, {"query": "分支合并"})


def test_diagram_summary_does_not_dump_the_mermaid_source():
    """Mermaid 源码可能几百字符 —— 摘要里不能整段塞进去。"""
    tool = _section_tools()["make_diagram"]
    long_mermaid = "graph LR; " + " --> ".join(f"N{i}" for i in range(60))

    summary = _summary(tool, {"mermaid": long_mermaid})

    assert len(summary) <= MAX_SUMMARY
    assert "N59" not in summary, "整段源码漏进摘要了"


def test_write_section_summary_states_how_many_slides():
    """「提交 3 页课件」—— 这是教师最关心的数字。"""
    tool = _section_tools()["write_section"]

    assert "3" in _summary(tool, {"slides": [{}, {}, {}]})
    assert "1" in _summary(tool, {"slides": [{}]})


def test_write_section_summary_stays_short_for_a_huge_deck():
    """三页摘要要短,五十页也要短 —— 别把整本课件塞进一条进度事件。"""
    tool = _section_tools()["write_section"]
    huge = [{"title": "标题" * 50, "speakerNotes": "讲稿" * 200} for _ in range(50)]

    summary = _summary(tool, {"slides": huge})

    assert len(summary) <= MAX_SUMMARY
    assert "50" in summary


def test_plan_entry_summary_names_the_phase():
    tool = _section_tools()["write_plan_entry"]
    assert "概念导入" in _summary(tool, {"entry": {"phase": "概念导入"}})


def test_patch_summary_names_the_slide():
    """L2 里「在改哪一页」是最关键的信息。"""
    tool = _edit_tools()["patch_slide"]
    assert "s3" in _summary(tool, {"slide_id": "s3", "patch": {}, "reason": "太密了"})


def test_patch_summary_does_not_dump_the_patch_body():
    tool = _edit_tools()["patch_slide"]
    args = {
        "slide_id": "s3",
        "patch": {"speakerNotes": "很长的讲稿" * 100},
        "reason": "太密了" * 50,
    }

    assert len(_summary(tool, args)) <= MAX_SUMMARY


def test_read_slide_summary_names_the_slide():
    assert "s7" in _summary(_edit_tools()["read_slide"], {"slide_id": "s7"})


# ═══════════════════════════════════════════════════════════════
# 健壮性:参数长得不对也不能炸
# ═══════════════════════════════════════════════════════════════


def test_no_summarizer_crashes_on_empty_arguments():
    """模型可能给个空对象。摘要器自己炸了会拖垮整个生成(§14)。"""
    for name, tool in {**_section_tools(), **_edit_tools()}.items():
        assert isinstance(_summary(tool, {}), str), f"{name} 在空参数上出错了"


def test_no_summarizer_crashes_on_wrong_argument_types():
    """模型填错类型是常事:`slides` 传成字符串、`entry` 传成数字。"""
    hostile = [
        {"slides": "不是数组"},
        {"slides": 42},
        {"entry": "不是对象"},
        {"query": 123},
        {"mermaid": None},
        {"slide_id": ["s1"]},
        {"prompt": {"nested": "object"}},
    ]
    for name, tool in {**_section_tools(), **_edit_tools()}.items():
        for args in hostile:
            assert isinstance(_summary(tool, args), str), f"{name} 在 {args} 上出错了"
