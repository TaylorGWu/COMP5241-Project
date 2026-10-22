"""SectionAgent 的工具集 —— 设计规格 §6.2。

═══════════════════════════════════════════════════════════════════
两条设计原则
═══════════════════════════════════════════════════════════════════
1. **工具要少而正交。** 一个工具一个动作。工具一多,模型就会乱调、
   参数也会填错(设计规格 §14「工具膨胀」)。

2. **用依赖注入,不直接 import 具体服务。**
   `make_diagram` 不知道图是怎么渲染的,它只知道
   「给我 Mermaid 代码,还我一个 assetId」。
   好处:
     · 演示时传假实现 —— 不需要 Kroko、不需要 API key
     · 生产时传真实现
     · 测试时传记录调用的桩

   这就是「工具与实现解耦」的落点:agent 面向接口,不面向实现。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services.agent import Tool


@dataclass
class SectionDeps:
    """SectionAgent 跑起来需要的外部能力。每个字段都是一个可替换的实现。"""

    #: 检索教师上传的讲义,返回相关片段(含页码,用于溯源 —— §9.2)
    search_materials: Callable[[str], Awaitable[list[dict[str, Any]]]]
    #: Mermaid 代码 → assetId(§8.2:示意图走确定性渲染,不用生图模型)
    make_diagram: Callable[[str], Awaitable[str]]
    #: 生图 prompt → assetId(§8.2:这是兜底路径)
    request_illustration: Callable[[str], Awaitable[str]]

    # ── 产出暂存在这里,而不是直接写数据库 ──────────────────
    # 与 L2 编辑的「写操作只暂存、不落库」是同一个原则(§7.2)。
    # agent 没有直接写库的权限,产出的东西交给上层决定要不要采纳。
    written_slides: list[dict[str, Any]] = field(default_factory=list)
    written_plan: list[dict[str, Any]] = field(default_factory=list)

    #: 本节产生的资产。上层会把它们汇总进**项目级资产池**(§5.2),
    #: 这样课件、考题、视频可以复用同一张图,零重复成本。
    assets: list[dict[str, Any]] = field(default_factory=list)
    #: Invalid optional playback metadata is stripped without dropping courseware.
    animation_warnings: list[str] = field(default_factory=list)


#: `write_section` 的参数结构。
#:
#: 这份 schema 必须与 `app/schemas/ir.py` 的 `Slide` 保持一致(设计规格 §5.1)。
#: 写清楚它的意义:模型知道该产出什么形状的 dict,**才可能一次就过 IR 校验**。
#: 只写 "items": {"type": "object"} 的话,模型会自由发挥,然后校验失败。
#: 教案时间线条目的 schema。**字段必须和 `schemas.ir.TimelineEntry` 一一对应。**
#:
#: 这里踩过一个坑:原先只写了一个空壳 `{"type": "object"}`,
#: description 里写「字段见设计规格 §5.1」—— 但**模型看不到设计规格**,
#: 它只能看到这段 JSON schema,于是自己猜出了 `start` / `duration` 之类的字段,
#: 直到装配时才报 ValidationError。假模型「恰好」传对了,所以测试全绿。
#: `tests/test_tools.py` 里有一条测试专门盯着两边不能漂移。
PLAN_ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "本环节唯一 id,如 t1"},
        "phase": {
            "type": "string",
            "description": "环节名称,如「概念导入」「动手练习」「小结」",
        },
        "minutes": {
            "type": "integer",
            "description": "本环节时长(分钟),必须大于 0",
        },
        "teacherAction": {"type": "string", "description": "教师在这个环节做什么"},
        "studentAction": {"type": "string", "description": "学生在这个环节做什么"},
        "objectiveIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": "本环节对应的学习目标 id,如 [\"LO1\"]",
        },
        "slideIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": "本环节用到的幻灯片 id,如 [\"s1\", \"s2\"]",
        },
        "checkUnderstanding": {
            "type": "string",
            "description": "怎么确认学生听懂了 —— 写一个具体的提问或检查动作",
        },
    },
    "required": ["id", "phase", "minutes", "teacherAction"],
}


SLIDE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "本页唯一 id,如 s1"},
        "order": {"type": "integer", "description": "页码,从 1 开始"},
        "layout": {
            "type": "string",
            "enum": ["title", "bullets", "diagram", "twoCol", "code", "quiz"],
            "description": (
                "版面类型:title=封面或章节页,bullets=要点页,diagram=示意图页,"
                "twoCol=左右对比,code=代码页,quiz=随堂测验页"
            ),
        },
        "title": {
            "type": "string",
            "description": "本页标题。要具体到能看出讲什么,不要「第一部分」这种",
        },
        "bullets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "每页 3–5 个完整信息单元，一条一至两句，包含结论及依据、条件或具体例子。中文通常 25–60 字、英文 12–28 词，仅作可读性参考。案例应展示输入、推理、操作和结果；不可只列名词或同义句。",
        },
        "speakerNotes": {"type": "string", "description": "可实际授课的讲稿：引入问题、解释机制/推理、预期回答、纠错及过渡，不能复述要点。通常中文 120–220 字、英文 80–140 词。练习必须含正确答案、错误选项的误解及反馈；操作须说明前提、结果和验证方式。"},
        "visuals": {
            "type": "array",
            "description": (
                "本页需要的视觉元素。要配图的页必须在这里列出,"
                "并且先调 make_diagram 拿到 assetId 再填进来"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "本页内唯一 id,如 v1"},
                    "kind": {
                        "type": "string",
                        "enum": ["diagram", "chart", "icon", "illustration", "audio"],
                        "description": (
                            "视觉类型:diagram=关系或流程示意图(走 Mermaid),"
                            "chart=数据图表,icon=图标,illustration=插画,audio=音频"
                        ),
                    },
                    "spec": {
                        "type": "object",
                        "description": (
                            "生成参数。diagram 放 Mermaid 源码(以 graph / flowchart 开头);"
                            "illustration 放画面描述。"
                            "**Mermaid 代码里的换行要写成 \\n 两个字符**,"
                            "不能是真正的换行符,否则整个参数不是合法 JSON"
                        ),
                    },
                    "assetId": {
                        "type": "string",
                        "description": "make_diagram / request_illustration 返回的 id",
                    },
                },
                "required": ["id", "kind"],
            },
        },
        "objectiveIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": "本页对应的学习目标 id",
        },
        "sourceRefs": {
            "type": "array",
            "description": (
                "本页内容来自哪几处讲义。origin=sourced 时不能为空;"
                "自己补充的内容就不要编来源"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "materialId": {
                        "type": "string",
                        "description": "来源材料的文件名,要和 search_materials 返回的一致",
                    },
                    "page": {
                        "type": "integer",
                        "description": "来源页码,从 1 开始;没有页码就不填这个字段",
                    },
                },
                "required": ["materialId"],
            },
        },
        "origin": {
            "type": "string",
            "enum": ["sourced", "ai"],
            "description": (
                "有讲义出处填 sourced,并且 sourceRefs 不能为空;"
                "自己补充的内容填 ai。不要声称有来源却给不出。"
            ),
        },
        "teachingRole": {
            "type": "string",
            "enum": [
                "explain",
                "worked_example",
                "guided_practice",
                "check_understanding",
                "transfer",
                "recap",
            ],
            "description": (
                "本页唯一教学动作：讲解、具体案例、引导练习、理解检查、迁移或小结。"
                "不要为凑页数重复同一种动作。"
            ),
        },
        "visualPurpose": {
            "type": "string",
            "enum": [
                "comparison",
                "sequence",
                "mechanism",
                "scenario",
                "evidence",
                "none",
            ],
            "description": (
                "视觉服务的理解目的。sequence/mechanism 才适合 Mermaid；"
                "comparison/scenario/evidence/none 不要硬画流程图，none 是合法选择。"
            ),
        },
        "animation": {
            "type": "object",
            "description": (
                "可选的教师预览动画，仅编排既有内容，不得新增教学内容。"
                "target 只能是 title、bullet:0 等已有 bullet，或 visual:已有视觉 id；"
                "sequence 只能用于 visual。"
            ),
            "properties": {
                "autoplay": {"type": "boolean", "description": "默认 true"},
                "steps": {
                    "type": "array",
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "enum": ["reveal", "emphasis", "sequence"]},
                            "target": {"type": "string"},
                            "atMs": {"type": "integer", "minimum": 0, "maximum": 20000},
                            "durationMs": {"type": "integer", "minimum": 100, "maximum": 3000},
                        },
                        "required": ["kind", "target", "atMs"],
                    },
                },
            },
            "required": ["steps"],
        },
    },
    "required": [
        "id",
        "order",
        "layout",
        "title",
        "teachingRole",
        "visualPurpose",
    ],
}


#: 摘要的长度上限。摘要会进 SSE 事件、进浏览器,而且是每轮都发 ——
#: 不能让 `write_section` 的整页内容或 `make_diagram` 的整段源码漏进去。
_SUMMARY_LIMIT = 60


def _text(args: dict[str, Any], key: str) -> str:
    """取一个字符串参数。类型不对就当没有 —— 模型填错类型是常事。"""
    value = args.get(key)
    return value.strip() if isinstance(value, str) else ""


def _count(args: dict[str, Any], key: str) -> int:
    """数一个数组参数的长度。不是数组就返回 0。"""
    value = args.get(key)
    return len(value) if isinstance(value, list) else 0


def _clip(text: str) -> str:
    return text[:_SUMMARY_LIMIT]


# ── 摘要器:把参数压成界面上给教师看的一行(§6.1.2)──────────
#
# 为什么放在这里而不是 agent.py:agent 层是通用的,它不该知道有哪些工具。
# 只有定义工具的地方才知道 `{"query": ...}` 里哪个字段是重点。


def _summarize_search(args: dict[str, Any]) -> str:
    return f"检索「{_text(args, 'query')}」"


def _summarize_diagram(args: dict[str, Any]) -> str:
    """**故意不回显 Mermaid 源码** —— 它可能几百字符,而且教师也读不懂。"""
    return "画示意图(Mermaid)"


def _summarize_illustration(args: dict[str, Any]) -> str:
    prompt = _text(args, "prompt")
    return f"请求插画:{_clip(prompt)}" if prompt else "请求插画"


def _summarize_plan_entry(args: dict[str, Any]) -> str:
    entry = args.get("entry")
    phase = entry.get("phase") if isinstance(entry, dict) else None
    return f"教案环节「{phase}」" if isinstance(phase, str) else "写教案环节"


def _summarize_write_section(args: dict[str, Any]) -> str:
    """「提交 3 页课件」—— **页数是教师最关心的那个数字**。"""
    return f"提交 {_count(args, 'slides')} 页课件"


def _summarize_read_slide(args: dict[str, Any]) -> str:
    return f"读取 {_text(args, 'slide_id')}"


def _summarize_read_question(args: dict[str, Any]) -> str:
    return f"读取题目 {_text(args, 'question_id')}"


def _summarize_patch_slide(args: dict[str, Any]) -> str:
    """**故意不回显 patch 内容** —— 那可能是整段讲稿。"""
    slide_id = _text(args, "slide_id")
    return f"提议修改 {slide_id}" if slide_id else "提议修改某页"


def _summarize_patch_question(args: dict[str, Any]) -> str:
    question_id = _text(args, "question_id")
    return f"提议修改题目 {question_id}" if question_id else "提议修改题目"


def _summarize_patch_paper(_args: dict[str, Any]) -> str:
    return "提议修改试卷"


def _summarize_patch_plan(args: dict[str, Any]) -> str:
    reason = _text(args, "reason")
    return f"提议修改教案:{_clip(reason)}" if reason else "提议修改教案"


def _summarize_regenerate(args: dict[str, Any]) -> str:
    return f"请求重生成 {_text(args, 'slide_id')}"


def _summarize_timing(_args: dict[str, Any]) -> str:
    return "检查教案时长"


def _summarize_coverage(_args: dict[str, Any]) -> str:
    return "检查学习目标覆盖"


def build_section_tools(deps: SectionDeps, *, include_search: bool = True) -> list[Tool]:
    """组装 SectionAgent 工具；没有真实讲义时不向模型暴露检索。"""


    async def search_materials(args: dict[str, Any]) -> Any:
        """检索讲义。返回带页码的片段,便于模型标注来源。"""

        chunks = await deps.search_materials(args["query"])
        # 返回页码,让模型有能力标注来源(§9.2 内容溯源)
        return {"chunks": chunks, "count": len(chunks)}


    async def make_diagram(args: dict[str, Any]) -> Any:
        """登记 Mermaid 源码；预览与导出时由 CLI 渲染同一份 IR。"""

        code = args["mermaid"].replace("\\n", "\n")
        asset_id = await deps.make_diagram(code)
        deps.assets.append(
            {
                "id": asset_id,
                "kind": "diagram",
                "status": "ready",
                "provider": "mermaid-cli",
                "spec": {"engine": "mermaid", "code": code},
            }
        )
        return {"asset_id": asset_id}


    async def request_illustration(args: dict[str, Any]) -> Any:
        """请求无文字插画(兜底路径),并登记资产。"""

        asset_id = await deps.request_illustration(args["prompt"])
        deps.assets.append(
            {
                "id": asset_id,
                "kind": "illustration",
                "status": "ready",
                "provider": "flux-1-schnell",
                "spec": {"prompt": args["prompt"]},
            }
        )
        return {
            "asset_id": asset_id,
            "note": "这是兜底路径。优先考虑图标库 / 插画库 / 图表库(§8.2)",
        }


    async def write_plan_entry(args: dict[str, Any]) -> Any:
        """写入教案的一个环节。产出进 written_plan,由流水线装配。"""

        deps.written_plan.append(args["entry"])
        return {"ok": True, "plan_entries": len(deps.written_plan)}


    async def write_section(args: dict[str, Any]) -> Any:
        """终止工具。调用它 = 本节写完了,循环立即结束。"""
        deps.written_slides.extend(args["slides"])
        return {"ok": True, "slides": len(args["slides"])}

    tools = [
        Tool(
            name="search_materials",
            description=(
                "检索教师上传的讲义,返回相关片段。"
                "每个片段带页码,便于在幻灯片里标注来源。"
                "一次检索不够时可以再调一次,换关键词。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词"}
                },
                "required": ["query"],
            },
            fn=search_materials,
            summarize=_summarize_search,
        ),
        Tool(
            name="make_diagram",
            description=(
                "把 Mermaid 代码渲染成示意图,返回 assetId。"
                "凡是有文字标注的图(流程图、结构图、关系图)都必须走这个工具,"
                "不要用生图模型 —— 扩散模型画中文会乱码。"
                "每张图只表达一个教学关系:最多 6 个节点,每个节点不超过 12 个汉字或 6 个英文词;"
                "流程用 graph LR/TD,对比用左右两组节点,层级用 graph TD。"
                "节点必须写当前页的真实角色、对象或动作，边必须写关系；禁止 Step 1/2、"
                "概念图、应用、开始/结束等占位标签。"
                "不要把讲稿、完整句子、项目符号或多段解释塞进节点。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "mermaid": {
                        "type": "string",
                        "description": "紧凑 Mermaid 源码; 3–6 个短标签节点,例如 graph LR; A[创建分支] --> B[独立修改] --> C[合并审阅]",
                    }
                },
                "required": ["mermaid"],
            },
            fn=make_diagram,
            summarize=_summarize_diagram,
        ),
        Tool(
            name="request_illustration",
            description=(
                "请求一张无文字的概念插画,返回 assetId。"
                "这是兜底路径:先用图标库和插画库,只有它们表达不出来时才用。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "画面描述,不含文字"}
                },
                "required": ["prompt"],
            },
            fn=request_illustration,
            summarize=_summarize_illustration,
        ),
        Tool(
            name="write_plan_entry",
            description="写入教案的一个教学环节(时间线条目)。",
            parameters={
                "type": "object",
                "properties": {
                    "entry": {
                        "type": "object",
                        "description": "一个教学环节",
                        **PLAN_ENTRY_SCHEMA,
                    }
                },
                "required": ["entry"],
            },
            fn=write_plan_entry,
            summarize=_summarize_plan_entry,
        ),
        Tool(
            name="write_section",
            description=(
                "提交本节幻灯片。**这是本节的最后一步** —— "
                "调用它之后本次生成立即结束,不会再有下一轮。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "slides": {
                        "type": "array",
                        "description": "本节的幻灯片数组",
                        "items": SLIDE_SCHEMA,
                    }
                },
                "required": ["slides"],
            },
            fn=write_section,
            summarize=_summarize_write_section,
            terminal=True,  # ← 关键:调它即结束循环
        ),
    ]
    return tools if include_search else [tool for tool in tools if tool.name != "search_materials"]


class EditDepsProtocol(Protocol):
    """编辑工具依赖的四个方法。

    这是「工具」与「实现」之间的接缝:

        tools.py      只声明「我需要什么」(这个 Protocol)
        edit.py       提供「真的怎么做」(EditDeps)

    所以换实现(内存版 → 数据库版)既不用动工具,也不用动 agent。
    """


    async def read_slide(self, slide_id: str) -> dict[str, Any]:
        """读某一页的当前内容。模型改页面之前必须先调它。"""
        ...
    async def read_question(self, question_id: str) -> dict[str, Any]:
        """读一道题目的当前内容。"""
        ...
    async def read_paper(self) -> dict[str, Any]:
        """读当前试卷的结构与约束。"""
        ...
    async def propose_patch(self, kind: str, args: dict[str, Any]) -> str:
        """暂存一个改动(幻灯片或教案),返回 patch id。产物不会因此改变。"""
        ...
    async def estimate_timing(self) -> dict[str, Any]:
        """查教案总时长是否超课时。只读,不改任何东西。"""
        ...


    async def check_coverage(self) -> dict[str, Any]:
        """查学习目标覆盖情况。只读。"""
        ...


#: 只需要一个 slide_id 的工具
_SLIDE_ID_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "slide_id": {"type": "string", "description": "幻灯片 id,例如 s3"}
    },
    "required": ["slide_id"],
}

#: 提议改动的工具。**reason 是必填的** ——
#: 因为版本历史里必须留下「为什么这么改」,那是教师审查的依据,
#: 也是 AI Fluency「Diligence」的证据(§7.3)。
_PATCH_PARAMS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "patch": {
            "type": "object",
            "description": (
                "要修改的字段及其新值。字段名用 camelCase,"
                "例如 title / bullets / speakerNotes / layout / animation。"
                "animation 只能编排已存在的 title、bullet:索引或 visual:视觉 id。"
            ),
        },
        "reason": {
            "type": "string",
            "description": "为什么要这样改。会记入版本历史供教师审查,必须填写",
        },
    },
    "required": ["patch", "reason"],
}


def build_edit_tools(deps: EditDepsProtocol) -> list[Tool]:
    """L2 编辑 Agent 的工具集 —— 设计规格 §7.1。

    与 L1 的关键差别:**这里的写工具只暂存 patch,不落库。**
    调用 `patch_slide` 之后,产物内容一字未变;只有教师确认、
    上层调用 `apply_patch()` 之后才会真正写入(§7.2)。
    """

    async def read_slide(args: dict[str, Any]) -> Any:
        """读某一页的当前内容。模型改页面之前必须先调它。"""

        return await deps.read_slide(args["slide_id"])


    async def patch_slide(args: dict[str, Any]) -> Any:
        """暂存一个针对某页的改动。**不落库** —— 只写进 patch 暂存区。"""

        patch_id = await deps.propose_patch("slide", args)
        return {
            "patch_id": patch_id,
            "status": "proposed",
            "note": "改动已暂存,**尚未生效**;教师确认后才会写入",
        }

    async def read_question(args: dict[str, Any]) -> Any:
        return await deps.read_question(args["question_id"])

    async def patch_question(args: dict[str, Any]) -> Any:
        patch_id = await deps.propose_patch("question", args)
        return {"patch_id": patch_id, "status": "proposed", "note": "改动已暂存,尚未生效"}

    async def read_paper(_: dict[str, Any]) -> Any:
        return await deps.read_paper()

    async def patch_paper(args: dict[str, Any]) -> Any:
        patch_id = await deps.propose_patch("paper", args)
        return {"patch_id": patch_id, "status": "proposed", "note": "改动已暂存,尚未生效"}


    async def patch_plan(args: dict[str, Any]) -> Any:
        """暂存一个针对教案的改动。同样不落库。"""

        patch_id = await deps.propose_patch("plan", args)
        return {"patch_id": patch_id, "status": "proposed",
                "note": "改动已暂存,尚未生效"}


    async def regenerate_slide(args: dict[str, Any]) -> Any:
        """请求重生成某一页。也只是暂存一个请求。"""

        patch_id = await deps.propose_patch("regenerate_slide", args)
        return {"patch_id": patch_id, "status": "proposed",
                "note": "已提出重生成请求,尚未生效"}

    async def estimate_timing(_: dict[str, Any]) -> Any:
        """查教案总时长是否超课时。只读,不改任何东西。"""

        return await deps.estimate_timing()

    async def check_coverage(_: dict[str, Any]) -> Any:
        """查学习目标覆盖情况。只读。"""

        return await deps.check_coverage()

    return [
        Tool(
            name="read_slide",
            description="读取某一页幻灯片的当前内容。改任何一页之前都必须先读它。",
            parameters=_SLIDE_ID_PARAMS,
            fn=read_slide,
            summarize=_summarize_read_slide,
        ),
        Tool(
            name="patch_slide",
            description="提出对某一页的修改。改动会暂存待教师确认,**不会立刻生效**。",
            parameters={
                "type": "object",
                "properties": {
                    **_SLIDE_ID_PARAMS["properties"],
                    **_PATCH_PARAMS["properties"],
                },
                "required": ["slide_id", "patch", "reason"],
            },
            fn=patch_slide,
            summarize=_summarize_patch_slide,
        ),
        Tool(
            name="read_question",
            description="读取一道题目的当前内容。改题之前必须先读。",
            parameters={"type": "object", "properties": {"question_id": {"type": "string"}}, "required": ["question_id"]},
            fn=read_question,
            summarize=_summarize_read_question,
        ),
        Tool(
            name="patch_question",
            description="提出对一道题目的修改，等待教师确认后才生效。",
            parameters={"type": "object", "properties": {"question_id": {"type": "string"}, **_PATCH_PARAMS["properties"]}, "required": ["question_id", "patch", "reason"]},
            fn=patch_question,
            summarize=_summarize_patch_question,
        ),
        Tool(
            name="read_paper",
            description="读取当前试卷的结构与约束。改试卷之前必须先读。",
            parameters={"type": "object", "properties": {}},
            fn=read_paper,
            summarize=lambda _args: "读取试卷",
        ),
        Tool(
            name="patch_paper",
            description="提出对整份试卷的修改，等待教师确认后才生效。",
            parameters=_PATCH_PARAMS,
            fn=patch_paper,
            summarize=_summarize_patch_paper,
        ),
        Tool(
            name="patch_plan",
            description="提出对教案的修改。同样需要教师确认后才生效。",
            parameters=_PATCH_PARAMS,
            fn=patch_plan,
            summarize=_summarize_patch_plan,
        ),
        Tool(
            name="regenerate_slide",
            description="请求重新生成某一页(由外层重新调用生成流程)。",
            parameters=_SLIDE_ID_PARAMS,
            fn=regenerate_slide,
            summarize=_summarize_regenerate,
        ),
        Tool(
            name="estimate_timing",
            description="检查教案总时长是否超出设定课时。",
            parameters={"type": "object", "properties": {}},
            fn=estimate_timing,
            summarize=_summarize_timing,
        ),
        Tool(
            name="check_coverage",
            description="检查学习目标是否都被幻灯片覆盖,返回缺口。",
            parameters={"type": "object", "properties": {}},
            fn=check_coverage,
            summarize=_summarize_coverage,
        ),
    ]
