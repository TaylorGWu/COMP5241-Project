# Student and administrator interface refinement

Date: 2026-11-01. Base: `321bcb5`, branch `codex/student-admin-portals`.

## User request and boundary

Refine the two existing portals without replacing Coursework's identity or
changing their business rules. Keep Manrope/CJK fonts, semantic light/dark colors,
cookie/CSRF requests, publication boundaries, progress and qualification review.
No new package, backend change, model request or original database edit.

## Observed issues and changes

- The resume course title was18px, below its24px section label. It is now24px
  under a20px section heading, with course metadata and a clear continuation action.
- A single catalogue result occupied only half the main column. A single-result
  grid now uses the available width; multiple results retain the two-column grid.
- The saved-goals editor dominated the sidebar. Existing values now appear in a
  summary and a native keyboard-operable disclosure retains the editable form.
  Empty profiles start expanded. Save/error feedback remains outside the disclosure.
- Admin counts were five long full-width rows. Four existing counts now share a
  compact definition list; pending applications retain their count and a distinct
  Review applications action. No new statistics or activity claims were invented.
- Navigation uses a shared small inline-SVG vocabulary. User access controls align
  beside identity on wide screens and stack below it on narrower screens. Course
  moderation buttons no longer stretch across the list. Mobile navigation omits
  decorative icons while retaining every label/action.
- Course chapter lists receive the same surface and numbering treatment. The
  read-only slide renderer, IR, quizzes and their revision guard are unchanged.

## Verification

Before editing, actual browser DOM/style checks returned false for title priority,
single-result width above90% and saved-goals disclosure presence. The same checks
returned true after editing. These are browser layout checks, not newly added
automated unit tests or external user research.

Actual student disclosure expansion and an unchanged goal save showed one Saved
acknowledgement. Admin login, section navigation, user search/list, original
qualification actions and overview were inspected. No user role or qualification
was changed. Student/admin widths320px and390px equalled document widths; desktop
was1440×1000. Dark theme, Traditional and Simplified Chinese were inspected and
English/system theme restored. Screenshot dimensions were checked with `sips`.

`node --experimental-strip-types --test tests/*.test.mjs`:94passed,0failed.
Production `npm run build` passed, including TypeScript. Scoped ESLint passed;
`git diff --check` passed. Existing Node type-stripping/module warnings remain.
Impeccable detector ran once on changed portal sources and returned `[]`.

Evidence is archived under `assets/student-admin-polish/`. It shows internal
synthetic accounts and the independent preview database, not external testing.
The previous design-check record describes the pre-refinement version; this note
supersedes its portal layout/type details, not the root design system.

The context loader also reported a pre-existing unset marketing-page build-path
preference. This does not affect code-led operating screens; no unrelated design
configuration repair was performed.
