# Semantic Teaching Diagrams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render generated course diagrams with a deterministic visual template that preserves the teaching relationship encoded in Mermaid rather than flattening every graph into the same step strip.

**Architecture:** Mermaid remains compact IR, never browser-executed. `svg_diagrams.py` will classify the graph from its syntax and labels, then render a bounded SVG template: linear sequence, two-party exchange, or decision branch. The teacher workspace only exposes existing animation metadata as a quiet outline badge; it does not alter slide content or publishing state.

**Tech Stack:** Python 3.12, FastAPI, deterministic SVG, pytest, Next.js/TypeScript, Node test runner.

**Spec:** `docs/design/course-generation-design.md`

## Global Constraints

- Keep IR as the only source of truth; do not emit HTML or PPTX from a model.
- Preserve deterministic visuals before generated imagery; diagrams with labels stay SVG/Mermaid-derived.
- Do not alter an artifact without a teacher applying its proposed patch.
- Do not change slide content, components, or published/draft behavior while improving visual treatment.
- One failed asset must retain a readable fallback rather than interrupting a package.

---

### Task 1: Preserve graph semantics in deterministic SVG

**Files:**
- Modify: `backend/tests/test_mermaid_assets.py`
- Modify: `backend/app/services/svg_diagrams.py`

**Interfaces:**
- Consumes: `render_course_svg(code: str) -> str`
- Produces: SVG with `data-template` identifying `step-sequence`, `exchange-lane`, or `decision-branch`.

- [ ] **Step 1: Write the failing test**

```python
def test_course_svg_uses_a_decision_template_when_mermaid_has_yes_no_branches():
    svg = render_course_svg(
        "graph LR\\nA[git pull] --> B{同一区域?}\\nB -- 否 --> C[自动合并]\\nB -- 是 --> D[手动解决]"
    )

    assert 'data-template="decision-branch"' in svg
    assert "自动合并" in svg
    assert "手动解决" in svg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest backend/tests/test_mermaid_assets.py::test_course_svg_uses_a_decision_template_when_mermaid_has_yes_no_branches -q`

Expected: FAIL because the renderer currently falls through to `step-sequence`.

- [ ] **Step 3: Write minimal implementation**

```python
def _decision_branch(labels: list[str], edges: list[Edge]) -> str:
    # Render one central decision diamond and two short, labelled outcomes.
    ...

def render_course_svg(code: str) -> str:
    labels, edges = _graph(code)
    if _has_branch_condition(code, edges):
        template, body = "decision-branch", _decision_branch(labels, edges)
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest backend/tests/test_mermaid_assets.py -q`

Expected: PASS.

### Task 2: Render two-party exchanges without generic flow boxes

**Files:**
- Modify: `backend/tests/test_mermaid_assets.py`
- Modify: `backend/app/services/svg_diagrams.py`

**Interfaces:**
- Consumes: Mermaid labels and directional edges.
- Produces: `data-template="exchange-lane"` for local/remote, user/system, or other two-party exchanges.

- [ ] **Step 1: Write the failing test**

```python
def test_course_svg_uses_exchange_lanes_for_local_remote_sync():
    svg = render_course_svg(
        "graph LR\\nA[开发者A 本地] -->|push| R[远程仓库]\\nR -->|pull| B[开发者B 本地]"
    )

    assert 'data-template="exchange-lane"' in svg
    assert "push" in svg
    assert "pull" in svg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest backend/tests/test_mermaid_assets.py::test_course_svg_uses_exchange_lanes_for_local_remote_sync -q`

Expected: FAIL because current label extraction loses edge labels and renders a generic sequence.

- [ ] **Step 3: Write minimal implementation**

```python
def _exchange_lane(labels: list[str], edges: list[Edge]) -> str:
    # Render endpoints on two lanes and only the named transfers between them.
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest backend/tests/test_mermaid_assets.py -q`

Expected: PASS.

### Task 3: Make a slide animation discoverable in the course outline

**Files:**
- Modify: `frontend/tests/teacher-workspace-layout.test.mjs`
- Modify: `frontend/app/courses/[courseId]/chapters/[chapterId]/page.tsx`

**Interfaces:**
- Consumes: `Slide.animation` from the existing API type.
- Produces: a compact, translated animation marker next to a slide in the course outline only when the slide has animation metadata.

- [ ] **Step 1: Write the failing source-contract test**

```js
assert.match(page, /s\.animation\s*\?\s*<[^>]+.*animation/i);
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test frontend/tests/teacher-workspace-layout.test.mjs`

Expected: FAIL because the outline has no animation marker.

- [ ] **Step 3: Add the minimal quiet marker**

```tsx
{s.animation ? <span aria-label={t.slide.animationAvailable} className="..." /> : null}
```

- [ ] **Step 4: Run test and TypeScript verification**

Run: `node --test frontend/tests/teacher-workspace-layout.test.mjs && npx tsc --noEmit`

Expected: PASS.

### Task 4: Verify visual safety and regressions

**Files:**
- Verify: `backend/tests/test_mermaid_assets.py`
- Verify: `backend/tests/test_slide_animation.py`
- Verify: `frontend/components/SlideCanvas.tsx`
- Verify: `frontend/app/courses/[courseId]/chapters/[chapterId]/page.tsx`

- [ ] **Step 1: Run focused backend and frontend checks**

Run: `.venv/bin/pytest backend/tests/test_mermaid_assets.py backend/tests/test_slide_animation.py -q && node --test frontend/tests/teacher-workspace-layout.test.mjs && npx tsc --noEmit`

Expected: PASS.

- [ ] **Step 2: Run the full backend suite and whitespace check**

Run: `.venv/bin/pytest -q && git diff --check`

Expected: all tests pass; no whitespace errors.

- [ ] **Step 3: Run the UI quality detector once after edits**

Run: `/Users/taylor/.agents/skills/impeccable/scripts/impeccable detect --json frontend/components/SlideCanvas.tsx 'frontend/app/courses/[courseId]/chapters/[chapterId]/page.tsx'`

Expected: inspect and resolve only findings attributable to this small scoped change.
