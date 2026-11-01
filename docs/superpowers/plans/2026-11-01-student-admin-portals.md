# Student and administrator portals implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Complete authenticated student learning and administrator operations, integrated with the instructor workspace.

**Architecture:** Add small SQLite-backed publication, learning and administration services to the existing application. Student delivery uses an explicitly published IR snapshot. Keep instructor response contracts compatible and combine real student records into analytics.

**Tech Stack:** Existing FastAPI, SQLite, Pydantic, Next.js, React and TypeScript; no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-11-01-student-admin-portals-design.md`

## Global constraints

- Branch `codex/student-admin-portals`; preserve original branch, DB and handoff ZIPs. No push/merge.
- SQLite migrations are additive, versioned and backed up before upgrading existing populated data.
- Reuse opaque sessions, server-side RBAC and CSRF. Never accept client identity or grade as authoritative.
- Student delivery reads publication snapshots; draft changes require explicit republish.
- Student APIs omit private prompts, original materials, notes, answer keys before submission, other learners and credentials.
- No general AI tutor, new model calls, automatic publication or destructive deletion.
- Administrator suspension cannot be undone by instructor publication. Restoring does not publish drafts.
- Disable/demotion revokes sessions; guard self-lockout and the last enabled administrator.
- Use existing semantic theme tokens and Manrope/CJK fonts, 320px layout, English/Traditional/Simplified copy.
- Tests exercise real services against temporary DBs; no model requests, no mutation of active teacher data.

## Task 1: Integrated portal backend

**Files:**
- Create `backend/app/services/portal_store.py` (schema/transactions/backup), `publication.py` (snapshot and safe delivery), `student_learning.py` (profile/enrolment/progress/grading), `administration.py` (users/moderation/audit).
- Create `backend/app/api/routes/student.py`, `admin.py` and `backend/tests/test_portals.py`.
- Modify `backend/app/main.py`, `backend/app/api/routes/auth.py` middleware prefixes, and minimal instructor integration in `backend/app/api/routes/demo.py` / `backend/app/services/teacher_courses.py` as needed.
- Create `docs/design/student-admin-api.md` documenting the actual API and invariants.

**Interfaces:**
All JSON fields camelCase. Admin existing qualification routes stay unchanged.

```text
GET /api/student/home -> {courses: CourseSummary[], profile: {background,goal}, recommendation: {courseId,reason}|null}
PUT /api/student/profile {background,goal} -> {profile}
GET /api/student/courses/{id} -> {course: CourseSummary, chapters: ChapterSummary[], enrolled: bool}
POST /api/student/courses/{id}/enroll {} -> {course,chapters,enrolled}
POST /api/student/join {code} -> {courseId}
GET /api/student/courses/{id}/chapters/{chapterId} -> {chapter: {id,title,slides,questions,glossary}, progress, results}
POST /api/student/courses/{id}/chapters/{chapterId}/progress {slideId} -> {progress}
POST /api/student/courses/{id}/chapters/{chapterId}/attempts {questionId,optionId,submissionId} -> {result,progress}
GET /api/student/courses/{id}/chapters/{chapterId}/assets/{assetId}.{svg|png} -> private referenced asset

CourseSummary: {id,title,description,courseCode,subject,level,durationMin,chapterCount,enrolled,completionPercent,lastChapterId,lastSlideId}
ChapterSummary: {id,title,slideCount,questionCount,completionPercent,completed}
Slide: safe existing Slide IR visual/content fields, excluding private fields; asset URL uses student endpoint.
Question: {id,stem,options:[{id,text}]} (no answer/explanation until submitted).
Progress: {visitedSlideIds,lastSlideId,completionPercent,completed}
Results: dictionary keyed by questionId of latest result.
Result: {questionId,selectedOptionId,correct,correctOptionId,explanation,attemptId}

GET /api/admin/overview -> {users,courses,publishedCourses,pendingApplications,enrollments}
GET /api/admin/users -> {users:[{id,name,email,role,status,active,createdAt}]}
PATCH /api/admin/users/{id} {role?,active?} -> {user}
GET /api/admin/courses -> {courses:[{id,title,courseCode,ownerName,status,archived,moderationReason,chapterCount}]}
POST /api/admin/courses/{id}/archive {reason} -> {course}
POST /api/admin/courses/{id}/restore {} -> {course}
GET /api/admin/audit -> {events:[{id,kind,actor,courseId?,title,status,at?,model?,reason?}]}
```

Exact optional fields can be extended if justified; document deviations in API contract before UI work begins. Backend client errors use existing FastAPI detail style. Profile values are bounded strings; recommendation is deterministic token/topic matching with background/goal in its explanation, not ML.

- [ ] Step 1: Add tests covering one publish/join/learn/submit/resume/analytics journey using actual routes. Use registered teacher/student sessions and a locally generated fixture package; literal answer expectations, real temporary SQLite DB. Example assertion:

```python
assert (await student.get('/api/student/home')).json()['courses'] == []
assert (await teacher.post(f'/api/demo/courses/{course_id}/publish')).status_code == 200
assert (await student.post(f'/api/student/courses/{course_id}/enroll', json={})).status_code == 200
assert 'answer' not in (await student.get(chapter_url)).text
```

- [ ] Step 2: Run `.../.venv/bin/pytest tests/test_portals.py -q`, record expected failures from missing portal routes before implementation.
- [ ] Step 3: Implement versioned schema and services; initialise legacy published snapshots once, freeze new publications explicitly, persist auth-linked enrolments, idempotent joins/submission IDs and progress. Update publish/invite/analytics contracts without changing unrelated generation paths. Implement safe student asset rendering using existing deterministic helpers and referenced private illustration storage.
- [ ] Step 4: Add failing security/admin tests before each corresponding behavior: role/CSRF rejection, pre-submit answer/notes stripping, snapshot isolation, withdrawal/suspension direct-ID denial, forbidden teacher republish, session revocation, self/last-admin protection, unknown/foreign quiz IDs, duplicate submission, restart persistence, legacy backup preservation. Implement each to green.
- [ ] Step 5: Run focused portal tests and all backend tests. Inspect whitelist payloads and migrated schema. Document actual contracts and limits; commit backend/API changes only with test evidence.

## Task 2: Student and administrator operating interfaces

**Files:**
- Create `frontend/components/portals/PortalShell.tsx`, `StudentPortal.tsx`, `StudentCourse.tsx`, `StudentPlayer.tsx`, `AdminPortal.tsx`, `frontend/lib/portal.ts`, `portal-copy.ts`, `frontend/app/portals.css`.
- Replace student/admin route placeholder imports; add `/student/courses/[courseId]/page.tsx` and `/student/courses/[courseId]/chapters/[chapterId]/page.tsx` with existing Next.js documented async params conventions.
- Minimal changes to root stylesheet import and AccountPages exports. Preserve qualification UI by extracting/reusing its review queue rather than losing it.
- Create `frontend/tests/portals.test.mjs` for pure portal helpers and client request contracts; use existing test/runtime patterns.

**Consumes:** Actual contracts in `docs/design/student-admin-api.md`, shared `authJson` / `authFetch`, AccountGate, i18n, PublicHeader and semantic themes.

**Produces:** Working student and administrator routes; no frontend-only fake learning data.

**Surface direction:** Extend the existing Coursework Operate system, code-led and fixed by the approved design. Compact header/account menu; student home leads with resume then recommendation and course discovery. The player is a readable content canvas with an outline and separate MCQ practice, never instructor tools. Admin is a quiet section navigation and searchable operational lists; actions are inline with explicit pending/result/error states. Use navy text, blue actions, green completion and amber review from current tokens; flat surfaces and clear hierarchy rather than a hero/metric-template dashboard. Do not redesign public/auth/teacher routes.

- [ ] Step 1: Read `frontend/AGENTS.md`, installed Next.js route/client docs, DESIGN.md and existing components. Read required frontend design skills. Record an Operate surface brief inheriting existing tokens with a direction contract; no aesthetic tournament because scope/world have been approved and user explicitly declined further confirmations.
- [ ] Step 2: Add failing behavioral helper tests for route encoding, clamped progress, current chapter resume selection, question option/result mapping and request targets. Example:

```js
assert.equal(studentChapterHref('c/1','ch 2'), '/student/courses/c%2F1/chapters/ch%202');
assert.equal(progressPercent({visitedSlideIds:['s1'], totalSlides:2}), 50);
```

Use the actual helper names selected in `portal.ts`; test independent literal expectations, never grep source. Run the focused test to RED.
- [ ] Step 3: Implement API client types/helpers and student pages. Abort stale GET requests on identity/route changes; all writes use authJson and prevent repeated clicks. Backend controls completion and correctness; failed writes keep honest status. Render diagrams/images from student-authorized URLs and do not request teacher APIs. Provide onboarding, search, join/invite, continue, previous/next, MCQ feedback/retry and persisted result display.
- [ ] Step 4: Implement admin Overview/Applications/Users/Courses/Activity using actual APIs; retain qualification profile/download/approve/reject. Visible labels, reason fields and inline confirmation/error for destructive-looking moderation, no window.alert/confirm. Prevent accidental self-actions in UI without relying on that as security. No stale lists after successful mutation.
- [ ] Step 5: Run frontend behavioral tests, TypeScript, ESLint for changed TSX and production build. Read final code against 320px CSS, dark theme, all three locale dictionaries, keyboard/focus/empty/loading/error states. Commit frontend files with evidence.

## Task 3: Cross-role verification and handoff

**Files:** `docs/design/student-admin-verification.md`, `backend/README.md` or root README only for accurate run/manual guidance. UI fixes remain scoped to portal files; service fixes keep tests.

- [ ] Step 1: Run full backend suite, frontend tests, typecheck and build once on integrated changes; record exact counts and failures, not historical counts.
- [ ] Step 2: Start isolated backend/frontend on free ports with a SQLite backup/copy of the teacher dataset, never overwrite source DB. Use test-only accounts in the isolated copy; do not publish original courses as a side effect.
- [ ] Step 3: Actual browser walkthrough: teacher explicit publish, student search/join/read/quiz/refresh, teacher sees participation, admin qualification/users/suspension/restore/audit. Verify private draft boundary and direct navigation. Capture portal screenshots without browser chrome at desktop/mobile when supported.
- [ ] Step 4: Run Impeccable detector once on changed UI; independently review code and screenshots, fix material findings with regression tests, and rerun affected checks. Confirm design-system extension does not rewrite incumbent identity or unasked stale sidecar.
- [ ] Step 5: Record limitations, setup/URLs, schema migration and rollback/backup instructions. Commit verified work on new branch only. Leave original branch, handoff archives and original DB intact; no push or merge without request.
