# Teaching-quality generation rubric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated mini-course sections consistently teach through a concrete situation, evidence, decision, practice and feedback rather than generic summaries.

**Architecture:** Keep `SlideDeck` IR unchanged so existing renderers and exports remain deterministic. Strengthen the ArtifactPlanner and SectionAgent prompt contracts, then make the offline/demo generator model the same complete teaching chain so the local prototype never falls back to generic bullets.

**Tech Stack:** Python 3.12, FastAPI, Pydantic IR, existing LLM prompt contracts, pytest.

**Spec:** `docs/design/course-generation-design.md`

## Global Constraints

- IR remains the sole source of truth; models emit structured JSON only.
- AI output stays draft and needs teacher review before publishing.
- Model names remain behind `ModelRouter` configuration.
- One invalid section must not abort the full generation job.
- Diagram text remains deterministic Mermaid/SVG, never text-to-image.

---

### Task 1: Make the course outline plan for a learning arc

**Files:**
- Modify: `backend/app/services/planner.py`
- Test: `backend/tests/test_planner.py`

**Interfaces:**
- Consumes: `PlannerRequest(topic, audience, duration_min, requested_objectives, language)`.
- Produces: unchanged `Outline` and `PlannedSection` JSON contract.

- [x] **Step 1: Write the failing test**

```python
def test_planner_prompt_requires_a_situation_decision_and_practice_arc():
    assert "真实工程情境" in PLANNER_PROMPT
    assert "决策" in PLANNER_PROMPT
    assert "练习" in PLANNER_PROMPT
```

- [x] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest backend/tests/test_planner.py -q -k learning_arc`

- [x] **Step 3: Add the three arc requirements to `PLANNER_PROMPT`**

```python
6. 章节顺序要形成「真实工程情境 → 概念/证据 → 决策或操作 → 练习与反馈」的学习弧线。
```

- [x] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest backend/tests/test_planner.py -q -k learning_arc`

### Task 2: Require SectionAgent to author teachable slides

**Files:**
- Modify: `backend/app/services/pipeline.py`
- Test: `backend/tests/test_content_language.py`

**Interfaces:**
- Consumes: `section_user_prompt(index, PlannedSection, GenerationRequest)` and `SECTION_SYSTEM_PROMPT`.
- Produces: existing `write_section` payload and unchanged `Slide` IR.

- [x] **Step 1: Write the failing prompt-contract tests**

```python
def test_section_contract_requires_a_concrete_situation_and_decision():
    assert "具体工程情境" in SECTION_SYSTEM_PROMPT
    assert "决策" in SECTION_SYSTEM_PROMPT

def test_section_contract_requires_a_checkable_practice_with_feedback():
    assert "练习" in SECTION_SYSTEM_PROMPT
    assert "反馈" in SECTION_SYSTEM_PROMPT
```

- [x] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest backend/tests/test_content_language.py -q -k contract`

- [x] **Step 3: Add bounded authoring constraints**

```python
8. 每节至少有一页具体工程情境或失败案例、一页需要学生作出选择/判断的练习；练习讲稿必须解释常见错误为什么错。
9. 每页只承担一个教学动作：引出问题、解释证据、比较决策、指导操作或检查理解；不要用泛泛总结替代它。
```

- [x] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest backend/tests/test_content_language.py -q -k contract`

### Task 3: Make the offline/demo deck demonstrate the same teaching chain

**Files:**
- Modify: `backend/app/demo_pipeline.py`
- Test: `backend/tests/test_progress_stream.py`

**Interfaces:**
- Consumes: the scripted section model used by local/demo generation.
- Produces: unchanged `SlideDeck` IR with a scenario, evidence, decision, and practice slide per section.

- [x] **Step 1: Write a failing test for the demo deck contract**

```python
async def test_generated_demo_deck_contains_a_scenario_and_practice_feedback():
    result = await _sync(PAYLOAD)
    slides = result["package"]["slideDeck"]["slides"]
    assert any(slide["layout"] == "quiz" for slide in slides)
    assert any("情境" in slide["title"] for slide in slides)
    assert any("常見錯誤" in slide["speakerNotes"] for slide in slides)
```

- [x] **Step 2: Run it to verify it fails**

Run: `.venv/bin/pytest backend/tests/test_progress_stream.py -q -k scenario_and_practice`

- [x] **Step 3: Replace generic demo bullets with the four-step teaching chain**

```python
_fake_slides(...) -> [
    scenario_with_diagram,
    evidence,
    decision,
    quiz_with_feedback,
]
```

- [x] **Step 4: Run targeted and integration tests**

Run: `.venv/bin/pytest backend/tests/test_content_language.py backend/tests/test_planner.py backend/tests/test_progress_stream.py -q`
