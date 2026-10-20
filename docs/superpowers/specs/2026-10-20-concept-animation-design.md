# Concept animation design

## Goal

Add restrained, automatic teaching animations to the existing courseware
preview and student lesson player. The animation must make the sequence of an
explanation easier to follow; it is not a video export, a decorative motion
layer, or a generated media asset.

The intended learning loop remains the existing one: a teacher reviews a
draft, previewing the animation as part of the same slide, before publishing
the course. Students see the approved animation once when they arrive at a
slide and can replay it.

## Scope and non-goals

This change adds a small, structured animation plan to optional `Slide` IR and
a deterministic browser renderer. It initially supports only:

- `reveal`: show a title, bullet, case fact, or diagram element in a teaching
  order;
- `emphasis`: briefly highlight one already-rendered element; and
- `sequence`: reveal a named diagram node and its outgoing relationship in
  causal or chronological order.

The first release uses the existing `title`, `bullets`, `visuals`,
`teaching_role`, and `visual_purpose` fields. It does not introduce an MP4
download, TTS, Remotion, a new model call, a background media job, or a second
copy of slide content. It must not alter the existing PPTX export. Animation
metadata is optional and all existing slides render statically without it.

## Data contract

`Slide` gains a backwards-compatible optional `animation` object. The plan
references stable elements already owned by the slide; it cannot contain new
teaching prose, replace visual assets, or embed HTML/CSS/JavaScript.

```jsonc
{
  "animation": {
    "autoplay": true,
    "steps": [
      { "kind": "reveal", "target": "title", "atMs": 0 },
      { "kind": "reveal", "target": "bullet:0", "atMs": 850 },
      { "kind": "emphasis", "target": "bullet:0", "atMs": 1500,
        "durationMs": 1000 },
      { "kind": "sequence", "target": "diagram:commit", "atMs": 2600 }
    ]
  }
}
```

Allowed targets are `title`, `bullet:<zero-based index>`, a named visual
region, and a Mermaid node identifier owned by a slide diagram. The validator
rejects missing targets, duplicate conflicting steps, negative timing, timing
beyond the bounded slide duration, and animation plans on layouts that cannot
address the requested target.

The Python schema uses safe defaults (`animation = None`) and the TypeScript
`Slide` type mirrors the optional structure. Stored legacy records therefore
continue to validate, preview, publish, and export unchanged.

## Rendering and playback

### Component boundary

`SlideAnimationPlayer` is a client-side wrapper around the existing
`SlideFrame`/`SlideBody` renderer. It owns only timing, replay state, reduced
motion handling, and CSS data attributes. `SlideCanvas` continues to own the
semantic layout and reads the current step only through explicit props.

The component uses React state and CSS transitions already available in the
project; no motion dependency is added. Content is present in the DOM for
screen readers from the start. While it is visually unrevealed, it is neither
removed nor replaced with a different content string.

### Teaching treatments

| Existing slide form | Animation treatment |
| --- | --- |
| Bullet/explanation | Reveal one idea at a time; briefly emphasise the current idea before the next one. |
| Scenario/worked example | Reveal actor, constraint, evidence, and consequence in the order prescribed by its teaching role. |
| Mermaid sequence/mechanism | Reveal nodes and relationship strokes in the plan order. A rendering failure falls back to the normal static diagram. |
| Title/quiz/code | Static by default. Only title or deliberately supplied supported targets may animate; a quiz never delays answer choices. |

When an animation plan is missing, invalid, disabled, or motion reduction is
requested, the renderer immediately shows the full existing slide. One failed
diagram element cannot hide the slide or block lesson navigation.

### Surfaces

In the teacher workspace, slides remain static by default. A compact
`Preview animation` control starts playback for the active slide and exposes a
`Replay` action once it finishes. The control does not affect course data.

In the student lesson player, an eligible animation begins once per visit to
an active slide. The student can replay it; navigating away cancels timers and
returning starts a new visit. `prefers-reduced-motion: reduce` disables timed
effects and shows the completed slide immediately.

## Generation, review, and authority

Animation plans are generated as part of the existing structured slide
generation contract, not by a renderer. The planner may add a plan only when
it can identify a concrete instructional reason from `teaching_role` and
`visual_purpose`:

- mechanism/sequence diagrams may use a `sequence` plan;
- worked examples and scenarios may reveal context, constraint, evidence, and
  consequence; and
- explanation slides may reveal at most the existing bullet list.

Other slides receive no plan. New generation validates the plan after the
normal slide IR validation. An invalid plan is discarded with a concise
machine-readable warning and the slide stays a valid static draft.

The edit agent treats `animation` as a slide field. It may propose an
`animation` patch only after reading the target slide. The existing review
margin displays the before/after structured steps and the pedagogical reason;
the teacher can approve or reject it through the existing patch workflow.
No proposed animation mutates an artifact or becomes visible to students until
the teacher applies it and publishes the containing course.

## Failure handling

- Legacy or planless slides render static.
- Invalid or unsupported targets are ignored for playback and recorded as a
  validation warning; they never make the slide blank.
- A missing Mermaid node falls back to the complete static SVG.
- Timers are cancelled on unmount, slide change, replay, and reduced-motion
  preference changes to prevent stale animation states.
- PPTX/document exports consume the same slide IR but deliberately ignore
  `animation`, leaving content/export determinism intact.

## Test strategy and acceptance criteria

Schema and pipeline tests verify that legacy Slide JSON defaults safely,
valid plans can only reference existing targets, and invalid plans are removed
without failing the containing draft. Planner/edit-agent tests assert the
structured field and review authority rather than model wording.

Frontend tests verify that:

- a planless slide renders its full current content immediately;
- each supported target obtains the expected timed state;
- replay resets to the first teaching step without duplicating content;
- changing slide/unmounting cancels pending timers;
- reduced motion renders the completed state and does not schedule playback;
- the teacher preview control is opt-in while student playback is automatic;
- PPTX export receives the original visible content and no renderer invokes an
  AI or media service.

Acceptance is met when a teacher can generate or review a course with both
animated and static pages, preview a slide's explanation sequence, explain
why each animated step supports the stated teaching role, and publish the
same reviewed course without changing the exported PPTX content.
