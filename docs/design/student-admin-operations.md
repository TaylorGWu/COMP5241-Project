# Student and administrator operations

This branch extends the same Coursework application and SQLite database. It does
not need a new model key or a separate authentication service.

## Role entry points

- `/student`: learning home, published catalogue, background/goal and invitation entry.
- `/student/courses/{courseId}`: published chapter overview and enrolment.
- `/student/courses/{courseId}/chapters/{chapterId}`: read-only lesson and MCQ practice.
- `/admin`: overview, applications, users, courses and activity.
- Existing instructor `/courses` and `/application` flows remain in place.

Students register through the existing student registration form. Instructor
accounts still require qualification approval before teaching tools become
available. Public registration cannot create an administrator. Provision one
locally with the existing command, from `backend`:

```sh
../.venv/bin/python -m app.auth_cli create-admin --name "Administrator" --email "admin@example.com"
```

The command prompts privately for the password. Do not place a real password or
API token in a command line, documentation or source control.

## Publishing and learning

An empty student catalogue is correct until an instructor explicitly publishes a
course with usable content. Publication saves the ready chapters as a delivery
snapshot. Editing a teacher draft afterwards does not change what students see;
publish again to replace the snapshot. Unpublishing removes student access while
retaining enrolment and learning records.

Joining a course is idempotent. A teacher-created invitation joins only its own
available course. Imported roster entries matching the student's account email
are reconciled in teacher analytics rather than counted a second time. This local
prototype still does not verify email ownership.

Progress counts visited current slide IDs and submitted supported MCQs. An
incorrect submission counts as participation, not as a correct answer. A chapter
without supported MCQs completes through reading. The score and participation
progress are separate. Only MCQs with valid options and an identifiable answer are
automatically graded; free-text/code/scenario items are not silently auto-marked.

The server calculates correctness and stores attempts. Retries retain history;
the latest compatible result determines current feedback. If a published question
changes, an earlier answer is not reused as a result for the new version.

## Administrative safety

Disabling or changing an account's role revokes its sessions. The administrator
cannot lock themself out or remove the last enabled administrator. Assigning the
instructor role starts pending qualification review rather than granting approval.

Course suspension requires a reason, blocks student access and blocks teacher
republishing. Restore removes the suspension; it does not publish a teacher draft.
Disabling an instructor's account and suspending their published course are
separate decisions. No operation physically deletes a course or learning attempt.

Activity is read-only. New administrative decisions have real actor/time metadata;
old generation, version and patch records with missing metadata display it as not
recorded. The activity API does not expose credentials, full upstream requests or
raw private teaching materials. Teacher version recording still follows, rather
than shares, the atomic publication transaction.

## Database and running

The existing backend/frontend dependency commands remain applicable. The database
path is selected through `TEACHER_WORKSPACE_DB`; an isolated worktree does not
automatically share another worktree's database or `env.yaml`. Choose that path
deliberately. For development checks, use a SQLite backup/copy first.

The portal migration uses schema version3, adds `portal_*` tables and preserves
existing accounts, courses, chapters, roster state and patches. Upgrading a
populated auth database takes a `.pre-portal-*.bak` SQLite backup; an initial
combined auth upgrade uses its existing `.pre-auth-*.bak` instead. Keep the backup
outside version control. Restore only with all application processes stopped,
after separately preserving the newer database and associated uploads.

If running on nondefault ports, configure matching `CORS_ORIGINS` on the backend
and `NEXT_PUBLIC_API_BASE` on the frontend. Use the same loopback hostname for both
so cookie sessions work. Real model keys remain backend-only; the new learning and
administration routes work without them.

API contracts: `docs/design/student-admin-api.md`. Actual test results and the
browser verification record: `docs/design/student-admin-verification.md`.

## Current local preview

The frontend is running on `http://localhost:3000` (or `http://127.0.0.1:3000`),
with the backend on port8000. Keep the same hostname throughout a login session.
The running code lives in the `codex/student-admin-portals` managed worktree,
not the original teacher checkout.

Its selected database is `backend/.local/student-admin-workspace.db` in that
worktree. It is an independent SQLite backup/copy, with original teacher identities
and sessions restored into the copy for compatibility, plus synthetic portal test
accounts. The original teacher DB was not migrated or published as a side effect.
Only the copied AI Concepts course was explicitly published for verification;
the other copied courses remain drafts. Test enrolments, answers and administrative
audit entries are internal verification data, not real learner evidence.

Student/admin flows and existing generated content do not require an API key.
Verification initially loaded no real model configuration. The final local service
reads the existing teacher worktree's private `backend/env.yaml` by path, without
copying or printing its contents, so existing teacher generation configuration is
available. No live model request was needed to test these portals. New deployments
must configure their own backend environment/YAML; never commit real keys.

For this machine's existing checkout, restart in two terminals (stop an existing
listener normally before starting another):

```sh
cd /Users/taylor/.codex/worktrees/student-admin-portals/COMP5241-Project/backend
APP_CONFIG_FILE=/Users/taylor/.codex/worktrees/teacher-courses/COMP5241-Project/backend/env.yaml TEACHER_WORKSPACE_DB="$PWD/.local/student-admin-workspace.db" CORS_ORIGINS='["http://127.0.0.1:3000","http://localhost:3000"]' /Users/taylor/Workspace/python/COMP5241/COMP5241-Project/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
cd /Users/taylor/.codex/worktrees/student-admin-portals/COMP5241-Project/frontend
npm run dev -- --hostname 127.0.0.1 --port 3000
```

These absolute paths describe this local managed worktree, not a portable team
distribution. Other machines should install the documented backend/frontend
dependencies and select their own private configuration and database paths.
