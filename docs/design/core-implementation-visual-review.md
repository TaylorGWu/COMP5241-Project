# Core implementation: visual revision

Date: 2026-10-27. Scope: the six English slides of the local midterm course's
Core Implementation chapter, not a rebrand or a change to other chapters.

## Current status: superseded and rolled back

The instructor subsequently rejected presentation-specific refinement because
the discussion should represent normal product usage. The Core Implementation
chapter was restored to its pre-redesign six-slide diagram-plus-bullets package
using application version rollback (`version-21`). The specialised diagram-led
deck below is historical, not the current accepted presentation. The MoSCoW
progress chapter and other chapters remain unchanged. Shared diagram readability
improvements requested separately are retained.

Important provenance correction: the original English package was also authored
as IR by the assistant, not produced by clicking Build in the product. Restoring
its default style does not constitute runtime-generation evidence. A genuine
generation demonstration must use the normal chapter-brief/Build workflow.

## Instructor request and decisions

Replace diagram-plus-paragraph repetition with diagram-led slides. Use full-width
figures, short explanatory titles, and speaker notes for implementation details.
The architecture makes the shared IR explicit; the pipeline isolates the section
agent stage; editing distinguishes proposal, human review, and applied state.
The asset slide separates SVG preview and PNG export. Prompt contracts use three
columns with the stage above its output. The final slide pairs risks with the
chosen boundaries. Exact source prompts remain in the existing prompt appendix;
the contract diagram is not a fabricated literal transcript.

The initial three-row prompt map still left excessive horizontal whitespace in
the real browser. It was reflowed into three vertical pairs before acceptance.
No figures are diffusion-generated or raster mockups containing text. Mermaid
specifications remain the source, with deterministic SVG/PNG rendering.

## Safe diagram emphasis

The compact renderer recognizes only `primary`, `review`, and `accepted` Mermaid
classes, using the incumbent blue, amber and green semantic palette. Unknown
styles are ignored rather than injected into SVG. Style directives are excluded
from graph-node parsing so `url(...)` cannot accidentally become a node.
PNG uses the same colors and geometry. Existing unclassified figures retain
their neutral treatment. Rendering remains a pure transformation without models.

## Evidence and boundaries

- 60 targeted backend tests passed: diagram layout, Mermaid assets, exporters,
  generation pipeline, and slide animation (1.71 seconds in the recorded run).
- Added checks cover semantic color emphasis, unchanged edges, ignored external
  style URLs, and actual exported PNG colors.
- Internal browser review covered the architecture, human-review flow and prompt
  contract diagram. This is not an external usability study.
- The original chapter was backed up locally before editing; revisions use the
  existing teacher patch/apply and version-history services. Other chapter
  payloads and course metadata were asserted unchanged. The course stays draft.
- Original implementation caveats and source notes remain in speaker notes.
  The visual refinement does not claim production infrastructure, connected
  diffusion generation, guaranteed output correctness or measured learning gains.
