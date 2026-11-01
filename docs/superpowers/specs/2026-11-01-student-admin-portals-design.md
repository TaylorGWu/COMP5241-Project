# Student and administrator portals

Date: 2026-11-01  
Base: `codex/teacher-courses`, commit `7efa5e9`  
Development branch: `codex/student-admin-portals`

## Purpose and scope

Complete the existing product's learning and administration loop without replacing
the instructor workspace. This implements FR-01, FR-02, FR-03, FR-06 and FR-18–20
from `docs/requirements.md`. These remain product requirements, not findings from
external user research.

The first acceptance journey is:

1. An approved instructor publishes an existing course.
2. A student discovers it, joins, reads a chapter and submits an MCQ.
3. The student receives feedback and resumes with saved progress after signing in again.
4. The instructor sees the student's actual participation and results.
5. An administrator can review qualifications, manage access, and take the course offline.

Use the existing Next.js/FastAPI/SQLite application, opaque cookie sessions and
CSRF handling. No additional AI API or secret is required for these flows.
Do not migrate to PostgreSQL, add a general AI tutor, payments, realtime collaboration,
or new generation/export capabilities as part of this work.

## Existing implementation and approaches

The student route currently renders an account welcome/empty state. The admin route
already supports qualification review. Instructor rosters, attempts and versions
are persisted in a teacher-state JSON snapshot, but enrolment IDs are not
authenticated student IDs and invite strings are not persisted as redeemable records.

Chosen approach: additive, authenticated portal services and database tables within
the existing application. Keep the current instructor endpoints compatible and
merge authenticated learning data into their analytics response. This avoids a
second, unrelated dashboard and avoids a risky whole-database rewrite.

Rejected alternatives:

- Separate frontend-only demos: quick to show, but cannot demonstrate persisted learning or permissions.
- Full persistence/auth replacement: expands deployment and migration risk without improving this core journey.

## Student experience

### Home and catalogue

The student home prioritises Continue learning, then one explained recommendation,
then the published catalogue. Search covers course title, code and subject. Use real
counts, no fabricated activity, testimonials, completion statistics or charts.

Allow students to join a publicly listed published course themselves. Registration
remains unrestricted. Existing CSV invitations may link the matching authenticated
email to its roster record; no user can claim another email or student identity.
Redeemable instructor invite codes must be stored, validated and restricted to their
course. Repeated joining is idempotent.

A short editable background/goal form supports one deterministic recommendation.
Explain the matching inputs in plain language. Do not call this ML personalisation.
If no suitable published course exists, show an honest empty state rather than a
draft course or invented recommendation.

### Course and chapter player

Use a read-only course overview and chapter player, separate from instructor editor
routes. The player has a chapter outline, readable slides, previous/next controls,
progress and a chapter practice section. Reuse existing IR visual rendering where
safe, but never expose editing, generation, answer keys or instructor-only notes.

Persist visited slide IDs and the last location against the authenticated account.
Reading completion is based on visited slides, not a browser-supplied percentage.
For chapters with supported MCQs, completion also requires submission of the
chapter's MCQs; passing is not required to count participation. Show score separately.
Chapters without supported MCQs can complete through reading alone. Explain this
definition in the UI and documentation.

Grade supported MCQs on the backend against the published question version. Return
correct answer and explanation only after submission. Keep immutable attempts,
allow retry, and use the latest answer per question for the current score/common-
mistake summary. Reject unknown questions/options and attempts without enrolment.
Do not silently auto-grade free-text/code/scenario questions as MCQs.

## Publication and private content boundary

Student delivery reads a persisted publication snapshot, not the instructor's live
draft package. Publishing freezes the ready chapters, slide order, supported
questions and asset references. Later teacher edits remain invisible until another
explicit publish. Pending/failed/empty chapters never enter a snapshot.

Existing courses already marked published can be initialised from their currently
ready content by a documented, idempotent migration. Draft courses are never seeded.
No course is automatically published to make the catalogue look populated.

Student responses use explicit allowlists. Exclude answer keys before submission,
speaker notes, original uploaded materials, source excerpts, prompts, proposed
patches, versions, qualifications and other students' identities/results. Slide quiz
pages must not accidentally reveal a practice answer through teacher-side fields.

Serve referenced images/diagrams through student-scoped asset endpoints that require
an enabled student, enrolment and a currently available publication snapshot. Never
relax the existing instructor asset ownership checks or expose upload filesystem paths.

Teacher unpublishing or administrator suspension removes the course from both
catalogue and direct student access. Retain enrolments and learning records so they
are available if the course returns. Republished changes must reconcile progress
using stable IDs; removed slide/question IDs must not inflate completion or score.

## Instructor integration

Preserve the existing instructor analytics response shape and owner checks. Combine
legacy imported roster entries with authenticated enrolments without duplicate
students. New progress and server-graded attempts are the source for real learner
completion, average score and current common mistakes. Keep historical attempts
separate from current per-student scores; repeated mistakes by one student must not
be presented as several affected students.

Publishing must respect administrator suspension. An instructor cannot undo it by
publishing again, updating course metadata or using a second existing publish path.

## Administrator experience

One focused admin shell with Overview, Applications, Users, Courses and Activity.
Reuse the existing qualification download/profile and approve/reject flow; rejection
continues to require a reason. Do not expose public admin registration.

Users: search/filter, inspect role and enabled state, change role, disable/re-enable.
Backend guards prevent disabling/demoting the last enabled administrator and prevent
self-lockout. Changes revoke affected sessions. Promoting someone to instructor
does not approve qualifications: newly assigned instructors start pending. Keep
credentials, password hashes and session tokens out of every response.

Courses: list all courses, their owner and publication/moderation state. Suspension
requires a reason and records administrator/time. Restore removes suspension but
does not publish a draft or overwrite instructor edits. Administrator actions never
edit someone else's lesson content and never physically delete courses or attempts.

Activity: read-only views of qualification decisions, new administrative actions,
and available course generation/version/patch evidence. Preserve real provenance.
For old records without time/model/actor metadata, show Not recorded instead of
inventing it. Expose only safe, necessary fields, not raw upstream requests or secrets.
No update/delete audit API.

## Data and service boundaries

Add versioned, idempotent SQLite schema changes for student profiles, authenticated
enrolments, publication snapshots, progress, quiz attempts, course invitations,
moderation and administrator action logs. Use foreign keys and unique enrolment /
progress keys. Take a SQLite backup before upgrading a populated database.

Separate services own publication delivery, learning state and administration;
separate routers own `/api/student/*` and `/api/admin/*` additions. Reuse AuthStore
for identity and its connection boundary, not copied login logic. Keep request-body
limits and no-store/security headers consistent for both portal APIs.

Transactions protect joining, submissions, moderation and last-admin checks.
Backend derives student identity from the session, never a submitted student ID.
Preserve existing teacher-state data; do not replace it with an empty snapshot.

## Interface and failure states

Follow `DESIGN.md` and existing semantic light/dark tokens, Manrope and Chinese
fallbacks, the circular account menu and current language preference. English is
the default; new UI copy also supports Simplified and Traditional Chinese.
Keep the operating screens compact, with visible labels and purposeful whitespace.

Support desktop and 320px mobile, keyboard controls and visible focus. Do not reduce
slide text to fit an unreadable fixed-height mobile canvas. Loading, empty, denied,
unpublished and request-failure states have distinct messages and retry/navigation.
Mutations show pending state and prevent repeated clicks. Failed saves do not show
success; retries must not duplicate enrolments or recorded submissions.

## Verification and evidence

Use test-first implementation with temporary databases, no live model calls.

- Published-only catalogue/direct access; edited drafts remain private until republish.
- Student enrolment and identity isolation, private asset checks, no answer leakage.
- Server grading, malformed/foreign answer rejection, retry and refresh persistence.
- Progress after slide deletion/republication, no-question chapters and withdrawal.
- Instructor analytics match actual authenticated attempts without roster duplication.
- Admin-only APIs, immediate disable/role effects, last-admin and self-lockout guards.
- Suspension blocks student access and teacher republishing until admin restores it.
- Schema upgrade/backup preserves legacy courses, accounts, rosters and versions.
- No secret-bearing audit payloads and no mutation API for audit history.
- Existing teacher/auth/export tests remain green; frontend tests, typecheck and build.
- Actual browser walkthroughs for all three roles and mobile overflow/keyboard checks.

Record commands and actual results, and provide concise run/manual instructions.
Browser checks are internal verification, not external usability tests. Do not push
to main or overwrite teammates' handoff archives.
