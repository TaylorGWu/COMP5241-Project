# Public UI refinement — verification

## Follow-up: approved course library and chapter editor, 2026-10-26

Implemented the two approved concepts with scoped CSS and native controls, not
raster mockups. The library has two columns, compact search/filters and real
course metadata; the removed title banner remains absent. The editor separates
material tabs, export and slide actions, shows new-request scope using stable
selection IDs, and places the composer before pending proposals. The prefilled
slide-2 instruction was removed so a new request starts empty. Existing plan
execution, manual edits, review approval and backend permissions are unchanged.

Evidence: frontend 76 tests, TypeScript, and changed-file ESLint passed with
zero errors (three pre-existing warnings: image optimization and unused tool
props). `course-library-layout.cjs` checks two columns, filtering, empty state,
computed Manrope font and widths800/390/320. `export-target.cjs` checks separate
toolbar, composer order, stable inserted UUID, frozen plan after navigation,
download hit testing and multi-bullet content at390/320. `slide-actions.cjs`
passed before/after insertion, editing, deletion confirmation, failure and narrow
layout checks. New layout assertions failed before implementation. Review found
mobile fixed-aspect clipping; the realistic multi-bullet regression reproduced
it and passed after the editor-only content-height correction.

Real signed-in course library and software-engineering chapter were inspected
without editing/applying/publishing content. Screenshots:
`/private/tmp/coursework-library-refined-20261026.png` and
`/private/tmp/coursework-editor-refined-20261026.png`.
Browser automation uses synthetic fixtures for mutations; these are internal
verification, not external usability tests. No commit or push was made.

Date: 2026-10-24. Scope: homepage, teacher profile and application review page.

## Design decisions

The requested frontend-design and design-taste-frontend skills guided the
audit-first redesign: scoped Manrope headings and Source Sans 3 body text,
locale-appropriate Noto Sans, a compact account header and less oversized
spacing. Existing Coursework blue, profile persistence and approval rules remain.
Homepage copy and an illustrative photograph now share the first viewport;
the existing interactive teaching example remains a real keyboard-operable demo.
The profile groups identity/photo, education and teaching information. Review
status stays a focused task rather than an oversized marketing panel.

The generated hero asset is
`frontend/public/images/lesson-planning.png`. Its complete prompt and provenance
are in `frontend/public/images/lesson-planning.provenance.md`. The image is
labelled AI-generated, not presented as a real interview, user or institution.

## Executed checks

- Frontend test suite: 70 passed.
- Changed-file ESLint, TypeScript and production Next.js build: passed.
- Public refinement browser checks: 19 route/locale/viewport/theme states,
  including 320px, 390px, 1024px and 1440px widths, English, simplified and
  traditional Chinese, light and dark modes.
- Live English → simplified → traditional Chinese font switching preserved
  unsaved profile text. Actual computed font families were checked.
- Profile browser flow: edit/save/reload, failed-save retention, navigation
  guard, subject selection, photo save/remove without overwriting other edits,
  role/expiry boundaries and pending/error/rejected/approved refresh: passed.
- Homepage demo: keyboard accept and replay across 3 locales × 2 widths, with
  no API mutation: passed.
- Session-boundary browser suite: 7 scenarios passed.
- Read-only review found a hidden approved-teacher workspace link on mobile.
  A regression check failed before the correction and passed afterwards.
- Final whitespace/diff check: clean.

Final production-preview captures:
`/var/folders/jp/r407sgwj3n78ncjf00tlghpm0000gn/T/coursework-public-refinement-T0DrVW/`.
These use synthetic fixtures, not real accounts or external usability testers.

## Performance and evidence boundaries

Local production Lighthouse, mobile-throttled: performance 85, accessibility
100, LCP 4.0s, CLS 0 and total blocking time 20ms. Contrast passed after removing
the demo's low-opacity idle text. LCP remains above a 2.5s target; this is not a
claim of production performance or a completed performance optimisation.

No backend implementation changed in this refinement. These checks do not
establish teaching effectiveness, real-user usability or deployment readiness.
No real account data was edited, and no commit or push was made.

## Follow-up: compact homepage navigation

After feedback that the top region felt empty, only homepage spacing was
tightened: 64px header, smaller mark/actions, 32px desktop and 24px mobile hero
top inset. Profile/application spacing and all behavior remain unchanged.
Browser layout regression failed before the adjustment and passed afterwards.
The 19-state browser suite and live locale-switch check passed again. Guest
checks at 1440px, 390px and 320px measured a 64px header without horizontal
overflow; final desktop/mobile screenshots were visually inspected. The
layout detector returned no findings and the whitespace check was clean.

## Follow-up: course workflow animation

Replaced the old three-column lesson example with a deterministic three-act,
six-scene walkthrough: course information/course card, chapter brief/draft,
pending modification/teacher-confirmed draft. There are no API clients or
generation calls in the demo component. Samples are labelled illustrative;
publication is deliberately absent.

Motion stays inside one canvas, with a 450ms scene reveal and short timeline.
Autoplay runs only while the canvas intersects the viewport and the document
is visible. It stops at the confirmed draft; explicit manual actions pause it.
Reduced motion starts paused and removes spatial animation. When an action
replaces its scene, keyboard focus moves to the labelled canvas rather than
falling back to the document.

Fresh verification:

- Production build, TypeScript and changed-file ESLint passed.
- 70 frontend tests passed.
- Browser workflow checks passed in English, simplified and traditional
  Chinese at 1440px, 390px and 320px, including keyboard confirmation,
  focus continuity, manual act switching and reduced-motion replay.
- Real timed autoplay, pause/resume, fully offscreen suspension and final
  confirmed-draft stop passed. A failed offscreen test was traced to a viewport
  that still showed part of the demo; the test now verifies actual geometry
  before asserting suspension.
- 19 public/profile/application visual states and live locale switching
  passed again; no horizontal overflow or write API requests were observed.
- Read-only review found no Critical/Important issues; Chinese slide labels
  were translated following a Minor observation.
- Layout detector and whitespace checks were clean.

Final workflow captures:
`/var/folders/jp/r407sgwj3n78ncjf00tlghpm0000gn/T/coursework-workflow-dcaLox/`.
Desktop chapter/review and narrow Chinese review captures were visually inspected.
No new backend verification or Lighthouse result is claimed for this increment.

## Follow-up: application identity placement

Removed the duplicate account name from the application header only. Its existing
name/email row now includes the private teacher photo; missing photos or failed
profile reads retain an initial avatar without blocking qualification download
or status refresh. Other account-header variants are unchanged. The photo uses
the existing credentialed blob loader, not a new public image URL.

The browser assertion failed on the former duplicate header name before the
change. Afterwards, all 19 visual states and live locale switching passed, plus
photo-present, photo-absent and failed-profile cases. The full teacher profile /
review-refresh browser flow, 70 frontend tests, changed-file ESLint, production
build/TypeScript, layout detection and whitespace check passed. Desktop and
Chinese mobile captures were visually inspected:
`/var/folders/jp/r407sgwj3n78ncjf00tlghpm0000gn/T/coursework-public-refinement-Kf1mip/`.

## Follow-up: unified circular account menu

The earlier name-only adjustment affected application review but left the profile
header's horizontal identity/actions intact. The approved replacement now changes
the shared account control itself: signed-in home, profile, application and teacher
navigation all use one circular avatar disclosure. Name/email, role destination,
teacher profile, home and logout live inside it. Student/admin body duplicates
were removed; public guest navigation is unchanged.

The private-photo component was extracted to avoid a header/profile import cycle.
The account menu is keyed by account ID, aborts obsolete profile/photo reads and
refreshes after a photo-save/remove event. Non-teachers do not request teacher
profiles. A focused sign-out button becoming disabled initially caused a null
blur target and hid failures; a regression reproduced it, and null-target blur
now preserves the panel so its error and retry remain visible.

Verification: production build/TypeScript, changed-file ESLint, 70 frontend tests,
19 public visual states plus locale switching and 3 identity fallback scenarios,
the full teacher-profile/review-refresh browser flow, and 7 session-boundary
scenarios passed. Dedicated account-menu checks passed against both production
preview (3001) and the user's running development service (3000): 3 languages,
1440/390/320px, Enter/ArrowDown/Tab/Escape, outside dismissal, photo changes,
initial fallback, failed/successful logout, guest controls and role destinations.
The read-only static review reported no actionable findings. Layout detector and
whitespace checks were clean. No real accounts were modified.

Final development-service captures:
`/var/folders/jp/r407sgwj3n78ncjf00tlghpm0000gn/T/coursework-account-menu-ojOQ3e/`.
Desktop profile and narrow Chinese home/menu captures were visually inspected
from the equivalent production build. Only the temporary 3001 preview was closed;
the user's 3000/8000 services were retained.

Homepage nav follow-up: removed “See how it works” and added a signed-in
Dashboard / 進入後台 / 进入后台 link beside the avatar. It reuses the existing
role destination, including pending-teacher qualification review, rather than
bypassing approval. Guests keep login/register without a duplicate dashboard.
The added assertion failed before the change, then the full account-menu browser
suite passed on port 3000, including approved teacher/student/admin destinations.
Changed-file lint, TypeScript, 70 frontend tests and whitespace checks passed.
The 320px Chinese capture was visually inspected:
`/var/folders/jp/r407sgwj3n78ncjf00tlghpm0000gn/T/coursework-account-menu-lQresk/`.

### 2026-10-25 — Chapter navigation and empty-deck recovery

Replaced the separate Open/Build chapter action with a semantic title link whose
hit area covers the row. Manage and rename remain independent controls above
the hit area, with a visible keyboard focus ring. Empty decks now offer a
localized review-and-retry path without deleting the saved package on entry.
Generation no longer marks an empty deck ready; incomplete output remains a
draft. Sections without submitted slides report failed, not written, and include
their agent stop reason in assembly diagnostics. This does not establish the
original upstream failure cause: the old saved package did not retain that trace.

Regression tests were observed failing before fixes. Afterwards 68 affected
backend tests, the two new frontend contract tests, TypeScript and changed-file
ESLint passed. Real logged-in browser checks verified row-background navigation
and independent Manage expansion. The user-requested COMP5241 regeneration saved
12 slides; one planned section still produced no slides, so the chapter remains
draft rather than ready. Existing COMP5355 (12 slides) and COMP5511 (8 slides)
were preserved. Nothing was published. These are internal checks, not external
usability-test evidence.

### 2026-10-25 — Manual slide controls

Added a compact slide toolbar: Add opens before/after choices for the current
slide, Edit uses the existing editor, Delete opens a native modal confirmation.
An empty deck can start again; an empty title never disables a real slide.
IDs remain stable while orders are recalculated. Inserts join the anchor's
first lesson-plan entry; deletion removes that slide's timeline references.
Teacher-authored applied deck patches retain reason/diff and version snapshots;
new blank slides are marked teacher-added, not AI-added. No model calls or
automatic publication are involved.

Verified 401 backend tests, 72 frontend tests, TypeScript and changed-file
ESLint. The synthetic browser regression exercises before/after payloads,
selection, editing/save/reload, confirmation/cancel, failure, empty titles,
last-page deletion/re-add and 390px layout. A focused code review found the
empty-title bug; its regression now passes. Updated one obsolete frontend test
that still expected the previously removed create-course back link. Real-browser
inspection opened the insertion menu only: existing course slides were not
modified. This is internal verification, not external usability evidence.

### 2026-10-25 — Teaching relationship-diagram rendering

Replaced the four-node keyword-template rendering with a deterministic layout
of the actual supported compact Mermaid graph: stable node identities, complete
labels, directed edges, branch captions and feedback links. SVG previews and
offline PNG fallback share geometry; normal PNG export still uses Mermaid CLI.
Typography, stroke weights and padding are consistent, with conservative wide-
glyph wrapping, reserved caption space and collision handling. No generation
calls or course IR edits are required to refresh existing supported diagrams.

Seven new regressions were observed failing before fixes, then passed; the full
backend suite passed 408 tests. Review caught wide-glyph and long/sibling-caption
clipping, covered by those regressions. A real logged-in software-engineering
chapter was inspected at full-size: both lifecycle paths and the feedback loop
remain visible. Screenshot: `/private/tmp/coursework-diagram-polish-20261025.jpg`.
No real slide content or publication status was changed. Point-cloud sampling,
Bézier controls and numerical classifier charts in the reference screenshots
are not existing components in this repository and were not implemented in this
bounded relationship-renderer refinement. This is not a general Mermaid parser.

### 2026-10-26 — Export menu clipping and inserted-slide revision scope

Reproduced Export opening invisibly inside the material-tab scroll container;
moved the dropdown outside that container, with narrow-screen alignment. The
editing planner previously picked the densest slide without receiving the
selected ID. Planning and execution now preserve both material target and stable
slide ID; backend proposal tools reject writes outside that selected slide.
Only newly proposed patches are returned for an edit, avoiding stale duplicates.
Missing/deleted selected slides return 404 before model execution.

Regressions observed failing before fixes: inserted-page planning, backend scope
enforcement, API missing-target handling, browser menu hit-testing. Follow-up
review caught material-tab scope loss, now covered by navigation-before-execution.
Verification: 411 backend tests, 73 frontend tests, TypeScript and diff checks
passed. ESLint had no errors (two existing unused-prop warnings in TeacherTools).
The synthetic browser fixture verified desktop/mobile menu hit testing,
attachment download event, and stable scope across slide/material navigation.
A real logged-in COMP5434 chapter triggered a PPTX download event, and its newly
inserted third page produced a read-only plan scoped to that page. The reported
download path could not be opened for file-content inspection; this does not
claim desktop PowerPoint or pixel-equivalence verification. No real AI plan was
executed or approved during this check; prior pending patches remain untouched.
Screenshot: `/private/tmp/coursework-export-fixed-20261026.jpg`. This is internal
regression verification, not external usability-test evidence.

### 2026-10-26 — Approved homepage concept implementation

Implemented the user-approved landing-page-design concept as live code rather
than using the generated mockup as a screenshot asset. Compact navigation and
one Manrope homepage face frame the existing deterministic course/chapter/review
walkthrough in the hero. Replaced homepage photos with that live demonstration;
kept the original account and role boundaries. Added localized factual FAQ,
flat process overview, reduced-motion-safe tagline reveal and student entry.
Profile, auth, course editing, persistence and generation were not changed.

The new homepage composition test was observed failing against the previous
headline before implementation. Browser checks passed three locales at 1440,
768, 390 and 320px, including dark mode, keyboard confirmation, replay, FAQ and
no API writes. Existing walkthrough tests passed all scenes, autoplay, pause,
resume and offscreen suspension. Account-menu checks passed guest registration,
teacher/student/admin destinations, narrow layouts, fallback photo and logout.
73 frontend tests, TypeScript and changed-file ESLint passed. Impeccable's scoped
layout scan returned no findings; a read-only code review found no important
issues. This is internal verification, not external user feedback.

### 2026-10-26 — Approved teacher Profile concept implementation

Scoped `profile-refinement.css` implements the approved identity-rail/unified-form
concept. Profile text uses Manrope with existing Chinese glyph fallbacks; real
saved identity, private photo and qualification state replace the mockup samples.
Personal/education/teaching anchors, paired desktop fields and normal-flow save
feedback improve grouping without changing API payloads, photo behavior or
approval permissions. Only the Profile header gains a role-appropriate dashboard
link; the shared avatar menu remains unchanged.

The new layout check failed against the old missing identity rail before changes.
Visual QA found a sticky save row covering fields; a scroll-to-top regression
failed, then passed with the row restored to normal flow. Read-only review found
an 800px old/new breakpoint collision; new 800/801px box/reflow assertions failed
before the display/breakpoint fix. Final layout matrix passed three languages at
1440/800/801/768/390/320px, light/dark themes, four qualification states, discard,
keyboard order and no page overflow. Existing interactive Profile checks passed
edit/save/reload, failure retention, unsaved-navigation guard, subjects, independent
status, separate photo save/remove, admin disclosure, student guard and expiry.
The public/profile/application isolation suite also passed live language changes
without losing dirty form values. 73 frontend tests, TypeScript, changed-file
ESLint and diff checks passed. Scoped layout detector returned no findings;
follow-up code review had none remaining. Real account inspection was read-only:
no user profile values, photos or approval records were written by these checks.
This is internal regression verification, not external usability evidence.
