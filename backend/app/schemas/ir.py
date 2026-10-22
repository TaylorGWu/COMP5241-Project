"""IR(中间表示)—— 对应设计规格 docs/design/course-generation-design.md §5.1。

硬规则(AGENTS.md 第 3 节):AI 只产出结构化 IR,不产出 HTML / pptx。
渲染器与导出器都是本数据结构的纯转换,内部不得调用模型 ——
这条保证教案与课件不会互相矛盾,也让导出可以单元测试。
"""

from __future__ import annotations

import re
from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

class _IRBase(BaseModel):
    """所有 IR 模型的基类。

    Python 代码里用 snake_case(符合 Python 习惯),
    但**序列化与解析用 camelCase** —— 也就是设计规格 §5.1 里那种写法
    (`objectiveIds` / `sourceRefs` / `speakerNotes`)。

    这样文档、数据库 JSONB、前端拿到的 JSON 三者形式统一,
    代码内部又不用迁就 JSON 的命名习惯。两边不会漂移。
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ═══════════════════════════════════════════════════════════════
# 项目级共享(§5.1)
# ═══════════════════════════════════════════════════════════════


class SourceRef(_IRBase):
    """指向上传讲义中的某个位置,用于内容溯源(§9.2)。"""

    material_id: str
    page: int | None = None


class LearningObjective(_IRBase):
    """一个学习目标。整份产物的一致性围绕它的 id 展开。"""

    id: str
    text: str


class GlossaryEntry(_IRBase):
    """术语的一句话白话解释(§9.4)。解释里不得再引入未解释的术语。"""

    term: str
    plain: str = Field(description="一句话白话解释,不得引入新的未解释术语(§9.4)")
    objective_ids: list[str] = Field(default_factory=list)


class ProjectMeta(_IRBase):
    """项目元信息:标题、受众、难度、课时、语言。"""

    title: str
    subject: str = "software-engineering"
    audience: str
    level: Literal["intro", "intermediate", "advanced"] = "intro"
    duration_min: int = Field(gt=0)
    language: str = "zh-HK"


class Project(_IRBase):
    """项目级共享内容。同一项目下的所有产物都引用它的学习目标。"""

    id: str
    meta: ProjectMeta
    learning_objectives: list[LearningObjective] = Field(default_factory=list)
    glossary: list[GlossaryEntry] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# 资产池(§5.2)—— 项目级共享,按 hash 去重
# ═══════════════════════════════════════════════════════════════

AssetKind = Literal["diagram", "chart", "icon", "illustration", "audio"]
AssetStatus = Literal["pending", "ready", "failed"]


class Asset(_IRBase):
    """一件资产(示意图/图表/图标/插画/音频)。项目级共享,按 hash 去重(§5.2)。"""

    id: str
    kind: AssetKind
    status: AssetStatus = "pending"
    url: str | None = None
    hash: str | None = None
    provider: str | None = None
    alt_text: str | None = Field(
        default=None, description="描述这张图在讲什么,而不是罗列图中元素(§9.4)"
    )
    spec: dict = Field(default_factory=dict)
    meta: dict = Field(default_factory=dict)


class Visual(_IRBase):
    """一处视觉需求。AssetResolver(§8.2)决定它的 kind 与 spec。"""

    id: str
    kind: AssetKind
    spec: dict = Field(default_factory=dict, description="engine+code,或生图 prompt")
    asset_id: str | None = None


# ═══════════════════════════════════════════════════════════════
# 教案(§5.1)
# ═══════════════════════════════════════════════════════════════


class TimelineEntry(_IRBase):
    """教案时间线上的一个教学环节。通过 slideIds 引用课件页。"""

    id: str
    phase: str
    minutes: int = Field(gt=0)
    teacher_action: str
    student_action: str = ""
    objective_ids: list[str] = Field(default_factory=list)
    slide_ids: list[str] = Field(default_factory=list)
    check_understanding: str = ""


class DiscussionQuestion(_IRBase):
    """教案里的一个提问设计:问什么、为什么问、期望答案。"""

    text: str
    intent: str = ""
    expected_answer: str = ""


class Differentiation(_IRBase):
    """同一节课的入门版与进阶版差异(§9.4 / FR-17)。"""

    beginner: str = ""
    advanced: str = ""


class LessonPlan(_IRBase):
    """教案:教学环节、时间分配、提问设计、板书、作业、差异化。"""

    artifact_id: str
    type: Literal["lessonPlan"] = "lessonPlan"
    overview: str = ""
    key_points: list[str] = Field(default_factory=list)
    difficult_points: list[str] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    questions: list[DiscussionQuestion] = Field(default_factory=list)
    board_plan: list[str] = Field(default_factory=list)
    homework: list[str] = Field(default_factory=list)
    differentiation: Differentiation = Field(default_factory=Differentiation)
    source_refs: list[SourceRef] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# 课件(§5.1)
# ═══════════════════════════════════════════════════════════════

SlideLayout = Literal["title", "bullets", "diagram", "twoCol", "code", "quiz"]
Origin = Literal["sourced", "ai"]
TeachingRole = Literal[
    "explain",
    "worked_example",
    "guided_practice",
    "check_understanding",
    "transfer",
    "recap",
]
VisualPurpose = Literal[
    "comparison",
    "sequence",
    "mechanism",
    "scenario",
    "evidence",
    "none",
]
AnimationKind = Literal["reveal", "emphasis", "sequence"]


class AnimationStep(_IRBase):
    """One deterministic playback instruction for an existing slide region."""

    kind: AnimationKind
    target: str
    at_ms: int = Field(ge=0, le=20_000)
    duration_ms: int = Field(default=700, ge=100, le=3_000)


class SlideAnimation(_IRBase):
    """Optional teacher-preview playback metadata; it never changes slide content."""

    autoplay: bool = True
    steps: list[AnimationStep] = Field(min_length=1, max_length=8)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_steps(cls, value: Any) -> Any:
        """Accept the short-lived pre-IR animation shape stored in old patches.

        Early animation proposals used ``action`` (including ``emphasize``) and
        omitted timing.  Keep those teacher-review records usable by converting
        them at the IR boundary; new output still serializes only the canonical
        ``kind`` / ``atMs`` fields.
        """
        if not isinstance(value, dict) or not isinstance(value.get("steps"), list):
            return value

        migrated = dict(value)
        steps: list[Any] = []
        for index, raw_step in enumerate(value["steps"]):
            if not isinstance(raw_step, dict):
                steps.append(raw_step)
                continue

            step = dict(raw_step)
            legacy_action = step.pop("action", None)
            if "kind" not in step and isinstance(legacy_action, str):
                step["kind"] = "emphasis" if legacy_action == "emphasize" else legacy_action
            if "atMs" not in step and "at_ms" not in step:
                step["atMs"] = index * 700
            steps.append(step)

        migrated["steps"] = steps
        return migrated


_BULLET_TARGET_RE = re.compile(r"^bullet:(\d+)$")


def slide_animation_validation_error(slide: "Slide", animation: SlideAnimation) -> str | None:
    """Return a stable warning code when animation points outside the slide IR."""

    seen_targets: set[str] = set()
    visual_ids = {visual.id for visual in slide.visuals}
    for step in animation.steps:
        if step.target in seen_targets:
            return "animation_duplicate_target"
        seen_targets.add(step.target)

        if step.target == "title":
            if step.kind == "sequence":
                return "animation_invalid_sequence"
            continue

        bullet_match = _BULLET_TARGET_RE.match(step.target)
        if bullet_match:
            if int(bullet_match.group(1)) >= len(slide.bullets):
                return "animation_unknown_target"
            if step.kind == "sequence":
                return "animation_invalid_sequence"
            continue

        if step.target.startswith("visual:"):
            if step.target.removeprefix("visual:") not in visual_ids:
                return "animation_unknown_target"
            continue

        return "animation_unknown_target"
    return None


class Slide(_IRBase):
    """课件的一页。origin 用来区分「有讲义出处」和「AI 补充」(§9.2)。"""

    id: str
    order: int
    layout: SlideLayout
    title: str
    bullets: list[str] = Field(default_factory=list)
    speaker_notes: str = Field(default="", description="讲稿,同时用作视频旁白来源(§12.3)")
    visuals: list[Visual] = Field(default_factory=list)
    objective_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    origin: Origin = "ai"
    #: Why the slide exists in the teaching sequence. Defaults preserve old drafts.
    teaching_role: TeachingRole = "explain"
    #: What visual form, if any, makes the teaching action easier to understand.
    visual_purpose: VisualPurpose = "none"
    #: Optional deterministic preview metadata. Renderers may ignore it safely.
    animation: SlideAnimation | None = None

    @model_validator(mode="after")
    def _sourced_needs_refs(self) -> "Slide":
        """§6.4:不能声称有来源却拿不出来。"""
        if self.origin == "sourced" and not self.source_refs:
            raise ValueError("origin=sourced 的幻灯片必须有非空 sourceRefs")
        if self.animation:
            error = slide_animation_validation_error(self, self.animation)
            if error:
                raise ValueError(error)
        return self


class SlideDeck(_IRBase):
    """课件:一组有序的幻灯片。"""

    artifact_id: str
    type: Literal["slideDeck"] = "slideDeck"
    slides: list[Slide] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# 考题与模拟卷(§5.1)
# ═══════════════════════════════════════════════════════════════

QuestionType = Literal["mcq", "short", "code", "scenario"]


class Option(_IRBase):
    """选择题的一个选项。"""

    id: str
    text: str


class Question(_IRBase):
    """一道题。answer 必须经跨厂商验证后才可信(§11.3)。"""

    id: str
    type: QuestionType
    stem: str
    options: list[Option] = Field(default_factory=list)
    answer: str = Field(default="", description="须经跨厂商验证后才可信(§11.3)")
    explanation: str = ""
    difficulty: int = Field(default=1, ge=1, le=5)
    objective_ids: list[str] = Field(default_factory=list)
    points: int = Field(default=0, ge=0)
    visuals: list[Visual] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)


class QuestionSet(_IRBase):
    """题库:按知识点组织的题目集合。"""

    artifact_id: str
    type: Literal["questionSet"] = "questionSet"
    questions: list[Question] = Field(default_factory=list)


class PaperDifficulty(_IRBase):
    """模拟卷的难度分布(三档占比)。"""

    easy: float = 0.0
    medium: float = 0.0
    hard: float = 0.0


class ExamConstraints(_IRBase):
    """组卷约束:总分、时长、必须覆盖的知识点、难度分布。"""

    total_points: int = Field(gt=0)
    duration_min: int = Field(gt=0)
    coverage: list[str] = Field(default_factory=list)
    difficulty: PaperDifficulty = Field(default_factory=PaperDifficulty)


class PaperSection(_IRBase):
    """模拟卷的一个大题。"""

    title: str
    rule: str = ""
    question_ids: list[str] = Field(default_factory=list)


class ExamPaper(_IRBase):
    """模拟卷:在约束下从题库选出的有序试卷(含答案卷)。"""

    artifact_id: str
    type: Literal["examPaper"] = "examPaper"
    constraints: ExamConstraints
    sections: list[PaperSection] = Field(default_factory=list)
    answer_key: bool = True
    source_refs: list[SourceRef] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# 补救包(§9.1)—— 由错题统计触发
# ═══════════════════════════════════════════════════════════════


class RemediationTrigger(_IRBase):
    """补救包的触发条件:哪个目标、哪道题、错误率多少(§9.1)。"""

    objective_id: str
    question_id: str
    wrong_rate: float = Field(ge=0.0, le=1.0)


class RemediationKit(_IRBase):
    """补救包:归因假设 + 讲解 + 示意图 + 检查题(§9.1)。"""

    artifact_id: str
    type: Literal["remediationKit"] = "remediationKit"
    trigger: RemediationTrigger
    hypothesis: str = Field(description="归因假设 —— 必须与 summary 分开呈现,它是推测不是结论")
    summary: str
    visuals: list[Visual] = Field(default_factory=list)
    check_question: Question | None = None


# ═══════════════════════════════════════════════════════════════
# 视频(§12.3)
# ═══════════════════════════════════════════════════════════════


class Scene(_IRBase):
    """视频的一个场景。通过 slideRef 引用课件页,不复制内容(§12.3)。"""

    id: str
    slide_ref: str = Field(description="引用课件页,不复制内容 —— 改课件则视频跟着变")
    narration: str
    duration_sec: float = 0.0
    asset_ids: list[str] = Field(default_factory=list)


class Voice(_IRBase):
    """旁白音色配置。"""

    provider: str = "edge"
    voice_id: str = "zh-CN-XiaoxiaoNeural"
    speed: float = 1.0


class VideoScript(_IRBase):
    """视频脚本:逐页旁白 + 时间轴 + 音色(§12.3)。"""

    artifact_id: str
    type: Literal["videoScript"] = "videoScript"
    scenes: list[Scene] = Field(default_factory=list)
    voice: Voice = Field(default_factory=Voice)
    total_duration_sec: float = 0.0


ArtifactDoc = Union[
    LessonPlan, SlideDeck, QuestionSet, ExamPaper, RemediationKit, VideoScript
]


# ═══════════════════════════════════════════════════════════════
# 组合与交叉引用校验(§6.4)
# ═══════════════════════════════════════════════════════════════


class CoursePackage(_IRBase):
    """一个项目下的全部产物 + 资产池。

    这是 AI 的唯一输出契约,也是渲染器与导出器的唯一输入。
    """

    project: Project
    assets: list[Asset] = Field(default_factory=list)
    lesson_plan: LessonPlan | None = None
    slide_deck: SlideDeck | None = None
    question_set: QuestionSet | None = None
    exam_paper: ExamPaper | None = None
    remediation_kit: RemediationKit | None = None
    video_script: VideoScript | None = None

    def _all_visuals(self) -> list[Visual]:
        out: list[Visual] = []
        if self.slide_deck:
            out += [v for s in self.slide_deck.slides for v in s.visuals]
        if self.question_set:
            out += [v for q in self.question_set.questions for v in q.visuals]
        if self.remediation_kit:
            out += self.remediation_kit.visuals
            if self.remediation_kit.check_question:
                out += self.remediation_kit.check_question.visuals
        return out

    def validate_integrity(self) -> list[str]:
        """规格 §6.4 的交叉引用完整性检查。

        返回问题列表;**空列表表示通过**。校验失败时应保存部分草稿并报错,
        而不是整包丢弃(§6.4)。
        """
        issues: list[str] = []

        obj_ids = {o.id for o in self.project.learning_objectives}
        asset_ids = {a.id for a in self.assets}
        slides = self.slide_deck.slides if self.slide_deck else []
        slide_ids = {s.id for s in slides}

        # 1. 每个学习目标至少被一页幻灯片引用 —— 目标不能没被覆盖
        used = {oid for s in slides for oid in s.objective_ids}
        for oid in sorted(obj_ids - used):
            issues.append(f"学习目标 {oid} 未被任何幻灯片覆盖")

        # 2. 教案引用的幻灯片必须存在
        if self.lesson_plan:
            for entry in self.lesson_plan.timeline:
                for sid in entry.slide_ids:
                    if sid not in slide_ids:
                        issues.append(f"教案环节 {entry.id} 引用了不存在的幻灯片 {sid}")

        # 3. 教案总时长 ≈ 设定时长(±10%)
        if self.lesson_plan and self.lesson_plan.timeline:
            total = sum(e.minutes for e in self.lesson_plan.timeline)
            limit = self.project.meta.duration_min
            if abs(total - limit) > limit * 0.10:
                issues.append(f"教案总时长 {total} 分钟与设定 {limit} 分钟相差超过 10%")

        # 4. 视觉需求指向的资产必须存在
        for v in self._all_visuals():
            if v.asset_id and v.asset_id not in asset_ids:
                issues.append(f"视觉需求 {v.id} 指向不存在的资产 {v.asset_id}")

        # 5-7. 模拟卷:题目存在、总分、知识点覆盖
        if self.exam_paper:
            bank = {q.id: q for q in (self.question_set.questions if self.question_set else [])}
            picked = [qid for sec in self.exam_paper.sections for qid in sec.question_ids]

            for qid in picked:
                if qid not in bank:
                    issues.append(f"模拟卷引用了题库中不存在的题目 {qid}")

            actual = sum(bank[qid].points for qid in picked if qid in bank)
            want = self.exam_paper.constraints.total_points
            if actual != want:
                issues.append(f"模拟卷实际总分 {actual} 与设定 {want} 不符")

            covered = {oid for qid in picked if qid in bank for oid in bank[qid].objective_ids}
            for oid in self.exam_paper.constraints.coverage:
                if oid not in covered:
                    issues.append(f"模拟卷未覆盖知识点 {oid}")

        return issues
