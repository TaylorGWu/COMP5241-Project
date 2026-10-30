# Public entry and reviewed instructor accounts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Ship a polished public entry and real SQLite student/instructor accounts with administrator-reviewed qualifications.

**Architecture:** Cookie-based opaque sessions authenticate FastAPI. Server-side role, instructor approval and course ownership guard all existing teacher tools. Public/auth pages share the established brand; private editing context is separated across accounts and chapter paths.

**Tech Stack:** Next.js/React/TypeScript, FastAPI, SQLite, Argon2id, multipart uploads.

**Spec:** `docs/superpowers/specs/2026-10-22-public-entry-auth-design.md`, including its qualification-review amendment.

**2026-10-23 revision:** teacher registration is account-only. Instructor account
JSON additionally exposes `qualificationSubmitted`; initial qualification upload
is a separate authenticated action. This supersedes the original combined-form
wording below, while preserving the approval gate on teacher APIs.

## Global Constraints

- Work in the existing `codex/teacher-courses` worktree; preserve unrelated dirty files and previous navigation changes.
- Students self-register; instructors register an account first, separately upload PDF/PNG/JPEG up to 5 MiB, and wait for administrator approval before creating courses.
- No public admin registration, default passwords, first-user privileges, automatic legacy ownership, fake testimonials or unavailable social sign-in.
- Existing SQLite data is preserved; real-workspace migration is backed up. Tests use temporary databases.
- Three UI languages, responsive layouts, keyboard labels/focus, reduced motion, no private data in public demos.
- Passwords use Argon2id; 15–128 characters; session cookie HttpOnly/Lax, Secure in production. Origin plus CSRF for unsafe requests.
- No production auth bypass. Single-process generation remains an explicitly documented limitation.

## Task 1: Accounts, sessions, qualifications and administrator review

**Files:** new `backend/app/services/auth.py`, `backend/app/api/routes/auth.py`, `backend/app/auth_cli.py`, `backend/tests/test_auth.py`; modify configuration, requirements and app routing.

**Interfaces:** public user JSON `{id, name, email, role, status, reviewReason}`; roles student/instructor/admin; instructor status pending/approved/rejected, other roles active. `/api/auth/me` returns `{user, csrfToken}`. Register accepts multipart name/email/password/role/qualification. Login accepts JSON email/password. Both return `{user, csrfToken}` and set a fresh session cookie. `/api/auth/csrf` returns `{csrfToken}`. Logout is POST. `/api/auth/qualification` replaces a rejected application's file; GET downloads own file. Admin GET `/api/admin/applications` returns `{applications}` with applicant safe fields, qualification filename and submitted timestamp; GET `/api/admin/applications/{id}/qualification` downloads a file; POST `/api/admin/applications/{id}/review` accepts `{decision: "approved"|"rejected", reason}`. Authentication store resolves the current user for request and exposes approved-instructor/admin dependencies.

- [x] Write failing temporary-database tests for missing registration/login, student activation, mandatory qualifications, pending instructor denial, approval/rejection/resubmission, unauthorized downloads and public admin rejection.
- [x] Run the tests and confirm missing endpoints/behavior fail.
- [x] Implement additive auth schema, password hashing off the event loop, opaque sessions, CSRF/Origin checks, throttling, bounded file validation and review audit history.
- [x] Add local hidden-password CLI administrator creation and explicit unowned-course assignment; tests must reject automatic/reassignment behavior.
- [x] Verify registration persistence, duplicate normalized emails, invalid credentials, logout/expiry, cookie settings, unsafe redirects, hostile Origin and disabled-user checks.

## Task 2: Teacher authorization and state isolation

**Files:** modify `backend/app/api/routes/demo.py`, `backend/app/services/sqlite_workspace.py`, `backend/app/api/deps.py`, existing API test fixtures; new `backend/tests/test_auth_isolation.py`.

**Interfaces:** every `/api/demo/*` route requires an approved instructor. Course IDs are authorized against `course_owners`; JSON lists contain only owned courses. New courses are created and assigned transactionally. Legacy courses remain unowned until CLI assignment. Scoped DOCX export URLs mirror the existing chapter deck path. State resolves request-local packages by authenticated session and requested chapter, not module-global last activation.

- [x] Write failing tests using two independently authenticated teachers and a student; assert 401/403/404 on list/read/write/export/assets/patch misuse.
- [x] Write an interleaved chapter/session test that would fail if shared `STATE` were restored.
- [x] Implement router-wide authentication, owner filtering and request-bound editing context with locks that survive until streaming ends and release on disconnect.
- [x] Update existing API regression fixtures to explicitly authenticate with temporary data. Do not disable production authentication.
- [x] Run old generation/export/review/persistence tests plus new isolation tests.

## Task 3: Public identity and real auth flows

**Files:** new public/auth React components, `frontend/lib/auth.ts`, public copy dictionaries, route guards, `/login`, `/register`, role-specific registration, `/application`, `/student`, `/admin`; modify root page/layout, teacher navigation and API transport.

**Interfaces:** frontend calls Task 1 endpoints with cookies and CSRF; `roleDestination(user)` sends pending/rejected instructors to `/application`, approved instructors to `/courses`, students to `/student`, admins to `/admin`. Only role-appropriate relative redirects are accepted. Guarded teacher pages do not mount editors or fetch private courses before `/me` succeeds.

- [x] Write failing behavior tests for destination and safe redirect helpers and a browser smoke script exercising actual forms.
- [x] Build the public homepage with a labelled deterministic teaching-review demo, three-language copy, navy/light visual system, authored limited motion and reduced-motion fallback.
- [x] Build unified login, student/instructor registration, separate qualification upload, pending/rejected application status and resubmission. No unusable controls or invented learning data.
- [x] Build real administrator application queue, private qualification download and approve/reject interaction with mandatory rejection reason.
- [x] Update every existing API JSON/stream/upload/delete call with credentials/CSRF. Scope all export URLs. Add visible account identity/sign-out without reintroducing duplicate create actions.
- [x] Verify desktop/mobile, keyboard submission, error focus, password visibility, role redirects, missing sessions and expired sessions.

## Task 4: Integrated verification and handoff

**Files:** README and backend/frontend setup docs; browser verification artifact under temporary files; tests from Tasks 1–3.

- [x] Run backend pytest, frontend node tests, TypeScript and production build; inspect complete failures before claiming success.
- [x] Drive new accounts and approval through the browser against disposable databases only. Test two isolated browser contexts; non-owner downloads are separately covered by backend integration tests.
- [x] Review security boundaries and rendered screenshots independently; fix actionable findings and rerun relevant checks.
- [x] Document admin creation, private qualification handling, explicit legacy-course assignment, no email service, single-worker generation and local-only prototype boundaries.
- [x] Report actual implementation status and remaining limitations. Do not push, publish, assign real courses or create a real admin without explicit authorization.

## Verification record — 2026-10-23

- Full backend suite: 378 passed. Frontend Node suite: 62 passed; TypeScript and
  production build passed. Existing experimental Node warnings remain.
- Disposable-database browser flow passed: student activation, teacher account
  without a file, later upload, denied teacher access, admin download/rejection,
  resubmission, approval, logout/login and course creation.
- Seven synthetic-HTTP browser scenarios passed for account-switch state reset,
  expired-session CSRF recovery, late successful/401 identity responses and stale
  admin/applicant state. These are frontend regressions, not server authorization
  evidence; backend integration tests cover authorization separately.
- Fourteen public/auth captures cover desktop/mobile, light/dark and three
  interface languages; login actions are visible and no horizontal overflow or
  JavaScript page errors were observed. Revised mobile Git content is stacked.
- Independent code delta review found no Critical/Important issue. Original CSRF
  and identity-state findings were resolved. Visual review's final verdict scored
  both its documentation and approval-copy fixes resolved, disposition `ship`.
- PRODUCT.md, token-bearing DESIGN.md and sidecar capture the implemented system.
  The generated decorative photo retains its exact prompt in metadata and its
  adjacent provenance record. It is not evidence of a real campus affiliation.
- No real administrator created, no old course assigned, no real data reset and
  no push/merge. Student learning integration, email services, ARQ and production
  deployment remain outside this increment. Automated checks are not interviews
  or outside-group usability testing.
