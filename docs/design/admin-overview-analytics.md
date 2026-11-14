# Administrator overview: actionable statistics

Date: 2026-11-01. Branch: `codex/student-admin-portals`; baseline: `373b555`.

The user asked for clickable totals and professional charts of different
categories. This extends the current operational interface, not the teacher
workspace or the global design system.

## Design and data decisions

- Four metric buttons open users, all courses, published courses, or courses
  with enrollments. Filters remain visible and can be cleared.
- An account-role donut compares student, instructor and administrator accounts.
  Its labelled legend opens the exact role filter. Disabled accounts still count
  as accounts; the graph does not claim that they are active users.
- A stacked bar compares mutually exclusive course states. Suspended courses
  belong only to Suspended, even if their stored publication status is published.
  Unpublished means all other non-suspended courses, not only an IR draft status.
- Horizontal bars compare the five highest course enrollment counts. The total
  counts memberships, not unique people: one learner in two courses counts twice.
  A row opens that exact course; the top metric opens all courses with members.
  Historical memberships remain counted when a course is unpublished/suspended.
- Counts, category values, course IDs and titles come from authenticated admin
  reads. There are no invented trends, percentages of growth or sample statistics.
  No schema migration, model call, raster-generated chart or new runtime package.
- Keep Manrope, semantic light/dark colors and native buttons. SVG only draws the
  donut geometry; adjacent text exposes every value and action without depending
  on color. Destination regions receive focus after navigation. Existing write
  confirmations and role/publication boundaries remain unchanged.

## Verification and evidence

Backend tests were added first and failed on the missing category fields. They
then passed against real temporary SQLite data: publication/suspension partition,
membership totals, zero-course categories, course counts and 401/403 boundaries.
Frontend tests cover exact role/identity filters, suspended publications, empty
enrollment filters and clearing to all records.

- Complete backend suite: **469 passed**.
- Complete frontend suite: **96 passed**; existing Node type-stripping/module
  warnings remain. Production build and scoped ESLint passed.
- Actual browser checks: published metric opens one live published course; role
  legend opens only students; a course bar opens the matching course; membership
  metric opens two courses; clearing restores all seven courses/five accounts.
  Zero suspended courses shows an empty list, not invented data.
- At390px and320px, document width equals viewport width. Individual metric/chart
  controls also have no horizontal overflow. A4px arrow overflow was found by
  DOM measurement and fixed by matching the icon to its16px grid cell.
- Dark Traditional Chinese and English light rendering were visually inspected.
  Theme/language and the viewport override were restored afterwards.
- Read-only independent code/visual review found no Critical/Important issues.
  Its minor wording suggestion was addressed: the membership action now says
  “View by course”, not “View enrollments”.
- The final overview capture is `assets/admin-overview-analytics/desktop.png`.
  It shows real counts from the independent local preview database, including an
  internal verification course. It is internal QA, not external usability research.

This note supersedes only the earlier overview definition-list layout in
`student-admin-polish.md`. Original teacher content/database and existing handoff
archives were not edited. No remote push or merge was performed.
