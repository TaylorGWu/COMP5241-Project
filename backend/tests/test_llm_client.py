"""模型客户端 —— 请求形状与参数解析。

═══════════════════════════════════════════════════════════════════
这个文件守的是什么
═══════════════════════════════════════════════════════════════════
`OpenAICompatClient` 是**唯一真正发网络请求**的类。它有两个地方很容易写错,
而错了之后症状都不指向真正的原因:

1. **思考开关必须显式发。**DeepSeek 服务端**默认开启**思考模式,而开着的时候:
     · `temperature` 被静默忽略 —— 配置里写的温度全部失效,且不报错
     · 输出 token 大幅增加(reasoning_content 也算输出)
   所以「不传这个参数」和「显式传 disabled」是两件完全不同的事。
   真模型第一次跑通时就踩过:漏传,一直跑在思考模式下而没人发现。

2. **工具调用的参数 JSON 不合法时不能抛异常。**模型偶尔会产出残的或转义错的
   参数(长 Mermaid 源码里的真换行最常见)。在这里抛异常会让整次生成白跑,
   而且丢掉一次让模型自我纠正的机会。要带上原始文本和原因,由 `run_agent`
   回喂给它(§14)。

═══════════════════════════════════════════════════════════════════
这里**不测流式** —— 因为模型层已经没有流式了
═══════════════════════════════════════════════════════════════════
曾经有一条 `on_delta` + `stream=True` 的分支,专为「把思维链逐字显示给教师」
而加。那个界面撤掉之后它就没有调用方了,于是整条删除(见设计规格 §11.7)。

**进度上的实时感不来自这里** —— 它来自 SSE 传输层
(`StreamingResponse` + `run_agent` 的 `on_step`),见 test_progress_stream.py。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.llm.client import ChatMessage, OpenAICompatClient

# ═══════════════════════════════════════════════════════════════
# 造假的响应对象。形状照着 OpenAI SDK 来。
# ═══════════════════════════════════════════════════════════════


def _full_tool_call(call_id: str, name: str, arguments: str) -> Any:
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=arguments))


def _response(
    *,
    content: str = "",
    reasoning: str | None = None,
    tool_calls: list[Any] | None = None,
    finish_reason: str = "stop",
    usage: Any = None,
) -> Any:
    message = SimpleNamespace(
        content=content, reasoning_content=reasoning, tool_calls=tool_calls or []
    )
    if usage is None:
        usage = SimpleNamespace(prompt_tokens=3, completion_tokens=5, total_tokens=8)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)],
        usage=usage,
    )


class _StubCompletions:
    """假的 `client.chat.completions`,同时记录我们到底发了什么。"""

    def __init__(self, response: Any, record: list[dict[str, Any]]) -> None:
        self._response = response
        self._record = record

    async def create(self, **kwargs: Any) -> Any:
        self._record.append(kwargs)
        return self._response


def _client(response: Any) -> tuple[OpenAICompatClient, list[dict[str, Any]]]:
    """造一个不联网的 OpenAICompatClient。"""
    record: list[dict[str, Any]] = []
    client = OpenAICompatClient(api_key="test-key", base_url="http://localhost:0", thinking=False)
    client._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=_StubCompletions(response, record))
    )
    return client, record


async def _complete(client: OpenAICompatClient, **kwargs: Any) -> ChatMessage:
    params: dict[str, Any] = {
        "model": "fake-model",
        "messages": [{"role": "user", "content": "说点什么"}],
    }
    params.update(kwargs)
    return await client.complete(**params)


# ═══════════════════════════════════════════════════════════════
# 请求形状
# ═══════════════════════════════════════════════════════════════


async def test_the_request_is_never_streamed():
    """模型层不走 `stream=True`。

    进度上的实时感来自 SSE 传输层,不是这里 —— 所以这个参数一旦出现,
    就说明有人把已经删掉的流式分支又加回来了。
    """
    client, record = _client(_response(content="你好"))

    await _complete(client)

    assert "stream" not in record[0]
    assert "stream_options" not in record[0]


async def test_thinking_off_is_sent_explicitly():
    """显式开启 / 关闭思考模式,不能什么都不发。

    「不发」= 用服务端默认 = **思考开启**,而开着的时候 temperature 会被静默忽略。
    这个区别很容易搞反,所以钉住它。
    """
    client, record = _client(_response(content="嗯"))

    await _complete(client)

    assert record[0]["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "reasoning_effort" not in record[0], "关着的时候不该带 effort"


async def test_thinking_on_sends_effort_too():
    record: list[dict[str, Any]] = []
    client = OpenAICompatClient(
        api_key="k", base_url="http://localhost:0", thinking=True, reasoning_effort="low"
    )
    client._client = SimpleNamespace(  # type: ignore[assignment]
        chat=SimpleNamespace(completions=_StubCompletions(_response(content="嗯"), record))
    )

    await _complete(client)

    assert record[0]["extra_body"] == {"thinking": {"type": "enabled"}}
    assert record[0]["reasoning_effort"] == "low"


async def test_tools_are_only_sent_when_there_are_some():
    client, record = _client(_response(content="嗯"))

    await _complete(client)
    assert "tools" not in record[0]

    await _complete(client, tools=[{"type": "function", "function": {"name": "x"}}])
    assert record[1]["tools"]


# ═══════════════════════════════════════════════════════════════
# 参数解析 —— 坏了也不能抛异常
# ═══════════════════════════════════════════════════════════════


async def test_tool_calls_are_parsed():
    client, _ = _client(
        _response(
            tool_calls=[_full_tool_call("c1", "write_section", '{"slides": [{"id": "s1"}]}')],
            finish_reason="tool_calls",
        )
    )

    msg = await _complete(client)

    assert [c.name for c in msg.tool_calls] == ["write_section"]
    assert msg.tool_calls[0].arguments == {"slides": [{"id": "s1"}]}
    assert msg.tool_calls[0].parse_error is None
    assert msg.finish_reason == "tool_calls"


async def test_broken_arguments_become_a_parse_error_not_an_exception():
    """**不能抛异常** —— 要留给 run_agent 回喂给模型让它自己重来(§14)。"""
    client, _ = _client(
        _response(tool_calls=[_full_tool_call("c1", "write_section", '{"slides": [')])
    )

    msg = await _complete(client)

    assert msg.tool_calls[0].parse_error is not None
    assert msg.tool_calls[0].arguments == {}
    # 原始文本要留着,回喂时模型需要看见自己写了什么
    assert msg.tool_calls[0].raw_arguments == '{"slides": ['


async def test_empty_arguments_are_treated_as_an_empty_object():
    """没有参数的工具(比如 check_coverage)不该被当成解析失败。"""
    client, _ = _client(_response(tool_calls=[_full_tool_call("c1", "check_coverage", "")]))

    msg = await _complete(client)

    assert msg.tool_calls[0].arguments == {}
    assert msg.tool_calls[0].parse_error is None


async def test_reasoning_content_is_captured():
    """思考模式下必须把它抓下来 —— agent 下一轮要原样回传,漏了直接 400。"""
    client, _ = _client(_response(reasoning="我得先查一下讲义", content="好了"))

    msg = await _complete(client)

    assert msg.reasoning_content == "我得先查一下讲义"


async def test_missing_reasoning_content_stays_none():
    """没开思考模式时上游不返回它 —— 要留 None,不要变成空字符串。"""
    client, _ = _client(_response(content="好了"))

    msg = await _complete(client)

    assert msg.reasoning_content is None


# ═══════════════════════════════════════════════════════════════
# 用量 —— NFR-10 要求成本可观测
# ═══════════════════════════════════════════════════════════════


async def test_usage_is_accumulated_across_calls():
    client, _ = _client(_response(content="嗯"))
    before = dict(client.usage)

    await _complete(client)
    await _complete(client)

    assert client.usage["requests"] == before["requests"] + 2
    assert client.usage["total_tokens"] == before["total_tokens"] + 16
    assert client.usage["prompt_tokens"] == before["prompt_tokens"] + 6
    assert client.usage["completion_tokens"] == before["completion_tokens"] + 10


async def test_a_response_without_usage_does_not_crash():
    """有些兼容端点不返回 usage。不能因此炸掉。"""
    client, _ = _client(SimpleNamespace(
        choices=[SimpleNamespace(
            message=SimpleNamespace(content="嗯", reasoning_content=None, tool_calls=[]),
            finish_reason="stop")],
        usage=None,
    ))

    msg = await _complete(client)

    assert msg.content == "嗯"
    assert client.usage["requests"] == 1
