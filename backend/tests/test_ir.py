"""IR 交叉引用校验测试 —— 对应设计规格 §6.4。

这些断言是能直接写进报告的质量证据。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ir import (
    Asset,
    CoursePackage,
    ExamConstraints,
    ExamPaper,
    LearningObjective,
    LessonPlan,
    Option,
    PaperSection,
    Project,
    ProjectMeta,
    Question,
    QuestionSet,
    Slide,
    SlideDeck,
    SourceRef,
    TimelineEntry,
    Visual,
)


def _pkg(**overrides) -> CoursePackage:
    """造一个最小可用包(一个目标 + 一页幻灯片),各测试在它上面加东西。"""

    base = dict(
        project=Project(
            id="p1",
            meta=ProjectMeta(title="Git 基础", audience="non-CS", duration_min=45),
            learning_objectives=[LearningObjective(id="LO1", text="解释分支")],
        ),
        slide_deck=SlideDeck(
            artifact_id="a1",
            slides=[
                Slide(
                    id="s1",
                    order=1,
                    layout="bullets",
                    title="分支",
                    objective_ids=["LO1"],
                )
            ],
        ),
    )
    base.update(overrides)
    return CoursePackage(**base)


# ── §6.4 规则:origin=sourced 必须有来源 ──────────────────────


def test_sourced_slide_without_refs_is_rejected():
    """声称有来源却不给 sourceRefs —— 必须被拒。"""

    with pytest.raises(ValidationError, match="sourceRefs"):
        Slide(id="s", order=1, layout="bullets", title="x", origin="sourced")


def test_sourced_slide_with_refs_is_accepted():
    """给了来源就通过。"""

    s = Slide(
        id="s",
        order=1,
        layout="bullets",
        title="x",
        origin="sourced",
        source_refs=[SourceRef(material_id="m1", page=14)],
    )
    assert s.origin == "sourced"


def test_ai_slide_needs_no_refs():
    """标记为 AI 补充的内容不要求出处。"""

    assert Slide(id="s", order=1, layout="bullets", title="x").origin == "ai"


# ── §6.4 规则:学习目标覆盖 ─────────────────────────────────


def test_uncovered_objective_is_reported():
    """有学习目标没被任何页覆盖 —— 必须报出来。"""

    pkg = _pkg()
    pkg.project.learning_objectives.append(LearningObjective(id="LO2", text="合并"))
    issues = pkg.validate_integrity()
    assert any("LO2" in i and "未被" in i for i in issues)


def test_fully_covered_package_passes():
    """都覆盖了就应该零问题。"""

    assert _pkg().validate_integrity() == []


# ── §6.4 规则:教案引用与时长 ────────────────────────────────


def test_lesson_plan_referencing_missing_slide_is_reported():
    """教案引用了不存在的幻灯片。"""

    pkg = _pkg(
        lesson_plan=LessonPlan(
            artifact_id="a2",
            timeline=[
                TimelineEntry(
                    id="T1", phase="导入", minutes=45, teacher_action="x", slide_ids=["s999"]
                )
            ],
        )
    )
    assert any("s999" in i for i in pkg.validate_integrity())


def test_lesson_plan_minutes_mismatch_is_reported():
    """总时长与设定课时差超 10%。"""

    pkg = _pkg(
        lesson_plan=LessonPlan(
            artifact_id="a2",
            timeline=[
                TimelineEntry(id="T1", phase="导入", minutes=10, teacher_action="x", slide_ids=["s1"])
            ],
        )
    )
    assert any("总时长" in i for i in pkg.validate_integrity())


def test_lesson_plan_within_ten_percent_passes():
    """差在 10% 以内应当放过。"""

    pkg = _pkg(
        lesson_plan=LessonPlan(
            artifact_id="a2",
            timeline=[
                TimelineEntry(id="T1", phase="导入", minutes=42, teacher_action="x", slide_ids=["s1"])
            ],
        )
    )
    assert pkg.validate_integrity() == []


# ── §6.4 规则:资产引用 ─────────────────────────────────────


def test_dangling_asset_reference_is_reported():
    """视觉需求指向不存在的资产。"""

    pkg = _pkg()
    pkg.slide_deck.slides[0].visuals = [
        Visual(id="v1", kind="diagram", asset_id="as-missing")
    ]
    assert any("as-missing" in i for i in pkg.validate_integrity())


def test_resolvable_asset_reference_passes():
    """资产存在就通过。"""

    pkg = _pkg(assets=[Asset(id="as-1", kind="diagram", status="ready")])
    pkg.slide_deck.slides[0].visuals = [Visual(id="v1", kind="diagram", asset_id="as-1")]
    assert pkg.validate_integrity() == []


# ── §6.4 规则:组卷 ─────────────────────────────────────────


def _paper_pkg(total_points: int, coverage: list[str], q_points: int, q_objs: list[str]):
    """造一个带题库和模拟卷的包,用来测组卷校验。"""

    return _pkg(
        question_set=QuestionSet(
            artifact_id="a3",
            questions=[
                Question(
                    id="q1",
                    type="mcq",
                    stem="?",
                    options=[Option(id="A", text="a")],
                    answer="A",
                    points=q_points,
                    objective_ids=q_objs,
                )
            ],
        ),
        exam_paper=ExamPaper(
            artifact_id="a4",
            constraints=ExamConstraints(
                total_points=total_points, duration_min=90, coverage=coverage
            ),
            sections=[PaperSection(title="一、选择题", question_ids=["q1"])],
        ),
    )


def test_exam_paper_total_points_mismatch_is_reported():
    """卷面实得总分与设定不符。"""

    issues = _paper_pkg(100, ["LO1"], 3, ["LO1"]).validate_integrity()
    assert any("总分" in i for i in issues)


def test_exam_paper_coverage_gap_is_reported():
    """有必考知识点没被覆盖。"""

    issues = _paper_pkg(3, ["LO1", "LO2"], 3, ["LO1"]).validate_integrity()
    assert any("LO2" in i for i in issues)


def test_exam_paper_referencing_missing_question_is_reported():
    """卷子引用了题库里没有的题号。"""

    pkg = _paper_pkg(3, ["LO1"], 3, ["LO1"])
    pkg.exam_paper.sections[0].question_ids = ["q404"]
    assert any("q404" in i for i in pkg.validate_integrity())


def test_correct_exam_paper_passes():
    """组卷正确就零问题。"""

    assert _paper_pkg(3, ["LO1"], 3, ["LO1"]).validate_integrity() == []
