"""出题 —— 按学习目标生成题目。对应需求 FR-09 的「考题」。

═══════════════════════════════════════════════════════════════════
为什么不用 agent 循环
═══════════════════════════════════════════════════════════════════
分节生成(services/pipeline.py 阶段 3)用的是 agent 循环,因为模型运行时
才需要决定「先查讲义、这页要配图、写完检查覆盖率」——那些决策提前猜不到。

出题不一样:输入是学习目标,输出是题目,中间没有需要模型临场决定的事。
所以走 planner.py 那条路:**一次结构化调用 + 校验 + 优雅降级**。
少一层循环,少一份不确定性,也便宜。

═══════════════════════════════════════════════════════════════════
两条契约(都是踩过坑才加的,见 tests/test_questions.py)
═══════════════════════════════════════════════════════════════════
1. **语言必须写进 prompt。**「教材语言」那个开关曾经是假的 —— 参数一路传到
   大纲阶段就断了,真正写内容的 agent 完全不知道要写哪种语言。

2. **prompt 里的 schema 必须和 IR 一一对应。**`write_plan_entry` 的 schema
   曾经是个空壳,description 里写「字段见设计规格 §5.1」—— 但模型看不到设计规格。

═══════════════════════════════════════════════════════════════════
降级策略(§14)
═══════════════════════════════════════════════════════════════════
出题是流水线里的可选步骤。它失败**不能让整包失败** —— 课件和教案还在,
教师不该因为出题失败就丢掉整次生成。

    能解析 + 校验通过  → 用模型的
    单道题不合规        → 只丢那一道,其余照常
    任何一步整体失败    → 返回空题库并说明原因,**不抛异常**
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from app.llm.client import ChatClient
from app.schemas.ir import LearningObjective, Question, QuestionSet
from app.services.planner import extract_json

#: 难度区间。IR 里是 `ge=1, le=5`,这里也要知道才能夹紧。
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5


#: `Question` 的 JSON 形状。
#:
#: **这份 schema 必须和 `schemas/ir.py` 的 `Question` 保持一致。**
#: 少了任何一个字段,模型就只能猜 —— 而它猜错要到装配阶段才会炸。
#: `tests/test_questions.py` 里有三条测试盯着这件事:
#: 字段集合要一致、必填项要写清、每个字段都要有 description。
QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "题目唯一 id,如 q1。不要重复"},
        "type": {
            "type": "string",
            "enum": ["mcq", "short", "code", "scenario"],
            "description": (
                "题型:mcq=单选(必须有 options 和 answer),short=简答,"
                "code=写代码,scenario=情境分析"
            ),
        },
        "stem": {"type": "string", "description": "题干,一句话说清在问什么"},
        "options": {
            "type": "array",
            "description": "选项。mcq 必填,其余题型留空数组",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "选项编号,如 A / B / C / D"},
                    "text": {"type": "string", "description": "选项文字"},
                },
                "required": ["id", "text"],
            },
        },
        "answer": {
            "type": "string",
            "description": "正确答案。mcq 填选项 id(如 A);其余题型填参考答案",
        },
        "explanation": {
            "type": "string",
            "description": "解析:为什么这个答案对,其余选项错在哪",
        },
        "difficulty": {
            "type": "integer",
            "description": f"难度 {MIN_DIFFICULTY} 到 {MAX_DIFFICULTY},{MIN_DIFFICULTY} 最简单",
        },
        "objectiveIds": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "这道题考的是哪几个学习目标。**必须用给定的目标 id**"
                "(如 LO1),不要自己编号,也不要发明不存在的 id"
            ),
        },
        "points": {"type": "integer", "description": "分值,正整数"},
        "visuals": {
            "type": "array",
            "description": "题目配图。一般留空数组",
            "items": {"type": "object"},
        },
        "sourceRefs": {
            "type": "array",
            "description": (
                "题干如果来自讲义,在这里标出文件名和页码;自己编的就留空数组"
            ),
            "items": {
                "type": "object",
                "properties": {
                    "materialId": {"type": "string", "description": "讲义文件名"},
                    "page": {"type": "integer", "description": "页码,从 1 开始"},
                },
                "required": ["materialId"],
            },
        },
    },
    "required": ["id", "type", "stem"],
}


QUESTION_SYSTEM_PROMPT = f"""你在为一份软件工程迷你课程出题。

只输出一个 JSON 对象,不要写解释、不要加前后缀:

{{"questions": [ ...题目... ]}}

每道题的字段定义:

{json.dumps(QUESTION_SCHEMA, ensure_ascii=False, indent=2)}

要求:

1. **每道题都要标 objectiveIds**,值必须是下面给出的目标 id(如 LO1)。
   不要自己编号,不要发明不存在的 id。
2. **mcq 必须有 3 到 4 个选项和一个正确答案。**answer 填选项 id(如 "A")。
   干扰项要像真的错法,不要一眼假。
3. **explanation 要说出为什么。**只写「选 A」不算解析 —— 要说清 A 对在哪、
   其他选项错在哪。学生答错之后主要靠这段文字。
4. **难度分布要分散。**不要所有题都是同一个难度。
5. **题干用给定的语言书写。**
6. 不要出需要查资料才能答的题 —— 学生看完这课件就该会。"""


@dataclass
class QuestionRequest:
    """出题的输入。"""

    #: 要覆盖的学习目标。**必须带 id** —— 模型靠它标注 objectiveIds。
    objectives: list[LearningObjective]
    audience: str
    #: 题目用哪种语言写。与界面语言无关。
    language: str = "zh-HK"
    #: 每个目标出几道题。
    count_per_objective: int = 2
    #: 讲义片段(已检索好的),给模型做依据。空字符串表示没有材料。
    material_context: str = ""
    artifact_id: str = "a-questions"


@dataclass
class QuestionResult:
    """出题的结果。**永远返回,永远不抛异常。**"""

    question_set: QuestionSet
    #: True 表示整体降级了(一道题都没出出来)。
    used_fallback: bool = False
    #: 降级或丢题的原因。**非空就说明有问题**,空字符串才是正常。
    reason: str = ""
    #: 被跳过的题目及原因,一条一个。
    dropped: list[str] = field(default_factory=list)


def build_user_message(req: QuestionRequest) -> str:
    """写给模型的用户消息。

    单独抽成函数是为了能被测试钉住:这段文字是**模型能看到的契约**的一部分。
    原来的版本漏了语言,于是「教材语言」这个开关是假的,而且所有单元测试都是绿的。
    """
    lines = [
        f"学习者:{req.audience}",
        f"每个学习目标出 {req.count_per_objective} 道题。",
        f"**题干、选项和解析全部用 {req.language} 书写。**",
        "",
        "要覆盖的学习目标:",
    ]
    lines += [f"  {o.id}  {o.text}" for o in req.objectives]

    if req.material_context.strip():
        lines += ["", "可以参考的讲义片段:", req.material_context.strip()]

    return "\n".join(lines)


def _clamp_difficulty(raw: dict[str, Any]) -> None:
    """把难度夹进合法区间。**改的是原 dict,不是返回新对象。**

    难度写 7 是模型手滑,不是结构错误。夹到 5 比丢掉一整道题划算 ——
    尤其是题干和解析可能都是好的。
    """
    if "difficulty" not in raw:
        return
    try:
        raw["difficulty"] = min(MAX_DIFFICULTY, max(MIN_DIFFICULTY, int(raw["difficulty"])))
    except (TypeError, ValueError):
        # 不是数字 —— 交给 Pydantic 去报错,这里不猜
        pass


def _validate_one(
    raw: Any, known_objectives: set[str]
) -> tuple[Question | None, str]:
    """校验一道题。返回 (题目, 丢弃原因)。**二选一有值。**"""
    if not isinstance(raw, dict):
        return None, "不是对象"

    candidate = dict(raw)

    # 模型偶尔会编一个不存在的目标 id。整道题丢掉太狠(题干可能是好的),
    # 但**绝不能留着** —— 留着会让覆盖率检查把一个不存在的目标算成已覆盖。
    objectives = [
        o for o in (candidate.get("objectiveIds") or []) if isinstance(o, str)
    ]
    kept = [o for o in objectives if o in known_objectives]
    if not kept:
        return None, "标的学习目标都对不上"
    candidate["objectiveIds"] = kept

    _clamp_difficulty(candidate)

    try:
        question = Question.model_validate(candidate)
    except Exception as exc:  # noqa: BLE001
        return None, f"结构不合法({type(exc).__name__})"

    if question.type == "mcq":
        if not question.options:
            # 没有选项的选择题,学生没法作答
            return None, "选择题没有选项"
        option_ids = {o.id for o in question.options}
        if question.answer and question.answer not in option_ids:
            # 答案说选 C 但只有 A 和 B —— 这种题会把学生逼疯
            return None, f"答案 {question.answer} 不在选项里"

    return question, ""


async def generate_questions(
    req: QuestionRequest,
    *,
    client: ChatClient,
    model: str,
    temperature: float = 0.4,
) -> QuestionResult:
    """按学习目标出题。**失败一律降级,不抛异常。**"""

    def empty(reason: str) -> QuestionResult:
        return QuestionResult(
            question_set=QuestionSet(artifact_id=req.artifact_id, questions=[]),
            used_fallback=True,
            reason=reason,
        )

    if not req.objectives:
        return empty("没有给学习目标,无法出题")

    try:
        reply = await client.complete(
            model=model,
            messages=[
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(req)},
            ],
            temperature=temperature,
        )
    except Exception as exc:  # noqa: BLE001
        # 上游抖一下不能让整次生成白跑 —— 课件和教案还在
        return empty(f"模型调用失败({type(exc).__name__}):{exc}")

    data = extract_json(reply.content)
    if data is None:
        return empty("模型没有返回可解析的 JSON")

    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list):
        return empty("questions 不是数组")

    known = {o.id for o in req.objectives}
    questions: list[Question] = []
    dropped: list[str] = []
    seen: Counter[str] = Counter()
    used: set[str] = set()

    for index, raw in enumerate(raw_questions, start=1):
        question, why = _validate_one(raw, known)
        if question is None:
            label = raw.get("id") if isinstance(raw, dict) else None
            dropped.append(f"第 {index} 题(#{label or '无 id'})被跳过:{why}")
            continue

        # 模型会重复用同一个 id。不修的话组卷会把同一道题选中两次,
        # 而总分对不上,界面上还看不出来为什么。
        if question.id in used:
            seen[question.id] += 1
            new_id = f"{question.id}-{seen[question.id] + 1}"
            while new_id in used:
                seen[question.id] += 1
                new_id = f"{question.id}-{seen[question.id] + 1}"
            question = question.model_copy(update={"id": new_id})
        used.add(question.id)
        questions.append(question)

    if not questions:
        reason = "所有题目都不合规" if raw_questions else "模型没有给出任何题目"
        if dropped:
            reason += ":" + ";".join(dropped)
        return QuestionResult(
            question_set=QuestionSet(artifact_id=req.artifact_id, questions=[]),
            used_fallback=True,
            reason=reason,
            dropped=dropped,
        )

    return QuestionResult(
        question_set=QuestionSet(artifact_id=req.artifact_id, questions=questions),
        used_fallback=False,
        # 丢了几道题要说出来 —— 静默少几道题,教师会以为是模型就这水平
        reason=";".join(dropped),
        dropped=dropped,
    )
