"""模型客户端 —— 所有 LLM 调用的最底层出口。

设计要点:

1. **上层只依赖 `ChatClient` 协议**,不关心背后是哪家模型。
   换模型只改 `ModelRouter` 配置(AGENTS.md 硬规则 2:禁止硬编码模型名)。

2. **`ScriptedChatClient` 让整条流水线在没有 API key 时也能跑通。**
   这既是演示手段,也是测试手段 —— 想断言「工具调用序列」,
   就必须有一个可控的模型输出,真模型做不到。

**这里没有流式。**模型层曾经有一条 `on_delta` + `stream=True` 的分支,
专为「把思维链逐字显示给教师看」而加;那个界面撤掉之后它就没有调用方了,
于是整条删掉(见 §11.7)。**进度上的实时感来自 SSE 传输层**
(`StreamingResponse` + `run_agent` 的 `on_step`),不依赖模型的流式输出。

**但 `reasoning_content` 一个字都不能少。**它和思考模式的开关是绑在一起的:
配置里 `deepseek_thinking` 默认关,可是把它打开只是改一行 YAML 的事,
而一旦开着思考模式,带 `tools` 的请求在后续每一轮都必须完整回传它,
否则 API 直接返回 400。所以字段留着、回传逻辑留着(见 agent.py)。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """模型要求调用某个工具。`id` 用来把执行结果对应回这次请求。"""

    id: str
    name: str
    arguments: dict[str, Any]
    #: 模型给的原始参数文本。解析失败时靠它把错误回喂,让模型自己改。
    raw_arguments: str = ""
    #: 解析失败的原因。**有值就说明这不是一次可用的调用。**
    parse_error: str | None = None


@dataclass
class ChatMessage:
    """模型的一次回复。可能带文字,也可能只带工具调用要求。"""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    #: 思考模式下的思维链。**带 tools 的请求必须原样回传它,否则 API 返回 400。**
    #: 详见 https://api-docs.deepseek.com/zh-cn/guides/thinking_mode
    reasoning_content: str | None = None
    #: "stop" 正常结束;"length" 说明**输出被截断了** —— 工具参数多半也是残的。
    finish_reason: str | None = None


class ChatClient(Protocol):
    """所有模型客户端的共同接口。agent 层只认这个。"""

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        """发一次对话补全请求,一次性拿到完整回复。"""
        ...


class ScriptedChatClient:
    """离线假模型:按预设脚本依次返回回复。

    两个用途:

    * **演示** —— 没有 API key 也能跑完整条流水线,看清每一步在干什么
    * **测试** —— 断言工具调用序列必须靠可控输出

    脚本用完后返回空回复,等价于「模型不再调工具」,循环自然结束。
    """

    def __init__(self, script: list[ChatMessage] | None = None) -> None:
        self._script: list[ChatMessage] = list(script or [])
        # 记录每次请求,便于测试断言「我们到底给模型发了什么」
        self.requests: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        """返回脚本里的下一条回复。"""

        # 存一份快照 —— 注意 messages 是可变列表,必须拷贝
        self.requests.append(
            {
                "model": model,
                "messages": [dict(m) for m in messages],
                "tool_names": [t["function"]["name"] for t in (tools or [])],
                "temperature": temperature,
            }
        )
        return self._script.pop(0) if self._script else ChatMessage(content="(脚本已耗尽)")


def build_deepseek_client() -> OpenAICompatClient:
    """按当前配置造一个 DeepSeek 客户端。**所有入口都应该用它。**

    为什么要有个工厂:思考模式开关是个容易漏的参数,而漏了的后果很隐蔽 ——
    服务端**默认开启**思考模式,于是:

        · `temperature` 被静默忽略,config/models.yaml 里配的温度全部失效
        · 输出 token 大幅增加(reasoning_content 也算输出)
        · 带 tools 时必须回传 reasoning_content,否则 400

    真模型第一次跑通时就踩过:`demo_deepseek.py` 漏传了这个参数,
    一直跑在思考模式下而没人发现。统一走这里就不会再漏。
    """
    from app.config import settings

    return OpenAICompatClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        thinking=settings.deepseek_thinking,
    )


def _build_tool_call(call_id: str, name: str, raw: str) -> ToolCall:
    """把「id + 工具名 + 原始参数文本」拼成一个 ToolCall。**解析失败不抛异常。**

    模型偶尔会产出不合法的参数 JSON。最常见的原因是**长文本里的换行没转义** ——
    比如 Mermaid 代码:

        {"spec": {"mermaid": "graph TD
          A --> B"}}}          ← 字符串里有真换行,不是合法 JSON

    在这里抛异常会让整次生成白跑,而且丢掉了一次让模型自我纠正的机会。
    所以:把原始文本和错误原因都带上,由 `run_agent` 回喂给模型重试。
    """
    try:
        arguments = json.loads(raw)
        parse_error = None
    except json.JSONDecodeError as exc:
        arguments = {}
        parse_error = f"参数不是合法 JSON:{exc.msg}(第 {exc.colno} 列)"
        if len(raw) > 2000:
            parse_error += ";参数很长,可能被输出长度截断"
    return ToolCall(
        id=call_id,
        name=name,
        arguments=arguments,
        raw_arguments=raw,
        parse_error=parse_error,
    )


def _parse_tool_call(tc: Any) -> ToolCall:
    """把 SDK 回来的 tool_call 转成我们的 ToolCall。"""
    return _build_tool_call(tc.id, tc.function.name, tc.function.arguments or "{}")


class OpenAICompatClient:
    """DeepSeek / 任何 OpenAI 兼容端点。

    **只有这个类真正发网络请求。** 上层完全不知道它的存在。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        *,
        thinking: bool | None = None,
        reasoning_effort: str = "high",
    ) -> None:
        """建客户端。

        `thinking` 三态:
            None  → 不发这个参数,用服务端默认(DeepSeek **默认开启**思考模式)
            False → 显式关闭。**这样 `temperature` 才会生效**
            True  → 显式开启,并按 `reasoning_effort` 控制强度
        """
        # 延迟导入:不用真模型时不强依赖 openai 包
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._thinking = thinking
        self._reasoning_effort = reasoning_effort
        # token 用量累计 —— NFR-10 要求成本可观测,而成本 = token × 单价
        self.usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
        }

    async def complete(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
    ) -> ChatMessage:
        """发一次对话补全请求,一次性拿到完整回复。"""

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        if self._thinking is not None:
            # 思考模式要放在 extra_body 里(OpenAI SDK 不认识这个字段)。
            # 注意:**思考模式下 temperature 不生效** —— 服务端不报错,但会忽略。
            kwargs["extra_body"] = {
                "thinking": {"type": "enabled" if self._thinking else "disabled"}
            }
            if self._thinking:
                kwargs["reasoning_effort"] = self._reasoning_effort

        resp = await self._client.chat.completions.create(**kwargs)

        self.usage["requests"] += 1
        if resp.usage is not None:
            self.usage["prompt_tokens"] += resp.usage.prompt_tokens or 0
            self.usage["completion_tokens"] += resp.usage.completion_tokens or 0
            self.usage["total_tokens"] += resp.usage.total_tokens or 0

        msg = resp.choices[0].message

        return ChatMessage(
            content=msg.content or "",
            # 必须抓下来。思考模式 + tools 时,不回传它下一轮会 400。
            # 配置里 thinking 默认关,但**这不是删掉它的理由** ——
            # 打开它只是改一行 YAML,而漏回传的后果是整次生成直接失败。
            reasoning_content=getattr(msg, "reasoning_content", None),
            finish_reason=resp.choices[0].finish_reason,
            tool_calls=[_parse_tool_call(tc) for tc in (msg.tool_calls or [])],
        )

    async def list_models(self) -> list[str]:
        """列出这个 key 能用的模型名。

        排查「模型名写错」时最有用 —— 比对着文档猜快得多。
        有些兼容端点不提供 /models,失败时返回空列表而不是抛异常。
        """
        try:
            resp = await self._client.models.list()
        except Exception:  # noqa: BLE001
            return []
        return sorted(m.id for m in resp.data)
