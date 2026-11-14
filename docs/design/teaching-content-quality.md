# Teaching content quality — generation revision

Date: 2026-10-22. Scope: teacher-side course generation on `codex/teacher-courses`.

## Problem and decision

The previous section prompt limited each point to 30 Chinese characters and
required only two sentences of notes. This encouraged short assertions instead
of explanations. Section agents received a section name and teaching arc, but
not the actual objective text and ID mapping produced by the planner.

Keep the existing four-page learning loop and IR. Improve the writing contract
and pass the planned objectives into the section agent. No renderer-side content
generation, automatic publication, or rewriting of existing teacher materials.

## Content standard

| Page role | Evidence expected in the draft |
| --- | --- |
| Explanation | Meaning, mechanism, reason, and an applicable boundary |
| Worked example | Concrete starting state, reasoning, action, observable result |
| Understanding check | Sufficient information, plausible alternatives, reasoned answer and corrective feedback |
| Transfer/recap | One changed condition, and an explanation of whether the original decision still applies |

Page text should contain 3–5 distinct information units, normally one or two
sentences each. Length guidance is advisory: 25–60 Chinese characters or 12–28
English words per unit. Notes normally contain 120–220 Chinese characters or
80–140 English words, explaining introduction, reasoning, expected response,
correction and transition. Length alone does not establish quality.

Technical examples must state their preconditions and distinguish local actions
from shared outcomes. Verification and synchronization cannot be omitted from an
example that claims an externally visible result. Avoid unconditional guarantees
about success, conflicts or data preservation.

Visuals must expose a relationship used in the explanation. Each section has a
one-diagram budget, with one repair attempt on failure; remaining content can use
comparison or text. Delivering the teaching draft takes priority over repeated
diagram tool calls.

The deterministic review checks flag exact repeated points after Unicode,
punctuation and case normalization. They do not judge semantic equivalence or
technical truth. Natural Traditional Chinese wording such as 誤解 and 追問 must
not require literal template headings to satisfy feedback checks.

## Editorial example (hand-authored, not a measured model improvement)

Weak point: “revert is safer.”

More teachable point: “For a commit already shared with teammates, revert usually
preserves the shared sequence by adding a reversing commit. Inspect the working
tree, apply the reversal, run the relevant tests, then push the new commit;
conflicts may still require resolution.”

Teacher follow-up: “What would change if the commit had never been pushed? Which
evidence would you inspect before choosing an operation?”

## Validation and limitations

- Automated tests cover assigned-objective propagation, planner-generated
  objectives when teacher inputs are blank, the actual pipeline-to-agent path,
  repeated-point warnings and preservation of draft content.
- An isolated real-model probe on shared Git history used the configured section
  route without writing courses or patches. The first attempt exhausted its tool
  rounds on diagrams. A second probe explicitly using comparison/case layouts
  completed with `write_plan_entry` then `write_section` and four schema-valid
  slides. This motivated the diagram budget.
- Editorial review of that second probe found overconfident conflict claims and
  omitted synchronization in an example. The final prompt adds explicit checks
  for those omissions. That final revision has not yet had another live-model
  comparison, and no improvement percentage is claimed.
- These are internal engineering checks, not external teacher/user feedback or
  proof of learning effectiveness. Semantic accuracy remains a teacher review
  responsibility; structured validation alone cannot establish it.

New generations use the revised contract. Existing reviewed material stays as it
is. Test future samples in the supported languages, with and without uploaded
materials, and retain the unedited output alongside reviewer corrections.
