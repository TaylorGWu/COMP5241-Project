"""Agent 实时叙述 —— 设计规格 §6.1.2 的「动作流」。

═══════════════════════════════════════════════════════════════════
这个文件守的是什么
═══════════════════════════════════════════════════════════════════
教师盯着生成界面等 30–120 秒,总得看见点什么。原来的界面上什么都没有 ——
`ProgressEvent` 只在**某一节整节跑完**时发一次,一节内部二十秒完全静止。

「动作流」补的就是这段:agent 每转一轮、每调一个工具,都往外报一句。
信息源是**本地**的(我们自己执行工具),所以它:

  · 不需要思考模式
  · 不需要真模型
  · 不花钱

因此可以完全离线测试 —— 这个文件就是干这个的。

═══════════════════════════════════════════════════════════════════
为什么断言的是事件序列
═══════════════════════════════════════════════════════════════════
和 test_agent.py 同一条规矩(AGENTS.md 硬规则):**断言工具调用序列,不断言文本。**

叙述层的 `summary` 是给人读的中文,措辞迟早会改,断言它等于给未来的自己
下绊子。要断言的是结构:先 `tool_start` 后 `tool_end`、`turn` 递增、
结束原因正确、失败的工具也要有一条 `tool_end`(否则界面上那一条会永远转圈)。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.llm.client import ChatMessage, ScriptedChatClient, ToolCall
from app.services.agent import AgentStep, Tool, run_agent


def _tool(
    name: str,
    *,
    terminal: bool = False,
    crash: bool = False,
    summarize: Callable[[dict[str, Any]], str] | None = None,
) -> Tool:
    """造一个测试用工具。可选:终止 / 抛异常 / 自带摘要器。"""

    async def fn(args: dict[str, Any]) -> Any:
        if crash:
            raise RuntimeError("上游服务挂了")
        return {"ok": True, "tool": name}

    return Tool(
        name=name,
        description=f"{name} 工具",
        parameters={"type": "object", "properties": {}},
        fn=fn,
        terminal=terminal,
        summarize=summarize,
    )


def _call(name: str, cid: str = "c1", **args: Any) -> ChatMessage:
    """造一条「模型要求调工具」的回复。"""
    return ChatMessage(tool_calls=[ToolCall(id=cid, name=name, arguments=args)])


def _kinds(steps: list[AgentStep]) -> list[str]:
    return [s.kind for s in steps]


# ═══════════════════════════════════════════════════════════════
# 结构:先 start 后 end,轮次递增
# ═══════════════════════════════════════════════════════════════


async def test_a_turn_is_reported_before_any_tool_runs():
    """「正在思考」这一刻也要有事件 —— 等模型回复是界面最长的静止期。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好了")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    assert _kinds(steps)[0] == "turn"
    assert steps[0].turn == 1


async def test_every_tool_call_reports_a_start_then_an_end():
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好了")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    relevant = [(s.kind, s.tool) for s in steps if s.tool == "search"]
    assert relevant == [("tool_start", "search"), ("tool_end", "search")]


async def test_steps_carry_the_turn_number_they_happened_in():
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search", cid="c1"), _call("finish", cid="c2")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search"), _tool("finish", terminal=True)],
        on_step=steps.append,
    )

    assert [s.turn for s in steps if s.tool == "search"] == [1, 1]
    assert [s.turn for s in steps if s.tool == "finish"] == [2, 2]


async def test_a_tool_start_is_marked_running():
    """`tool_start` 必须自带 `status="running"`,不能留空。

    留空的后果不是「少个字段」而是**消费方猜错**:L2 的步骤列表按
    "running" 把 start 和 end 配成一行,status 是空串就一条都配不上,
    两次工具调用会显示成四行。这个 bug 只在界面上看得见 ——
    单元测试断言了「有 start 有 end」,但没人断言 status 的值。
    """
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    assert next(s for s in steps if s.kind == "tool_start").status == "running"


async def test_a_successful_tool_ends_with_status_ok():
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好了")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    end = next(s for s in steps if s.kind == "tool_end")
    assert end.status == "ok"


# ═══════════════════════════════════════════════════════════════
# 失败也要收尾 —— 否则界面上那一条会永远转圈
# ═══════════════════════════════════════════════════════════════


async def test_a_failing_tool_still_reports_an_end_with_error_status():
    """§14:单个工具失败不致命。但界面上必须看见它失败了,而且要收尾。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("boom"), ChatMessage(content="我换个方式")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("boom", crash=True)], on_step=steps.append,
    )

    assert _kinds(steps).count("tool_start") == 1
    assert _kinds(steps).count("tool_end") == 1, "失败的工具也必须发一条 tool_end"
    end = next(s for s in steps if s.kind == "tool_end")
    assert end.status == "error"


async def test_an_unparseable_tool_call_reports_a_start_and_an_end():
    """参数不是合法 JSON 时不执行,但**依然要有 start / end** —— 界面上不能留个洞。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient(
        [
            ChatMessage(
                tool_calls=[
                    ToolCall(id="c1", name="search", arguments={}, parse_error="参数不是合法 JSON")
                ]
            ),
            ChatMessage(content="好"),
        ]
    )

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    assert _kinds(steps).count("tool_start") == 1
    assert _kinds(steps).count("tool_end") == 1
    assert next(s for s in steps if s.kind == "tool_end").status == "error"


async def test_an_unknown_tool_is_narrated_as_an_error():
    """模型编了个不存在的工具 —— 界面上要看得见,而不是静默跳过。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("hack_the_planet"), ChatMessage(content="好的")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    end = next(s for s in steps if s.kind == "tool_end")
    assert end.status == "error"
    assert end.tool == "hack_the_planet"


# ═══════════════════════════════════════════════════════════════
# 摘要:给人看的一行
# ═══════════════════════════════════════════════════════════════


async def test_the_summary_comes_from_the_tool_itself():
    """工具最清楚自己的参数是什么意思 —— 摘要由它提供,agent 层保持通用。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search", query="分支合并"), ChatMessage(content="好")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search", summarize=lambda a: f"检索「{a.get('query', '')}」")],
        on_step=steps.append,
    )

    assert next(s for s in steps if s.kind == "tool_start").summary == "检索「分支合并」"


async def test_a_tool_without_a_summarizer_gets_a_generic_one():
    """没有摘要器也不能空着 —— 退回到「第一个标量参数」,总比只显示函数名强。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search", query="分支合并"), ChatMessage(content="好")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    assert "分支合并" in next(s for s in steps if s.kind == "tool_start").summary


async def test_a_tool_with_no_useful_arguments_summarises_to_empty_string():
    """没有参数可摘时给空串,不要塞个 "None" 或大括号上去。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("tick"), ChatMessage(content="好")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("tick")], on_step=steps.append,
    )

    assert next(s for s in steps if s.kind == "tool_start").summary == ""


async def test_the_end_summary_matches_the_start_summary():
    """成功时 `tool_end` 复述同一句人话,而不是空字符串。

    消费方(L2 的步骤列表)靠这个把两行配上对。如果 end 只有工具名,
    每个消费方都得自己记住「刚才那条 start 说的是什么」——
    那是白给的复杂度,而且每处实现都可能记错。
    """
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search", query="分支合并"), ChatMessage(content="好")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search", summarize=lambda a: f"检索「{a.get('query', '')}」")],
        on_step=steps.append,
    )

    start = next(s for s in steps if s.kind == "tool_start")
    end = next(s for s in steps if s.kind == "tool_end")
    assert end.summary == start.summary == "检索「分支合并」"


async def test_a_failed_tool_reports_the_error_not_the_summary():
    """失败时要给真正的错误信息 —— 「画示意图(Mermaid)」看不出哪里炸了。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("boom"), ChatMessage(content="我换个方式")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("boom", crash=True, summarize=lambda _a: "做某件事")],
        on_step=steps.append,
    )

    end = next(s for s in steps if s.kind == "tool_end")
    assert "RuntimeError" in end.summary
    assert "做某件事" not in end.summary


async def test_a_crashing_summarizer_does_not_break_the_run():
    """摘要器是给人看的辅助品,它自己炸了不能把生成搞挂(§14)。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search", query="x"), ChatMessage(content="好")])

    def boom(_args: dict[str, Any]) -> str:
        raise ValueError("摘要器写错了")

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search", summarize=boom)], on_step=steps.append,
    )

    assert any(s.tool == "search" for s in steps)


# ═══════════════════════════════════════════════════════════════
# 结束原因 + 工具真实返回值
# ═══════════════════════════════════════════════════════════════


async def test_the_loop_reports_why_it_stopped():
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("write_section")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("write_section", terminal=True)], on_step=steps.append,
    )

    assert steps[-1].kind == "stop"
    assert steps[-1].status == "terminal"


async def test_the_stop_event_is_the_last_thing_reported():
    """收尾事件之后不能再有事件 —— 否则前端画完了又被改一下。"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好了")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    assert _kinds(steps)[-1] == "stop"
    assert _kinds(steps).count("stop") == 1


async def test_the_tool_end_step_carries_the_real_result():
    """流水线靠这个读「这一节写了几页」。**不是给人看的,不要往 SSE 上放。**"""
    steps: list[AgentStep] = []
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好了")])

    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("search")], on_step=steps.append,
    )

    assert next(s for s in steps if s.kind == "tool_end").result == {
        "ok": True,
        "tool": "search",
    }


# ═══════════════════════════════════════════════════════════════
# 缺省路径:不传就不该有任何开销
# ═══════════════════════════════════════════════════════════════


async def test_narration_is_off_by_default():
    """不传 on_step 时一切照旧 —— 现有的 130 个测试一个都不该受影响。"""
    client = ScriptedChatClient([_call("search"), ChatMessage(content="好了")])

    result = await run_agent(
        client=client, model="m", system="s", user="u", tools=[_tool("search")]
    )

    assert result.stopped_by == "no_tool_calls"
