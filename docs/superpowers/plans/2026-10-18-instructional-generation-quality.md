# Instructional Generation Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated course sections teach through explanation, a concrete example, checkable practice, and transfer/recap, with visuals chosen for concept comprehension rather than default flowcharts.

**Architecture:** Add backwards-compatible teaching and visual semantics to Slide IR, then validate a section before it joins the draft package. The planner and section agent author those semantics. Existing web/PPTX renderers consume the IR only and choose deterministic visual treatments from `visualPurpose`.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, Next.js/TypeScript, SVG/Mermaid/PPTX renderers.

**Spec:** `docs/superpowers/specs/2026-10-18-instructional-generation-quality-design.md`

## Global Constraints

- IR is the only source of truth; models output structured JSON, never HTML/PPTX.
- Renderers/exporters are pure IR-to-output transformations and never call a model.
- Keep model selection behind configuration, retain draft-only publication and agent patch staging.
- Deterministic visual order stays Mermaid/SVG, chart, icon, illustration, generated-image fallback.
- Text-labelled diagrams do not use image generation.
- A failed visual or invalid section degrades/retries without aborting other sections.
- Legacy slide JSON keeps working via defaults; no draft migration is required.

## File structure

- `backend/app/schemas/ir.py`: Slide semantic enums/defaults.
- `backend/app/services/instructional_quality.py`: pure quality validator and visual policy.
- `backend/app/services/planner.py`: section teaching blueprint.
- `backend/app/services/tools.py`: model-facing slide schema.
- `backend/app/services/pipeline.py`: per-section validation and retryable progress events.
- `backend/app/demo_pipeline.py`: deterministic learning-loop fixture.
- `backend/app/services/svg_diagrams.py`, `mermaid_assets.py`: diagram-only purpose rendering.
- `backend/app/exporters/pptx.py`, `frontend/components/SlideCanvas.tsx`, `frontend/lib/api.ts`: semantic render treatments.
- `backend/tests/test_instructional_quality.py`: quality policy test suite.

### Task 1: Add backwards-compatible teaching semantics

**Files:**

- Modify: `backend/app/schemas/ir.py`
- Modify: `backend/app/services/tools.py`
- Modify: `backend/tests/test_tools.py`
- Create: `backend/tests/test_instructional_quality.py`

**Interfaces:**

- Consumes: legacy `Slide` JSON without the new fields.
- Produces: `Slide.teaching_role: TeachingRole` and `Slide.visual_purpose: VisualPurpose`, serialized as camel case.

- [ ] **Step 1: Write failing schema/default tests**

```python
from app.schemas.ir import Slide

def test_legacy_slide_defaults_to_safe_semantics():
    slide = Slide.model_validate({"id": "s1", "order": 1, "layout": "bullets", "title": "Git"})
    assert slide.teaching_role == "explain"
    assert slide.visual_purpose == "none"

def test_slide_serializes_semantics_in_camel_case():
    slide = Slide.model_validate({
        "id": "s2", "order": 2, "layout": "twoCol", "title": "Compare",
        "teachingRole": "worked_example", "visualPurpose": "comparison",
    })
    assert slide.model_dump(by_alias=True)["teachingRole"] == "worked_example"
    assert slide.model_dump(by_alias=True)["visualPurpose"] == "comparison"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `../.venv/bin/pytest tests/test_instructional_quality.py -q -k semantics`

Expected: FAIL because `Slide` has no semantic fields.

- [ ] **Step 3: Implement minimal schema fields**

```python
TeachingRole = Literal["explain", "worked_example", "guided_practice",
                       "check_understanding", "transfer", "recap"]
VisualPurpose = Literal["comparison", "sequence", "mechanism",
                        "scenario", "evidence", "none"]

class Slide(_IRBase):
    # retain every existing field
    teaching_role: TeachingRole = "explain"
    visual_purpose: VisualPurpose = "none"
```

- [ ] **Step 4: Make the tool schema complete**

Add `teachingRole` and `visualPurpose` to `SLIDE_SCHEMA.properties`, with exact enums and descriptions telling the model that `none` is valid and a flowchart is only appropriate for sequence/mechanism. Add both to the schema’s required list for newly generated slides.

- [ ] **Step 5: Add a schema-drift regression and run focused tests**

```python
def test_slide_schema_exposes_semantic_fields():
    _assert_schema_matches_model(SLIDE_SCHEMA, Slide)
    assert {"teachingRole", "visualPurpose"} <= set(SLIDE_SCHEMA["properties"])
```

Run: `../.venv/bin/pytest tests/test_tools.py tests/test_instructional_quality.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/ir.py backend/app/services/tools.py backend/tests/test_tools.py backend/tests/test_instructional_quality.py
git commit -m "feat: add instructional slide semantics"
```

### Task 2: Build a deterministic teaching-quality validator

**Files:**

- Create: `backend/app/services/instructional_quality.py`
- Modify: `backend/tests/test_instructional_quality.py`

**Interfaces:**

- Consumes: `list[Slide]` belonging to one planned section.
- Produces: `validate_section_quality(slides) -> list[SectionQualityIssue]` and `visual_policy(slide) -> VisualPolicy`.

- [ ] **Step 1: Write failing learning-loop tests**

```python
from app.services.instructional_quality import validate_section_quality

def _slide(role, purpose="none", *, layout="bullets", notes="提问：为什么？\n误区：只改档名。\n过渡：接着比较。"):
    return Slide(id=role, order=1, layout=layout, title=role,
                 teaching_role=role, visual_purpose=purpose, speaker_notes=notes)

def test_valid_learning_loop_has_no_issues():
    slides = [_slide("explain"), _slide("worked_example", "scenario"),
              _slide("check_understanding", notes="正确答案：B。\n常见错误：A。\n反馈：版本号没有记录差异。"),
              _slide("transfer")]
    assert validate_section_quality(slides) == []

def test_missing_practice_reports_stable_reason():
    codes = {x.code for x in validate_section_quality(
        [_slide("explain"), _slide("worked_example"), _slide("recap")])}
    assert "missing_practice" in codes

def test_comparison_as_flow_diagram_is_rejected():
    slides = [_slide("explain"), _slide("worked_example"), _slide("check_understanding"),
              _slide("recap"), _slide("transfer", "comparison", layout="diagram")]
    assert "comparison_rendered_as_flow" in {x.code for x in validate_section_quality(slides)}
```

- [ ] **Step 2: Run the tests and verify failure**

Run: `../.venv/bin/pytest tests/test_instructional_quality.py -q -k 'learning_loop or practice or comparison'`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement pure validator and policy**

```python
@dataclass(frozen=True)
class SectionQualityIssue:
    code: str
    message: str

@dataclass(frozen=True)
class VisualPolicy:
    render_treatment: Literal["diagram", "comparison", "case", "evidence", "none"]
    requires_diagram: bool

def validate_section_quality(slides: list[Slide]) -> list[SectionQualityIssue]:
    roles = {slide.teaching_role for slide in slides}
    issues: list[SectionQualityIssue] = []
    if "explain" not in roles:
        issues.append(SectionQualityIssue("missing_explain", "缺少概念讲解页"))
    if "worked_example" not in roles:
        issues.append(SectionQualityIssue("missing_worked_example", "缺少具体工程案例"))
    if not roles & {"guided_practice", "check_understanding"}:
        issues.append(SectionQualityIssue("missing_practice", "缺少可检查练习"))
    if not roles & {"transfer", "recap"}:
        issues.append(SectionQualityIssue("missing_transfer_or_recap", "缺少迁移或小结"))
    return issues
```

Implement `visual_policy` with these exact mappings: `sequence/mechanism → diagram`, `comparison → comparison`, `scenario → case`, `evidence → evidence`, `none → none`. The function cannot import a renderer or model.
Then add exact note checks for a practice role (correct answer, misconception and feedback), worked-example checks (role, constraint, evidence and consequence), and purpose/layout compatibility. Every failure uses a stable `SectionQualityIssue.code`.

- [ ] **Step 4: Test every purpose mapping**

```python
def test_visual_policy_only_requires_diagrams_for_sequence_or_mechanism():
    assert visual_policy(_slide("explain", "sequence")).requires_diagram is True
    assert visual_policy(_slide("explain", "mechanism")).requires_diagram is True
    assert visual_policy(_slide("explain", "comparison")).requires_diagram is False
    assert visual_policy(_slide("explain", "none")).requires_diagram is False
```

Run: `../.venv/bin/pytest tests/test_instructional_quality.py tests/test_tools.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/instructional_quality.py backend/tests/test_instructional_quality.py
git commit -m "feat: validate instructional slide quality"
```

### Task 3: Plan and author the learning loop

**Files:**

- Modify: `backend/app/services/planner.py`
- Modify: `backend/app/services/pipeline.py`
- Modify: `backend/app/services/tools.py`
- Modify: `backend/app/demo_pipeline.py`
- Modify: `backend/tests/test_planner.py`
- Modify: `backend/tests/test_content_language.py`
- Modify: `backend/tests/test_pipeline.py`

**Interfaces:**

- Consumes: `PlannerRequest`, then `PlannedSection`.
- Produces: `PlannedSection.teaching_arc` containing `situation`, `misconception`, `practice`, and `transfer_prompt`.

- [ ] **Step 1: Write failing planner tests**

```python
def test_planned_section_accepts_teaching_arc():
    section = PlannedSection.model_validate({
        "title": "Merge", "minutes": 10, "objectiveIds": ["LO1"],
        "teachingArc": {
            "situation": "两人同时改同一行", "misconception": "最后保存者总是对的",
            "practice": "选择合并步骤", "transferPrompt": "下次冲突怎么避免？",
        },
    })
    assert section.teaching_arc.practice == "选择合并步骤"

def test_fallback_outline_has_teaching_arcs():
    outline = _fallback(PlannerRequest(topic="Git", audience="beginner", duration_min=45), "test")
    assert all(s.teaching_arc.situation and s.teaching_arc.practice for s in outline.sections)
```

- [ ] **Step 2: Run and verify failure**

Run: `../.venv/bin/pytest tests/test_planner.py -q -k teaching_arc`

Expected: FAIL because `TeachingArc` does not exist.

- [ ] **Step 3: Implement the blueprint**

Add a `TeachingArc(BaseModel)` with the four string fields and `Field(default_factory=TeachingArc)` to `PlannedSection`. Extend the planner JSON example and hard requirements. Update `_fallback()` with specific non-empty situation/practice/transfer values without changing its resilience behavior.

- [ ] **Step 4: Pass blueprint and strict semantic instructions to the section agent**

Add this exact contract to `SECTION_SYSTEM_PROMPT`:

```text
本节必须按 teachingArc 形成：explain → worked_example → guided_practice 或 check_understanding → transfer 或 recap。
案例页必须写出角色、约束、证据和后果；练习页必须有学生可执行的判断/操作及讲稿反馈。
visualPurpose=sequence/mechanism 时才调用 make_diagram；comparison/scenario/evidence/none 不得为了配图调用流程图。
```

In `section_user_prompt()`, print all four arc values under `教学蓝图`.

- [ ] **Step 5: Upgrade deterministic generation fixture**

Each fake section must emit, in order:

```python
[
    {"teachingRole": "explain", "visualPurpose": "mechanism", "layout": "diagram"},
    {"teachingRole": "worked_example", "visualPurpose": "scenario", "layout": "twoCol"},
    {"teachingRole": "check_understanding", "visualPurpose": "none", "layout": "quiz"},
    {"teachingRole": "transfer", "visualPurpose": "comparison", "layout": "twoCol"},
]
```

Only the mechanism slide calls `make_diagram`. The practice notes must include correct answer, common misconception and feedback; the example must name role, constraint, evidence and consequence.

- [ ] **Step 6: Run authoring tests**

Run: `../.venv/bin/pytest tests/test_planner.py tests/test_content_language.py tests/test_pipeline.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/planner.py backend/app/services/pipeline.py backend/app/services/tools.py backend/app/demo_pipeline.py backend/tests/test_planner.py backend/tests/test_content_language.py backend/tests/test_pipeline.py
git commit -m "feat: generate a structured learning arc"
```

### Task 4: Isolate invalid sections and report quality outcomes

**Files:**

- Modify: `backend/app/services/pipeline.py`
- Modify: `backend/tests/test_pipeline.py`

**Interfaces:**

- Consumes: raw slide dictionaries staged by one `SectionDeps`.
- Produces: valid section content only; invalid sections report stable retry codes with `status="failed"`.

- [ ] **Step 1: Write a failing failure-isolation test**

```python
async def test_invalid_section_is_dropped_without_aborting_others():
    result = await generate_course(_req(), _deps(client=_OneBadSectionModel()))
    assert result.package.slide_deck is not None
    assert any(e.status == "failed" and "missing_practice" in e.detail for e in result.events)
    assert len(result.agents) == 3
    assert result.package.status == "draft"
```

Use a fake model whose first section omits the practice role but whose remaining sections are valid.

- [ ] **Step 2: Run and verify failure**

Run: `../.venv/bin/pytest tests/test_pipeline.py -q -k invalid_section_is_dropped`

Expected: FAIL because the pipeline accepts all staged slides.

- [ ] **Step 3: Validate before global assembly**

After the agent returns, validate that section’s raw slide dictionaries as `Slide` instances. On any quality issue, clear only that `SectionDeps.written_slides` and `written_plan`, retain agent audit calls, discard its local assets, and emit:

```python
codes = ",".join(issue.code for issue in issues)
emit("分节生成", section_percent(index, 1.0), f"「{section.title}」待重试:{codes}",
     kind="section", status="failed", section_index=index, section_title=section.title)
```

- [ ] **Step 4: Correct visual-progress reporting**

Replace the hard-coded “all diagram” message with counts from validated `Slide.visual_purpose`, for example `视觉用途：机制 2、情境 3、对照 1；流程图仅用于机制/步骤`.

- [ ] **Step 5: Run pipeline regression**

Run: `../.venv/bin/pytest tests/test_pipeline.py tests/test_progress_stream.py -q`

Expected: PASS; progress is monotonic and an invalid section does not terminate the package.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/pipeline.py backend/tests/test_pipeline.py backend/tests/test_progress_stream.py
git commit -m "feat: isolate instructional quality failures"
```

### Task 5: Render each visual purpose appropriately

**Files:**

- Modify: `backend/app/services/svg_diagrams.py`
- Modify: `backend/app/services/mermaid_assets.py`
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/app/exporters/pptx.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/SlideCanvas.tsx`
- Modify: `backend/tests/test_mermaid_assets.py`
- Create: `frontend/tests/slide_canvas.test.mjs`

**Interfaces:**

- Consumes: `Slide.visual_purpose`, layout, and existing asset IDs.
- Produces: diagram treatment only for sequence/mechanism; comparison/case/evidence/none each gets an intentional deterministic layout.

- [ ] **Step 1: Write failing purpose-rendering tests**

```python
def test_render_treatment_is_not_a_flowchart_for_every_purpose():
    assert render_treatment("sequence") == "diagram"
    assert render_treatment("mechanism") == "diagram"
    assert render_treatment("comparison") == "comparison"
    assert render_treatment("scenario") == "case"
    assert render_treatment("evidence") == "evidence"
```

```javascript
test("comparison is rendered as comparison rather than a course-flow fallback", async () => {
  const source = await readFile("components/SlideCanvas.tsx", "utf8");
  assert.match(source, /ComparisonFrame/);
  assert.match(source, /visualPurpose === "comparison"/);
});
```

- [ ] **Step 2: Run and verify failure**

Run: `../.venv/bin/pytest tests/test_mermaid_assets.py -q -k treatment && cd frontend && node --test tests/slide_canvas.test.mjs`

Expected: FAIL because purpose renderer components do not exist.

- [ ] **Step 3: Restrict diagram rendering**

Add a keyword-only purpose argument to `render_course_svg` and `render_mermaid_png`. Resolve it from the owning slide in `demo.py`, not a query parameter. Accept only `sequence` and `mechanism`; choose a stepper/timeline for sequence and a relationship layout for mechanism. Raise `ValueError` for every other purpose.

- [ ] **Step 4: Add pure semantic render treatments**

In `SlideCanvas.tsx`, add local pure components:

```tsx
function ComparisonFrame({ items }: { items: string[] }) { /* criteria/options, no arrows */ }
function ScenarioFrame({ title, items }: { title: string; items: string[] }) { /* role, constraint, consequence */ }
function EvidenceFrame({ items }: { items: string[] }) { /* claim plus source/code/data evidence */ }
```

Choose them from `slide.visualPurpose` before the generic diagram fallback. In `pptx.py`, mirror them using native cards/text boxes. Only insert a diagram picture when the purpose is sequence/mechanism.

- [ ] **Step 5: Keep failures readable**

If an allowed diagram asset fails, retain its semantic text/card fallback on both web and PPTX. For `none`, render no blank visual region and make no asset request.

- [ ] **Step 6: Run rendering tests**

Run: `../.venv/bin/pytest tests/test_mermaid_assets.py tests/test_teacher_courses_api.py -q && cd frontend && node --test tests/*.test.mjs && npx tsc --noEmit --incremental false`

Expected: PASS; comparison/scenario/evidence have no automatic Mermaid flow and valid sequence/mechanism still export deterministic graphics.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/svg_diagrams.py backend/app/services/mermaid_assets.py backend/app/api/routes/demo.py backend/app/exporters/pptx.py backend/tests/test_mermaid_assets.py frontend/lib/api.ts frontend/components/SlideCanvas.tsx frontend/tests/slide_canvas.test.mjs
git commit -m "feat: render instructional visual purposes"
```

### Task 6: Full verification and evidence

**Files:**

- Modify: `backend/README.md` only if the generation contract section becomes inaccurate.
- Test: `backend/tests/`, `frontend/tests/`.

**Interfaces:**

- Consumes: full source tree and deterministic demo endpoint.
- Produces: evidence that every generated section is structured, resilient, draft-only and exportable.

- [ ] **Step 1: Run backend suite**

Run: `../.venv/bin/pytest tests -q`

Expected: PASS.

- [ ] **Step 2: Run frontend suite, static check and production build**

Run: `cd frontend && node --test tests/*.test.mjs && npx tsc --noEmit --incremental false && npm run build`

Expected: every command exits 0.

- [ ] **Step 3: Verify end-to-end generated deck semantics**

Extend the existing demo-generation test to assert, for each section:

```python
assert {"explain", "worked_example"} <= roles
assert roles & {"guided_practice", "check_understanding"}
assert roles & {"transfer", "recap"}
assert package["chapter"]["status"] == "draft"
```

Also assert a comparison slide does not export a Mermaid picture.

- [ ] **Step 4: Document only factual contract changes**

If needed, document `teachingRole`/ `visualPurpose` and the pre-render quality gate in `backend/README.md`; never copy model-private prompts into documentation.

- [ ] **Step 5: Review and commit**

Run: `git diff --check && git status --short`

```bash
git add backend/README.md backend/tests frontend/tests
git commit -m "test: verify instructional generation quality"
```

## Spec coverage review

- Teaching blueprint and full learning loop: Task 3.
- Backward-compatible IR semantics: Task 1.
- Stable quality checks and reason codes: Task 2.
- Per-section isolation and retryability: Task 4.
- Deterministic visual-purpose mapping/no-default-flowchart rule: Task 5.
- Pure renderer/exporter, draft-only behavior, regression evidence: Task 6.
