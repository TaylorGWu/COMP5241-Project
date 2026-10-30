---
name: Coursework
description: The existing navy and blue visual system for focused teaching and account workflows.
colors:
  ink: "#172033"
  body: "#536176"
  muted: "#7a8798"
  canvas: "#f4f6f9"
  surface: "#ffffff"
  soft: "#f1f3f6"
  line: "#dde3ea"
  blue: "#315fc6"
  blue-deep: "#264eaa"
  blue-soft: "#edf2ff"
  green: "#2a7755"
  green-soft: "#f0f8f3"
  violet: "#6555a6"
  violet-soft: "#f1effb"
  amber: "#96601a"
  amber-soft: "#fdf5e9"
  teaching-navy: "#172b4b"
  teaching-paper: "#f6f8ff"
  teaching-body: "#ced9ed"
typography:
  display:
    fontFamily: "Manrope, Noto Sans SC, Noto Sans TC, sans-serif"
    fontSize: "clamp(44px, 4.5vw, 64px)"
    fontWeight: 560
    lineHeight: 1.12
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Manrope, Noto Sans SC, Noto Sans TC, sans-serif"
    fontSize: "clamp(28px, 3vw, 38px)"
    fontWeight: 550
    lineHeight: 1.25
    letterSpacing: "-0.03em"
  public-body:
    fontFamily: "Source Sans 3, Noto Sans SC, Noto Sans TC, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.65
  profile-title:
    fontFamily: "Manrope, Noto Sans SC, Noto Sans TC, sans-serif"
    fontSize: "30px"
    fontWeight: 550
    lineHeight: 1.3
  title:
    fontFamily: "Geist, sans-serif"
    fontSize: "32px"
    fontWeight: 620
    lineHeight: 1.24
    letterSpacing: "-0.035em"
  body:
    fontFamily: "Geist, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "Geist, sans-serif"
    fontSize: "13px"
    fontWeight: 550
  code:
    fontFamily: "Geist Mono, monospace"
rounded:
  sm: "8px"
  md: "12px"
  lg: "16px"
  form: "7px"
  public-panel: "14px"
  status: "5px"
spacing:
  control-gap: "8px"
  related-gap: "12px"
  group-gap: "16px"
  form-gap: "18px"
  auth-form-gap: "20px"
  section-inset: "24px"
  desktop-gutter: "48px"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "38px"
  button-primary-hover:
    backgroundColor: "{colors.blue-deep}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "38px"
  button-quiet:
    textColor: "{colors.body}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "38px"
  button-public:
    backgroundColor: "{colors.blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "13px 23px"
    height: "50px"
  input-auth:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.form}"
    padding: "11px 13px"
    height: "50px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  status-pending:
    backgroundColor: "{colors.amber-soft}"
    textColor: "{colors.amber}"
    rounded: "{rounded.status}"
    padding: "5px 9px"
  status-approved:
    backgroundColor: "{colors.green-soft}"
    textColor: "{colors.green}"
    rounded: "{rounded.status}"
    padding: "5px 9px"
---

# Design System: Coursework

## Overview

**Creative North Star: "Make teaching decisions visible."**

Extend the incumbent Coursework system: navy ink, restrained blue actions and light blue-grey surfaces. The approved home/profile/application refinement uses Manrope display, Source Sans 3 body and locale-appropriate Noto Sans SC/TC. Course editing and authentication retain Geist. Authentication uses a focused form and a quiet photographic learning-studio illustration; the homepage has its own labelled lesson-planning image and live teaching example.

This is an extraction of the current system, not a rebrand. Sources include `frontend/app/globals.css`, `frontend/app/public.css`, `frontend/app/public-refinement.css`, `frontend/components/ui.tsx`, `PublicHeader.tsx`, `AccountActions.tsx`, `PublicHome.tsx`, `TeacherProfile.tsx`, `AuthScreen.module.css` and `AccountPages.tsx`. The approved surface composition and narrative remain in `docs/design/public-entry-interface.md`; they are not mandatory layouts for every new screen.

**Key Characteristics:**

- Light surfaces separated by fine borders and modest tonal changes.
- Blue actions, green acceptance and amber review/revision feedback.
- Compact, legible operational controls with larger public headings.
- Real text and code in demonstrations; visible human review states.

## Colors

The frontmatter records the light-theme primitives; `globals.css` remains the implementation source for light and dark theme values. Preserve semantic CSS variables when building app surfaces.

### Primary

**Restrained royal blue** (`blue`) identifies actions, links, selected steps and active navigation. **Deep royal blue** (`blue-deep`) gives hover/emphasis; **pale blue** (`blue-soft`) supports selected regions without turning them into heavy blocks.

### Secondary

**Acceptance green** (`green` / `green-soft`) communicates accepted or approved state. **Review amber** (`amber` / `amber-soft`) communicates a pending decision, revision request or recoverable error. **Muted violet** (`violet` / `violet-soft`) identifies AI-related material in the incumbent component vocabulary.

### Neutral

**Navy ink** (`ink`) carries primary text; **slate body** (`body`) carries supporting text; **muted slate** (`muted`) carries lower-priority metadata. **Blue-grey canvas**, **white surface**, **soft grey** and **fine line** (`canvas`, `surface`, `soft`, `line`) establish the everyday hierarchy. Legacy teaching-navy tokens remain available, but the revised homepage follows the selected light/dark theme. Authentication uses a decorative image rather than the former navy editorial panel.

**The State Color Rule.** Green means acceptance and amber means review or revision; do not use either as an unrelated marketing accent.

## Typography

Geist remains the course-editor and authentication family; Geist Mono serves actual code and selected numeric information. Home, profile and application pages use Manrope headings (550-600) and Source Sans 3 body (400-600), scoped by their main classes. Chinese pages use Noto Sans SC or TC. Fonts are self-hosted through `next/font` with swap; the large CJK face sheets load only for Chinese interfaces and on live locale changes, without reloading dirty forms. The recorded display/headline/public-body/profile-title roles describe these three surfaces; title/body/label remain authentication roles.

Public headings are tightly tracked with moderate variable weights. Forms keep their labels visible; supporting copy uses generous line height. Auth text inputs are larger than labels (15px desktop, 16px mobile). At the mobile public breakpoint, the teaching demonstration becomes a vertical sequence with readable titles (15px), guiding questions and descriptions (13px).

Teacher profiles extend this Operate system with one grouped About/Education/Teaching form, a quiet section index and two-column fields on desktop. Below 800px fields stack and the qualification note moves after the form. Photo changes save independently of text. Native selects cover education/experience; subject search reveals a labelled checkbox group and removable selection tags. Refresh status uses a secondary control with in-place checking/result/error feedback, not a page reload or success toast for unchanged review state.

**The Readable Example Rule.** Reflow demonstration content on small screens before reducing its text size.

## Layout

Home uses a 1280px shell with 40px desktop gutters, a copy/photo first viewport and the existing interactive teaching example below. Profile uses a 1120px shell; application uses an 820px shell, 756px panel and 25-30px title. Both consolidate account controls into the 76px header. Do not show a primary workspace link pointing back to the pending application page. On mobile keep the approved teacher's workspace exit visible, collapsing redundant current-page text instead. Authentication retains its 1200px shell and focused 400px form beside an image; the administrator queue remains 1140px.

The refined public surfaces stack at 800px, with a 1050px intermediate demo layout. Stories and the brief/slide/review demonstration stack in reading order; demonstration text stays full-contrast at every step. Authentication keeps its own 820px breakpoint: the decorative image disappears, horizontal padding becomes 24px and inputs use 16px type. Forms and controls wrap; filenames and user-provided text may break rather than force overflow. Minimum width is 320px. Course workspace breakpoints remain unchanged.

Use the extracted small gaps and insets to preserve relationships; the source has a contextual spacing vocabulary, not a rigid universal grid. Public language/theme preferences stay in document flow so they cannot cover the form or example controls.

## Elevation & Depth

Borders and surface tones carry most structural separation. The shared card shadow is a small ambient layer; the raised shadow belongs to elevated workspace menus and selected hover treatments. Public account panels and the teaching example remain primarily border-defined. The full shadow values are in the sidecar, extracted from `globals.css`.

Motion clarifies an existing state change. The public buttons transition color briefly (150ms); example regions change emphasis rather than move through a theatrical scene. The demonstration advances through its steps at bounded intervals (5 seconds per step), allows direct selection/replay, and honors reduced motion. Reduced-motion styles remove transitions and reveal the text without requiring animation.

## Shapes

Controls use gently rounded corners (`sm`); workspace cards use the medium radius. Auth fields have the observed slightly tighter form radius, and public enclosing panels use the observed public-panel radius. Status labels are compact softened rectangles. Workspace badges also include the existing pill variant; neither shape replaces the other globally.

Keep separators thin (1px). Dashed borders identify qualification selection and empty learning states in the current account UI. Small SVG line icons use the established public stroke treatment (20px nominal size, 1.7px stroke) and support their adjacent labels.

## Components

### Buttons

The shared workspace primitive has primary, ghost and quiet variants with a compact minimum height (38px). Primary uses blue; ghost combines a white surface and fine border; quiet relies on text. The public primary is roomier (50px minimum), with a smaller header variant (42px). Preserve the distinction rather than inflating every workspace control.

Hover changes color; the workspace primitive and auth submit button have a small pressed translation. Shared disabled controls use the existing muted fill/text, while public pending submissions use reduced opacity and a waiting cursor. The global keyboard focus outline is visible (3px, 2px offset); auth text fields have their own blue focus outline (2px, 2px offset). Preserve visible focus on both themes.

### Chips

Status badges include their state in text, with semantic fill/text pairs. Account pending and revision states share amber; approved uses green. Workspace badges support neutral, blue, green, violet and amber tones. Do not communicate approval with color alone.

### Cards / Containers

Workspace cards combine surface, line and the card shadow. The public example, application panel and review queue use a larger panel radius and fine border. Keep the flat account panels distinct from floating menus. Internal padding follows context instead of imposing a new universal card template.

### Inputs / Fields

Auth fields use visible labels, theme-aware surfaces, fine strokes and the form radius, with a comfortable minimum height (50px). Hover strengthens the border; keyboard focus changes the border and outline to blue. Password controls reserve space for a labelled Show/Hide button (64px width), rather than an icon alone. Errors appear in a readable amber summary; submitted form errors receive focus. Retain autocomplete, paste and password-manager support.

Registration is account-only for both roles. The labelled dashed qualification selector belongs on the later application page, for first submission or resubmission. Its native file input and visible focus-within treatment remain; do not move this additional task back into teacher registration. Application status must distinguish not submitted, in review and needs revision.

### Authentication image

The right-hand image is a generated, photographic learning-studio scene with no text or simulated course interface. It is decorative, uses empty alt text in an aria-hidden region, and is hidden below the authentication breakpoint. Its container uses the existing medium radius, with cover cropping; dark mode reduces brightness and saturation. The scene and prompt are documented in `frontend/public/images/learning-studio.provenance.md`. It is not a named campus or an institutional endorsement. This is a scoped auth pattern, not a requirement to add photos to every product screen.

### Navigation

The public header pairs the existing CW mark and Coursework wordmark with text actions and a small primary action. The homepage uses a compact 64px header and 32px hero top inset (24px on mobile), with a smaller mark and 44px action target. Auth pages use its simple variant. On mobile the optional explanatory anchor disappears while login/workspace access remains; below 400px the homepage reduces horizontal gaps to avoid wrapping. Workspace course navigation uses blue text/tonal selection and its existing active marker; it is not the public header repeated in an editor.

The homepage walkthrough uses three real workflow acts, with two scenes each:
course setup/result, chapter brief/draft, proposed/confirmed modification.
The act index stays in place while the canvas reveals the next state over 450ms.
Six short timeline segments describe this actual sequence, not outcome metrics.
Autoplay stops at the confirmed draft and pauses offscreen or in a hidden tab.
Manual controls stop autoplay; reduced motion defaults to manual navigation.
Mobile replaces the side index with a top row and stacks preview/review content.

Signed-in public and teacher headers use one circular avatar disclosure rather
than a horizontal name/profile/sign-out row. Its panel contains name/email,
role-appropriate workspace or qualification review, teacher profile for teachers,
home and sign-out. Guest login/registration remains unchanged. Keep the 44px
trigger target, private-image loading and initial fallback, outside/Escape/Tab
dismissal and inline sign-out error/retry. Account identity keys and aborted
requests prevent stale photos across accounts. Application-review identity also
stays inside its panel; no name is repeated beside the top avatar.

### Teaching example

The labelled example shows source, draft and proposed revision as live text, with semantic deletion/insertion and explicit acceptance. Acceptance changes the visible example and its status; replay restores it. This component is illustrative and never edits a real course. Keep its controls keyboard reachable and its full content available under reduced motion.

## Do's and Don'ts

Profile override approved 2026-10-26: `profile-refinement.css` uses Manrope for
body/display with existing Chinese fallbacks. A 240px private identity rail and
24px gap frame the unified form; collapse to one column at <=800px. Main title
30px/36, section20px/28, labels14px/20 and fields16px/24. Circular photos80px in
the rail and64px (48px mobile) in the upload editor retain private loading and
initial fallback. Complete 12px panel borders, 8px controls and24px/16px insets.
Actual unsubmitted/pending/rejected/approved state is labelled, never fabricated.
The save row stays in normal flow to avoid field occlusion. Application/auth
styling and backend qualification rules are outside this change.

User refinement later on 2026-10-26: omit the duplicate photo from the Profile
identity rail. Keep name/email there; retain the account-menu avatar and the
photo upload/editor preview. Removing the display never removes the saved photo.

Homepage override approved 2026-10-26: `homepage.css` replaces the earlier
photographic hero with the code-native six-scene walkthrough beside the headline.
Use Manrope for homepage body and display, Noto only for Chinese glyphs. Display
60px/1 (48px tablet/mobile, 36px at 320px); body20px/28 desktop and16px/24 mobile;
overview/FAQ30px/36 desktop and24px/32 mobile. Section gutters32px desktop/16px
mobile, related gaps8/12/16/24px, major gaps32/48/64px. Floating header64px tall,
16px radius, preserved avatar/dashboard for signed-in accounts. The approved
landing-page-design concept permits a subtle neutral text gradient on the hero
heading only; flat themed backgrounds everywhere else. Sample UI stays readable
at rest; existing pause/replay and reduced-motion behavior remain. Profile,
application, login and editing surfaces retain their previous tokens.

- Do reuse semantic theme variables and keep the refined homepage in one consistent light or dark theme.
- Do distinguish approved, pending and revision states with visible text as well as color.
- Do reflow examples, forms and review actions into a readable mobile sequence.
- Do preserve visible keyboard focus and reduced-motion access to the complete content.
- Don't replace the approved scoped type system or carry public display typography into the course editor.
- Don't replace readable text/code demonstrations with raster artwork containing labels.
- Don't add visual proof such as logos, testimonials, adoption numbers or progress that the product cannot substantiate.

Teacher operating screens override approved 2026-10-26: the course library uses
two aligned columns above 760px, one below, without restoring the removed title
banner. Use real descriptions/counts/status, 24px cards and gaps, 24px/32 titles,
14px/20 supporting text and 12px/16 metadata. Library and chapter UI use Manrope
with explicit CJK sans fallbacks; this supersedes the earlier editor-face note.
The chapter editor uses a 200px outline, flexible canvas and 304px review column
on wide screens. Export stays outside the tab scroller. Slide actions have their
own toolbar, and previous/next controls sit below the canvas rather than over
content. New-request scope shows visible slide order plus title, keyed by stable
ID; existing plans retain their frozen execution target. Composer precedes
pending proposals. On phones the reading canvas grows to contain its content;
the IR and fixed-layout export are unchanged. No other operating screens change.
