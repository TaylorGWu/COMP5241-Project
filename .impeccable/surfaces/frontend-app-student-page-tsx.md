---
version: 1
slug: "frontend-app-student-page-tsx"
primary_target: "frontend/app/student/page.tsx"
related_targets: ["frontend/app/admin/page.tsx"]
---

# Student and administrator surfaces

Mode: Operate (learning content canvas also Read). Extend the existing Coursework
visual world; this is not a homepage redesign. The user approved the functional
scope and explicitly asked to proceed without further confirmation rounds.

## Direction contract

**THESIS:** Make the next learning action and the next administrative decision
obvious. Reject a decorative dashboard of counters and equal-weight icon cards.

**OWN-WORLD:** Inherit DESIGN.md: Manrope and existing CJK fallbacks, navy text,
blue action/selection, semantic green/amber, flat themed surfaces, 12–16px panels,
8px controls. Read semantic CSS variables from current implementation. No new
background gradient, decorative photography or raster mock UI.

**STORY:** Students resume a real chapter, discover a published course, answer a
question and see saved feedback. Administrators find a user/course/application,
make an attributable decision and see its result. The UI never claims more data
or completed work than the backend supplies.

**FIRST VIEWPORT:** Compact brand/account header and role-specific navigation.
Student home: 30px heading, a 24px resume course title beneath a 20px section heading, restrained
recommendation and searchable catalogue. Player: 240px outline, flexible slide
canvas, controls below content; practice follows the lesson. Admin: 200px section
navigation, flexible operational list and inline actions. No oversized hero.

**FORM:** Code-led extension of the incumbent operating screens, chosen for their
existing conventions and the approved task. No concept seed or new aesthetic
selection: scope and visual world are fixed by the user's instruction.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Composition and interactions

- Desktop shell: max-width 1280px, 32px gutters, 24px group gaps. At 800px,
  navigation becomes a wrapping row and multi-column content stacks; at 480px use
  16px gutters. At 320px, inputs/actions wrap and user-provided strings break.
- Prefer lists for admin operations; no tiny fixed-width table that hides actions.
  Identity, role/status and action have stable visual positions. Search labels
  remain visible; per-row pending state must not look like every row is saving.
- Student course cards communicate actual subject/code, title, short description,
  chapters/duration and a single Join/Continue action. Progress is labelled text and
  a simple accessible bar; do not invent a score when no question was submitted.
- Recommended course explanation cites the saved background/goal. Invite join and
  preference editing are inline secondary tasks, not blocking onboarding modals.
- Student slide renderer is read-only; use existing SlideFrame if suitable. Never
  use SlideCanvas's editing/generation toolbar. Keep figure text readable and use
  student-scoped URLs. On phones allow content height to grow rather than shrink
  the whole 16:9 slide into unreadable miniature text.
- Practice uses labelled radio groups and explicit Check answer. After submission,
  show correct/incorrect, explanation, saved state and Try again. Avoid making a
  changed radio selection look as though it already has the previous answer's
  feedback; hide/reset the old attempt display during retry.
- Visiting a slide and submitting an answer are different events. Progress errors
  remain visible with a retry and never fabricate Saved. Fresh results restore
  from the backend after refresh. No confetti or modal score celebration.
- Course suspension asks for a reason inline. Restore is named Restore access,
  not Publish, because restoring does not publish draft material. Role change and
  disabling have a visible confirmation step and status feedback.
- Reuse existing application qualifications/profile/rejection feedback. Do not add
  duplicate avatars or move credentials back into registration.

## Accessibility and UI states

Visible labels, normal sentence case, 14px supporting/16px form text, 20px section
headings. Every action keyboard reachable with visible focus. Busy actions disabled
and labelled; GETs abort on route/account change. Alert/retry for failed requests,
honest loading and empty states; no fake success or loading forever after 401.
Honor current light/dark mode, reduced motion and English/zh-HK/zh-CN settings.

2026-11-01 refinement: single catalogue results fill the main column, saved goals
use native expandable editing, and admin counts share one compact definition list
with a distinct pending-review action. See `docs/design/student-admin-polish.md`.

## Known context drift

The context loader reported that DESIGN.md is newer than `.impeccable/design.json`.
Use DESIGN.md and current CSS as authority; do not regenerate the sidecar or alter
other screens as an unrequested repair.
