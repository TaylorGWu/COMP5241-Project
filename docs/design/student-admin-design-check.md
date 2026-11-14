# Student and administrator design check

Date: 2026-11-01. Disposition: **ship this local prototype extension** at the
reviewed desktop (1440px), phone (390px) and minimum (320px) widths.

This is an ordinary extension of the established Coursework visual system. The
surface direction is in `student-admin-interface.md`; product boundaries are in
root `PRODUCT.md`. No replacement identity or new global tokens were needed.
Root `DESIGN.md` and `.impeccable/design.json` are preserved.

## Sources checked

- `PRODUCT.md`, `DESIGN.md`, and `docs/design/student-admin-interface.md`.
- `frontend/app/globals.css` for semantic light/dark colors and existing radii;
  `frontend/app/layout.tsx` for the Manrope font binding.
- `frontend/app/portals.css` for the actual scoped type, layout, state, focus and
  responsive rules.
- `frontend/components/portals/PortalShell.tsx`, `AdminPortal.tsx` and
  `StudentPlayer.tsx` for shared header, navigation, operational lists,
  read-only slides, progress, practice and recovery patterns.
- `docs/design/student-admin-verification.md` for the controller's browser and
  detector record. Screenshot inspection below supplements that record; it is
  not a separate browser run.

## System inheritance and actual values

The portal aliases existing `--color-*` properties rather than declaring another
palette. Light values checked against the incumbent source include navy ink
`#172033`, supporting text `#536176`, canvas `#f4f6f9`, surface `#ffffff`, line
`#dde3ea`, action blue `#315fc6` and selected blue `#edf2ff`. Green/amber pairs
identify completion and review/error with text labels. These references also
inherit the existing dark overrides, including ink `#eef3fa`, canvas `#111722`,
surface `#182131` and blue `#8aaeff`.

Manrope uses the existing public display variable, with the established SC/TC
fallbacks selected by locale. Body is 16px/1.5; page titles 30px/36px at weight 600;
section headings 24px/32px; item headings 18px/28px. Panel headings use 20px/28px
and supporting text uses 14px. This follows the current teacher operating-screen
override rather than copying homepage display sizing. Code remains monospaced
through the reused slide renderer.

The 1280px shell uses 32px desktop gutters. Student home pairs flexible content
with a 304px sidebar; player uses a 240px outline and 24px gap; administrator uses
a 200px section navigation and 32px gap. Panels/cards have 12px corners, 1px themed
borders and 24px insets. Controls use 8px corners, 40px minimum button height and
44px minimum field height; fields keep 16px text. These are scoped portal values,
not changes to incumbent 38px workspace or 50px public controls.

Depth comes from borders and tonal surfaces. The resume region uses selected
blue; admin operations use separated rows instead of a dashboard of equal cards.
The reused application queue explicitly drops its enclosing shadow in this
surface. No new raster artwork, decorative gradient or generated diagram ships
with the portal extension.

## Component and state patterns

`PortalShell` reuses the simple `PublicHeader` and account menu, with a skip link
and role gate. Active navigation and outline entries carry `aria-current` and a
blue tonal selection. Student reading uses `SlideFrame` without teacher editing
controls; previous/next actions sit below the canvas. Progress uses a labelled
native progress element. Practice presents labelled radio options and explicit
submission with textual answer feedback.

Administration reuses qualification review and adds searchable operational
lists, wrapping row actions and inline confirmation. Status is stated in words;
restore access does not claim to publish a draft. Shared resource/write helpers
provide loading, disabled busy controls and alert/retry errors, and abort stale
requests. These are implementation observations, not a claim that all error
paths have been manually exercised.

Keyboard focus uses a 3px blue outline with 2px offset. Reduced-motion styles
remove transitions and smooth scrolling. Existing locale/theme controls remain
available through the shared shell.

## Responsive evidence

The supplied screenshots were visually inspected:

| Surface | 1440px | 390px | 320px |
|---|---|---|---|
| Student home | `assets/student-admin/coursework-student-desktop.png` | `assets/student-admin/coursework-student-mobile.png` | `assets/student-admin/coursework-student-320.png` |
| Administrator overview | `assets/student-admin/coursework-admin-desktop.png` | `assets/student-admin/coursework-admin-mobile.png` | `assets/student-admin/coursework-admin-320.png` |

The desktop student capture shows the primary resume action, catalogue and
separate goals/invite panels. Phone captures retain readable course titles,
search labels and progress; long titles wrap at 320px. Administrator navigation
wraps above the list on phones. At 320px the application-review action moves onto
its own row instead of compressing the label/count.

Actual CSS stacks the main grids at 800px, reduces gutters/panel insets to 16px
at 480px and makes the course grid one column at 1000px. Player content grows in
height instead of preserving a tiny 16:9 canvas. Mobile slide columns/flex groups
stack; monospaced content uses `pre-wrap` and `overflow-wrap:anywhere`.
`assets/student-admin/coursework-student-code-320.png` shows the synthetic long-code
fixture wrapping within the 320px reading panel. It is a stress fixture, not an
authored teaching example.

The controller's verification record reports document width equalling viewport
width for ordinary content at 390px/320px, targeted keyboard focus, locale/dark
inspection and one detector run returning `[]`. That detector result is a
bounded source check, not proof of overall design quality or accessibility.

## Known limits and preserved drift

The screenshots cover the visible light-theme states, not every lower-page
control, translated string, authored slide layout or error condition. The
controller's targeted checks do not constitute a comprehensive accessibility
audit. The original temporary screenshot files have been archived under
`docs/design/assets/student-admin/` for reproducible course-submission evidence.

The context loader reported pre-existing drift: root `DESIGN.md` is newer in
content than `.impeccable/design.json` (whose generated timestamp is
2026-10-23). Current CSS and the later scoped overrides in `DESIGN.md` are the
authority for this extension. Neither file was regenerated as an unrelated
repair.

This record contains internal implementation and rendering evidence. It does
not establish external interviews, independent usability testing, production
readiness, learning gains or an A+ assessment outcome.
