"""组卷 —— 设计规格 §4.2 的 `PaperComposer`:题目池 + 约束 → `ExamPaper`。

═══════════════════════════════════════════════════════════════════
为什么这里没有模型调用
═══════════════════════════════════════════════════════════════════
设计规格写得很直接:「组卷 | 纯算法,无 AI」。

组卷是个**约束满足问题**:在总分和必考知识点的约束下从题库里挑题。
模型不擅长算术 —— 让它挑,卷子总分永远对不上。而总分必须精确等于设定值,
这是 §6.4 交叉引用校验里的一条硬规则,不是「差不多就行」。

纯函数还有个好处:**同样的题库 + 同样的约束 → 同样的卷子**。
教师看到的那份和导出的那份不会对不上,测试也才能断言东西。

═══════════════════════════════════════════════════════════════════
三个约束,都做不到就如实报出来
═══════════════════════════════════════════════════════════════════
1. **只引用题库里的题,且不重复** —— 这是组卷,不是编题
2. **覆盖 `constraints.coverage` 里的全部知识点** —— 组卷不能漏考点
3. **总分精确等于 `constraints.total_points`** —— 少一分多一分都算校验失败

第 1 条是构造保证的。第 2、3 条用一次 0/1 背包求出精确解;
求不出来就退到「最接近」并**在 reason 里说清差在哪**,不许四舍五入糊过去。

难度分布是**软约束**:按分数算实际占比,偏离超过容忍度就报出来,
但不会因此丢掉整个卷子 —— 教师宁可拿到一份难度偏简单的卷子并看见提示,
也不想拿到一份空卷子。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.ir import (
    ExamConstraints,
    ExamPaper,
    PaperDifficulty,
    PaperSection,
    Question,
    QuestionSet,
)

#: 难度 1–5 分成三档。这是「简单 / 中等 / 困难」的唯一定义处。
EASY_MAX = 2
MEDIUM = 3

#: 难度占比偏离目标多少算「没做到」。
#: 定 0.2 是因为精确命中占比通常不可能 —— 题目的分值是离散的。
DIFFICULTY_TOLERANCE = 0.2

#: 状态空间上限。掩码位数 = 必考知识点个数,每个掩码位翻一倍。
#: 现实里必考知识点是 3–6 个,离这个上限很远;超过就说明用法不对,
#: 与其卡死不如明确拒绝。
STATE_BUDGET = 4_000_000

#: 题型 → 大题名。顺序就是卷面顺序。
SECTION_TITLES: dict[str, str] = {
    "mcq": "选择题",
    "short": "简答题",
    "code": "编程题",
    "scenario": "情境题",
}
SECTION_ORDER: tuple[str, ...] = ("mcq", "short", "code", "scenario")
CHINESE_NUMERALS: tuple[str, ...] = ("一", "二", "三", "四", "五", "六")


def difficulty_band(difficulty: int) -> str:
    """难度 1–5 → easy / medium / hard。"""
    if difficulty <= EASY_MAX:
        return "easy"
    if difficulty <= MEDIUM:
        return "medium"
    return "hard"


@dataclass
class PaperRequest:
    """组卷的输入。"""

    question_set: QuestionSet
    constraints: ExamConstraints
    artifact_id: str = "a-paper"


@dataclass
class PaperResult:
    """组卷的结果。**永远返回,永远不抛异常。**

    `ok=False` 时 `reason` 一定非空 —— 它说的是「哪条约束没满足」。
    """

    paper: ExamPaper
    ok: bool
    reason: str = ""
    actual_points: int = 0
    #: 约束要求覆盖、但卷子里一道题都没考到的知识点。
    missing: set[str] = field(default_factory=set)
    #: 实际难度占比(按分数算,不按题数 —— 一道 20 分的难题比三道 5 分的重要)。
    actual_difficulty: PaperDifficulty = field(default_factory=PaperDifficulty)


def _mask_of(question: Question, index_of: dict[str, int]) -> int:
    """这道题覆盖了哪几个**必考**知识点,压成一个位掩码。"""
    mask = 0
    for objective_id in question.objective_ids:
        position = index_of.get(objective_id)
        if position is not None:
            mask |= 1 << position
    return mask


def _select(
    candidates: list[tuple[Question, int]], target: int, full_mask: int
) -> tuple[list[Question], int] | None:
    """0/1 背包:找出总分恰好等于 target 且覆盖全部必考点的题目组合。

    ═══════════════════════════════════════════════════════════════
    为什么不能贪心
    ═══════════════════════════════════════════════════════════════
    贪心会先挑大分题,然后永远凑不齐。题库 [20, 20, 15, 10] 目标 25 就是例子:
    拿 20 就无解,正确解是 15 + 10。这类情况必须靠回退,而背包天然带回退。

    ═══════════════════════════════════════════════════════════════
    为什么状态里要有掩码
    ═══════════════════════════════════════════════════════════════
    只记「凑到多少分」的话,找到的组合可能整个漏掉一个考点,
    而总分是对的 —— 那种卷子过不了 §6.4 的覆盖检查。

    返回 `(选中的题, 覆盖掩码)`;无解返回 None。
    """
    # parent[状态] = (上一个总分, 上一个掩码, 用的是第几道题)
    parent: dict[tuple[int, int], tuple[int, int, int] | None] = {(0, 0): None}

    for index, (question, mask) in enumerate(candidates):
        # 先快照再遍历 —— 这是 0/1 背包的关键,保证每道题最多用一次
        for total, covered in list(parent.keys()):
            next_total = total + question.points
            if next_total > target:
                continue
            next_key = (next_total, covered | mask)
            if next_key in parent:
                continue
            parent[next_key] = (total, covered, index)

    if (target, full_mask) not in parent:
        return None

    # 沿着 parent 往回走,还原选了哪些题
    picked: list[Question] = []
    cursor: tuple[int, int] | None = (target, full_mask)
    while cursor is not None:
        step = parent[cursor]
        if step is None:
            break
        total, covered, index = step
        picked.append(candidates[index][0])
        cursor = (total, covered)

    picked.reverse()
    return picked, full_mask


def _best_effort(
    candidates: list[tuple[Question, int]], target: int
) -> tuple[list[Question], int, set[str] | None]:
    """凑不出精确解时,退到「总分最接近、覆盖最多」的组合。

    返回 `(选中的题, 达到的总分, None)`。
    """
    # 单看总分的背包 —— 不求覆盖,只求离 target 最近
    reachable: dict[int, tuple[int, int] | None] = {0: None}
    for index, (question, _mask) in enumerate(candidates):
        for total in list(reachable.keys()):
            next_total = total + question.points
            if next_total > target or next_total in reachable:
                continue
            reachable[next_total] = (total, index)

    best_total = max(reachable.keys(), default=0)
    picked: list[Question] = []
    cursor: int | None = best_total
    while cursor is not None:
        step = reachable[cursor]
        if step is None:
            break
        total, index = step
        picked.append(candidates[index][0])
        cursor = total
    picked.reverse()

    covered: set[str] = set()
    for question in picked:
        covered.update(question.objective_ids)
    return picked, best_total, covered


def _mix_of(questions: list[Question]) -> tuple[PaperDifficulty, int]:
    """按**分数**算难度占比。返回 (占比, 总分)。"""
    buckets = {"easy": 0, "medium": 0, "hard": 0}
    for question in questions:
        buckets[difficulty_band(question.difficulty)] += question.points
    total = sum(buckets.values())
    if total <= 0:
        return PaperDifficulty(), 0
    return (
        PaperDifficulty(
            easy=buckets["easy"] / total,
            medium=buckets["medium"] / total,
            hard=buckets["hard"] / total,
        ),
        total,
    )


def _target_mix(constraints: ExamConstraints) -> PaperDifficulty | None:
    """把约束里的难度占比归一化。**三个都是 0 表示教师没提要求。**

    全 0 不能理解成「三档都要 0%」—— 那是自相矛盾的条件,
    按那个判的话每一份卷子都不合格。
    """
    raw = constraints.difficulty
    total = raw.easy + raw.medium + raw.hard
    if total <= 0:
        return None
    return PaperDifficulty(
        easy=raw.easy / total, medium=raw.medium / total, hard=raw.hard / total
    )


def _mix_within(target: PaperDifficulty, actual: PaperDifficulty) -> bool:
    return (
        abs(target.easy - actual.easy) <= DIFFICULTY_TOLERANCE
        and abs(target.medium - actual.medium) <= DIFFICULTY_TOLERANCE
        and abs(target.hard - actual.hard) <= DIFFICULTY_TOLERANCE
    )


def _build_sections(questions: list[Question]) -> list[PaperSection]:
    """按题型分大题。**只发出非空的大题** —— 空的简答题大题很荒唐。"""
    by_type: dict[str, list[Question]] = {}
    for question in questions:
        by_type.setdefault(question.type, []).append(question)

    sections: list[PaperSection] = []
    for position, question_type in enumerate(SECTION_ORDER):
        group = by_type.get(question_type)
        if not group:
            continue
        points = sum(q.points for q in group)
        numeral = CHINESE_NUMERALS[len(sections)] if len(sections) < len(CHINESE_NUMERALS) else str(len(sections) + 1)
        sections.append(
            PaperSection(
                title=f"{numeral}、{SECTION_TITLES.get(question_type, question_type)}",
                # 每个大题报**自己的**题数和分值 —— 都写全卷的,学生会算错时间
                rule=f"共 {len(group)} 题,合计 {points} 分。",
                question_ids=[q.id for q in sorted(group, key=lambda q: (-q.points, q.id))],
            )
        )
    return sections


def compose_paper(req: PaperRequest) -> PaperResult:
    """按约束组卷。**纯函数,不调用模型,不抛异常。**"""
    constraints = req.constraints
    target = constraints.total_points

    # 去重但保序 —— coverage 里写重复不改变语义,但会让掩码算错
    required = list(dict.fromkeys(constraints.coverage))
    index_of = {objective_id: i for i, objective_id in enumerate(required)}

    if len(required) > 20:
        return PaperResult(
            paper=ExamPaper(artifact_id=req.artifact_id, constraints=constraints),
            ok=False,
            reason=f"必考知识点有 {len(required)} 个,超出精确求解的范围;请精简 coverage",
        )

    # 0 分题对总分没贡献,留着只会让卷子变长
    usable = [q for q in req.question_set.questions if q.points > 0]
    if not usable:
        return PaperResult(
            paper=ExamPaper(artifact_id=req.artifact_id, constraints=constraints),
            ok=False,
            reason="题库里没有可用的题目(需要分值大于 0 的题)",
        )

    full_mask = (1 << len(required)) - 1
    if (target + 1) * max(1, 1 << len(required)) > STATE_BUDGET:
        return PaperResult(
            paper=ExamPaper(artifact_id=req.artifact_id, constraints=constraints),
            ok=False,
            reason="约束组合过多,无法精确求解;请降低总分或减少必考知识点",
        )

    # 两种候选顺序各试一次。
    # 先大分题:通常更快命中精确总分。
    # 再按难度缺口优先:给难度分布一个机会,不然它永远是碰运气。
    target_mix = _target_mix(constraints)

    def by_points() -> list[tuple[Question, int]]:
        return [(q, _mask_of(q, index_of)) for q in sorted(usable, key=lambda q: (-q.points, q.id))]

    def by_difficulty_gap() -> list[tuple[Question, int]]:
        if target_mix is None:
            return by_points()
        # 目标占比低的档排在前面 —— 让背包先在「稀缺」的那一档里做选择
        def rank(question: Question) -> tuple[float, int, str]:
            band = difficulty_band(question.difficulty)
            return (getattr(target_mix, band), -question.points, question.id)
        return [(q, _mask_of(q, index_of)) for q in sorted(usable, key=rank)]

    best: tuple[list[Question], int, set[str], PaperDifficulty] | None = None
    for ordering in (by_points, by_difficulty_gap):
        found = _select(ordering(), target, full_mask)
        if found is None:
            continue
        picked, _ = found
        mix, _total = _mix_of(picked)
        covered = {oid for q in picked for oid in q.objective_ids}
        missing = set(required) - covered

        exact = sum(q.points for q in picked) == target
        if exact and not missing and (target_mix is None or _mix_within(target_mix, mix)):
            return PaperResult(
                paper=ExamPaper(
                    artifact_id=req.artifact_id,
                    constraints=constraints,
                    sections=_build_sections(picked),
                ),
                ok=True,
                actual_points=target,
                actual_difficulty=mix,
            )
        if best is None:
            best = (picked, sum(q.points for q in picked), missing, mix)

    if best is not None:
        picked, actual_points, missing, mix = best
        reasons = []
        if actual_points != target:
            reasons.append(f"总分凑不出 {target},最接近是 {actual_points}")
        if missing:
            reasons.append(f"这些考点没题可考:{'、'.join(sorted(missing))}")
        if target_mix is not None and not _mix_within(target_mix, mix):
            wanted = f"{target_mix.easy:.0%}/{target_mix.medium:.0%}/{target_mix.hard:.0%}"
            got = f"{mix.easy:.0%}/{mix.medium:.0%}/{mix.hard:.0%}"
            reasons.append(f"难度分布是 {got},要求 {wanted}(易/中/难)")
        return PaperResult(
            paper=ExamPaper(
                artifact_id=req.artifact_id,
                constraints=constraints,
                sections=_build_sections(picked),
            ),
            ok=False,
            reason=";".join(reasons) or "无法满足全部约束",
            actual_points=actual_points,
            missing=missing,
            actual_difficulty=mix,
        )

    # 连一个精确解都没有 —— 退到最接近的组合,把差在哪说清楚
    picked, actual_points, covered = _best_effort(by_points(), target)
    mix, _ = _mix_of(picked)
    missing = set(required) - (covered or set())
    if not picked:
        return PaperResult(
            paper=ExamPaper(artifact_id=req.artifact_id, constraints=constraints),
            ok=False,
            reason=f"题库里没有单题分值不超过 {target} 的题,凑不出这张卷子",
        )
    reasons = [f"总分凑不出 {target},最接近是 {actual_points}"]
    if missing:
        reasons.append(f"这些考点没题可考:{'、'.join(sorted(missing))}")
    return PaperResult(
        paper=ExamPaper(
            artifact_id=req.artifact_id,
            constraints=constraints,
            sections=_build_sections(picked),
        ),
        ok=False,
        reason=";".join(reasons),
        actual_points=actual_points,
        missing=missing,
        actual_difficulty=mix,
    )
