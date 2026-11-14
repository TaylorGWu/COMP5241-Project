"""Tests for deterministic instructional-quality contracts."""

from __future__ import annotations

from app.schemas.ir import Slide
from app.services.instructional_quality import validate_section_quality, visual_policy


def test_legacy_slide_defaults_to_safe_instructional_semantics():
    slide = Slide.model_validate(
        {"id": "s1", "order": 1, "layout": "bullets", "title": "Git"}
    )

    assert slide.teaching_role == "explain"
    assert slide.visual_purpose == "none"


def test_slide_serializes_instructional_semantics_in_camel_case():
    slide = Slide.model_validate(
        {
            "id": "s2",
            "order": 2,
            "layout": "twoCol",
            "title": "Compare choices",
            "teachingRole": "worked_example",
            "visualPurpose": "comparison",
        }
    )

    assert slide.model_dump(by_alias=True)["teachingRole"] == "worked_example"
    assert slide.model_dump(by_alias=True)["visualPurpose"] == "comparison"


def _slide(
    role: str,
    purpose: str = "none",
    *,
    layout: str = "bullets",
    notes: str = "提问：为什么？\n误区：只改档名。\n过渡：接着比较。",
    title: str | None = None,
    bullets: list[str] | None = None,
) -> Slide:
    return Slide(
        id=role,
        order=1,
        layout=layout,
        title=title or role,
        teaching_role=role,  # type: ignore[arg-type]
        visual_purpose=purpose,  # type: ignore[arg-type]
        speaker_notes=notes,
        bullets=bullets if bullets is not None else ["核心概念", "判断依据", "下一步行动"],
    )


def test_valid_learning_loop_has_no_quality_issues():
    slides = [
        _slide("explain"),
        _slide(
            "worked_example",
            "scenario",
            title="案例：两位同学同时修改登入模块",
            bullets=["角色：开发者甲与乙", "约束：同一条主线交付", "证据：测试失败", "后果：覆盖对方改动"],
        ),
        _slide(
            "check_understanding",
            notes="正确答案：B。\n常见错误：A。\n反馈：版本号没有记录差异。",
        ),
        _slide("transfer"),
    ]

    assert validate_section_quality(slides) == []


def test_missing_practice_reports_a_stable_reason_code():
    codes = {
        issue.code
        for issue in validate_section_quality(
            [_slide("explain"), _slide("worked_example"), _slide("recap")]
        )
    }

    assert "missing_practice" in codes


def test_comparison_must_not_be_rendered_as_a_flow_diagram():
    slides = [
        _slide("explain"),
        _slide("worked_example"),
        _slide("check_understanding"),
        _slide("recap"),
        _slide("transfer", "comparison", layout="diagram"),
    ]

    assert "comparison_rendered_as_flow" in {
        issue.code for issue in validate_section_quality(slides)
    }


def test_worked_example_without_context_and_consequence_is_rejected():
    slides = [
        _slide("explain"),
        _slide("worked_example", "scenario"),
        _slide(
            "check_understanding",
            notes="正确答案：B。\n常见错误：A。\n反馈：版本号没有记录差异。",
        ),
        _slide("recap"),
    ]

    assert "generic_worked_example" in {
        issue.code for issue in validate_section_quality(slides)
    }


def test_practice_without_feedback_is_rejected():
    slides = [
        _slide("explain"),
        _slide(
            "worked_example",
            "scenario",
            title="案例：两位同学同时修改登入模块",
            bullets=["角色：开发者甲与乙", "约束：同一条主线交付", "证据：测试失败", "后果：覆盖对方改动"],
        ),
        _slide("check_understanding", notes="请选一个答案。"),
        _slide("recap"),
    ]

    assert "practice_missing_feedback" in {
        issue.code for issue in validate_section_quality(slides)
    }


def test_sparse_slide_content_is_marked_for_teacher_review():
    slides = [
        _slide("explain", bullets=["只有一个要点"]),
        _slide(
            "worked_example",
            "scenario",
            title="案例：两位同学同时修改登入模块",
            bullets=["角色：开发者甲与乙", "约束：同一条主线交付", "证据：测试失败", "后果：覆盖对方改动"],
        ),
        _slide("check_understanding", notes="正确答案：B。常见错误：A。反馈：版本号没有记录差异。"),
        _slide("recap"),
    ]

    assert "thin_slide_content" in {
        issue.code for issue in validate_section_quality(slides)
    }


def test_only_sequence_and_mechanism_require_a_diagram():
    assert visual_policy(_slide("explain", "sequence")).requires_diagram is True
    assert visual_policy(_slide("explain", "mechanism")).requires_diagram is True
    assert visual_policy(_slide("explain", "comparison")).requires_diagram is False
    assert visual_policy(_slide("explain", "none")).requires_diagram is False


def test_repeated_bullets_do_not_count_as_content_depth():
    slide = _slide("explain", bullets=["Commit records a snapshot.", " commit records a snapshot! ", "Check git status."])
    before = slide.model_dump_json()

    assert "duplicate_slide_points" in {
        issue.code for issue in validate_section_quality([slide])
    }
    assert slide.model_dump_json() == before


def test_distinct_conditions_using_the_same_terms_are_not_duplicates():
    slide = _slide("explain", bullets=[
        "Reset may rewrite local history.",
        "Revert adds a new commit to history.",
        "Inspect history before choosing a command.",
    ])
    assert "duplicate_slide_points" not in {
        issue.code for issue in validate_section_quality([slide])
    }


def test_natural_traditional_chinese_case_and_feedback_do_not_need_template_labels():
    case = _slide("worked_example", "scenario", bullets=[
        "初始狀態：小明推送了錯誤提交，小華已拉取。",
        "約束：工作區還有需要保護的修改。",
        "驗證：執行測試確認修正結果，推送後請小華檢查。",
    ])
    practice = _slide("check_understanding", notes=(
        "正確答案是 A。B 的誤解是以為尚未提交的修改已經保存在歷史中。"
        "若學生只回答選項，追問：要如何確認修改仍然存在？"
    ))
    codes = {issue.code for issue in validate_section_quality([case, practice])}
    assert "generic_worked_example" not in codes
    assert "practice_missing_feedback" not in codes
