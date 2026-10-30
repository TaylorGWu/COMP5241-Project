# Teacher profile verification

Date: 2026-10-24 (Hong Kong). Branch: `codex/teacher-courses`.

## Scope and decisions

User approved a separate, optional profile after account registration: own photo,
name, biography, graduation institution, degree, current institution or independent
teacher, position, experience and multiple subjects. Only name is required.
University/institution are free text to avoid pretending to maintain a complete
verified school directory. Degree and experience use native selects; subjects use
a searchable checkbox group with removable tags and an Other field. Existing
Geist/blue-grey tokens and responsive form patterns are preserved, as guided by
the requested frontend-design and design-taste-frontend skills. This is an Operate
surface, not a marketing-page redesign.

Profile data and photos remain private to the teacher and administrators. Photos
are decoded, bounded to 20 million pixels and 5 MiB, resized to at most 512px and
re-encoded without EXIF metadata. Qualification review remains separate; profile
editing cannot grant course access. Photo saves do not overwrite dirty text.
Navigation and unload warn about unsaved work. Admins can inspect a submitted
applicant's profile on demand.

Application refresh is secondary and reports checking, unchanged pending review,
updated rejection or retryable failure. Transient failures retain the current
page; real 401 expiry clears identity and returns to login. Existing abort-based
identity restoration is reused, so delayed responses cannot revive signed-out
accounts.

## Automated evidence

- New API tests first failed on missing profile routes (404), then passed after
  implementation. Full backend suite: **396 passed**. Tests use temporary SQLite
  databases, real image decoding and real session/CSRF checks, not developer data.
- Frontend payload whitelist and private-account expiry tests were observed red
  before their fixes. Full frontend suite: **70 passed**. Existing Node type-strip
  and typeless-package warnings remain; no test failures.
- Scoped ESLint for TeacherProfile, teacher-profile copy/helpers, AccountProvider
  and AccountPages: exit 0. TypeScript: exit 0. Production build: exit 0, including
  `/profile` among 15 routes.
- `teacher-profile.cjs`: real mounted browser controls with synthetic HTTP
  responses; covers saves/reload, failure retaining input, navigation cancellation,
  multi-subject search, photo save/remove without overwriting text, independent
  status, three mobile locales, admin disclosure, student guard, session expiry,
  pending/error/rejected/approved refresh. Passed on development and production
  previews. Desktop and mobile captures inspected, including light/dark variants.
- `auth-session-boundary.cjs`: **7 scenarios passed** on the temporary production
  preview. Development StrictMode duplicates course fetches and violates that
  script's exact-request-count assertion; the production run resolves this test
  environment difference without weakening the assertion.
- Read-only reviewer found no Critical/Important issue; its unsaved internal
  navigation observation was addressed with explicit discard confirmation.
- `git diff --check`: clean. Existing 3000/8000 services retained; 8000 health OK.

## Evidence boundaries

Browser scripts intercept HTTP boundaries and do not mutate real accounts or
demonstrate a production deployment. Backend integration tests independently
exercise persistence and access controls. These are automated/internal checks,
not external usability tests, teacher identity verification or proof of teaching
effectiveness. No interview, school affiliation or real user feedback is claimed.
No commits or pushes were made for this increment.
