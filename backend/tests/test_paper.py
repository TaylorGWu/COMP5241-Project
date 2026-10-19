"""组卷 —— 设计规格 §185 的 `PaperComposer`:题目池 + 约束 → `ExamPaper`。

═══════════════════════════════════════════════════════════════════
为什么这里没有模型调用
═══════════════════════════════════════════════════════════════════
设计规格写得很直接:「组卷 | 纯算法,无 AI」。

组卷是个**约束满足问题**:在总分、时长、必考知识点的约束下从题库里挑题。
模型不擅长算术 —— 让它挑,它给你的卷子总分永远对不上。
而总分必须精确等于设定值,这是 §6.4 交叉引用校验里的一条硬规则。

所以这是个纯函数:同样的题库 + 同样的约束 → 同样的卷子。可复现、可断言。

═══════════════════════════════════════════════════════════════════
三个约束,优先级不同
═══════════════════════════════════════════════════════════════════
1. **引用的题目必须在题库里** —— 这是编出来的卷子,不是选择题
2. **覆盖 constraints.coverage 里的全部知识点** —— 组卷不能漏考点
3. **总分精确等于 constraints.total_points** —— 少一分多一分都算校验失败

前两条做不到就是「这卷子不合规」,第三条做不到就是「这题库凑不出这个分」。
两种都**如实报出来**,不许四舍五入糊过去。
"""

from __future__ import annotations

from app.schemas.ir import (
    ExamConstraints,
    ExamPaper,
    LearningObjective,
    Option,
    PaperDifficulty,
    Project,
    ProjectMeta,
    Question,
    QuestionSet,
    Slide,
    SlideDeck,
)
from app.services.paper import PaperRequest, compose_paper, difficulty_band

OBJECTIVES = [
    LearningObjective(id="LO1", text="解释分支与主干的关系"),
    LearningObjective(id="LO2", text="完成一次安全的合并"),
    LearningObjective(id="LO3", text="看懂冲突标记"),
]


def _q(
    qid: str,
    points: int,
    objectives: list[str],
    *,
    difficulty: int = 2,
    qtype: str = "mcq",
) -> Question:
    """一道题。默认是带 A/B 选项、答案 A 的选择题。"""
    return Question(
        id=qid,
        type=qtype,  # type: ignore[arg-type]
        stem=f"题干 {qid}",
        options=[Option(id="A", text="选项甲"), Option(id="B", text="选项乙")],
        answer="A",
        points=points,
        difficulty=difficulty,
        objective_ids=objectives,
    )


def _bank(*questions: Question) -> QuestionSet:
    return QuestionSet(artifact_id="a-questions", questions=list(questions))


def _constraints(
    total: int, coverage: list[str] | None = None, **kwargs: object
) -> ExamConstraints:
    return ExamConstraints(
        total_points=total,
        duration_min=90,
        coverage=coverage if coverage is not None else ["LO1", "LO2"],
        **kwargs,  # type: ignore[arg-type]
    )


def _req(*questions: Question, total: int, coverage: list[str] | None = None) -> PaperRequest:
    return PaperRequest(
        question_set=_bank(*questions),
        constraints=_constraints(total, coverage),
        artifact_id="a-paper",
    )


def _picked_ids(paper: ExamPaper) -> list[str]:
    return [qid for section in paper.sections for qid in section.question_ids]


# ═══════════════════════════════════════════════════════════════
# 硬约束一:总分必须精确
# ═══════════════════════════════════════════════════════════════


def test_the_selected_questions_sum_to_the_exact_target():
    """总分对不上,§6.4 的交叉引用校验会直接报错。"""
    req = _req(
        _q("q1", 5, ["LO1"]),
        _q("q2", 10, ["LO2"]),
        _q("q3", 15, ["LO1", "LO2"]),
        total=25,
    )
    result = compose_paper(req)

    total = sum(
        q.points for q in req.question_set.questions if q.id in _picked_ids(result.paper)
    )
    assert total == 25
    assert result.ok is True


def test_it_finds_a_combination_that_a_greedy_scan_would_miss():
    """贪心会先挑大分题然后凑不齐,正确解需要回退。

    这边 [20, 20, 15, 10] 目标 25:拿 20 就永远凑不出 25。
    正确解是 15 + 10。
    """
    req = _req(
        _q("q1", 20, ["LO1"]),
        _q("q2", 20, ["LO1"]),
        _q("q3", 15, ["LO1", "LO2"]),
        _q("q4", 10, ["LO2"]),
        total=25,
    )
    result = compose_paper(req)

    assert result.ok is True
    assert sorted(_picked_ids(result.paper)) == ["q3", "q4"]


def test_a_total_that_cannot_be_reached_is_reported_not_faked():
    """题库是 [3, 3],目标 10 —— 凑不出来。

    这时候**不许四舍五入**:要么如实说凑不出,要么给一个总分不对的卷子
    并明确标出来。假装成功是最坏的选项。
    """
    req = _req(_q("q1", 3, ["LO1"]), _q("q2", 3, ["LO2"]), total=10)
    result = compose_paper(req)

    assert result.ok is False
    assert result.actual_points != 10
    assert "总分" in result.reason or "凑" in result.reason


def test_zero_point_questions_are_ignored():
    """0 分题对总分没有贡献,留着只会让卷子变长。"""
    req = _req(
        _q("q1", 0, ["LO1"]),
        _q("q2", 10, ["LO1"]),
        _q("q3", 15, ["LO2"]),
        total=25,
    )
    result = compose_paper(req)

    assert "q1" not in _picked_ids(result.paper)
    assert result.ok is True


# ═══════════════════════════════════════════════════════════════
# 硬约束二:不能漏考点
# ═══════════════════════════════════════════════════════════════


def test_every_required_objective_is_covered():
    req = _req(
        _q("q1", 5, ["LO1"]),
        _q("q2", 5, ["LO2"]),
        _q("q3", 5, ["LO3"]),
        _q("q4", 10, ["LO1"]),
        total=15,
        coverage=["LO1", "LO2", "LO3"],
    )
    result = compose_paper(req)

    picked = _picked_ids(result.paper)
    covered = {
        oid
        for q in req.question_set.questions
        if q.id in picked
        for oid in q.objective_ids
    }
    assert {"LO1", "LO2", "LO3"} <= covered
    assert result.ok is True


def test_an_objective_no_question_covers_is_reported():
    """题库里没有 LO3 的题 —— 那这张卷子必然漏考点,得说出来。"""
    req = _req(
        _q("q1", 5, ["LO1"]),
        _q("q2", 5, ["LO2"]),
        total=10,
        coverage=["LO1", "LO2", "LO3"],
    )
    result = compose_paper(req)

    assert result.ok is False
    assert "LO3" in result.missing
    assert "LO3" in result.reason


def test_covering_an_objective_is_preferred_over_a_higher_point_question():
    """同一分下,优先选能补上缺口的题 —— 但绝不能为了覆盖而丢掉精确总分。"""
    req = _req(
        _q("q1", 10, ["LO1"]),
        _q("q2", 10, ["LO2"]),
        _q("q3", 10, ["LO1"]),
        total=20,
        coverage=["LO1", "LO2"],
    )
    result = compose_paper(req)

    assert result.ok is True
    assert "q2" in _picked_ids(result.paper), "没选 q2 就漏了 LO2"


# ═══════════════════════════════════════════════════════════════
# 硬约束三:只能引用题库里的题,且不能重复用
# ═══════════════════════════════════════════════════════════════


def test_the_paper_references_only_questions_from_the_bank():
    req = _req(_q("q1", 5, ["LO1"]), _q("q2", 5, ["LO2"]), total=10)
    result = compose_paper(req)

    bank = {q.id for q in req.question_set.questions}
    assert set(_picked_ids(result.paper)) <= bank


def test_no_question_is_picked_twice():
    """同一道题在卷子里出现两次,总分就是假的。"""
    req = _req(_q("q1", 5, ["LO1", "LO2"]), _q("q2", 5, ["LO1"]), total=10)
    result = compose_paper(req)

    picked = _picked_ids(result.paper)
    assert len(picked) == len(set(picked))


# ═══════════════════════════════════════════════════════════════
# 卷面结构
# ═══════════════════════════════════════════════════════════════


def test_questions_are_grouped_into_sections_by_type():
    """按题型分大题 —— 选择题放一起,简答题放一起。"""
    req = _req(
        _q("q1", 5, ["LO1"], qtype="mcq"),
        _q("q2", 5, ["LO2"], qtype="mcq"),
        _q("q3", 10, ["LO1"], qtype="short"),
        total=20,
    )
    result = compose_paper(req)

    titles = [s.title for s in result.paper.sections]
    assert len(titles) == 2, f"应该分成两个大题,拿到 {titles}"
    by_title = {s.title: s.question_ids for s in result.paper.sections}
    assert set(by_title[titles[0]]) == {"q1", "q2"} or set(by_title[titles[1]]) == {"q1", "q2"}


def test_each_section_rule_states_its_points():
    """大题说明里要写清这个部分多少分 —— 学生看卷子先看这个。"""
    req = _req(
        _q("q1", 5, ["LO1"]),
        _q("q2", 5, ["LO2"]),
        _q("q3", 10, ["LO1"], qtype="short"),
        total=20,
    )
    result = compose_paper(req)

    for section in result.paper.sections:
        assert section.rule, f"「{section.title}」没有写分值说明"
        assert "分" in section.rule


def test_an_empty_section_is_not_emitted():
    """只出到选择题时,不该冒出一个空的简答题大题。"""
    req = _req(_q("q1", 5, ["LO1"]), _q("q2", 5, ["LO2"]), total=10)
    result = compose_paper(req)

    assert all(s.question_ids for s in result.paper.sections)
    assert len(result.paper.sections) == 1


def test_a_section_rule_counts_its_own_questions_not_the_whole_paper():
    """两个大题各自报自己的题数 —— 都写成全卷题数的话学生会算错时间。"""
    req = _req(
        _q("q1", 5, ["LO1"], qtype="mcq"),
        _q("q2", 5, ["LO2"], qtype="mcq"),
        _q("q3", 10, ["LO1"], qtype="short"),
        total=20,
    )
    result = compose_paper(req)

    rules = {s.title: s.rule for s in result.paper.sections}
    mcq_rule = next(r for t, r in rules.items() if "选择" in t)
    short_rule = next(r for t, r in rules.items() if "简答" in t)

    assert "共 2 题" in mcq_rule, mcq_rule
    assert "共 1 题" in short_rule, short_rule
    assert "10 分" in short_rule, short_rule


# ═══════════════════════════════════════════════════════════════
# 难度分布
# ═══════════════════════════════════════════════════════════════


def test_difficulty_bands_split_one_to_five_into_three():
    """1-5 的难度映射到 easy / medium / hard 三档。"""
    assert difficulty_band(1) == "easy"
    assert difficulty_band(2) == "easy"
    assert difficulty_band(3) == "medium"
    assert difficulty_band(4) == "hard"
    assert difficulty_band(5) == "hard"


def test_the_actual_difficulty_mix_is_reported_in_points():
    """难度占比按**分数**算,不按题数 —— 一道 20 分的难题比三道 5 分的重要。"""
    req = PaperRequest(
        question_set=_bank(
            _q("q1", 10, ["LO1"], difficulty=1),
            _q("q2", 10, ["LO2"], difficulty=5),
        ),
        constraints=_constraints(
            20, ["LO1", "LO2"], difficulty=PaperDifficulty(easy=0.5, medium=0.0, hard=0.5)
        ),
    )
    result = compose_paper(req)

    # 两道题都被选中,难度正好一半一半
    assert result.actual_difficulty.easy == 0.5
    assert result.actual_difficulty.hard == 0.5


def test_a_difficulty_mix_it_cannot_meet_is_reported_not_faked():
    """题库里全是简单题,但约束要求一半是难题 —— 报出来,别假装做到了。"""
    req = PaperRequest(
        question_set=_bank(_q("q1", 10, ["LO1"], difficulty=1), _q("q2", 10, ["LO2"], difficulty=1)),
        constraints=_constraints(
            20, ["LO1", "LO2"], difficulty=PaperDifficulty(easy=0.5, medium=0.0, hard=0.5)
        ),
    )
    result = compose_paper(req)

    assert result.ok is False
    assert "难度" in result.reason


def test_an_all_zero_difficulty_mix_means_no_constraint():
    """easy/medium/hard 全写 0 时不该被理解成「三档都要 0%」——那是自相矛盾。

    它表示教师没提难度要求,所以不该因此判失败。
    """
    req = PaperRequest(
        question_set=_bank(_q("q1", 10, ["LO1"], difficulty=5), _q("q2", 10, ["LO2"], difficulty=5)),
        constraints=ExamConstraints(total_points=20, duration_min=90, coverage=["LO1", "LO2"]),
    )
    result = compose_paper(req)

    assert result.ok is True


# ═══════════════════════════════════════════════════════════════
# 确定性 —— 纯算法的意义就在这里
# ═══════════════════════════════════════════════════════════════


def test_the_same_input_gives_the_same_paper():
    """同样的题库和约束必须给同样的卷子。

    有随机性的话,「教师看到的那份」和「导出的那份」会对不上,
    而且测试也没法断言任何东西。
    """
    def build() -> PaperRequest:
        return _req(
            _q("q1", 5, ["LO1"]),
            _q("q2", 10, ["LO2"]),
            _q("q3", 15, ["LO1", "LO2"]),
            _q("q4", 5, ["LO3"]),
            total=20,
            coverage=["LO1", "LO2"],
        )

    a, b = compose_paper(build()), compose_paper(build())
    assert _picked_ids(a.paper) == _picked_ids(b.paper)


# ═══════════════════════════════════════════════════════════════
# 边界
# ═══════════════════════════════════════════════════════════════


def test_an_empty_bank_is_reported_not_crashed():
    req = PaperRequest(
        question_set=QuestionSet(artifact_id="a-questions", questions=[]),
        constraints=_constraints(100),
    )
    result = compose_paper(req)

    assert result.ok is False
    assert result.reason
    assert result.paper.sections == []


def test_no_required_coverage_means_only_the_total_matters():
    req = PaperRequest(
        question_set=_bank(_q("q1", 5, ["LO1"]), _q("q2", 5, ["LO2"])),
        constraints=ExamConstraints(total_points=10, duration_min=90, coverage=[]),
    )
    result = compose_paper(req)

    assert result.ok is True


# ═══════════════════════════════════════════════════════════════
# 最强的一条:产出必须过 §6.4 的交叉引用校验
# ═══════════════════════════════════════════════════════════════


def _package(question_set: QuestionSet, paper: ExamPaper):
    """拼一个最小的完整 CoursePackage,好让 validate_integrity 真跑一遍。"""
    from app.schemas.ir import CoursePackage

    return CoursePackage(
        project=Project(
            id="p1",
            meta=ProjectMeta(title="Git 基础", audience="初学者", duration_min=45),
            learning_objectives=OBJECTIVES,
        ),
        slide_deck=SlideDeck(
            artifact_id="a-slides",
            slides=[
                Slide(id="s1", order=1, layout="bullets", title="分支", objective_ids=["LO1"]),
                Slide(id="s2", order=2, layout="bullets", title="合并", objective_ids=["LO2"]),
                Slide(id="s3", order=3, layout="bullets", title="冲突", objective_ids=["LO3"]),
            ],
        ),
        question_set=question_set,
        exam_paper=paper,
    )


def test_a_successful_paper_passes_the_integrity_check():
    """组卷的最终验收标准就是这一条。

    §6.4 会检查三件事:引用的题在不在题库、总分对不对、覆盖全不全。
    上一层的测试断言的是这三件事各自的样子,这一条断言的是**合起来过不过**。
    """
    req = _req(
        _q("q1", 10, ["LO1"]),
        _q("q2", 10, ["LO2"]),
        _q("q3", 5, ["LO3"]),
        _q("q4", 15, ["LO1", "LO2"]),
        total=25,
        coverage=["LO1", "LO2", "LO3"],
    )
    result = compose_paper(req)

    assert result.ok is True
    package = _package(req.question_set, result.paper)
    assert package.validate_integrity() == []
