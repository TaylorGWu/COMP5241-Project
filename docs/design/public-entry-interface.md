# Public entry interface

Scope: `/`, `/login`, `/register/*`, `/application`, `/student`, `/admin`.
Teacher account extension: `/profile`, available before and after approval.
Modes: public homepage Persuade; authentication and account/review pages Operate.

2026-10-26 approved homepage concept supersedes the homepage photography and
first-viewport description below. Homepage alone uses Manrope for both body and
display (Noto SC/TC fallback), a compact floating navigation bar, and a three-line
teacher-agency headline beside the existing six-scene product walkthrough.
The walkthrough is code-native, not the generated concept image; its API-free
sample behavior, pause/replay, confirmation and reduced-motion support remain.
A flat three-step overview, word-reveal statement, six factual FAQ entries and
closing course action follow. Student registration remains a secondary link;
authenticated avatar and role destination are retained. No footer, fabricated
proof, pricing, legal policies or new product behavior is introduced. The scope
is isolated by `frontend/app/homepage.css`; profile/auth/editor typography stays
unchanged. The named landing-page-design skill and user-approved concept govern
the homepage's subtle heading text gradient and spacing/type scales.

2026-10-26 approved Profile concept: a private identity rail (photo, saved name,
email, in-page section navigation and real qualification state) sits beside one
unified form. Manrope extends to Profile body text; the application and login
surfaces retain their existing typography. Photo upload retains its separate
confirmation and never overwrites unsaved form edits. Experience/subjects pair
on desktop and stack on mobile. The save row stays in normal document flow:
an initial sticky treatment hid teaching fields during visual QA. The sidebar
collapses at <=800px, matching the incumbent breakpoint; qualification state
does not confer access by itself and all role gates remain server-enforced.
Signed-in public/teacher navigation shares one circular avatar disclosure, with
identity, role destination, teacher profile and logout inside. Guests retain
login/registration. A private photo is used when available; otherwise initials.
The user approved a product-led page inspired by major product sites, real local
accounts, and qualification-gated teacher registration. This extends the existing
Coursework visual system, not a rebrand. The interactive teaching example is
code-native UI, not a raster illustration or a live generation job.

## Direction contract

THESIS: Make teaching decisions visible. Demonstrate the transformation from a
course setup to a chapter draft and a teacher-approved change, instead of
listing generic AI features or presenting invented commercial proof.

OWN-WORLD: The existing light blue-grey canvas, navy ink, restrained royal blue,
and 8-14px control/panel corners. Home/profile/application use approved Manrope,
Source Sans 3 and Noto Sans SC/TC typography; course editing and authentication
retain Geist. The homepage respects the selected theme throughout, with labelled
illustrative photography distinct from the interactive teaching example. The auth
surface keeps its separate quiet photographic panel. Green is reserved for accepted state;
amber communicates review/revision, never a marketing accent.

STORY: A visitor sees what the product does, explores the labelled example, and
chooses learning or teaching. Students register immediately; teachers first create
an account, then separately submit a private credential and see review status.
An administrator reviews real files
and explicitly grants teacher access.

FIRST VIEWPORT: A compact 64px brand/nav row, restrained two-line left-aligned
title, short introduction and role actions next to a generated lesson-planning
photo. The image is explicitly illustrative, not user research. Below it, a
three-act walkthrough shows course setup, chapter creation and draft refinement.
Each act has a before/after scene: create/course card, chapter brief/generated
preview, pending proposal/confirmed change. The course stays draft throughout.
On mobile the act index becomes a top row and preview/review stack vertically.

FORM: User-approved product demonstration inside the established brand. Code-led
because the approved central visual is an interactive, deterministic product UI,
not painted artwork. Signature interaction: create course, add chapter, preview,
review, confirm and replay. A single bounded automatic progression runs only
onscreen in a visible document. Pause/play, replay and direct act selection are
available; manual interaction stops autoplay. Reduced motion starts paused and
disables spatial transitions. Samples are static semantic text, not fake editable
fields or requests to the generation API.

2026-10-23 user-directed auth revision: remove the large navy panel and fabricated
paper preview. Keep a focused 400px form on the left and a quiet, generated learning
studio photograph on the right, within a 1200px shell. Below 820px only the form
remains. The image is illustrative, not a campus affiliation or testimonial;
its prompt is retained in the PNG and adjacent provenance record. Use the same
Geist/navy/blue system with restrained interaction, not a second brand. Teacher
registration now creates the account before a separate qualification upload.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish
review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Boundaries and verification

2026-10-24 user-approved visual refinement: typography, single-row account header,
denser profile and review layout. No new approval, persistence or role behavior.
The homepage's previous repeated teacher/student/bottom actions are consolidated
in the hero and existing header. Public teaching text no longer fades to an
inaccessible contrast while the demo is idle. New image provenance:
`frontend/public/images/lesson-planning.provenance.md`.

2026-10-24 teacher profile increment: keep registration short. Add a private,
optional profile with photo, introduction, university, degree, institution or
independent-teacher status, position, experience and searchable multi-subject
selection. Group About/Education/Teaching in one restrained form; desktop uses a
section index and two-column fields, mobile stacks them. Preserve current tokens
and use native labelled form controls, not a marketing visual treatment. Photos
are saved separately and never overwrite unsaved text; show save/error feedback
and confirm discarding edits on navigation. Only the name is required.
Administrators can expand a submitted applicant's profile. No profile field
grants teacher access or implies a verified school affiliation.

Application refresh is a secondary action with a checking state, explicit
unchanged result and retryable error. A transient error does not discard the
current identity/page; real session expiry still returns to login. Approval
opens the teacher workspace and rejection exposes feedback and resubmission.

One generated decorative raster ships on auth pages, with its exact prompt embedded
and adjacent provenance documentation. No fake social sign-in, pricing, users, school
logos, testimonials, automatic approval or artificial learning progress. Student
and admin destinations explicitly describe what is currently implemented.
Public copy supports English, Traditional Chinese and Simplified Chinese through
`frontend/lib/public-copy.ts`; login/registration errors originate in backend
validation where necessary. Public preferences are in document flow so they do
not obscure form submission or example controls.

Verify desktop and mobile, form errors, keyboard focus, password visibility,
upload selection, application pending/rejected/resubmit, administrator decisions,
student activation, logout and protected route redirects. Authentication and
ownership need API tests independently of visual inspection.

Visual references inspected 2026-10-22: https://linear.app/,
https://www.notion.com/product, https://stripe.com/.
