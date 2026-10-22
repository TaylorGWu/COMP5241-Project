"""L1 生成流水线 —— 设计规格 §6.1。

═══════════════════════════════════════════════════════════════════
这一层在干什么
═══════════════════════════════════════════════════════════════════
把「一次课程生成」拆成 6 个阶段,**顺序写死**,并对外汇报进度。

═══════════════════════════════════════════════════════════════════
为什么顺序要写死
═══════════════════════════════════════════════════════════════════
这几步之间是确定的依赖关系:

    没有大纲 → 不知道要写几节
    没有节内容 → 不知道要配几张图
    没有资产 → 组装不出来

写死顺序让整件事**可预测、可测试、能算进度**。
(对比:如果交给模型自由编排,你没法告诉教师"现在到哪一步了"。)

═══════════════════════════════════════════════════════════════════
哪一步交给模型自由发挥
═══════════════════════════════════════════════════════════════════
只有第 3 阶段「分节生成」。那里每一节跑一次 agent(见 agent.py)。

    管道 = 外壳(顺序、进度、并发、错误隔离)
    agent = 内核(这一节内部怎么干,模型自己决定)

═══════════════════════════════════════════════════════════════════
并发与限流
═══════════════════════════════════════════════════════════════════
各节之间互不依赖 → 用 `asyncio.gather` 并发。
但同时打太多请求会被上游限流 → 用 `Semaphore(3)` 限制并发数。

串行跑 8 节要 8 倍时间;并发跑但要限流,这是两者的折中。

═══════════════════════════════════════════════════════════════════
进度怎么出去
═══════════════════════════════════════════════════════════════════
`on_event` 是一个回调。生产环境接 SSE(§13.2 的
`GET /api/generation/jobs/{id}/events`),演示时接 print。

**把「怎么算进度」和「怎么用进度」分开** —— 这样同一套逻辑既能推给前端,
也能打在终端上。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

from app.llm.client import ChatClient
from app.services.ingest import IngestDeps, IngestReport, ingest_file
from app.services.planner import Outline, PlannedSection, PlannerRequest, plan_outline
from app.schemas.ir import (
    Asset,
    CoursePackage,
    LearningObjective,
    LessonPlan,
    Project,
    ProjectMeta,
    Slide,
    SlideDeck,
    TimelineEntry,
)
from app.services.agent import AgentResult, AgentStep, ToolCallRecord, run_agent
from app.services.instructional_quality import (
    SectionQualityIssue,
    validate_section_quality,
)
from app.services.animation import normalize_slide_animation
from app.services.tools import SectionDeps, build_section_tools

# ────────────────────────────────────────────────────────────────
# 阶段定义:(阶段名, 起始进度%, 结束进度%)
# 这张表就是 §6.1 那张阶段表。改这里就等于改进度条。
# ────────────────────────────────────────────────────────────────
PHASES: list[tuple[str, int, int]] = [
    ("摄取材料", 0, 10),      # 解析上传文件、分块、向量化
    ("规划大纲", 10, 25),     # 出章节骨架 + 学习目标 + 时长
    ("分节生成", 25, 75),     # ← 唯一跑 agent 的阶段,最耗时
    ("判定视觉需求", 75, 85),  # 判断每处该用示意图还是插画(§8.2)
    ("生成资产", 85, 95),     # Mermaid 渲染 / 图标库 / 兜底生图
    ("组装与校验", 95, 100),   # 跑 §6.4 的交叉引用检查
]

#: SectionAgent 的系统提示。
#: 这段话决定了模型的行为边界 —— 它不是在"写作文",是在填结构化的 IR。
SECTION_SYSTEM_PROMPT = """你在为软件工程迷你课程撰写一节内容。

要求:
1. 先用 search_materials 查一下教师上传的讲义,基于材料写,不要凭空编。
2. 有文字标注的示意图必须用 make_diagram(传 Mermaid 代码),不要用生图。
3. 写完后调用 write_section 提交。这是本节的最后一步。
4. 如果某句话来自讲义,在 sourceRefs 里标注页码,并把 origin 设为 "sourced";
   如果是你自己补充的,origin 设为 "ai"。不要声称有来源却拿不出来。
5. **一节固定写 4 页**：explain → worked_example → check_understanding → transfer/recap。
   每页写 3–5 条彼此不同、能支持教师讲解或学生判断的要点；每条用一至两句表达
   一个完整信息单元，包含结论及其依据、条件或具体例子。中文通常 25–60 字，英文通常
   12–28 词；这是可读性参考，不要为凑字数删掉技术前提或添加废话。
   speakerNotes 应足以支持这一页的实际授课：写清如何引入、如何解释、预期学生回答
   以及如何追问或纠错。通常中文 120–220 字、英文 80–140 词，避免只复述 bullets。
   `write_section` 的参数是一次性提交的 JSON,内容太长会被截断导致提交失败。
6. 传 Mermaid 代码时,**字符串里的换行必须写成 \\n 两个字符**,
   不能出现真正的换行符 —— 否则 JSON 不合法,提交会失败。
7. **本节只调用一次 write_plan_entry**,写一条教案环节概括这一节怎么上。
   时长不用纠结 —— 系统会按大纲统一调整。
8. 每节必须包含至少一页**具体工程情境**或失败案例:交代角色、约束和后果,
   不能只写抽象定义。随后用图、代码或材料证据解释原因,让学生作出一个明确的**决策**或判断。
9. 每节必须有一页 layout="quiz" 的随堂**练习**。题干放在 title,选项或判断线索放在 bullets;
   speakerNotes 必须给出正确判断、一个常见错误思路及其**反馈**。这不是期末题,是检查理解。
10. 每页只承担一个教学动作:引出问题、解释证据、比较决策、指导操作或检查理解。
    不要用空泛总结、重复结论或超过 3 条的同义 bullet 凑页数。
11. 本节必须按 teachingArc 形成：explain → worked_example → guided_practice 或
    check_understanding → transfer 或 recap。案例页写出角色、约束、证据和后果；
    练习页写出学生可执行的判断/操作及讲稿反馈。
12. visualPurpose=sequence/mechanism 时才调用 make_diagram；
    comparison/scenario/evidence/none 不得为了配图调用流程图。
13. Mermaid 图不是装饰：节点必须是当前页的真实角色、对象或动作，边要写出
    关系（例如提交、查看、比较、确认）。禁止 Step 1/2、概念图、应用、开始/结束
    这类占位标签；若说不清一个具体关系，就不要调用 make_diagram。
    每节最多生成一张解释核心关系的图。拿到 asset_id 后写入 visual.assetId 即可，
    不要反复调用图示工具寻求更漂亮的图；图示失败只修正一次，仍失败改用文字/比较页。
    优先完成教案与 write_section 提交，不能耗尽轮数仍没有可读的教学内容。
14. `animation` 是可选的教师预览元数据，不会改变页面内容。仅在已有内容适合按步骤讲解时使用：
    target 只能是 title、bullet:0 这类已有 bullet，或 visual:已有视觉 id；
    kind 只能是 reveal/emphasis/sequence，且 sequence 只能指向 visual。不要为封面或 quiz 添加 animation。
15. 内容深度按教学动作区分：
    explain：解释概念是什么、解决什么问题、如何运作及一个适用边界；首次出现术语时解释。
    worked_example：沿用本节情境，给出具体输入/初始状态 → 判断依据 → 操作 → 可观察结果；
    不能只有角色、限制、后果的标签。关键推理必须在页面可见，补充解释放讲稿。
    check_understanding：让学生针对已教过的情境作出判断；干扰项对应真实误解、长度相近；
    正确选项不能总在 B，也不能靠措辞明显更完整来猜。讲稿解释正确与错误选项的依据。
    transfer/recap：改变案例的一个条件，让学生说明原来的做法是否仍适用及原因；
    不要只写“学以致用”“总结所学”或再次罗列名词。
16. 技术准确性优先：命令、代码、版本、前置条件和副作用须明确；给出操作后的验证方式。
    区分本地/远端、未提交/已提交、一般规则/例外，避免“永远”“一定”等无条件断言。
    不确定的数值、研究结论或 API 行为不编造；材料不足时说明假设，留给教师核对。
    操作链必须闭合：本地修改不等于远端已更新，保存不等于已发布；若结果涉及他人，
    不得遗漏同步/发布步骤。验证只声称能实际观察到的结果，不保证“不会冲突”或“必然成功”。
    对未提交、未跟踪、已提交的状态分别检查；不要声称一个命令会保护它并未覆盖的状态。
    表述“删除历史”时区分分支引用变化与对象物理消失。只有在前提明确且排除其他可行方案时，
    才把练习写成唯一正确答案；否则要求比较方案并说明取舍。
17. 标题表达本页要回答的问题或核心判断，避免“机制：”“案例：”后机械复用章节名。
    各页沿用一致的人物、文件、输入和术语，让练习承接案例；每页必须增加新的解释或决策。
18. 视觉必须提供可读的证据：图中对象和连线须对应本页机制，讲稿指出学生应看哪条关系、
    从图中推导什么判断。比较用并列条件与结果，操作示例给真实命令与结果；不强行画流程图。
19. 提交前自检：学习目标有可观察证据吗？案例推理可复现吗？练习信息充分且答案唯一吗？
    讲稿解释了为什么吗？是否遗漏前提、重复要点或编造来源？先修正，再调用 write_section。
"""

NO_MATERIAL_SECTION_SYSTEM_PROMPT = SECTION_SYSTEM_PROMPT.replace(
    "1. 先用 search_materials 查一下教师上传的讲义,基于材料写,不要凭空编。",
    "1. 教师没有上传材料。根据可靠的软件工程常识起草，不要编造讲义、页码或来源；所有页面使用 origin=\"ai\"、sourceRefs=[]。",
)

#: 每一节的 agent 轮数上限(§6.2)。
#:
#: 抽成常量是因为它有**两个**用处:传给 `run_agent`,以及给阶段 3 的
#: 进度插值当分母。写死两处的话,改了一个忘了另一个,
#: 进度条就会算出超过 100% 或者永远到不了头。
SECTION_MAX_TURNS = 6


@dataclass
class ProgressEvent:
    """一次进度汇报 —— 设计规格 §6.1.1 的事件契约。

    ═══════════════════════════════════════════════════════════════
    为什么 `detail` 之外还要这么多字段
    ═══════════════════════════════════════════════════════════════
    原实现把所有信息压进一个 `detail` 字符串,例如
    「2/3 节:合并与冲突(工具调用 4 次,terminal)」。前端想按节分组、
    想数「现在写到第几张」,就只能去正则拆这句话 ——
    中文措辞一改前端就静默失效,而且**没有任何测试会变红**。

    所以凡是 UI 要用来做判断的信息,都必须有自己的字段:

        section_index / section_title  → 界面按节分栏
        slide_count                    → 「已写 7 张」
        tool                           → 那一行前面挂哪个图标
        kind                           → 这条事件该渲染成什么

    `detail` 保留,但它**只给人看**:措辞允许变化,程序不得解析它。
    """

    phase: str
    percent: int
    #: 给人看的补充说明。**不得被程序解析。**
    detail: str = ""
    #: phase | section | turn | tool | slide | reasoning(见 §6.1.1)
    kind: str = "phase"
    #: 第几节(从 0 起)。用于界面按节分栏。
    section_index: int | None = None
    section_title: str | None = None
    #: **累计**已写出的幻灯片张数。
    slide_count: int = 0
    #: 本次触发的工具名。
    tool: str | None = None
    #: 细分状态。
    #:   kind=section → started | written | failed
    #:   kind=tool    → running | error
    #: **存在的理由**:界面要区分「这一节写完了」和「这一节失败了」。
    #: 如果只靠 `detail` 里的措辞去判断,那句话一改前端就静默失效 ——
    #: 而那正是这个字段存在的原因(§6.1.1)。
    status: str = ""

    def __str__(self) -> str:
        return f"[{self.percent:>3}%] {self.phase} — {self.detail}"

    def to_dict(self) -> dict[str, Any]:
        """转成 SSE 上发的形状(camelCase,与 §5.1 一致)。"""
        return {
            "phase": self.phase,
            "percent": self.percent,
            "detail": self.detail,
            "kind": self.kind,
            "sectionIndex": self.section_index,
            "sectionTitle": self.section_title,
            "slideCount": self.slide_count,
            "tool": self.tool,
            "status": self.status,
        }


@dataclass
class GenerationRequest:
    """教师填的那张生成表单。"""

    topic: str
    audience: str
    duration_min: int = 45
    language: str = "zh-HK"
    #: 学习目标。留空时(简单版)用默认的两条
    objectives: list[str] = field(default_factory=list)
    #: 上传的讲义路径。给了就走阶段 1 的真实摄取,并按 chunk 检索。
    material_paths: list[Path] = field(default_factory=list)


def section_user_prompt(
    index: int, section: "PlannedSection", req: "GenerationRequest",
    objectives: list[str] | None = None,
) -> str:
    """写给某一节的 user 消息。

    ═══════════════════════════════════════════════════════════════
    为什么单独抽成一个函数
    ═══════════════════════════════════════════════════════════════
    这段消息是**模型能看到的契约**的一部分。原来的版本只说了受众,
    没说语言 —— 于是 `language` 参数虽然被 API 和 PlannerRequest 接上了,
    真正写课件的 SectionAgent 却完全不知道要写哪种语言,内容语言
    实际由模型自己决定。「教材语言」这个开关是假的。

    抽出来是为了能被测试钉住:任何模型看得到的契约都必须有测试守着,
    否则它会在某次重构里被悄悄丢掉,而且不会有任何单元测试变红。
    """
    objective_texts = objectives if objectives is not None else req.objectives
    objective_map = {f"LO{i + 1}": text for i, text in enumerate(objective_texts)}
    assigned = [oid for oid in section.objective_ids if oid in objective_map]
    targets = assigned or list(objective_map)
    objective_brief = "；".join(f"{oid}: {objective_map[oid]}" for oid in targets)
    return (
        f"课程主题:{req.topic}。"
        f"写第 {index + 1} 节:{section.title}。"
        f"建议时长 {section.minutes} 分钟。"
        f"课程受众:{req.audience}。"
        f"**标题、要点、讲稿全部用 {req.language} 书写。**"
        f"本节学习目标（objectiveIds 只使用这里的 ID）：{objective_brief or '未指定；围绕本节主题设计可检查的学习结果'}。"
        "先确定学生在本节结束时能解释、比较或完成什么，再安排页面；"
        "页面中的例子、练习与教案的 checkUnderstanding 必须检验同一学习结果。"
        f"教学蓝图：情境={section.teaching_arc.situation}；"
        f"常见误解={section.teaching_arc.misconception}；"
        f"练习={section.teaching_arc.practice}；"
        f"迁移提问={section.teaching_arc.transfer_prompt}。"
    )


@dataclass
class PipelineDeps:
    """流水线需要的外部能力,全部可替换 —— 演示用假实现,生产传真实现。"""

    client: ChatClient
    model: str
    #: 下面三个会被原样透传给 SectionAgent 的工具
    search_materials: Callable[[str], Awaitable[list[dict[str, Any]]]]
    make_diagram: Callable[[str], Awaitable[str]]
    request_illustration: Callable[[str], Awaitable[str]]
    #: 同时跑几节。太大容易被上游限流,太小就慢。
    section_concurrency: int = 3
    #: 材料摄取的依赖(OCR 等)。没有它就只能用调用方传进来的 search_materials。
    ingest_deps: IngestDeps | None = None
    #: Live mode only offers source search when ingestion produced real materials.
    #: Offline scripted demos retain their historical fake-search sequence.
    only_search_uploaded_materials: bool = False


@dataclass
class PipelineResult:
    package: CoursePackage
    agents: list[AgentResult] = field(default_factory=list)
    events: list[ProgressEvent] = field(default_factory=list)
    #: 材料的摄取报告 —— 让上层能看到「哪份文件没读到字」
    materials: list[IngestReport] = field(default_factory=list)
    #: 阶段 2 的大纲。`used_fallback=True` 说明模型没给出可用的大纲。
    outline: Outline | None = None
    #: 装配时被跳过的内容及原因。**空列表才是正常的。**
    #: 非空说明模型产出的结构不合规 —— 要查,但它不该让整包失败。
    assembly_errors: list[str] = field(default_factory=list)

    @property
    def failed_materials(self) -> list[IngestReport]:
        return [m for m in self.materials if m.status == "failed"]

    @property
    def integrity_issues(self) -> list[str]:
        """§6.4 的交叉引用检查结果。空列表 = 通过。"""
        return self.package.validate_integrity()


async def generate_course(
    req: GenerationRequest,
    deps: PipelineDeps,
    on_event: Callable[[ProgressEvent], None] | None = None,
) -> PipelineResult:
    """跑完 6 个阶段,返回一个 CoursePackage。

    注意这里**没有 try/except 包住整条流程** —— 失败隔离在更细的粒度上:
      · 单个工具失败 → agent 内部捕获,回喂错误给模型(见 agent.py)
      · 单节失败 → 该节标为待生成,其余节照常(见下方 one_section)
    整条流程崩掉只会在真正不可恢复时发生(比如数据库挂了)。

    """
    events: list[ProgressEvent] = []
    #: 全课累计写出的幻灯片张数 —— 「现在写到第几张 ppt」的来源(§6.1.2)。
    slides_written = 0

    def emit(
        phase: str,
        percent: int,
        detail: str = "",
        *,
        kind: str = "phase",
        section_index: int | None = None,
        section_title: str | None = None,
        slide_count: int | None = None,
        tool: str | None = None,
        status: str = "",
    ) -> None:
        """汇报一次进度:先记下来(便于测试断言),再交给回调。"""
        ev = ProgressEvent(
            phase=phase,
            percent=percent,
            detail=detail,
            kind=kind,
            section_index=section_index,
            section_title=section_title,
            slide_count=slides_written if slide_count is None else slide_count,
            tool=tool,
            status=status,
        )
        events.append(ev)
        if on_event is not None:
            on_event(ev)

    # ══════════════════════════════════════════════════════════
    # 阶段 1:摄取材料
    # ══════════════════════════════════════════════════════════
    # 有材料就真跑摄取:探测格式 → 抽文字(扫描件转 OCR)→ 分块。
    # 抽出来的块直接用来做检索,替代假实现。
    materials: list[IngestReport] = []
    lo_i, hi_i = PHASES[0][1], PHASES[0][2]
    search = deps.search_materials          # 默认用调用方给的

    if req.material_paths and deps.ingest_deps is not None:
        total_files = len(req.material_paths)
        for i, path in enumerate(req.material_paths, start=1):
            report = await ingest_file(path, deps=deps.ingest_deps)
            materials.append(report)
            emit("摄取材料", lo_i + int((hi_i - lo_i) * i / total_files), report.summary())
        # 用真实的 chunk 替换假检索
        search = make_chunk_retriever(materials)
    else:
        emit("摄取材料", deps_percent(PHASES[0], 0.5), "未提供材料,跳过摄取")
        emit("摄取材料", PHASES[0][2], "完成")

    # ══════════════════════════════════════════════════════════
    # 阶段 2:规划大纲
    # ══════════════════════════════════════════════════════════
    # 简单版:章节写死。真实实现是让模型产出章节骨架(§4.2 ArtifactPlanner),
    # 并用 Pydantic 校验它的结构。
    # 让模型按主题/受众/课时产出骨架。**失败会自动退回默认骨架,不会中断流程。**
    emit("规划大纲", PHASES[1][1] + 5, "让模型产出章节骨架")
    outline = await plan_outline(
        PlannerRequest(
            topic=req.topic,
            audience=req.audience,
            duration_min=req.duration_min,
            requested_objectives=req.objectives,
            language=req.language,
        ),
        client=deps.client,
        model=deps.model,
    )
    objectives = [
        LearningObjective(id=f"LO{i + 1}", text=text)
        for i, text in enumerate(outline.objectives)
    ]
    emit(
        "规划大纲",
        PHASES[1][2],
        f"共 {len(outline.sections)} 节,{len(objectives)} 个学习目标"
        + ("  [兜底骨架]" if outline.used_fallback else "")
        + (f" — {outline.rationale}" if outline.rationale else ""),
    )

    # ══════════════════════════════════════════════════════════
    # 阶段 3:分节生成(并发,每节一个 agent)
    # ══════════════════════════════════════════════════════════
    sem = asyncio.Semaphore(deps.section_concurrency)
    total = len(outline.sections)
    finished = 0
    lo, hi = PHASES[2][1], PHASES[2][2]
    #: 各节目前做到哪一步(0.0–1.0)。**阶段 3 的进度由它求和得出。**
    progress: dict[int, float] = {}
    offer_material_search = bool(materials) or not deps.only_search_uploaded_materials

    def section_percent(index: int, fraction: float) -> int:
        """阶段 3 的进度插值。

        ═══════════════════════════════════════════════════════════
        为什么要这么算
        ═══════════════════════════════════════════════════════════
        原实现只在**某一节整节跑完**时进一格 —— 一节内部二十秒毫无反馈,
        界面上看不出是卡住了还是在干活。

        不能简单写成 `已完成节数 + 本节轮次占比`:三节并发时,
        第 1 节跑到第 5 轮会报 0.83,而刚起步的第 2 节会报 0.17 ——
        **后报的反而更小,进度条会倒退。**契约(§6.1.1)要求单调不减。

        改成按节各自记一份进度再求和:每个分量只增不减,
        所以总和只增不减,并发乱序上报也不会倒退。
        """
        progress[index] = max(progress.get(index, 0.0), min(max(fraction, 0.0), 1.0))
        if not total:
            return hi
        return lo + int((hi - lo) * (sum(progress.values()) / total))


    async def one_section(
        index: int, section: PlannedSection
    ) -> tuple[AgentResult, SectionDeps]:
        """生成一节。这一节内部完全由 agent 自主决定怎么干。"""
        nonlocal finished, slides_written

        async with sem:  # ← 限流:同时最多 deps.section_concurrency 节
            sdeps = SectionDeps(
                search_materials=search,
                make_diagram=deps.make_diagram,
                request_illustration=deps.request_illustration,
            )
            #: 本节**已经报过**几张。只报新增的,否则每轮都会把旧页重报一遍。
            reported_slides = 0

            def on_step(step: AgentStep) -> None:
                """把 agent 的一步翻译成一条进度事件 —— §6.1.2 的「动作流」。

                信息源全在本地,所以这条路不依赖思考模式,也不依赖真模型。
                """
                nonlocal reported_slides, slides_written

                fraction = step.turn / SECTION_MAX_TURNS
                percent = section_percent(index, fraction)
                where = {"section_index": index, "section_title": section.title}

                if step.kind == "turn":
                    # 「正在思考」—— 等模型回复是界面上最长的静止期
                    emit("分节生成", percent, f"第 {step.turn} 轮", kind="turn", **where)
                    return

                if step.kind != "tool_end":
                    if step.kind == "tool_start":
                        emit("分节生成", percent, step.summary, kind="tool",
                             tool=step.tool, status=step.status, **where)
                    return

                # ── tool_end ──────────────────────────────────────
                if step.tool == "write_section" and step.status == "ok":
                    # ★ 「现在写到第几张 ppt」的数据来源。
                    #   数的是**工具真的收下了几页**(写进 sdeps 的那批),
                    #   不是去解析参数 —— 参数里是整页内容,不该进事件。
                    fresh = sdeps.written_slides[reported_slides:]
                    reported_slides = len(sdeps.written_slides)
                    slides_written += len(fresh)
                    titles = [
                        str(s.get("title", "")).strip()
                        for s in fresh
                        if isinstance(s, dict)
                    ]
                    emit(
                        "分节生成",
                        percent,
                        f"「{section.title}」写了 {len(fresh)} 页:"
                        + " / ".join(t for t in titles if t),
                        kind="slide",
                        slide_count=slides_written,
                        **where,
                    )
                    return

                if step.status == "error":
                    emit("分节生成", percent, f"{step.tool} 出错:{step.summary}"[:160],
                         kind="tool", tool=step.tool, status="error", **where)

            emit("分节生成", section_percent(index, 0.0), f"开始写「{section.title}」",
                 kind="section", status="started",
                 section_index=index, section_title=section.title)

            try:
                result = await run_agent(
                    client=deps.client,
                    model=deps.model,
                    system=SECTION_SYSTEM_PROMPT if offer_material_search else NO_MATERIAL_SECTION_SYSTEM_PROMPT,
                    user=section_user_prompt(index, section, req, outline.objectives),
                    tools=build_section_tools(sdeps, include_search=offer_material_search),
                    max_turns=SECTION_MAX_TURNS,   # §6.2 的轮数上限
                    on_step=on_step,
                )
            except Exception as exc:  # noqa: BLE001
                # ★ §14:一节失败不能搞垮整包。
                # 真模型实测过两种:上游返回不合法 JSON(已单独处理),
                # 以及网络抖动 `APIConnectionError` —— 后者直接把整次生成打断,
                # 前面几节烧掉的 token 全白费。
                # 这里改成:记下失败原因,这一节没有产出,其余节照常。
                result = AgentResult(stopped_by="error", turns=0)
                result.content = f"{type(exc).__name__}: {exc}"
                result.calls.append(
                    ToolCallRecord(
                        turn=0,
                        name="<section_failed>",
                        arguments={"section": section.title},
                        error=result.content,
                    )
                )
                emit("分节生成", section_percent(index, 1.0),
                     f"「{section.title}」失败:{type(exc).__name__}",
                     kind="section", status="failed",
                     section_index=index, section_title=section.title)

            quality_issues: list[SectionQualityIssue] = []
            parsed_section_slides: list[Slide] = []
            normalized_slides: list[dict[str, Any]] = []
            for raw in sdeps.written_slides:
                normalized, animation_warning = normalize_slide_animation(raw)
                normalized_slides.append(normalized)
                if animation_warning:
                    sdeps.animation_warnings.append(animation_warning)
                    quality_issues.append(
                        SectionQualityIssue(
                            animation_warning,
                            "幻灯片动画计划无效，已保留静态课件供教师审核",
                        )
                    )
                try:
                    parsed_section_slides.append(Slide.model_validate(normalized))
                except Exception:  # noqa: BLE001
                    quality_issues.append(
                        SectionQualityIssue(
                            "invalid_slide_payload",
                            "本节含有无法读取的幻灯片结构",
                        )
                    )
            sdeps.written_slides[:] = normalized_slides
            if not quality_issues and parsed_section_slides:
                quality_issues = validate_section_quality(parsed_section_slides)

            quality_failed = bool(quality_issues)
            if quality_failed:
                codes = ",".join(issue.code for issue in quality_issues)
                # This is a *review warning*, not a destructive validation
                # gate.  A teacher must be able to see and revise an
                # imperfect draft; clearing every section that does not yet
                # meet the rubric can leave an otherwise successful chapter
                # with zero slides.  Keep the IR and audit trail intact, and
                # surface the exact warning in the completed-section event.
            else:
                codes = ""

            finished += 1
            # 这一节的进度封顶 —— 进度条按「各节进度之和」推进
            percent = section_percent(index, 1.0)
            emit(
                "分节生成",
                percent,
                f"{finished}/{total} 节:{section.title}"
                f"(工具调用 {len(result.calls)} 次,{result.stopped_by})"
                + (f" · needs review:{codes}" if quality_failed else ""),
                kind="section",
                status="written",
                section_index=index,
                section_title=section.title,
            )
            return result, sdeps

    pairs = await asyncio.gather(
        *(one_section(i, s) for i, s in enumerate(outline.sections))
    )
    agents = [r for r, _ in pairs]

    # 各节产出的资产汇总成**项目级资产池**,按 id 去重(§5.2 / §8.6)。
    # 提前算出来,阶段 4、5、6 都要用。
    assets_by_id: dict[str, Asset] = {}
    for _, sd in pairs:
        for raw in sd.assets:
            assets_by_id.setdefault(raw["id"], Asset.model_validate(raw))

    # ══════════════════════════════════════════════════════════
    # 阶段 4:判定视觉需求
    # ══════════════════════════════════════════════════════════
    # 简单版:认为所有带 visuals 的页都已经由 agent 调 make_diagram 处理过了。
    # 真实实现是 AssetResolver(§8.2):按决策树判断 diagram / chart /
    # icon / illustration,只有最后一种才可能走生图。
    emit("判定视觉需求", PHASES[3][1], "识别各页的视觉需求")
    # 注意 written_slides 里是 agent 传来的**原始 dict**,不是 Slide 对象,
    # 所以必须按 dict 取值,不能 getattr —— 否则恒为 0。
    visual_count = sum(
        len(s.get("visuals") or []) for _, sd in pairs for s in sd.written_slides
    )
    purpose_counts: dict[str, int] = {}
    for _, sd in pairs:
        for raw in sd.written_slides:
            try:
                purpose = Slide.model_validate(raw).visual_purpose
            except Exception:  # noqa: BLE001
                continue
            purpose_counts[purpose] = purpose_counts.get(purpose, 0) + 1
    purpose_labels = {
        "comparison": "对照",
        "sequence": "步骤",
        "mechanism": "机制",
        "scenario": "情境",
        "evidence": "证据",
        "none": "无额外视觉",
    }
    purpose_detail = "、".join(
        f"{purpose_labels[purpose]} {count}"
        for purpose, count in purpose_counts.items()
    )
    emit(
        "判定视觉需求",
        PHASES[3][2],
        f"{visual_count} 处视觉需求（资源）；教学用途：{purpose_detail}。流程图仅用于机制/步骤",
    )

    # ══════════════════════════════════════════════════════════
    # 阶段 5:生成资产
    # ══════════════════════════════════════════════════════════
    # 简单版:资产在 agent 调 make_diagram 时就已经产生了。
    # 真实实现会按 hash 去重并落对象存储(§8.6)。
    emit("生成资产", PHASES[4][1], "渲染 Mermaid 源码为 SVG")
    emit("生成资产", PHASES[4][2], f"{len(assets_by_id)} 个资产入池(按内容 hash 去重)")

    # ══════════════════════════════════════════════════════════
    # 阶段 6:组装与校验
    # ══════════════════════════════════════════════════════════
    emit("组装与校验", PHASES[5][1], "拼装 IR 并跑交叉引用检查")

    # 先组装全课幻灯片,并把模型常用的「本节 s1/s2/s3」局部 ID
    # 正规化为全课唯一、连续的 s1..sN。否则前端会出现重复 React key，
    # 教师在侧栏点击某一页或给某页提出 patch 时都会落到一组同名页上。
    # 映射按 section 保存,因为相同的局部 ID 在不同节本来就是不同页面。
    slides: list[Slide] = []
    section_slide_id_maps: list[dict[str, str]] = []
    dropped: list[str] = [
        f"幻灯片动画已忽略({warning})"
        for _, sd in pairs
        for warning in sd.animation_warnings
    ]
    next_slide_order = 1
    for _, sd in pairs:
        local_ids: dict[str, str] = {}
        for raw in sd.written_slides:
            try:
                candidate = Slide.model_validate(raw)
            except Exception as exc:  # noqa: BLE001
                dropped.append(f"幻灯片被跳过({type(exc).__name__})")
                continue

            original_id = candidate.id
            normalized_id = f"s{next_slide_order}"
            if not materials and candidate.origin == "sourced":
                # A fake retrieval snippet is not an uploaded source.
                candidate = candidate.model_copy(update={"origin": "ai", "source_refs": []})
            # 同一节里出现重复 ID 时,教案引用第一个有效页;每个输出页仍唯一。
            local_ids.setdefault(original_id, normalized_id)
            slides.append(candidate.model_copy(update={"id": normalized_id, "order": next_slide_order}))
            next_slide_order += 1
        section_slide_id_maps.append(local_ids)

    # 教案:把各节写的教学环节汇总成 LessonPlan。
    # 之前这里漏了 —— agent 写的 written_plan 被静默丢弃,教案永远是空的。
    # ══════════════════════════════════════════════════════════
    # 教案时长:以大纲为准,不采信各节 agent 自己猜的数
    # ══════════════════════════════════════════════════════════
    # 真模型实测:大纲规划 45 分钟,但各节 agent 并发跑、各自独立
    # 猜教案时长,加起来只有 32 分钟 —— 校验直接报
    # 「教案总时长 32 分钟与设定 45 分钟相差超过 10%」。
    #
    # 根因是职责没分清:**时长是课程的全局属性,大纲已经定好了**;
    # 每节 agent 负责的是「这一节讲什么、怎么讲」,不该由它决定时长。
    #
    # 做法:按节把该节写出的环节**按比例缩放到大纲给的时长**。
    # 保留了模型对环节之间相对轻重的判断,又保证总和正确。
    plan_entries: list[dict[str, Any]] = []
    for idx, (_, sd) in enumerate(pairs):
        if not sd.written_plan:
            continue

        planned_minutes = (
            outline.sections[idx].minutes
            if idx < len(outline.sections)
            else None
        )

        # 先逐条校验,再把这一节的时长归一化到大纲值
        valid: list[tuple[int, TimelineEntry]] = []
        slide_id_map = section_slide_id_maps[idx]
        for pos, entry in enumerate(sd.written_plan):
            try:
                parsed = TimelineEntry.model_validate(entry)
                valid.append((pos, parsed.model_copy(update={
                    "slide_ids": [slide_id_map.get(slide_id, slide_id) for slide_id in parsed.slide_ids]
                })))
            except Exception as exc:  # noqa: BLE001
                plan_entries.append({"__invalid__": f"{type(exc).__name__}"})

        if not valid:
            continue

        if planned_minutes is None:
            plan_entries.extend(t.model_dump(by_alias=True) for _, t in valid)
            continue

        # 注意变量名:不能叫 `total` —— 那会遮蔽上面阶段 3 用的节数 `total`,
        # 而 `section_percent` 是闭包,它读的就是那个变量。
        # 现在没有调用发生在之后,所以还看不出问题;但这是个纯粹的定时炸弹。
        entries_total = sum(t.minutes for _, t in valid) or len(valid)
        assigned = 0
        for i, (_, t) in enumerate(valid):
            if i == len(valid) - 1:
                minutes = planned_minutes - assigned      # 最后一条吃掉余数
            else:
                minutes = max(1, round(t.minutes * planned_minutes / entries_total))
                assigned += minutes
            plan_entries.append(
                t.model_copy(update={"minutes": max(1, minutes)}).model_dump(by_alias=True)
            )

    # 逐条校验而不是一把梭。
    # §14 要求「任何单个资产或章节失败,都不能让整包失败」——
    # 之前这里是 `[TimelineEntry.model_validate(e) for e in plan_entries]`,
    # 一条不合规就让整次生成白跑(真模型测出来的第一个问题)。
    # 现在:跳过坏的那条,把原因记下来给上层看,其余照常产出。
    timeline: list[TimelineEntry] = []
    for entry in plan_entries:
        if "__invalid__" in entry:
            dropped.append(f"教案环节被跳过({entry['__invalid__']})")
            continue
        try:
            timeline.append(TimelineEntry.model_validate(entry))
        except Exception as exc:  # noqa: BLE001
            dropped.append(f"教案环节被跳过({type(exc).__name__})")

    lesson_plan: LessonPlan | None = None
    if timeline:
        lesson_plan = LessonPlan(
            artifact_id="a-lesson",
            overview=f"{req.topic} 的教学设计,面向{req.audience}。",
            timeline=timeline,
        )
    elif plan_entries:
        dropped.append("教案环节全部不合规,教案为空")

    package = CoursePackage(
        project=Project(
            id="p-demo",
            meta=ProjectMeta(
                title=req.topic,
                audience=req.audience,
                duration_min=req.duration_min,
                language=req.language,
            ),
            learning_objectives=objectives,
        ),
        assets=list(assets_by_id.values()),
        lesson_plan=lesson_plan,
        slide_deck=SlideDeck(artifact_id="a-slides", slides=slides),
    )

    issues = package.validate_integrity()
    kinds = [k for k, v in (("课件", package.slide_deck),
                            ("教案", package.lesson_plan)) if v is not None]
    emit(
        "组装与校验",
        PHASES[5][2],
        f"产出 {'+'.join(kinds)};" + ("校验通过" if not issues else f"{len(issues)} 个问题:{issues[0]}"),
    )

    return PipelineResult(
        package=package, agents=agents, events=events,
        materials=materials, outline=outline, assembly_errors=dropped,
    )


def deps_percent(phase: tuple[str, int, int], ratio: float) -> int:
    """在一段进度区间内按比例取点。例:(0,10) 的 0.5 → 5。"""
    _, lo, hi = phase
    return lo + int((hi - lo) * ratio)


# ═══════════════════════════════════════════════════════════════
# 最简检索:按字符重叠打分
# ═══════════════════════════════════════════════════════════════


def make_chunk_retriever(reports: list[IngestReport]) -> Callable[[str], Awaitable[list[dict]]]:
    """用摄取出来的 chunk 做检索,替代假实现。

    这是**最简版**:中文不按空格分词,所以直接算字符重叠度。
    好处是零依赖、可预测;坏处是语义相近但用词不同就找不到。

    真实实现:chunk 入 `material_chunks` 表,用 BGE-M3 向量化,
    按 pgvector 相似度检索(§11.2)。接口一样,换掉即可。
    """
    pool: list[tuple[str, object]] = [
        (r.filename, c) for r in reports for c in r.chunks
    ]

    async def search(query: str) -> list[dict]:
        terms = set(query.strip())
        scored: list[tuple[int, str, object]] = []
        for filename, chunk in pool:
            score = len(terms & set(chunk.text))       # type: ignore[attr-defined]
            if score:
                scored.append((score, filename, chunk))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "materialId": filename,
                "page": chunk.page,                    # type: ignore[attr-defined]
                "text": chunk.text[:300],              # type: ignore[attr-defined]
            }
            for _, filename, chunk in scored[:4]
        ]

    return search
