"""导出 —— 设计规格 §12.2。`IR → pptx / docx` 的纯转换。

═══════════════════════════════════════════════════════════════════
为什么这段必须是纯函数
═══════════════════════════════════════════════════════════════════
AGENTS.md 的硬规则:**渲染器和导出器是纯粹的 `IR → 输出` 转换,
里面不许有模型调用。**

这条保证了两件事:
1. 教案和课件不会互相矛盾 —— 它们来自同一份 IR
2. 导出可以单元测试 —— 不用花钱、不用等模型,断言的是文件内容

═══════════════════════════════════════════════════════════════════
预期:内容等效,不是像素级还原
═══════════════════════════════════════════════════════════════════
规格里特意写了这条要提前说清楚,否则后面会被当成 bug。

所以下面断言的是「文字在不在、结构对不对」,不是「长得像不像网页」。
版式只保证**有限固定版式**(title / bullets / diagram / twoCol / code / quiz),
不追求任意排版 —— 占位符溢出不可控。

═══════════════════════════════════════════════════════════════════
图怎么办
═══════════════════════════════════════════════════════════════════
规格:图必须用**后端渲染的 PNG**,不能依赖前端。

现在 Mermaid 还没接渲染服务(§8.2 的 Kroki),所以传了 asset_paths 就插图,
没传就在版面上放一个占位框、写明这是什么图。**不留空白** ——
教师拿到一个空框会以为导出坏了。
"""

from __future__ import annotations

import io

from docx import Document
from pptx import Presentation

from app.schemas.ir import (
    Asset,
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
    TimelineEntry,
    Visual,
)
from app.exporters.docx import exam_paper_to_docx, lesson_plan_to_docx
from app.exporters.pptx import slide_deck_to_pptx

# ── 夹具 ──────────────────────────────────────────────────────


def _project() -> Project:
    return Project(
        id="p1",
        meta=ProjectMeta(title="Git 分支管理", audience="非计算机专业初学者", duration_min=45),
        learning_objectives=[
            LearningObjective(id="LO1", text="解释分支与主干的关系"),
            LearningObjective(id="LO2", text="完成一次安全的合并"),
        ],
    )


def _deck(*slides: Slide) -> SlideDeck:
    if not slides:
        slides = (
            Slide(
                id="s1",
                order=1,
                layout="title",
                title="Git 分支管理",
                speaker_notes="开场:问学生有没有遇到过「改了别人的代码」的情况。",
            ),
            Slide(
                id="s2",
                order=2,
                layout="bullets",
                title="分支是什么",
                bullets=["分支是一条独立的开发线", "主干始终保持可用"],
                speaker_notes="先讲直觉,再讲机制。",
                objective_ids=["LO1"],
            ),
        )
    return SlideDeck(artifact_id="a-slides", slides=list(slides))


def _plan() -> LessonPlan:
    return LessonPlan(
        artifact_id="a-lesson",
        overview="先建立直觉,再看机制。",
        timeline=[
            TimelineEntry(
                id="t1",
                phase="概念导入",
                minutes=15,
                teacher_action="用两个学生的冲突引入",
                student_action="说出自己的理解",
                slide_ids=["s1"],
                check_understanding="能否用自己的话解释分支",
            ),
            TimelineEntry(
                id="t2",
                phase="动手练习",
                minutes=30,
                teacher_action="带着做一次合并",
                student_action="自己走一遍流程",
                slide_ids=["s2"],
            ),
        ],
    )


# ── 读回文件的辅助 ────────────────────────────────────────────


def _pptx_text(data: bytes) -> str:
    """把 pptx 里所有文字抠出来(含备注)。"""
    prs = Presentation(io.BytesIO(data))
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                parts.append(shape.text_frame.text)
        if slide.has_notes_slide:
            parts.append(slide.notes_slide.notes_text_frame.text)
    return "\n".join(parts)


def _docx_text(data: bytes) -> str:
    """把 docx 里所有文字抠出来(含表格)。"""
    doc = Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)


def _is_zip(data: bytes) -> bool:
    """pptx 和 docx 都是 zip。开头四个字节是 PK\\x03\\x04。"""
    return data[:4] == b"PK\x03\x04"


# ═══════════════════════════════════════════════════════════════
# pptx —— 课件
# ═══════════════════════════════════════════════════════════════


def test_the_deck_becomes_a_valid_pptx():
    data = slide_deck_to_pptx(_project(), _deck())

    assert _is_zip(data)
    assert len(data) > 1000, "文件太小,八成是空壳"


def test_every_slide_becomes_one_pptx_page():
    data = slide_deck_to_pptx(_project(), _deck())
    prs = Presentation(io.BytesIO(data))

    assert len(prs.slides._sldIdLst) == 2  # noqa: SLF001


def test_slide_titles_and_bullets_are_present():
    text = _pptx_text(slide_deck_to_pptx(_project(), _deck()))

    assert "分支是什么" in text
    assert "分支是一条独立的开发线" in text
    assert "主干始终保持可用" in text


def test_speaker_notes_are_preserved():
    """讲稿丢了的话,教师拿到的就是一份没法讲的课件。"""
    text = _pptx_text(slide_deck_to_pptx(_project(), _deck()))

    assert "先讲直觉,再讲机制" in text


def test_the_deck_is_sixteen_by_nine():
    """16:9 —— 和网页预览的画布比例一致,不然教师会以为放错了。"""
    prs = Presentation(io.BytesIO(slide_deck_to_pptx(_project(), _deck())))

    assert prs.slide_width == 12192000
    assert prs.slide_height == 6858000


def test_a_code_slide_keeps_its_code_verbatim():
    """代码被换行或截断的话,导出的课件就不能用了。"""
    deck = _deck(
        Slide(
            id="s1",
            order=1,
            layout="code",
            title="三条命令",
            bullets=["git switch -c feature", "git commit -m 'x'"],
        )
    )
    text = _pptx_text(slide_deck_to_pptx(_project(), deck))

    assert "git switch -c feature" in text
    assert "git commit -m 'x'" in text


def test_a_diagram_without_a_rendered_image_leaves_a_placeholder_not_a_blank():
    """Mermaid 还没接渲染服务(§8.2),所以图暂时插不进去。

    但**必须留个占位**,写明这是什么图 —— 留空白教师会以为导出坏了。
    """
    deck = _deck(
        Slide(
            id="s1",
            order=1,
            layout="diagram",
            title="分支与主干",
            visuals=[
                Visual(
                    id="v1",
                    kind="diagram",
                    spec={"engine": "mermaid", "code": "graph LR; A-->B"},
                )
            ],
        )
    )
    text = _pptx_text(slide_deck_to_pptx(_project(), deck))

    assert "分支与主干" in text
    assert "图" in text, f"没有留下任何占位说明:{text!r}"


def test_a_diagram_with_a_rendered_image_is_embedded():
    """有渲染好的 PNG 就真的插进去。"""
    import tempfile
    from pathlib import Path

    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "d.png"
        Image.new("RGB", (640, 360), "white").save(png)

        deck = _deck(
            Slide(
                id="s1",
                order=1,
                layout="diagram",
                title="分支与主干",
                visuals=[Visual(id="v1", kind="diagram", asset_id="as-1")],
            )
        )
        prs = Presentation(
            io.BytesIO(slide_deck_to_pptx(_project(), deck, asset_paths={"as-1": png}))
        )
        pictures = [
            shape
            for slide in prs.slides
            for shape in slide.shapes
            if shape.shape_type == 13  # PICTURE
        ]
        assert pictures, "传了 asset_paths 却没有插图"


def test_an_empty_deck_still_produces_a_valid_file():
    """空课件也要导得出来 —— 崩掉的话教师连「我还没写内容」都表达不了。"""
    data = slide_deck_to_pptx(_project(), SlideDeck(artifact_id="a", slides=[]))

    assert _is_zip(data)


def test_the_cover_slide_shows_the_project_title_and_audience():
    """封面要有课程名和受众 —— 教师直接把文件发给别人时才知道这是什么。"""
    text = _pptx_text(slide_deck_to_pptx(_project(), _deck()))

    assert "Git 分支管理" in text
    assert "非计算机专业初学者" in text


def test_export_uses_a_distinct_cover_and_content_layout():
    """不是把每页塞进同一张白纸:封面和内容页必须有各自的视觉层级。"""
    prs = Presentation(io.BytesIO(slide_deck_to_pptx(_project(), _deck())))

    cover_text = "\n".join(
        shape.text_frame.text for shape in prs.slides[0].shapes if shape.has_text_frame
    )
    content_text = "\n".join(
        shape.text_frame.text for shape in prs.slides[1].shapes if shape.has_text_frame
    )

    assert "COURSE NOTE" in cover_text
    assert "BULLETS" in content_text
    # 内容页有背景 + 内容卡片,而不是只有一个标题和裸露的段落。
    assert len(prs.slides[1].shapes) >= 4


# ═══════════════════════════════════════════════════════════════
# docx —— 教案
# ═══════════════════════════════════════════════════════════════


def test_the_lesson_plan_becomes_a_valid_docx():
    data = lesson_plan_to_docx(_project(), _plan())

    assert _is_zip(data)
    assert len(data) > 1000


def test_every_phase_and_its_minutes_are_present():
    text = _docx_text(lesson_plan_to_docx(_project(), _plan()))

    assert "概念导入" in text
    assert "15" in text
    assert "动手练习" in text
    assert "30" in text


def test_teacher_and_student_actions_are_both_present():
    """教案的价值就在这两列 —— 少了哪一列都不成立。"""
    text = _docx_text(lesson_plan_to_docx(_project(), _plan()))

    assert "用两个学生的冲突引入" in text
    assert "说出自己的理解" in text


def test_the_check_understanding_prompt_is_present():
    text = _docx_text(lesson_plan_to_docx(_project(), _plan()))

    assert "能否用自己的话解释分支" in text


def test_the_lesson_plan_states_the_learning_objectives():
    """教案开头要写教学目标 —— 不然教师上完课没法自查。"""
    text = _docx_text(lesson_plan_to_docx(_project(), _plan()))

    assert "解释分支与主干的关系" in text
    assert "完成一次安全的合并" in text


def test_the_total_minutes_are_shown():
    """总时长要写出来,教师一眼能对上课时。"""
    text = _docx_text(lesson_plan_to_docx(_project(), _plan()))

    assert "45" in text


def test_an_empty_timeline_still_produces_a_valid_file():
    plan = LessonPlan(artifact_id="a", overview="", timeline=[])
    data = lesson_plan_to_docx(_project(), plan)

    assert _is_zip(data)


# ═══════════════════════════════════════════════════════════════
# docx —— 考卷
# ═══════════════════════════════════════════════════════════════


def _bank() -> QuestionSet:
    return QuestionSet(
        artifact_id="a-questions",
        questions=[
            Question(
                id="q1",
                type="mcq",
                stem="分支的作用是什么?",
                options=[Option(id="A", text="让改动互相隔离"), Option(id="B", text="加快编译")],
                answer="A",
                explanation="分支让不同人的改动互不影响。",
                points=10,
                objective_ids=["LO1"],
            ),
            Question(
                id="q2",
                type="short",
                stem="说说你会在什么时候开分支。",
                answer="改动可能影响别人的时候。",
                points=15,
                objective_ids=["LO2"],
            ),
        ],
    )


def _paper() -> "object":
    from app.schemas.ir import ExamConstraints, ExamPaper

    return ExamPaper(
        artifact_id="a-paper",
        constraints=ExamConstraints(total_points=25, duration_min=90, coverage=["LO1", "LO2"]),
        sections=[PaperSection(title="一、选择题", rule="共 1 题,合计 10 分。", question_ids=["q1"])],
    )


def test_the_exam_paper_becomes_a_valid_docx():
    data = exam_paper_to_docx(_project(), _bank(), _paper())

    assert _is_zip(data)
    assert len(data) > 1000


def test_question_stems_options_and_points_are_present():
    text = _docx_text(exam_paper_to_docx(_project(), _bank(), _paper()))

    assert "分支的作用是什么" in text
    assert "让改动互相隔离" in text
    assert "10" in text


def test_the_answer_key_is_included_by_default():
    """教师版要带答案和解析 —— 学生版才是空白的。"""
    text = _docx_text(exam_paper_to_docx(_project(), _bank(), _paper()))

    assert "参考答案" in text or "答案" in text
    assert "分支让不同人的改动互不影响" in text


def test_the_answer_key_can_be_left_out():
    """学生版:题目在,答案和解析不在。

    做成一个开关而不是两份模板,是因为两份模板迟早会漂移 ——
    改了一处忘了另一处,学生就拿不到最新的题。
    """
    text = _docx_text(
        exam_paper_to_docx(_project(), _bank(), _paper(), include_answer_key=False)
    )

    assert "分支的作用是什么" in text
    assert "分支让不同人的改动互不影响" not in text


def test_the_paper_states_its_total_points_and_duration():
    text = _docx_text(exam_paper_to_docx(_project(), _bank(), _paper()))

    assert "25" in text
    assert "90" in text


def test_a_section_rule_is_shown_before_its_questions():
    text = _docx_text(exam_paper_to_docx(_project(), _bank(), _paper()))

    assert "共 1 题" in text
