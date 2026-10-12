"""Agent 循环测试 —— 对应设计规格 §6.2,以及 AGENTS.md 的测试硬规则。

**断言的核心是工具调用序列,不是模型输出的文本。**

原因:文本每次都不一样,断言它等于没断言;
而「先读再改」「调了终止工具就停」这类行为是可复现的,
测试它们才真正守住逻辑。这也是为什么必须有可控的假模型。
"""

from __future__ import annotations

from typing import Any

from app.llm.client import ChatMessage, ScriptedChatClient, ToolCall
from app.services.agent import Tool, run_agent


def _tool(
    name: str,
    *,
    terminal: bool = False,
    crash: bool = False,
    sink: list[Any] | None = None,
) -> Tool:
    """造一个测试用工具,可选:终止 / 抛异常 / 记录调用。"""

    async def fn(args: dict[str, Any]) -> Any:
        if crash:
            raise RuntimeError("上游服务挂了")
        if sink is not None:
            sink.append((name, args))
        return {"ok": True, "tool": name}

    return Tool(
        name=name,
        description=f"{name} 工具",
        parameters={"type": "object", "properties": {}},
        fn=fn,
        terminal=terminal,
    )


def _call(name: str, cid: str = "c1", **args: Any) -> ChatMessage:
    """造一条「模型要求调工具」的回复。"""

    return ChatMessage(tool_calls=[ToolCall(id=cid, name=name, arguments=args)])


# ── 结束条件 ────────────────────────────────────────────────


async def test_terminal_tool_stops_the_loop():
    """终止工具被调用 → 立即结束,不再多问模型一轮。"""
    client = ScriptedChatClient([_call("write_section")])
    result = await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("write_section", terminal=True)],
    )
    assert result.stopped_by == "terminal"
    assert result.call_names == ["write_section"]
    # 只请求了一次 —— 没有多余的往返。这正是终止工具省 token 的地方。
    assert len(client.requests) == 1


async def test_loop_ends_when_model_stops_calling_tools():
    client = ScriptedChatClient([_call("search"), ChatMessage(content="写完了")])
    result = await run_agent(
        client=client, model="m", system="s", user="u", tools=[_tool("search")]
    )
    assert result.stopped_by == "no_tool_calls"
    assert result.content == "写完了"
    assert result.turns == 2


async def test_max_turns_is_enforced():
    """模型一直调工具停不下来 → 超限即停,并如实记录,不静默吞掉。"""
    script = [_call("search", cid=f"c{i}") for i in range(10)]
    result = await run_agent(
        client=ScriptedChatClient(script), model="m", system="s", user="u",
        tools=[_tool("search")], max_turns=3,
    )
    assert result.stopped_by == "max_turns"
    assert result.turns == 3
    assert len(result.calls) == 3


# ── 序列记录与顺序断言 ──────────────────────────────────────


async def test_tool_call_sequence_is_recorded_in_order():
    """先读再改 —— L2 编辑 Agent 最关键的一条不变式(§7.2)。"""
    script = [
        _call("read_slide", cid="c1", slide_id="s3"),
        _call("patch_slide", cid="c2", slide_id="s3"),
        _call("finish", cid="c3"),
    ]
    result = await run_agent(
        client=ScriptedChatClient(script), model="m", system="s", user="u",
        tools=[_tool("read_slide"), _tool("patch_slide"), _tool("finish", terminal=True)],
    )
    assert result.call_names == ["read_slide", "patch_slide", "finish"]
    assert result.index_of("read_slide") < result.index_of("patch_slide")


async def test_resources_reach_the_tool():
    """工具真的收到了模型传的参数,而且返回值被记了下来。"""
    sink: list[Any] = []
    client = ScriptedChatClient([_call("search", query="分支合并")])
    result = await run_agent(
        client=client, model="m", system="s", user="u", tools=[_tool("search", sink=sink)]
    )
    assert sink == [("search", {"query": "分支合并"})]
    assert result.calls[0].result == {"ok": True, "tool": "search"}


# ── 失败隔离(§14)────────────────────────────────────────────


async def test_unknown_tool_is_reported_back_not_crashed():
    """模型编了个不存在的工具 → 回喂错误让它自己改,循环不崩。"""
    client = ScriptedChatClient([_call("hack_the_planet"), ChatMessage(content="好的我换个方式")])
    result = await run_agent(
        client=client, model="m", system="s", user="u", tools=[_tool("search")]
    )
    assert result.calls[0].error and "未知工具" in result.calls[0].error
    assert result.stopped_by == "no_tool_calls"  # 循环继续了,没有抛异常


async def test_tool_exception_does_not_kill_the_pipeline():
    """单个工具失败不能让整条流水线挂掉。"""
    client = ScriptedChatClient([_call("boom"), ChatMessage(content="我换个方式")])
    result = await run_agent(
        client=client, model="m", system="s", user="u", tools=[_tool("boom", crash=True)]
    )
    assert "RuntimeError" in (result.calls[0].error or "")
    assert result.content == "我换个方式"


# ── 与模型的契约 ────────────────────────────────────────────


async def test_available_tools_are_sent_to_the_model():
    client = ScriptedChatClient([ChatMessage(content="完")])
    await run_agent(client=client, model="m", system="s", user="u", tools=[_tool("a"), _tool("b")])
    assert client.requests[0]["tool_names"] == ["a", "b"]


async def test_tool_results_are_appended_to_history():
    """执行结果必须以 role=tool 塞回消息,否则模型不知道结果。"""
    client = ScriptedChatClient([_call("search", cid="c9"), ChatMessage(content="够了我来写")])
    await run_agent(client=client, model="m", system="s", user="u", tools=[_tool("search")])
    last_request = client.requests[-1]["messages"]
    tool_msgs = [m for m in last_request if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert tool_msgs[0]["tool_call_id"] == "c9"


# ═══════════════════════════════════════════════════════════
# ★ DeepSeek 思考模式的硬性要求
# ═══════════════════════════════════════════════════════════


async def test_reasoning_content_is_echoed_back_to_the_api():
    """带 tools 的请求,后续每一轮都必须回传 reasoning_content。

    官方文档原文:「若您的代码中未正确回传 reasoning_content,
    API 会返回 400 报错。」

    而 DeepSeek **默认就开着思考模式** —— 所以这不是「可选优化」,
    漏了真模型第二轮直接报错。这个测试就是防这个回归。
    """
    from app.llm.client import ChatMessage, ScriptedChatClient, ToolCall

    client = ScriptedChatClient(
        [
            ChatMessage(
                content="",
                reasoning_content="我得先查一下讲义",
                tool_calls=[ToolCall(id="c1", name="lookup", arguments={})],
            ),
            ChatMessage(
                content="写好了",
                reasoning_content="资料够了,可以收尾",
                tool_calls=[ToolCall(id="c2", name="finish", arguments={})],
            ),
        ]
    )
    tools = [_tool("lookup"), _tool("finish", terminal=True)]

    await run_agent(client=client, model="m", system="s", user="u", tools=tools)

    # 第二轮请求里,历史中的 assistant 消息必须带上上一轮的思维链
    second = client.requests[1]["messages"]
    assistants = [m for m in second if m.get("role") == "assistant"]
    assert assistants, "历史里应该有 assistant 消息"
    assert assistants[0].get("reasoning_content") == "我得先查一下讲义"


async def test_missing_reasoning_content_does_not_add_an_empty_key():
    """非思考模式的模型不返回 reasoning_content —— 别塞个 None 进去。"""
    from app.llm.client import ChatMessage, ScriptedChatClient, ToolCall

    client = ScriptedChatClient(
        [
            ChatMessage(content="", tool_calls=[ToolCall(id="c1", name="finish", arguments={})]),
        ]
    )
    await run_agent(
        client=client, model="m", system="s", user="u",
        tools=[_tool("finish", terminal=True)],
    )

    first = client.requests[0]["messages"]
    assert all("reasoning_content" not in m for m in first)
