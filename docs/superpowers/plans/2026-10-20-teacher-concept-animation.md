# Teacher concept animation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let teachers preview a reviewed, content-driven teaching animation for an eligible course slide without changing the existing slide content or PPTX export.

**Architecture:** `Slide.animation` is optional, validated IR that references only title, existing bullet indices, or an existing visual id. The existing section agent may propose this structure within the normal slide JSON; the existing edit agent stores it as a proposed patch until the teacher approves it. A client-only `SlideAnimationPreview` owns playback and passes a small presentation state into the existing slide renderer, which remains a pure rendering of the same slide IR.

**Tech Stack:** Python 3.12, Pydantic v2, FastAPI demo pipeline, Next.js 16, React 19, TypeScript, existing CSS/Tailwind utilities, Node built-in test runner, pytest.

**Spec:** `docs/superpowers/specs/2026-10-20-concept-animation-design.md`

## Global Constraints

- Animation is teacher-side preview only in this implementation; do not add student-player autoplay.
- Do not add Remotion, TTS, ffmpeg, a media job, or a frontend animation dependency.
- `Slide.animation` must be optional, camelCase over the API, and harmless to legacy stored slides.
- The animation plan may only reference existing slide elements; it must never contain new lesson content or executable markup.
- AI-generated animation remains draft data and a patch may only change `artifacts` through the existing confirmed `apply_patch` path.
- The PPTX exporter intentionally ignores animation metadata and keeps its present content output.
- The UI must respect `prefers-reduced-motion: reduce`: immediately show the completed static slide and schedule no timer.

---

## File structure

| File | Responsibility |
| --- | --- |
| `backend/app/schemas/ir.py` | Defines `AnimationStep`, `SlideAnimation`, and the optional validated `Slide.animation` field. |
| `backend/app/services/animation.py` | Pure normalization/validation used to drop an invalid AI animation plan without discarding a valid generated slide. |
| `backend/app/services/pipeline.py` | Tells the section agent when an animation is educationally justified and normalizes AI-authored slide JSON before schema validation. |
| `backend/app/services/tools.py` | Makes the structured `animation` field explicit in `write_section` and `patch_slide` tool descriptions. |
| `backend/tests/test_slide_animation.py` | Exercises legacy compatibility, target/timing validation, and invalid-plan degradation. |
| `backend/tests/test_edit.py` | Proves an animation patch remains proposed until it is explicitly applied. |
| `frontend/lib/api.ts` | Mirrors the optional animation type in the frontend `Slide` contract. |
| `frontend/components/SlideAnimationPreview.tsx` | Owns teacher-only timer, replay, pause, completed-state, and reduced-motion behavior. |
| `frontend/components/SlideCanvas.tsx` | Accepts a presentational animation state and marks title, bullets, and visual regions without changing slide text. |
| `frontend/lib/i18n-config.ts` | Adds teacher-visible preview controls in every supported interface language. |
| `frontend/app/globals.css` | Supplies bounded reveal/emphasis styles and the reduced-motion fallback. |
| `frontend/tests/slide-animation-preview.test.mjs` | Guards the component contract and explicit accessibility behavior. |
| `frontend/tests/teacher-workspace-layout.test.mjs` | Guards that the teacher workspace exposes preview without adding a new material tab or export type. |

## Task 1: Add the safe animation IR contract

**Files:**
- Modify: `backend/app/schemas/ir.py:150-205`
- Create: `backend/app/services/animation.py`
- Create: `backend/tests/test_slide_animation.py`

**Interfaces:**
- Produces `AnimationStep(kind, target, at_ms, duration_ms)` and `SlideAnimation(autoplay, steps)` serialized as `animation`, `atMs`, and `durationMs`.
- Produces `normalize_slide_animation(raw_slide: dict[str, Any]) -> tuple[dict[str, Any], str | None]`, where the result either has a validated plan or no `animation` key.
- Consumes a `Slide` without animation to verify bullet and visual targets against the actual page.

- [ ] **Step 1: Write the failing schema and degradation tests**

```python
def test_legacy_slide_has_no_animation_by_default():
    slide = Slide(id="s1", order=1, layout="bullets", title="Git", bullets=["A", "B"])
    assert slide.animation is None

def test_slide_animation_serializes_in_camel_case():
    slide = Slide.model_validate({
        "id": "s1", "order": 1, "layout": "bullets", "title": "Git",
        "bullets": ["A"],
        "animation": {"autoplay": True, "steps": [
            {"kind": "reveal", "target": "bullet:0", "atMs": 0}
        ]},
    })
    assert slide.model_dump(by_alias=True)["animation"]["steps"][0]["atMs"] == 0

def test_invalid_generated_animation_is_dropped_but_the_slide_survives():
    raw, warning = normalize_slide_animation({
        "id": "s1", "order": 1, "layout": "bullets", "title": "Git",
        "bullets": ["A"],
        "animation": {"steps": [{"kind": "reveal", "target": "bullet:9", "atMs": 0}]},
    })
    assert raw["id"] == "s1"
    assert "animation" not in raw
    assert warning == "animation_unknown_target"
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run: `../.venv/bin/pytest tests/test_slide_animation.py -v`

Expected: import failure for `SlideAnimation`/`normalize_slide_animation` or a missing `animation` field.

- [ ] **Step 3: Implement strict, backwards-compatible IR types**

In `backend/app/schemas/ir.py`, add these models immediately before `Slide`:

```python
AnimationKind = Literal["reveal", "emphasis", "sequence"]

class AnimationStep(_IRBase):
    kind: AnimationKind
    target: str
    at_ms: int = Field(ge=0, le=20_000)
    duration_ms: int = Field(default=700, ge=100, le=3_000)

class SlideAnimation(_IRBase):
    autoplay: bool = True
    steps: list[AnimationStep] = Field(default_factory=list, max_length=8)
```

Add `animation: SlideAnimation | None = None` to `Slide`. In the existing
model validator, reject direct/manual invalid plans: duplicate `(target, at_ms)`
pairs, targets other than `title`, `bullet:<valid index>`, and
`visual:<existing visual id>`, plus `sequence` plans without a visual target.
Do not reject a planless slide.

In `backend/app/services/animation.py`, first remove `animation` from a copy
of raw AI slide JSON, validate the base `Slide`, then validate/reinsert the
plan. Catch only `pydantic.ValidationError`; return the original valid slide
without the field and a stable warning code (`animation_invalid_shape`,
`animation_unknown_target`, or `animation_invalid_sequence`) rather than
allowing one bad animation to fail the whole section.

- [ ] **Step 4: Run the focused tests and inspect serialization**

Run: `../.venv/bin/pytest tests/test_slide_animation.py tests/test_ir.py -v`

Expected: PASS, including legacy `Slide` construction and camelCase output.

- [ ] **Step 5: Commit the isolated IR contract**

```bash
git add backend/app/schemas/ir.py backend/app/services/animation.py backend/tests/test_slide_animation.py
git commit -m "feat: add validated slide animation IR"
```

## Task 2: Generate and review animation plans without weakening authority

**Files:**
- Modify: `backend/app/services/pipeline.py:88-112, 500-590`
- Modify: `backend/app/services/tools.py:51-80, 619-630`
- Modify: `backend/app/services/edit.py:115-165`
- Modify: `backend/tests/test_pipeline.py`
- Modify: `backend/tests/test_edit.py`

**Interfaces:**
- Consumes `normalize_slide_animation` from Task 1 before each raw generated slide becomes `Slide` IR.
- Produces static warning data for invalid generated animation while retaining the generated slide.
- Uses the pre-existing `patch_slide` and `apply_patch` interfaces; no new write endpoint is introduced.

- [ ] **Step 1: Write the failing generation and review tests**

```python
class _AnimationSectionModel(FakeSectionModel):
    async def complete(self, *, model, messages, tools=None, temperature=0.0):
        reply = await super().complete(model=model, messages=messages, tools=tools, temperature=temperature)
        for call in reply.tool_calls:
            if call.name == "write_section":
                call.arguments["slides"][0]["animation"] = {"steps": [{"kind": "reveal", "target": "bullet:0", "atMs": 0}]}
                call.arguments["slides"][1]["animation"] = {"steps": [{"kind": "reveal", "target": "bullet:99", "atMs": 0}]}
        return reply

async def test_section_generation_keeps_valid_animation_and_discards_only_bad_plan():
    result = await generate_course(_req(), _deps(client=_AnimationSectionModel()))
    assert result.package.slide_deck.slides[0].animation is not None
    assert result.package.slide_deck.slides[1].animation is None
    assert any("animation_unknown_target" in warning for warning in result.assembly_errors)

async def test_animation_patch_is_proposed_before_teacher_applies_it():
    package = await _package()
    store = InMemoryPatchStore()
    result = await edit_artifact(
        client=ScriptedChatClient([
            ChatMessage(tool_calls=[ToolCall(id="a1", name="read_slide", arguments={"slide_id": "s3"})]),
            ChatMessage(tool_calls=[ToolCall(id="a2", name="patch_slide", arguments={
                "slide_id": "s3",
                "patch": {"animation": {"steps": [{"kind": "reveal", "target": "bullet:0", "atMs": 0}]}},
                "reason": "讓學生先聚焦第一個判斷依據",
            })]),
        ]),
        model="fake", package=package, message="讓第 3 頁逐項顯示", store=store,
    )
    patch = next(p for p in result.proposed if "animation" in p.payload)
    assert find_slide(package, patch.target_id).animation is None
    apply_patch(package, store, patch.id)
    assert find_slide(package, patch.target_id).animation is not None
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `../.venv/bin/pytest tests/test_pipeline.py tests/test_edit.py -k animation -v`

Expected: FAIL because generated raw slides are not normalized and the agent prompt/tool descriptions do not request animation plans.

- [ ] **Step 3: Add bounded generation instructions and normalization**

In `SECTION_AGENT_PROMPT` in `pipeline.py`, state that `animation` is optional
and only appropriate for:

```text
mechanism/sequence: reveal an existing visual region after the explanation;
worked_example/scenario: reveal existing bullet facts in context → constraint → evidence → consequence order;
explain: reveal existing bullets only.
```

State that title/quiz pages normally have no plan and plans may not add content.
At the raw slide-to-`Slide.model_validate` seam, call
`normalize_slide_animation(raw)`, retain the base slide on warning, append the
stable code to `PipelineResult.assembly_errors`, and include it in the
existing completed-section review detail. Initialize the shared `dropped:
list[str]` accumulator before the nested `one_section` coroutine is declared;
normalization executes inside that coroutine, while the current assembly-only
declaration is too late for section-level warnings.

In `tools.py`, document the exact JSON structure for `animation` in the
`write_section` slide schema and `_PATCH_PARAMS` description, but keep the
existing generic patch object. In `edit.py`, retain the current per-field split:
the existing `else: field_payloads.append({field: value})` already makes one
atomic `{"animation": {"steps": [{"kind": "reveal", "target": "bullet:0", "atMs": 0}]}}` proposal; add a regression assertion rather than
new persistence behavior.

- [ ] **Step 4: Run focused and full backend regression tests**

Run: `../.venv/bin/pytest tests/test_slide_animation.py tests/test_pipeline.py tests/test_edit.py tests/test_ir.py -v`

Expected: PASS. The agent-read-before-patch and no-unconfirmed-write tests must continue to pass unchanged.

- [ ] **Step 5: Commit the pipeline/review integration**

```bash
git add backend/app/services/pipeline.py backend/app/services/tools.py backend/app/services/edit.py backend/tests/test_pipeline.py backend/tests/test_edit.py
git commit -m "feat: propose reviewable teaching animations"
```

## Task 3: Build a teacher-only playback controller

**Files:**
- Modify: `frontend/lib/api.ts:216-238`
- Create: `frontend/components/SlideAnimationPreview.tsx`
- Modify: `frontend/components/SlideCanvas.tsx:34-330, 463-590`
- Create: `frontend/tests/slide-animation-preview.test.mjs`

**Interfaces:**
- `Slide.animation?: { autoplay: boolean; steps: AnimationStep[] }` mirrors the API exactly.
- `SlideAnimationPreview({ slide, diagramUrl, children })` supplies
  `AnimationPresentation = { revealedTargets: ReadonlySet<string>; emphasizedTarget: string | null }` to its render prop.
- `SlideFrame` consumes `animationPresentation?: AnimationPresentation`; it never starts timers or mutates a slide.

- [ ] **Step 1: Write the failing frontend component contract tests**

```js
test("animation preview owns timer and replay while SlideFrame stays presentational", async () => {
  const preview = await readFile(new URL("../components/SlideAnimationPreview.tsx", import.meta.url), "utf8");
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");
  assert.match(preview, /prefers-reduced-motion/);
  assert.match(preview, /clearTimeout/);
  assert.match(preview, /Replay/);
  assert.match(canvas, /animationPresentation/);
  assert.doesNotMatch(canvas, /setTimeout/);
});

test("renderer only marks existing title bullet and visual targets", async () => {
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");
  assert.match(canvas, /data-animation-target=\{`bullet:\$\{i\}`\}/);
  assert.match(canvas, /data-animation-target=\{`visual:\$\{visual\.id\}`\}/);
});
```

- [ ] **Step 2: Run the test and verify failure**

Run: `node --test tests/slide-animation-preview.test.mjs`

Expected: FAIL because neither component nor `animationPresentation` exists.

- [ ] **Step 3: Implement deterministic playback and presentation state**

Create `SlideAnimationPreview.tsx` as a client component. It must:

1. expose an opt-in `Preview animation` button when `slide.animation.steps`
   has at least one step and show a plain `No animation planned for this slide`
   note otherwise;
2. initially render its child with all targets revealed (the normal editing
   canvas remains fully readable);
3. on preview, reset to zero revealed targets, schedule the sorted `atMs`
   steps with `window.setTimeout`, reveal the matching target, and set the
   current emphasis until its `durationMs` completes;
4. expose Pause/Resume and Replay; clear every timer before replay, on slide
   id change, and on component unmount; and
5. use `matchMedia("(prefers-reduced-motion: reduce)")` to skip scheduling,
   keep every target visible, and show a concise reduced-motion status.

Define `AnimationPresentation` in this component and pass it into exported
`SlideFrame`. In `SlideCanvas.tsx`, accept the optional prop through
`SlideFrame`, `SlideBody`, `SlideTitle`, `Bullets`, and `DiagramPreview`.
Each target receives `data-animation-target` and classes only; it always
retains the exact text/asset from `Slide`. A visual plan reveals the whole
existing diagram region, not individual SVG nodes. Do not hide quiz choices
or change thumbnail behavior.

- [ ] **Step 4: Run the frontend test and typecheck**

Run: `node --test tests/slide-animation-preview.test.mjs && npx tsc --noEmit`

Expected: PASS with no TypeScript errors.

- [ ] **Step 5: Commit the playback controller**

```bash
git add frontend/lib/api.ts frontend/components/SlideAnimationPreview.tsx frontend/components/SlideCanvas.tsx frontend/tests/slide-animation-preview.test.mjs
git commit -m "feat: add teacher slide animation preview"
```

## Task 4: Place the preview in the teacher slide workspace and localize it

**Files:**
- Modify: `frontend/components/SlideCanvas.tsx:463-590`
- Modify: `frontend/lib/i18n-config.ts`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/tests/teacher-workspace-layout.test.mjs`

**Interfaces:**
- `SlideCanvas` embeds `SlideAnimationPreview` only for its full-size active slide rendering; `SlideThumbnail` keeps `SlideFrame` static.
- Uses new `slide` dictionary keys: `previewAnimation`, `pauseAnimation`, `resumeAnimation`, `replayAnimation`, `noAnimation`, and `reducedMotion`.

- [ ] **Step 1: Write the failing workspace/layout assertions**

```js
test("teacher slide stage previews approved animation without creating a new material tab", async () => {
  const canvas = await readFile(new URL("../components/SlideCanvas.tsx", import.meta.url), "utf8");
  const page = await readFile(pagePath, "utf8");
  assert.match(canvas, /SlideAnimationPreview/);
  assert.match(canvas, /t\.slide\.previewAnimation/);
  assert.doesNotMatch(page, /value: "animation"/);
});

test("animation CSS has a completed reduced-motion presentation", async () => {
  const css = await readFile(stylesPath, "utf8");
  assert.match(css, /\[data-animation-state="hidden"\]/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});
```

- [ ] **Step 2: Run the workspace test and verify failure**

Run: `node --test tests/teacher-workspace-layout.test.mjs`

Expected: FAIL because the active slide has no preview controller or animation
copy/styles.

- [ ] **Step 3: Integrate with the existing teacher stage and CSS**

Wrap only the non-editing, full-size `SlideFrame` branch in
`SlideAnimationPreview`; leave the manual editor and left-hand thumbnail rail
static. Add translations for English, Traditional Chinese, and Simplified
Chinese beside the existing `slide` messages.

In `globals.css`, use short opacity/transform/outline transitions for
`[data-animation-state="hidden"]`, `visible`, and `emphasis`; never animate
layout dimensions. The completed state is the normal slide appearance. In the
reduced-motion media query, remove transform/transition but retain a visible
current-step color/outline state. Do not add vertical dividers, new workspace
tabs, or export controls.

- [ ] **Step 4: Run all frontend checks and visually inspect the real stage**

Run:

```bash
node --test tests/slide-animation-preview.test.mjs tests/teacher-workspace-layout.test.mjs
npx tsc --noEmit
npm run build
```

Expected: all tests pass and the production build succeeds. Open a generated
teacher chapter, select an eligible slide, use Preview animation, then replay
and pause it; verify the normal slide remains fully readable before preview.

- [ ] **Step 5: Commit the teacher experience**

```bash
git add frontend/components/SlideCanvas.tsx frontend/lib/i18n-config.ts frontend/app/globals.css frontend/tests/teacher-workspace-layout.test.mjs
git commit -m "feat: preview teaching animations in course workspace"
```

## Task 5: Protect exports and close the implementation evidence

**Files:**
- Modify: `backend/tests/test_exporters.py`
- Modify: `backend/tests/test_slide_animation.py`
- Modify: `docs/superpowers/specs/2026-10-20-concept-animation-design.md`

**Interfaces:**
- `slide_deck_to_pptx(deck)` remains unchanged in signature and ignores the
  optional `Slide.animation` field.

- [ ] **Step 1: Write the failing exporter regression test**

```python
def test_pptx_export_ignores_animation_metadata_but_keeps_slide_content():
    deck = SlideDeck(artifact_id="deck", slides=[Slide(
        id="s1", order=1, layout="bullets", title="Commit",
        bullets=["History is visible"],
        animation=SlideAnimation(steps=[AnimationStep(kind="reveal", target="bullet:0", at_ms=0)]),
    )])
    pptx = slide_deck_to_pptx(deck)
    assert b"Commit" in pptx
```

- [ ] **Step 2: Run the test and verify it fails only if metadata leaks into exporter logic**

Run: `../.venv/bin/pytest tests/test_exporters.py -k animation -v`

Expected: PASS once the IR contract is accepted by the existing pure exporter;
no exporter model call or animation-specific rendering is added.

- [ ] **Step 3: Record verification evidence and reconcile the spec**

Update the spec's test/acceptance paragraph to record the actual teacher-only
scope and link the completed test commands. Confirm that no production source
imports Remotion/TTS/ffmpeg and `git diff --check` reports no whitespace
errors.

- [ ] **Step 4: Run the final targeted regression suite**

Run:

```bash
../.venv/bin/pytest tests/test_slide_animation.py tests/test_pipeline.py tests/test_edit.py tests/test_exporters.py tests/test_ir.py -v
cd frontend && node --test tests/slide-animation-preview.test.mjs tests/teacher-workspace-layout.test.mjs && npx tsc --noEmit && npm run build
```

Expected: PASS. Capture one teacher-preview screenshot in normal motion and
one reduced-motion completed state for the discussion evidence folder if the
team wants to cite the feature later.

- [ ] **Step 5: Commit the final regression evidence**

```bash
git add backend/tests/test_exporters.py backend/tests/test_slide_animation.py docs/superpowers/specs/2026-10-20-concept-animation-design.md
git commit -m "test: protect static animation export behavior"
```
