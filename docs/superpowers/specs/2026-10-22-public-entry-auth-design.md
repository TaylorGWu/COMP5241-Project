# Public entry, role registration and local authentication

Status: approved design, including qualification-review amendment. Implementation
and verification status is tracked in the companion implementation plan.

## 1. Approved intent

Build a distinctive public homepage, unified login, separate student/instructor
registration, and working SQLite-backed accounts. Preserve the existing
Coursework identity and teacher workflow. Administrators are provisioned locally,
not through public registration. Existing course data must survive the change.

Approved amendment (2026-10-22, registration order revised below): students register without approval. Instructor
qualification submission creates a pending application. Only
an administrator may approve/reject it; pending/rejected instructors may sign in
to their application-status page but cannot access any teacher endpoint. Rejection
requires a reason. A rejected applicant can replace the document and resubmit.
PDF, JPEG and PNG are allowed up to 5 MiB with signature checks and bounded reads.
Store uploads privately in SQLite, expose only authorized attachment downloads
with nosniff/no-store, never an inline public URL. No automated identity-verification
claim. Record reviewer, timestamp and reason for each decision. Existing sessions
must observe approval changes on the next request.

Approved revision (2026-10-23): instructor account registration is separate from
qualification submission. Credentials alone create the account; the applicant
uploads qualification afterward on `/application`. Account JSON includes
`qualificationSubmitted` to distinguish not-yet-submitted from in-review. The
initial upload is allowed once; pending files cannot be replaced until rejection.
An administrator cannot review an account without a submitted file. Unsubmitted,
pending and rejected accounts cannot create courses or call teacher tools. Student
registration is unchanged. Registration may still accept a qualification for
backwards compatibility, but the current registration form does not collect one.

The user approved the combined visual and account-system scope on 2026-10-22.
This document resolves the implementation and safety boundaries for review before
coding. Existing uncommitted navigation refinements and unrelated student HTML
prototype changes must not be discarded or silently included in design commits.

## 2. Pre-implementation baseline and consequences

- `/` redirects directly to `/courses`; there is no public entry or auth flow.
- FastAPI mounts `/api/demo/*`; these teacher endpoints are not authenticated.
- `current_role()` is a fail-closed placeholder, not a working identity system.
- Courses and chapters live in `backend/.local/teacher-workspace.db`, but do not
  have account owners. They must not become visible to every new instructor.
- `demo.STATE` contains a process-global active package and patch store. Merely
  checking a cookie would not isolate concurrent teachers or browser tabs.
- JSON, uploads, streams, image URLs and export links all need authenticated
  access. Hiding pages in React is not an authorization boundary.
- The runnable student portal is not present in this teacher worktree. Do not
  merge another branch or label a new account landing screen a complete LMS.

## 3. Visual and interaction contract

### Homepage

Retain the existing deep navy, restrained blue, light surfaces and type family.
The public page is more expressive than the workspace without introducing a
second unrelated brand. Establish a clear heading, concise value proposition,
and a product-led first viewport rather than a generic feature-card wall.

The central demonstration is a deterministic, code-native illustration of the
real workflow: teaching brief, structured slide, proposed change, teacher
confirmation. Visitors can advance or replay it. It must be labelled as an
example and must not make model calls, read private course data or publish
anything. Reduced-motion users see a stable, fully readable demonstration.

Explain student learning and instructor preparation through differentiated
sections. End with working student/instructor registration actions. No invented
adoption numbers, testimonials, institutional logos or production-readiness
claims. References inform composition and clarity, not copied assets or copy:

- https://linear.app/
- https://www.notion.com/product
- https://stripe.com/

### Login and registration

One shared brand/header and form system. Desktop pairs a quiet editorial product
panel with the form; mobile puts the task first and removes nonessential artwork.
Student and instructor registration share credential controls but have different
role-specific introductions and an explicit link to switch registration type.
Use name, email, password and password confirmation. Do not collect school or
organization details unless a downstream implemented feature needs them.

Labels remain visible; use appropriate autocomplete, focus, password visibility,
inline errors, submission/loading states, and accessible error summaries. Do not
disable paste or prevent password-manager use. No social-login, password-reset
or email-verification controls until their services actually exist. State the
local prototype's lack of email verification without suggesting a verified
teacher identity. Approved self-registered instructors only gain their own empty
workspace; pending and rejected instructors see their application status instead.

Inherit the existing language/theme settings. New public/auth copy belongs in the
existing English, Traditional Chinese and Simplified Chinese dictionaries. Public
headings and metadata must no longer describe the whole app as teacher-only.

## 4. Routes and role destinations

| Route | Purpose |
| --- | --- |
| `/` | Public homepage; remains usable when logged in |
| `/login` | Shared email/password sign-in |
| `/register` | Accessible student/instructor choice, not an admin option |
| `/register/student` | Student account creation |
| `/register/instructor` | Instructor account creation |
| `/application` | Instructor qualification status, review reason and resubmission |
| `/courses` and descendants | Existing instructor workspace, now protected |
| `/student` | Authenticated student account landing, with honest availability/empty state |
| `/admin` | Authenticated administrator account landing, not the full planned admin console |

After sign-in or successful registration, redirect by server-established role.
Do not ask a user to select their role again at login. A `next` parameter may only
name a relative, role-appropriate internal route; reject absolute and protocol-
relative values. Unauthenticated users return to login; wrong-role requests get a
clear denied state and a link to their own destination.

The student landing provides identity/session confirmation and sign-out. Do not
invent courses, progress, recommendations or learning activities. Connecting the
separate student portal is a later explicit integration task. Likewise, full
user moderation and generation auditing are outside this increment.

## 5. Account and session storage

Add versioned, additive migrations to the existing local SQLite workspace:

- `users`: random ID, normalized unique email, display name, password hash, role
  constrained to student/instructor/admin, active flag, creation timestamp.
- `sessions`: SHA-256 digest of a cryptographically random session token, user
  foreign key, creation/expiry timestamps, CSRF-token digest; never store the raw
  bearer token. Absolute expiry is seven days; logout revokes the row.
- `course_owners`: course primary key/foreign key, instructor foreign key,
  assignment timestamp. Unowned legacy courses remain unowned.
- Bounded persisted auth-attempt counters for per-IP and normalized-account
  throttling, with expiry/cleanup; this is a local single-process prototype, not a
  distributed abuse-protection service.

Use Argon2id via a maintained password-hashing library, at least the OWASP
baseline (19 MiB memory, two iterations, parallelism one). Accept 15–128-character
passwords without silent truncation, forced character classes or trimming.
Cap request sizes before hashing. Password hashing/verification runs off the
async event loop. Unknown-email sign-in does a dummy verification and returns
the same generic response as an incorrect password.

Treat role and enabled state as server-controlled data read on every request;
neither cookies nor form fields may override them. Public registration accepts
only student/instructor and rejects admin or unexpected privilege fields.

## 6. Authentication transport and API

Prefer opaque server-side sessions over JWT for this local SQLite increment:
logout and disabled-account revocation are immediate without token deny lists.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/auth/csrf` | Issue a short-lived pre-auth CSRF challenge |
| `POST /api/auth/register` | Validate student/instructor account; create fresh session |
| `POST /api/auth/login` | Generic credential check; rotate session and CSRF token |
| `GET /api/auth/me` | Return safe user fields and session-bound CSRF token; no-store |
| `POST /api/auth/logout` | Revoke session; expire cookie |

Cookies are HttpOnly, SameSite=Lax and Path=/, without a broad Domain attribute.
Production requires HTTPS and Secure cookies. Development HTTP is explicitly
limited to loopback configuration. Configure exact frontend origins, never `*`
with credentials. Add `credentials: include` to all browser API requests.

Unsafe requests, including login/register/logout and uploads, require an allowed
Origin plus a valid CSRF header/challenge. Bind post-login CSRF to the session;
return it through a no-store authenticated response, not localStorage. Block
foreign and null origins; document explicit Origin/CSRF headers for CLI clients.
Do not rely on SameSite or CORS alone. Enforce JSON request types where intended.
Auth responses and authenticated private content use no-store caching.

Frontend route checks improve navigation but FastAPI authenticates every private
endpoint. SSR checks forward only the needed session cookie to a fixed backend
origin, never a user-supplied URL. All fetch/stream/upload/delete helpers share
credential/error handling. Image and download URLs must work with the same cookie
session and cannot become public file-serving escape hatches.

## 7. Course ownership and editing isolation

Protect the complete teacher router with instructor authorization, including
legacy state/reset, generation, exports, diagram resources and patch operations.
Administrator identity alone does not imply instructor edit permissions.

Course creation and owner assignment occur in one transaction. Lists are filtered
by owner; any path carrying a course ID checks ownership before loading chapters,
running a model, reading files or mutating state. Foreign resources return 404;
wrong-role access returns 403; missing/expired sessions return 401.

Replace process-global active editing state with explicit per-user, per-course,
per-chapter context, scoped before creating a streaming response. The deprecated
unscoped endpoints resolve an active context inside that user's session, never
the last chapter another user activated. Concurrent edits to the same chapter
are serialized/rejected with a clear retry response; distinct chapters and users
must not share package references or locks. Cancelling an SSE connection must
release state/locks. Stream closures capture their own context.

Keep proposed patches scoped to the authorized chapter. A guessed patch ID cannot
apply/reject another teacher's change. Reads and exports must not change the
active context behind an unrelated open tab. Preserve draft/publish semantics.

This increment does not replace the generation engine with ARQ or claim
multi-worker generation safety. Until that planned work is complete, run one
application worker and test concurrent requests within that process. Account and
ownership persistence must still survive restart.

## 8. Legacy data and local administration

Migrations do not drop or rewrite course IR, patches or version history. Back up
SQLite through its backup API before running a real-workspace migration; do not
copy a live WAL database incompletely or include backups in Git.

Provide local CLI commands to create an administrator and explicitly assign
listed unowned courses to a selected existing instructor email. Password input is
interactive/hidden, never a required command-line argument or printed output.
Assignment validates the account role and refuses overwriting another owner.
No default credentials and no automatic first-user admin/legacy-data claim.

Automated tests use temporary databases. Do not run real course ownership
assignment, create a real user, reset the workspace or publish existing courses
as an implementation smoke test without the user's explicit request.

## 9. Verification and acceptance

Write failing tests first for each new behavior; retain existing generation,
review, animation and export regressions with explicit authenticated fixtures.
Never introduce a production auth bypass merely to keep old tests green.

Acceptance includes:

1. Student/instructor registration and login work after reload and backend restart.
2. Duplicate normalized emails, invalid roles and invalid credentials are handled;
   password/session secrets are absent from API payloads and logs.
3. Missing, expired, revoked and disabled-account sessions are denied; old sessions
   cannot be fixed/reused through sign-in. Sign-out clears protected UI state.
4. CSRF, Origin checks, login throttling, cookie attributes and unsafe `next`
   redirects have negative tests.
5. Two teachers cannot list/read/edit/export each other's courses, chapters,
   patches, analytics or assets. Student/admin cannot call instructor tools.
6. Interleaved teacher requests and simultaneous streams do not cross packages;
   two tabs editing different chapters cannot silently modify the wrong chapter.
7. Existing SQLite data survives migration unowned; only explicit local assignment
   changes ownership. Assignment refuses reassignment and preserves IR/history.
8. Browser verification covers homepage interaction, both registrations, login,
   password visibility, validation failures, sign-out, expired session and guarded
   routes at desktop and mobile widths, keyboard-only and reduced motion.
9. Run backend tests, frontend tests, TypeScript check, production build and diff
   checks. Update README with local administration, account setup, limits and
   single-worker requirement. Report actual evidence, not planned success.

## 10. Security references

- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

These inform the implementation contract; they are not a security-audit claim.
