"""内容语言 —— 教师选的语言必须真的送到写内容的模型面前。

═══════════════════════════════════════════════════════════════════
这个文件守的是一个真实发生过的缺陷
═══════════════════════════════════════════════════════════════════
「教材语言」这个开关当时是**假的**:
  ✓ 前端传了
  ✓ API 收了
  ✓ PlannerRequest 有大纲阶段用上了
  ✗ 但真正写课件标题和要点的 SectionAgent,prompt 里一个字都没提

结果:元数据 `ProjectMeta.language` 变了,内容语言却由模型自己决定。
所有单元测试都是绿的 —— 因为没有任何测试看过那段 prompt。

原则(和 test_tools.py 同源):
**模型能看到的契约 —— schema 或 prompt —— 必须有测试守着。**
"""

from __future__ import annotations

from app.services.pipeline import (
    SECTION_SYSTEM_PROMPT,
    GenerationRequest,
    section_user_prompt,
)
from app.services.planner import PlannedSection


def _req(language: str) -> GenerationRequest:
    return GenerationRequest(
        topic="Git for group projects",
        audience="second-year students",
        duration_min=45,
        language=language,
    )


def _section() -> PlannedSection:
    return PlannedSection(title="Branches", minutes=15)


def test_section_prompt_states_the_content_language():
    prompt = section_user_prompt(0, _section(), _req("en"))
    assert "en" in prompt


def test_every_supported_language_reaches_the_prompt():
    for lang in ("en", "zh-HK", "zh-CN"):
        prompt = section_user_prompt(1, _section(), _req(lang))
        assert lang in prompt, f"{lang} 没有出现在 prompt 里"


def test_changing_the_language_changes_the_prompt():
    """两种语言产出的 prompt 必须不同 —— 否则这个参数只是装饰。"""
    section = _section()
    assert section_user_prompt(0, section, _req("en")) != section_user_prompt(
        0, section, _req("zh-CN")
    )


def test_prompt_still_carries_the_audience():
    """加了语言之后别忘了受众 —— 这两条是同一条消息里的。"""
    prompt = section_user_prompt(0, _section(), _req("zh-HK"))
    assert "second-year students" in prompt
    assert "Branches" in prompt


def test_section_contract_requires_a_concrete_situation_and_decision():
    """每节不能只是概念概览，必须让学生在情境里判断。"""
    assert "具体工程情境" in SECTION_SYSTEM_PROMPT
    assert "决策" in SECTION_SYSTEM_PROMPT


def test_section_contract_requires_a_checkable_practice_with_feedback():
    """题目必须带回到错误思路，不能只有结论。"""
    assert "练习" in SECTION_SYSTEM_PROMPT
    assert "反馈" in SECTION_SYSTEM_PROMPT


def test_section_contract_requires_semantic_roles_and_visual_purpose():
    assert "teachingArc" in SECTION_SYSTEM_PROMPT
    assert "visualPurpose=sequence/mechanism" in SECTION_SYSTEM_PROMPT


def test_section_prompt_includes_teaching_blueprint():
    section = PlannedSection.model_validate(
        {
            "title": "Branches",
            "minutes": 15,
            "teachingArc": {
                "situation": "两位同学共用主线",
                "misconception": "最后保存总没问题",
                "practice": "选择安全下一步",
                "transferPrompt": "如何避免重演？",
            },
        }
    )
    prompt = section_user_prompt(0, section, _req("zh-HK"))

    assert "教学蓝图" in prompt
    assert "两位同学共用主线" in prompt
    assert "选择安全下一步" in prompt


def test_section_receives_assigned_objective_text_and_course_context():
    request = _req("en")
    request.objectives = ["Explain a commit", "Choose merge or rebase"]
    section = PlannedSection(title="Team branches", minutes=15, objective_ids=["LO2"])

    prompt = section_user_prompt(0, section, request)

    assert "Git for group projects" in prompt
    assert "LO2: Choose merge or rebase" in prompt
    assert "LO1: Explain a commit" not in prompt


def test_planner_generated_objectives_reach_section_when_teacher_leaves_them_blank():
    prompt = section_user_prompt(
        0, PlannedSection(title="Branches", minutes=15, objective_ids=["LO1"]),
        _req("en"), ["Explain branch isolation"],
    )

    assert "LO1: Explain branch isolation" in prompt


def test_section_without_assigned_ids_receives_all_available_objectives():
    prompt = section_user_prompt(
        0, _section(), _req("en"), ["Explain commits", "Compare histories"],
    )

    assert "LO1: Explain commits" in prompt
    assert "LO2: Compare histories" in prompt
