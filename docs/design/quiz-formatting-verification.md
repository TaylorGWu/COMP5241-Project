# Quiz option formatting repair — 2026-10-27

## Root cause and contract

Quiz slides previously stored options and answering instructions in one `bullets`
list. Model-provided `A.` / `B.` prefixes were printed alongside the preview's own
letter badges. An unlabelled “Pick one…” tail became a fifth option.

The canonical Slide IR now has optional `quizInstruction`. Quiz `bullets` contain
answer content only; preview and PPTX supply numbering. Generation exposes the
field in the tool schema and explicitly keeps instructions out of answer lists.
The slide editor exposes the instruction separately in all three interface languages.

Legacy quiz validation removes sequential A/B/... prefixes and moves recognized,
unlabelled trailing answer instructions into `quizInstruction`. Explicitly labelled
answers are not treated as instructions. This compatibility heuristic is not a
general semantic classifier: teachers still review ambiguous or malformed questions.
Animation steps targeting a moved instruction are removed without disturbing
the remaining answer indexes. Non-quiz slides are unchanged.

The chapter read API presents canonical quiz IR without silently writing the stored
draft. Existing chapter-17 quizzes s3/s7/s11 were explicitly repaired following the
user's request through teacher-authored manual/apply patches with reasons and
before/after course version records. Images, titles, answer meanings and speaker
notes were retained. Midterm discussion and other course packages were not rewritten.

## Verification

- Backend full suite: **445 passed**; tests were first observed failing for the new
  instruction field, legacy separation and remaining instruction variants.
- Frontend suite: **79 passed**; TypeScript and changed frontend file lint exit 0.
- Live browser: chapter-17 slide 3 has exactly four option elements, one separate
  instruction and no duplicated A./B. text. Screenshot:
  `/private/tmp/coursework-quiz-options-fixed.png`.
- The actual chapter package passed through the same PPTX export service as the
  download route. Parsed output has 12 slides, four numbered choices on slide 3,
  and an independent instruction frame. Output:
  `/private/tmp/coursework-quiz-fixed-deck.pptx`.
- Browser export triggered a download, but its Downloads path was not readable by
  the execution environment; content verification used the export service output
  above, not a claim that the inaccessible downloaded file was inspected.
- `git diff --check` passed before this documentation addition.

This was internal automated and browser verification, not external user testing.
