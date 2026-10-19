"""术语白话化与无障碍 —— 设计规格 §9.4。

═══════════════════════════════════════════════════════════════════
两件不同的事,所以是两个函数
═══════════════════════════════════════════════════════════════════
· `build_glossary`   —— 把课件里的专业词挑出来,每个配一句白话解释
· `describe_visuals` —— 给每张图配一段替代文本

合在一起做的话,schema 会长出一个「要么有 term 要么有 assetId」的形状,
而那正是模型最容易填错的结构。分开两次调用,每次只问一件事,
降级也可以各自发生 —— 术语解释失败不影响替代文本。

═══════════════════════════════════════════════════════════════════
§9.4 的两条硬要求,都体现在 prompt 里
═══════════════════════════════════════════════════════════════════
· 白话解释**不得引入新的未解释术语**(否则读的人还得再查一次)
· 替代文本要**描述这张图在讲什么,而不是罗列图中元素**

「元素清单」是最常见的错误做法:「一张图,左边一个圆,右边一个方框」——
读屏用户听完不知道这张图想说什么。这两条没法自动判定,
所以测试断言的是 **prompt 里写了这两条要求**,以及后续 schema 不许漂移。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.llm.client import ChatClient
from app.schemas.ir import GlossaryEntry, LearningObjective, Visual
from app.services.planner import extract_json

#: `GlossaryEntry` 的 JSON 形状。**必须和 IR 一一对应** ——
#: 少了字段模型就只能猜,而猜错要到装配时才炸。
GLOSSARY_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "term": {
            "type": "string",
            "description": "课件里出现的专业词,如「分支」「合并冲突」",
        },
        "plain": {
            "type": "string",
            "description": (
                "一句话白话解释。**不能用到别的专业术语** —— "
                "用一个读的人不认识的词去解释另一个词等于没解释"
            ),
        },
        "objectiveIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": "这个词跟哪个学习目标有关。只能用给定的目标 id,没有就留空数组",
        },
    },
    "required": ["term", "plain"],
}

#: 替代文本的 JSON 形状。
ALT_TEXT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assetId": {"type": "string", "description": "图上标的资产 id,原样返回"},
        "altText": {
            "type": "string",
            "description": (
                "一句话说明这张图在讲什么。**要讲清它的意思,不要罗列图中元素** —— "
                "「左边一个圆、右边一个方框」对读屏用户没有用"
            ),
        },
    },
    "required": ["assetId", "altText"],
}


GLOSSARY_SYSTEM_PROMPT = f"""你在替一份课程材料做术语表,让没背景的读者也能看懂。

只输出一个 JSON 对象,不要写解释、不要加前后缀:

{{"glossary": [ ...词条... ]}}

每个词条的字段定义:

{json.dumps(GLOSSARY_ENTRY_SCHEMA, ensure_ascii=False, indent=2)}

要求:

1. **只挑真正的专业词。**「分支」「合并冲突」要收;「代码」「文件」不用收。
2. **一句话解释完。**不要写成一段话 —— 读者是在阅读中间扫一眼。
3. **解释里不能出现别的没解释过的专业术语。**这是硬要求:
   用一个读的人不认识的词去解释另一个词,等于把他从一个坑推到另一个坑。
4. **用给定的语言书写。**
5. 最多 12 条,挑最影响理解的。"""


ALT_TEXT_SYSTEM_PROMPT = f"""你在为课程材料里的图写替代文本,给用读屏软件的人听。

只输出一个 JSON 对象,不要写解释、不要加前后缀:

{{"descriptions": [ ... ]}}

每一项的字段定义:

{json.dumps(ALT_TEXT_SCHEMA, ensure_ascii=False, indent=2)}

要求:

1. **说这张图要表达什么**,不是图里有什么。
   反例:「左边一个圆,右边一个方框,箭头从左指向右」
   正例:「改动在分支上进行,确认后再合回主干」
2. **一句话。**读屏用户要听完才能继续,别写太长。
3. 图里的文字可以读出来,但不要逐字念 —— 挑关键的那几个。
4. **用给定的语言书写。**"""


@dataclass
class GlossaryRequest:
    """术语表的输入。"""

    #: 课件正文(标题、要点、讲稿拼在一起)。模型从这里挑词。
    content: str
    objectives: list[LearningObjective] = field(default_factory=list)
    language: str = "zh-HK"


@dataclass
class GlossaryResult:
    """术语表的结果。**永远返回,永远不抛异常。**"""

    glossary: list[GlossaryEntry] = field(default_factory=list)
    used_fallback: bool = False
    reason: str = ""


@dataclass
class VisualRequest:
    """替代文本的输入。"""

    visuals: list[Visual]
    language: str = "zh-HK"


@dataclass
class AltTextResult:
    """替代文本的结果:assetId → 一段说明文字。"""

    alt_texts: dict[str, str] = field(default_factory=dict)
    used_fallback: bool = False
    reason: str = ""


def build_glossary_message(req: GlossaryRequest) -> str:
    """写给模型的用户消息。

    单独抽成函数是为了能被测试钉住 —— 这段文字是模型能看到的契约的一部分。
    「教材语言」那个开关曾经就是在这里断掉的。
    """
    lines = [
        f"**全部用 {req.language} 书写。**",
        "",
        "课件正文:",
        req.content.strip() or "(还没有内容)",
    ]
    if req.objectives:
        lines += ["", "这门课的学习目标:"]
        lines += [f"  {o.id}  {o.text}" for o in req.objectives]
    return "\n".join(lines)


def build_alt_text_message(req: VisualRequest) -> str:
    """写给模型的用户消息,列出每一处视觉需求。"""
    lines = [f"**全部用 {req.language} 书写。**", "", "需要描述的图:"]
    for visual in req.visuals:
        spec = visual.spec or {}
        detail = spec.get("code") or spec.get("prompt") or ""
        lines.append(f"  assetId={visual.asset_id}  kind={visual.kind}  内容:{detail}")
    return "\n".join(lines)


def _validate_glossary_entries(
    raw_entries: Any, known_objectives: set[str]
) -> tuple[list[GlossaryEntry], list[str]]:
    """逐条校验词条。**坏的那条丢掉,好的留下。**"""
    entries: list[GlossaryEntry] = []
    dropped: list[str] = []
    seen: set[str] = set()

    if not isinstance(raw_entries, list):
        return [], ["glossary 不是数组"]

    for index, raw in enumerate(raw_entries, start=1):
        if not isinstance(raw, dict):
            dropped.append(f"第 {index} 条不是对象")
            continue

        candidate = dict(raw)
        # 模型偶尔会编一个不存在的目标 id —— 留着会让覆盖率统计出错
        candidate["objectiveIds"] = [
            o
            for o in (candidate.get("objectiveIds") or [])
            if isinstance(o, str) and o in known_objectives
        ]

        try:
            entry = GlossaryEntry.model_validate(candidate)
        except Exception as exc:  # noqa: BLE001
            dropped.append(f"第 {index} 条结构不合法({type(exc).__name__})")
            continue

        if not entry.plain.strip():
            # 没有解释的词条等于没写 —— 留着只会在界面上占一行
            dropped.append(f"「{entry.term}」没有解释")
            continue

        key = entry.term.strip()
        if key in seen:
            # 同一个词解释两遍,界面上会出现两条一样的
            dropped.append(f"「{key}」重复")
            continue
        seen.add(key)
        entries.append(entry)

    return entries, dropped


async def build_glossary(
    req: GlossaryRequest, *, client: ChatClient, model: str, temperature: float = 0.4
) -> GlossaryResult:
    """挑专业词并配白话解释。**失败一律降级,不抛异常。**"""
    if not req.content.strip():
        return GlossaryResult(used_fallback=True, reason="没有内容可挑词")

    try:
        reply = await client.complete(
            model=model,
            messages=[
                {"role": "system", "content": GLOSSARY_SYSTEM_PROMPT},
                {"role": "user", "content": build_glossary_message(req)},
            ],
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        return GlossaryResult(
            used_fallback=True, reason=f"模型调用失败({type(exc).__name__}):{exc}"
        )

    data = extract_json(reply.content)
    if data is None:
        return GlossaryResult(used_fallback=True, reason="模型没有返回可解析的 JSON")

    known = {o.id for o in req.objectives}
    entries, dropped = _validate_glossary_entries(data.get("glossary"), known)

    if not entries:
        reason = "所有词条都不合规" if data.get("glossary") else "模型没有给出词条"
        if dropped:
            reason += ":" + ";".join(dropped)
        return GlossaryResult(used_fallback=True, reason=reason)

    return GlossaryResult(glossary=entries, reason=";".join(dropped))


async def describe_visuals(
    req: VisualRequest, *, client: ChatClient, model: str, temperature: float = 0.4
) -> AltTextResult:
    """给每张图写替代文本。**失败一律降级,不抛异常。**"""
    # 没有 assetId 的视觉需求是「还没渲染的图」,替代文本没地方挂
    describable = [v for v in req.visuals if v.asset_id]
    if not describable:
        return AltTextResult(used_fallback=True, reason="没有已渲染的图需要描述")

    try:
        reply = await client.complete(
            model=model,
            messages=[
                {"role": "system", "content": ALT_TEXT_SYSTEM_PROMPT},
                {"role": "user", "content": build_alt_text_message(VisualRequest(
                    visuals=describable, language=req.language
                ))},
            ],
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        return AltTextResult(
            used_fallback=True, reason=f"模型调用失败({type(exc).__name__}):{exc}"
        )

    data = extract_json(reply.content)
    if data is None:
        return AltTextResult(used_fallback=True, reason="模型没有返回可解析的 JSON")

    raw = data.get("descriptions")
    if not isinstance(raw, list):
        return AltTextResult(used_fallback=True, reason="descriptions 不是数组")

    known_ids = {v.asset_id for v in describable}
    alt_texts: dict[str, str] = {}
    dropped: list[str] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            dropped.append(f"第 {index} 条不是对象")
            continue
        asset_id = item.get("assetId")
        text = item.get("altText")
        if not isinstance(asset_id, str) or asset_id not in known_ids:
            # 编了一个不存在的 assetId —— 挂不上去,丢掉
            dropped.append(f"第 {index} 条的 assetId 对不上({asset_id!r})")
            continue
        if not isinstance(text, str) or not text.strip():
            dropped.append(f"{asset_id} 的说明是空的")
            continue
        alt_texts[asset_id] = text.strip()

    if not alt_texts:
        reason = "所有说明都不合规" if raw else "模型没有给出说明"
        if dropped:
            reason += ":" + ";".join(dropped)
        return AltTextResult(used_fallback=True, reason=reason)

    return AltTextResult(alt_texts=alt_texts, reason=";".join(dropped))
