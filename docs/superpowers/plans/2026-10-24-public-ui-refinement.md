# Public home, profile and application refinement

Approved: preserve blue Coursework branding, replace typography, recompose the
homepage, consolidate account navigation and compact the profile/review pages.
Existing registration, profile fields, persistence and review permissions remain.

## Design read and tokens

Modern education product with a calm, task-first visual language. Homepage:
DESIGN_VARIANCE 6 / MOTION_INTENSITY 3 / VISUAL_DENSITY 4. Profile/application:
DESIGN_VARIANCE 3 / MOTION_INTENSITY 2 / VISUAL_DENSITY 5.

Preserved palette: navy ink #172033, blue #315fc6, canvas #f4f6f9, surface #ffffff,
body #536176, line #dde3ea. Existing amber/green retain semantic review roles.
Manrope display at 550-600, Source Sans 3 body at 400-600, Noto Sans SC/TC for
locale-appropriate Chinese. No serif, glow or new brand. Scope fonts only to
home/profile/application; keep course editor and login identities unchanged.

Layout: compact 76px navigation; home copy + generated editorial photo, followed
by the existing interactive IR-style teaching example; profile uses grouped form
and real identity/photo; review panel narrows to 756px with a 30px title. On
mobile, one-column forms and 16px inputs remain usable. Signature: a clear
distinction between illustrative teaching scene and an actual interactive demo,
not invented dashboard or outcome numbers.

## Execution and verification

- [x] Inspect incumbent code, screenshot, tokens, routes and existing tests.
- [x] Add browser acceptance checks; observe failure on old Geist type system.
- [x] Add scoped next/font faces and one-row account navigation, without changing
  session, profile-save or approval behavior.
- [x] Recompose home/profile/review and retain accessible labelled controls.
- [x] Inspect desktop/mobile/CJK/light/dark captures and actual font loading.
- [x] Run interactions, session boundaries, frontend tests, lint/typecheck/build.
- [x] Update design record and report honest verification boundaries.

No real-user edits, new account mutations, commits or pushes are authorized here.
