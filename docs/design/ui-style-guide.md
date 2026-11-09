# Coursework UI style and integration guide

Approved direction: 5 November 2026. The public homepage takes visual cues
from Kipwise: warm ivory, near-black typography and actions, white surfaces,
and restrained borders. This is a visual reference, not a claim of copied code.

## Source files

- `frontend/app/homepage.css`: public homepage composition and walkthrough.
- `frontend/components/PublicHome.tsx`: homepage structure and role-aware CTA.
- `frontend/app/workspace-theme.css`: shared teacher/student/admin skin.
- `frontend/app/portals.css`: student and administrator component layouts.
- `frontend/app/teacher-workspace-refinement.css`: teacher layout rules.

Import the shared skin **after** existing component styles in `app/layout.tsx`.
Do not replace `globals.css` or overwrite a teammate's business components to
apply the look. Keep the homepage JSX change when integrating its CSS: it adds
the actual hero CTA, not a decorative button.

## Colour tokens

| Role | Light | Dark |
| --- | --- | --- |
| Canvas | `#f7f6f2` | `#181818` |
| Content surface | `#ffffff` | `#242424` |
| Secondary surface | `#efeee8` | `#2b2b2b` |
| Border | `#deded5` | `#414141` |
| Primary text | `#242424` | `#f2f2f2` |
| Supporting text | `#555555` | `#bdbdbd` |
| Muted text | `#686868` | `#adadad` |
| Selected background | `#e6e9df` | `#343f2b` |
| Selected text | `#38462c` | `#dce8cd` |

Primary actions use dark fill and white text in light mode; invert in dark
mode. Secondary actions use a surface fill, thin border and primary text.
Keep green success, amber pending/warning, violet AI proposals, and the existing
error treatment. Do not redefine `--color-blue` as black: charts, focus rings
and existing content also consume that token.

## Typography and layout

Use the existing Manrope variable, with Noto/PingFang for Chinese. Operating
screen body weight is 450 and headings use 600, with -0.02em tracking. The
homepage headline uses 650 and -0.025em tracking. Keep text neutrally grey,
not olive-tinted; sage is reserved for selection, not general prose.
Operating
screens use 30/36px page titles, 20/28px section headings, 14/20px compact labels
and 16/24px form text. Do not copy the homepage's 72px headline into dashboards.
Cards have a 12px radius and 1px border; controls use 8px corners. Use 16/24/32px
group spacing, 32px desktop gutters and 16px mobile gutters. Keep primary
controls at least 44px high where space allows. Preserve existing responsive
stacking rather than imposing fixed widths.

## Scope when merging teammate code

The skin applies to `.course-library-page`, `.course-create-page`,
`.course-detail`, `.chapter-workspace-page` and `.portal`. Keep these root classes on the corresponding
teacher and portal pages. New student/admin pages should sit inside `PortalShell`.
Existing selectors then apply without importing CSS in every component.

The chapter editor shell now shares the warm canvas, neutral text, white panels,
dark primary actions and sage navigation. Its layout and generation/review logic
remain unchanged. The `.slide-body` boundary restores the original lesson colour
tokens through root-level `--lesson-*` aliases, including thumbnail content.
Do not remove that boundary when merging: UI changes must not recolour lessons.

Login and registration now share the operating canvas, palette, type and dark
primary action through the stable `.auth-page` root; their layout, field heights,
blue links and photographic panel are unchanged. Profile and qualification
application keep their existing layout and palette. Only navigation selection,
account disclosure and segmented preference controls share the global
`--ui-selection-bg` and `--ui-selection-text` tokens. Do not add the canvas skin
to teaching slides: their colours can carry teaching meaning. Homepage layout
styling stays scoped to `.public-home-page`.

Keep chart categories distinguishable and labelled. Selected navigation uses
sage; charts retain separate series colours.
The teacher course sidebar (`.course-menu__item.is-active`) also uses the shared
selected tokens, including its horizontal mobile layout. Keep the keyboard
focus outline independent of the selected background.
Do not remove keyboard focus, loading, empty, disabled or error states while
restyling. No invented metrics,
testimonials or functionality should be added for visual balance.

## Integration checklist

1. Merge functional code first and resolve API/type conflicts independently.
2. Keep the relevant root classes and add the shared CSS import last.
3. Review desktop and 320px mobile, light/dark, and English/Chinese.
4. Check teacher catalogue search/filters, student navigation, and admin chart
   drilldowns. These must retain their behaviour after the visual merge.
5. Run TypeScript, the existing portal tests, and the UI smoke scripts.

Current implementation branch: `codex/student-admin-portals`. The earlier
homepage branch is `codex/local-teacher-sync`; do not replace the complete
student/admin modules with its older account-only pages.

## Selected-state audit

The earlier teacher top-navigation override lost to the older, more specific
`.teacher-nav nav a.teacher-nav__link.is-active` selector. The final stylesheet
now matches that specificity and is loaded last; no `!important` is needed.
The audit also covers course sidebar tabs, profile section links, account menu
items, student/admin navigation, editor navigation and segmented settings.
Check resting, hover and keyboard states in both themes, not only CSS source.

`tools/ui-verify/workspace-theme.cjs` asserts computed selected backgrounds,
navigation behaviour and narrow layouts. Blue links, keyboard focus rings,
informational badges, chart series and diagram content are intentional and
must not be globally replaced with sage. Success, warning and AI review colours
also remain separate from navigation.
