"""Agent 循环 —— 设计规格 §6.2(L1 SectionAgent)与 §7(L2 EditAgent)。

═══════════════════════════════════════════════════════════════════
为什么管道里还需要 agent?
═══════════════════════════════════════════════════════════════════
管道(见 pipeline.py)把流程写死了:摄取 → 规划 → 分节 → 资产 → 组装。

但「写一节内容」这一步没法再往下写死,因为模型运行时才需要决定:
    · 先检索讲义 —— 发现不够,再检索一次
    · 这页该配一张示意图
    · 写完之后检查学习目标覆盖了没有

这些决策提前猜不到。所以给它一组工具,让它自己决定调哪个、调几次。

═══════════════════════════════════════════════════════════════════
循环在干什么
═══════════════════════════════════════════════════════════════════
    1. 把「系统提示 + 用户需求 + 可用工具清单」发给模型
    2. 模型返回 tool_calls —— 它想调哪些函数、传什么参数
    3. **我们在本地执行这些函数**(模型不执行任何东西,它只是"说要做")
    4. 把执行结果塞回消息列表
    5. 回到第 1 步
    6. 结束:模型不再调工具 / 调用了终止工具 / 超出轮数上限

═══════════════════════════════════════════════════════════════════
三条必须守住的规则
═══════════════════════════════════════════════════════════════════
1. **终止工具**:`write_section` 被调用即结束。不能只靠"模型自己觉得写完了",
   否则它可能一直调工具停不下来 —— 那会烧光 token。
2. **轮数上限**:即使模型从不调用终止工具也有兜底,超限就停并如实记录。
3. **全程留痕**:每次工具调用都记进 `result.calls`。
   我们断言的是**工具调用序列**,不是模型输出的文本(AGENTS.md 硬规则)。
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.llm.client import ChatClient, ChatMessage


@dataclass
class Tool:
    """一个可以交给模型调用的函数。

    * `parameters` 是 JSON Schema —— 模型靠它知道该传什么参数
    * `terminal=True` 表示「调了它就结束循环」
    * `summarize` 把参数压成**给人看的一行**(见下面 `AgentStep` 的说明)
    """

    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[[dict[str, Any]], Awaitable[Any]]
    terminal: bool = False
    #: 参数 → 一行中文摘要。**由工具自己提供**,因为只有它知道自己的参数是什么意思。
    #: 不提供时退回到「第一个标量参数」这种通用摘要。
    summarize: Callable[[dict[str, Any]], str] | None = None

    def to_openai_schema(self) -> dict[str, Any]:
        """转成 OpenAI 兼容端点要的 tools 字段格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCallRecord:
    """一次工具调用的完整记录 —— 测试断言的粒度就是它。"""

    turn: int
    name: str
    arguments: dict[str, Any]
    result: Any = None
    error: str | None = None


@dataclass
class AgentStep:
    """agent 循环往外报的一步 —— 设计规格 §6.1.2 的「动作流」。

    ═══════════════════════════════════════════════════════════════
    为什么要有这个东西
    ═══════════════════════════════════════════════════════════════
    教师等生成要 30–120 秒。原来的进度只在**某一节整节跑完**时跳一格,
    一节内部二十秒完全静止 —— 界面上看不出是卡住了还是在干活。

    `AgentStep` 把「现在在第几轮、正在调哪个工具、刚才那个工具回了什么」
    实时吐出来。信息源全在本地,所以**不需要思考模式,也不需要真模型**。

    ═══════════════════════════════════════════════════════════════
    为什么需要 summarize
    ═══════════════════════════════════════════════════════════════
    `search_materials` 这种函数名对教师没有意义。摘要让这一行变成
    「检索「分支合并」」—— 这才是「看得懂的过程」。

    摘要**故意不在这里生成**:agent 层是通用的,它不该知道有哪些工具。
    所以摘要器挂在 `Tool` 上,由定义工具的地方(services/tools.py)提供。
    """

    turn: int
    #: turn(本轮开始) | tool_start | tool_end | stop
    kind: str
    tool: str | None = None
    #: tool_end 时是 "ok" / "error";stop 时是结束原因
    status: str = ""
    #: 给人看的一行。**措辞允许变化,不得被程序解析。**
    summary: str = ""
    #: 工具的真实返回值。**只在进程内传给流水线用,绝不要放到 SSE 上** ——
    #: `write_section` 的返回值里可能有整页内容。
    result: Any = None


def _generic_summary(args: dict[str, Any], *, limit: int = 80) -> str:
    """通用摘要:第一个标量参数,截断。

    比只显示函数名强,但比不上工具自己提供的摘要 —— 所以它只是兜底。
    """
    for key in sorted(args):
        value = args[key]
        if isinstance(value, str):
            text = value.strip()
        elif isinstance(value, bool):
            continue
        elif isinstance(value, (int, float)):
            text = str(value)
        else:
            continue
        if text:
            return text[:limit]
    return ""


def _safe_summary(tool: Tool | None, args: dict[str, Any]) -> str:
    """取摘要。**摘要器自己炸了不能把生成搞挂**(§14)。"""
    if tool is None or tool.summarize is None:
        return _generic_summary(args)
    try:
        return tool.summarize(args) or ""
    except Exception:  # noqa: BLE001
        # 摘要只是给人看的辅助品,不值得为它中断一次生成
        return _generic_summary(args)


@dataclass
class AgentResult:
    content: str = ""
    calls: list[ToolCallRecord] = field(default_factory=list)
    turns: int = 0
    stopped_by: str = ""  # terminal | no_tool_calls | max_turns

    @property
    def call_names(self) -> list[str]:
        """工具调用名字序列 —— 最常用的断言对象。"""
        return [c.name for c in self.calls]

    def called(self, name: str) -> bool:
        return name in self.call_names

    def index_of(self, name: str) -> int:
        """返回首次调用的下标;没调过返回 -1。

        用法:断言顺序,例如
            assert r.index_of("read_slide") < r.index_of("patch_slide")
        """
        return self.call_names.index(name) if self.called(name) else -1


async def run_agent(
    *,
    client: ChatClient,
    model: str,
    system: str,
    user: str | list[dict[str, Any]],
    tools: list[Tool],
    max_turns: int = 6,
    temperature: float = 0.0,
    on_step: Callable[[AgentStep], None] | None = None,
) -> AgentResult:
    """跑一次 agent 循环。

    参数都是关键字参数,避免调用方把 client 和 model 写反。

    `on_step` 是**可选**的观察者,不传就完全没有开销 ——
    现有调用方因此一个字都不用改(§6.1.2)。
    """
    by_name = {t.name: t for t in tools}
    schemas = [t.to_openai_schema() for t in tools]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    result = AgentResult()

    def report(**fields: Any) -> None:
        """往上报一步。没人听就什么都不做。"""
        if on_step is not None:
            on_step(AgentStep(**fields))

    def finish(reason: str) -> AgentResult:
        """收尾:记下原因,报一条 stop,返回。

        **每条退出路径都必须经过这里** —— 否则界面上最后一条会永远转圈,
        而「为什么停了」也没人知道。
        """
        result.stopped_by = reason
        report(turn=result.turns, kind="stop", status=reason)
        return result

    for turn in range(1, max_turns + 1):
        result.turns = turn
        # 「正在思考」这一段也要有事件:等模型回复是界面上最长的静止期
        report(turn=turn, kind="turn")

        reply: ChatMessage = await client.complete(
            model=model, messages=messages, tools=schemas, temperature=temperature
        )

        # ── 结束条件 1:模型不再要求调工具 ──────────────────────
        if not reply.tool_calls:
            result.content = reply.content
            return finish("no_tool_calls")

        # 把模型的回复(含它想调的工具)记进消息历史。
        # 不记的话,下一轮它不知道自己上一轮要求过什么。
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": reply.content or "",
            "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                for tc in reply.tool_calls
            ],
        }

        # ★ DeepSeek 思考模式 + tools:后续每一次请求都必须完整回传
        #   reasoning_content,**即使这一轮没有调工具**。漏了会直接 400。
        #   不带 tools 时传了会被忽略,所以一律带上更安全。
        if reply.reasoning_content:
            assistant_message["reasoning_content"] = reply.reasoning_content

        messages.append(assistant_message)

        for tc in reply.tool_calls:
            record = ToolCallRecord(turn=turn, name=tc.name, arguments=tc.arguments)
            tool = by_name.get(tc.name)

            # 每一条调用都先报 start。**无论后面走哪条分支** ——
            # 参数坏了、工具不存在、真执行失败,都要有配对的一条 end,
            # 否则界面上那一条会一直转圈。
            #
            # 摘要在这里算一次,**end 事件复用它**:成功时 end 的 summary 就是
            # 同一句人话。不这么做的话 end 只有工具名,消费方要自己记住
            # 「刚才那条 start 说的是什么」才能把两行配上对 —— 那是白给的复杂度。
            summary = _safe_summary(tool, tc.arguments)
            # status 必须在这里就填上。不填的话 `tool_start` 的 status 是空串,
            # 消费方只能靠「不是 ok/error 就是 running」去猜 ——
            # L2 的步骤列表就是这么被坑的:它按 "running" 配对 start/end,
            # 一条都配不上,两次工具调用显示成了四行。
            report(turn=turn, kind="tool_start", tool=tc.name,
                   status="running", summary=summary)

            # ── 参数 JSON 不合法:不执行,把错误回喂让它重来 ──────
            # 直接抛异常会让整次生成白跑。模型通常能自己改对,
            # 尤其是「字符串里有未转义的换行」这种。
            if tc.parse_error:
                record.error = tc.parse_error
                result.calls.append(record)
                report(turn=turn, kind="tool_end", tool=tc.name,
                       status="error", summary=tc.parse_error)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(
                            {
                                "error": tc.parse_error,
                                "hint": (
                                    "上一次工具调用的参数不是合法 JSON,请重新提交。"
                                    "注意:JSON 字符串里不能出现真正的换行符 —— "
                                    "Mermaid 代码的换行要写成 \\n 两个字符。"
                                ),
                                "your_raw_arguments": tc.raw_arguments[:300],
                            },
                            ensure_ascii=False,
                        ),
                    }
                )
                continue

            if tool is None:
                # 模型编了一个不存在的工具 → 把错误回喂给它,让它自己改正。
                # 直接抛异常会让整条流水线挂掉,而模型往往能自己补救。
                record.error = f"未知工具:{tc.name}"
                payload: Any = {"error": record.error, "available": sorted(by_name)}
            else:
                try:
                    payload = await tool.fn(tc.arguments)
                    record.result = payload
                except Exception as exc:  # noqa: BLE001
                    # 单个工具失败不能搞挂整条流水线(设计规格 §14:
                    # 「任何单个资产或章节失败,都不能让整包失败」)。
                    record.error = f"{type(exc).__name__}: {exc}"
                    payload = {"error": record.error}

            result.calls.append(record)
            report(
                turn=turn,
                kind="tool_end",
                tool=tc.name,
                status="error" if record.error else "ok",
                # 失败给真正的错误(教师能看懂是什么意思),成功复用 start 那句话
                summary=record.error or summary,
                # 真实返回值只给流水线用(它靠这个数「这一节写了几页」),
                # **不要序列化到 SSE 上**。
                result=payload if record.error is None else None,
            )

            # 把执行结果塞回去,格式为 role="tool" + 对应 id
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(payload, ensure_ascii=False, default=str),
                }
            )

            # ── 结束条件 2:调用了终止工具 ─────────────────────
            if tool is not None and tool.terminal:
                result.content = reply.content
                return finish("terminal")

        # 输出被截断时明确记一笔 —— 不然只会看到「参数不是合法 JSON」,
# 查不出真正的原因。
        if reply.finish_reason == "length":
            result.calls.append(
                ToolCallRecord(turn=turn, name="<truncated>", arguments={},
                               error="模型输出被长度限制截断")
            )

    # ── 结束条件 3:轮数用尽。停下来并如实记录,不静默吞掉 ──────
    return finish("max_turns")
