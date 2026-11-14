# MoSCoW status-board refinement — 2026-10-29

## User-approved direction

Replace dense midterm progress prose with three concise English slides:
three-portal scope, teacher progress by priority, and remaining work/exclusions.
Use reusable product components, not bespoke HTML for the discussion course.

## Implementation and evidence boundaries

- `Slide.layout=statusBoard`, `statusGroups` are validated structured IR. One to
  three groups, one to six items each; explicit complete/partial/unverified/excluded
  states. Legacy slides remain valid. No HTML or inferred percentage is stored.
- `StatusBoard` renders real labels and status icons. Complete labels remain
  accessible without being repeated visually on every checked row. Mobile main
  canvases stack groups; fixed-size thumbnails preserve the presentation layout.
- The ordinary slide editor edits groups, item labels and status via native
  controls. Generation tools expose the schema, but live model selection of this
  new layout has not been evaluated. No claim of universal automatic layout quality.
- PPTX exports editable group headings, labels and explicit status text from the
  same IR without model calls. File typography can substitute installed fonts;
  content equivalence is the contract, not identical browser/file pixels.
- Course-7/chapter-14 was edited through manual/apply patches and version records.
  Three pages replace four, preserving stable IDs s1/s2/s4 and valid plan links.
  Previous notes and content remain in history. Other chapters were checked
  unchanged during the initial deck update. Publication was not changed.
- Teacher checks retain their prior internal-prototype meaning. Student/admin
  acceptance remains unverified; PDF, remediation and narrated video stay partial.
  Requirement IDs, source files and evidence limitations remain in concise notes.

## Verification

The new schema/round-trip/export/tool tests failed before implementation, then
passed. Full backend suite: 451 passed. Frontend suite: 84 passed, including real
server-rendered TSX tests for status/group output and text escaping. TypeScript
no-emit and changed-file ESLint checks passed; Impeccable detector returned no
findings for the changed rendering files. Existing Node experimental-type warnings
remain tooling warnings, not test failures.

Actual Chrome chapter page showed three slides and all teacher checklist groups.
The native editor showed group/item inputs and status selects; Cancel returned
to the board without a content mutation. PPTX was generated from the stored IR and
rendered for visual review. Initial review prompted aligned export rows and
shorter, nonduplicated notes plus the explicit prototype-progress title.

Files used for local verification (not committed private data):
`/private/tmp/coursework-moscow-status-board.pptx`,
`/private/tmp/coursework-moscow-web.png` and the before/after IR snapshots.
This is internal verification, not external participant usability evidence.
