# Instructional generation quality design

## Goal

Make generated teacher courseware teach a concept deliberately rather than
fill slides with information. Every instructional segment should form a
visible learning loop:

`explain → worked example → guided practice/check → transfer or recap`.

Visuals must explain the concept at hand. A diagram is not a decorative
requirement and a generic process flow must not become the default visual.

## Scope and non-goals

This change applies to the teacher-side course-generation pipeline, including
the section agent, structured courseware IR, deterministic visual planning,
quality checks, and the existing webpage/PPTX renderers.

It does not change publication authority, introduce automatic publishing,
name a model in source code, or let a renderer call an LLM. Generated work
continues to be a draft and remains editable/reviewable by a teacher.

## Content design

### Teaching blueprint

Before authoring slide content, the pipeline derives a per-section teaching
blueprint from the outline and learning objectives. A blueprint records:

- the concept students must be able to use;
- a concrete software-engineering situation, including actors, constraint and
  consequence;
- the misconception or tempting incorrect decision to surface;
- the practice/check that supplies observable evidence of understanding; and
- the transfer or recap that links the concept to a next decision.

The blueprint is an internal planning object. It informs generation and
validation but is not an independently publishable artifact.

### Slide teaching contract

The `Slide` IR gains optional, backwards-compatible metadata:

- `teaching_role`: `explain`, `worked_example`, `guided_practice`,
  `check_understanding`, `transfer`, or `recap`.
- `visual_purpose`: `comparison`, `sequence`, `mechanism`, `scenario`,
  `evidence`, or `none`.

Older stored slides receive safe defaults at schema load, so existing courses
and exporters continue to render. New generation must set both fields.

Each section must include at least one `explain`, one `worked_example`, one
practice/check role, and one `transfer` or `recap` role. A practice/check
slide carries a student action, an answer or assessment basis, one anticipated
misconception, and feedback in speaker notes. Worked examples include the
context, evidence and consequence; they cannot be a definition renamed as a
case.

Speaker notes remain the single source for narration. For newly generated
slides, they additionally contain a teacher move (question, demonstration or
prompt), anticipated response/misconception, and transition to the next move.

## Visual design

Visual choice is an explicit instructional decision, not a blanket generation
step:

| Teaching need | `visual_purpose` | Deterministic treatment |
| --- | --- | --- |
| Trade-offs or alternatives | `comparison` | comparison table/cards with shared criteria |
| Ordered steps | `sequence` | timeline or stepper |
| Causal/system relationship | `mechanism` | compact labelled relation diagram |
| Human or engineering context | `scenario` | case/evidence card, optional deterministic illustration asset |
| Measured claim or source evidence | `evidence` | chart, code excerpt, source extract or annotated artifact |
| No visual improves comprehension | `none` | deliberately text/practice-led layout |

Mermaid/SVG is reserved for `sequence` and `mechanism` when labels are needed.
It is not selected for comparison, scenario or evidence by default. The visual
planner selects from deterministic assets in the established order:
Mermaid/SVG, chart, icon library, illustration library, then generated imagery
only as a fallback. A failed asset produces the appropriate readable
card/table/text fallback and marks the asset retryable; it never aborts the
whole course package.

## Pipeline and validation

1. The planner asks for an instructional arc and creates a blueprint for each
   section.
2. The section agent reads the blueprint and writes structured `Slide` IR
   through `write_section` as it does today.
3. A deterministic teaching-quality validator checks the required role
   coverage, practice feedback, objective coverage, example specificity, notes
   contract and visual-purpose/layout compatibility.
4. A validation failure is isolated to the affected section. The generation
   job returns its other completed sections, reports the failed section as
   retryable, and never promotes any output beyond draft.
5. The existing renderer/exporter remains a pure IR-to-output transform. It
   chooses the visual component from `visual_purpose`; it does not invent
   pedagogical content or invoke a model.

The validator should report concise machine-readable reasons (for example,
`missing_guided_practice`, `generic_example`, or
`comparison_rendered_as_flow`) so the UI can present an actionable retry
message and tests do not depend on natural-language model output.

## Compatibility and migration

`teaching_role` and `visual_purpose` default on existing IR records. Existing
decks retain their current layout and export successfully. The quality gate is
enforced for new section generation and explicit regeneration, not retroactive
publication of historical drafts. The UI may display a compact semantic label
later, but this scope does not require a component redesign.

## Test strategy and acceptance criteria

Unit tests will verify:

- the planner and section prompts request a full learning loop;
- schema defaults preserve legacy slide JSON;
- a valid generated section satisfies all required teaching roles;
- missing example, practice feedback, or recap/transfer produces the precise
  validation reason;
- each visual purpose maps to the intended deterministic renderer/fallback;
- Mermaid is rejected for a comparison/scenario unless explicitly justified;
- one invalid section does not prevent the rest of the package from completing;
- renderers/exporters receive only IR and make no model calls.

End-to-end tests will generate the deterministic/demo package and assert that
every section contains a concrete scenario, explanation/evidence, checkable
practice with feedback, and transfer/recap, while retaining draft status.

Acceptance is met when a teacher can inspect each section and explain why a
slide exists, what students do with it, and why its visual form helps that
learning action.
