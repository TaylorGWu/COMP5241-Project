"""Deterministic quality rules for generated teaching sections.

The section agent may choose words and examples, but a course only becomes a
teacher-reviewable draft when the required learning loop is present.  Keeping
these rules pure makes them usable by the live pipeline, demo data and tests
without adding another model call.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import unicodedata

from app.schemas.ir import Slide


@dataclass(frozen=True)
class SectionQualityIssue:
    """A stable, UI-safe reason why one section should be regenerated."""

    code: str
    message: str


@dataclass(frozen=True)
class VisualPolicy:
    """The deterministic rendering treatment for one declared visual purpose."""

    render_treatment: Literal["diagram", "comparison", "case", "evidence", "none"]
    requires_diagram: bool


_VISUAL_POLICIES: dict[str, VisualPolicy] = {
    "sequence": VisualPolicy("diagram", True),
    "mechanism": VisualPolicy("diagram", True),
    "comparison": VisualPolicy("comparison", False),
    "scenario": VisualPolicy("case", False),
    "evidence": VisualPolicy("evidence", False),
    "none": VisualPolicy("none", False),
}

_PRACTICE_ROLES = {"guided_practice", "check_understanding"}
_TRANSFER_ROLES = {"transfer", "recap"}
_ANSWER_WORDS = ("正确答案", "正確答案", "答案", "correct answer")
_MISCONCEPTION_WORDS = ("常见错误", "常見錯誤", "误区", "誤區", "误解", "誤解", "misconception")
_FEEDBACK_WORDS = ("反馈", "反饋", "回饋", "追问", "追問", "feedback", "follow-up")
_EXAMPLE_MARKERS = (
    ("角色", "人物", "学生", "同学", "初始状态", "初始狀態", "developer", "team", "initial state"),
    ("约束", "約束", "限制", "期限", "constraint", "deadline"),
    ("证据", "證據", "資料", "测试", "測試", "evidence", "test"),
    ("后果", "後果", "结果", "結果", "影响", "影響", "consequence"),
)


def visual_policy(slide: Slide) -> VisualPolicy:
    """Return a visual treatment without talking to an asset generator."""

    return _VISUAL_POLICIES[slide.visual_purpose]


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    text_lower = text.lower()
    return any(word.lower() in text_lower for word in words)


def _has_complete_example(slide: Slide) -> bool:
    text = "\n".join((slide.title, *slide.bullets, slide.speaker_notes))
    return all(_contains_any(text, markers) for markers in _EXAMPLE_MARKERS)


def _has_feedback(notes: str) -> bool:
    return (
        _contains_any(notes, _ANSWER_WORDS)
        and _contains_any(notes, _MISCONCEPTION_WORDS)
        and _contains_any(notes, _FEEDBACK_WORDS)
    )


def validate_section_quality(slides: list[Slide]) -> list[SectionQualityIssue]:
    """Return all deterministic issues for a section; never raise for content."""

    roles = {slide.teaching_role for slide in slides}
    issues: list[SectionQualityIssue] = []
    if "explain" not in roles:
        issues.append(SectionQualityIssue("missing_explain", "缺少概念讲解页"))
    if "worked_example" not in roles:
        issues.append(SectionQualityIssue("missing_worked_example", "缺少具体工程案例"))
    if not roles & _PRACTICE_ROLES:
        issues.append(SectionQualityIssue("missing_practice", "缺少可检查练习"))
    if not roles & _TRANSFER_ROLES:
        issues.append(
            SectionQualityIssue("missing_transfer_or_recap", "缺少迁移或小结")
        )

    for slide in slides:
        # Only flag exact repetition after typography normalization. Semantic
        # similarity requires teacher judgment; shared technical terms are fine.
        points = [
            "".join(char for char in unicodedata.normalize("NFKC", point).casefold() if char.isalnum())
            for point in slide.bullets
        ]
        nonempty_points = [point for point in points if point]
        if len(set(nonempty_points)) < len(nonempty_points):
            issues.append(
                SectionQualityIssue(
                    "duplicate_slide_points",
                    "本页含重复要点，应补充不同的判断依据、条件或例子",
                )
            )
        if len(slide.bullets) < 3:
            issues.append(
                SectionQualityIssue(
                    "thin_slide_content",
                    "每页至少需要三条可用于讲解或判断的要点",
                )
            )
        if slide.teaching_role == "worked_example" and not _has_complete_example(slide):
            issues.append(
                SectionQualityIssue(
                    "generic_worked_example",
                    "案例页需要交代角色、约束、证据和后果",
                )
            )
        if slide.teaching_role in _PRACTICE_ROLES and not _has_feedback(
            slide.speaker_notes
        ):
            issues.append(
                SectionQualityIssue(
                    "practice_missing_feedback",
                    "练习讲稿需要答案、常见错误和反馈",
                )
            )

        policy = visual_policy(slide)
        if policy.requires_diagram and slide.layout != "diagram":
            issues.append(
                SectionQualityIssue(
                    "diagram_purpose_missing_diagram",
                    "步骤或机制页需要使用示意图版式",
                )
            )
        if not policy.requires_diagram and slide.layout == "diagram":
            code = (
                "comparison_rendered_as_flow"
                if slide.visual_purpose == "comparison"
                else "non_diagram_rendered_as_flow"
            )
            issues.append(
                SectionQualityIssue(code, "该视觉用途不应使用流程图版式")
            )
    return issues
