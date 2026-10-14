# Teacher Course Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single generated-package demo with a complete, in-memory instructor workspace where courses own ordered chapters and all MoSCoW teacher functions are scoped to that ownership.

**Architecture:** Add a typed in-memory course repository and a service that owns lifecycle, history, enrolments, analytics, CSV validation and demo jobs. Keep AI/pipeline, patch, question, paper, glossary and exporter services pure; route adapters load the selected chapter package, call the service, then record a version. Split the one-page studio into course navigation, chapter workspace and focused tool panels.

**Tech Stack:** FastAPI, Pydantic, pytest/httpx, Next.js, TypeScript, Tailwind, existing deterministic fake models and Office exporters.

**Spec:** `docs/superpowers/specs/2026-10-14-teacher-course-workspace-design.md`

## Global Constraints

- Course is the publishable aggregate; chapter is an ordered child and may never be treated as a course.
- Keep all storage in memory, behind a repository interface; do not add a database, authentication or real external invitations in this iteration.
- AI produces structured IR only and never publishes a course automatically.
- AI edit endpoints create only `proposed` patches; only an explicit apply changes a package.
- Keep model selection in `config/models.yaml`/`ModelRouter`; no hard-coded model names.
- A failed file, asset, chapter generation, video or export must be recoverable without corrupting the rest of the course.
- Add tests before implementation and assert agent tool-call sequence, not generated wording.

---

### Task 1: Define course-domain contracts and repository

**Files:**
- Create: `backend/app/services/course_repository.py`
- Create: `backend/tests/test_course_repository.py`

**Interfaces:** Produces `Course`, `Chapter`, `CourseVersion`, `Enrollment`, `Attempt`, `CourseRepository`, and `InMemoryCourseRepository` for all later tasks.

- [ ] **Step 1: Write failing lifecycle tests** for `create_course`, `add_chapter`, `reorder_chapters`, `delete_chapter`, and independent lookup by course/chapter ID; assert a chapter belonging to course A cannot be fetched through course B.
- [ ] **Step 2: Run** `cd backend && ../.venv/bin/pytest tests/test_course_repository.py -q`; expect import failure.
- [ ] **Step 3: Implement** frozen/validated dataclasses and a repository with `create_course`, `list_courses`, `get_course`, `update_course`, `create_chapter`, `get_chapter`, `update_chapter`, `reorder_chapters`, `delete_chapter`; enforce contiguous one-based chapter order and refuse deletion of the final chapter.
- [ ] **Step 4: Run the repository tests**; expect pass.
- [ ] **Step 5: Commit** `feat: add in-memory course repository`.

### Task 2: Add course lifecycle, history and classroom service

**Files:**
- Create: `backend/app/services/teacher_courses.py`
- Create: `backend/tests/test_teacher_courses.py`

**Interfaces:** Consumes `CourseRepository`; produces `TeacherCourseService.create_course`, `publish`, `unpublish`, `record_version`, `rollback`, `import_students`, `create_invite`, `record_attempt`, and `analytics`.

- [ ] **Step 1: Write failing tests** that draft courses cannot publish with no ready chapter; a publish/unpublish creates history; rollback restores a package snapshot; CSV returns valid records plus row-numbered invalid rows; analytics returns completion, average score and missed-question frequency.
- [ ] **Step 2: Run** `cd backend && ../.venv/bin/pytest tests/test_teacher_courses.py -q`; expect failure.
- [ ] **Step 3: Implement** the service with deep-copied before/after version snapshots, deterministic `invite-<course>-<counter>` codes, row validation for non-empty name/email, and aggregation from in-memory attempts.
- [ ] **Step 4: Run both service test files**; expect pass.
- [ ] **Step 5: Commit** `feat: add teacher course lifecycle service`.

### Task 3: Replace global demo state with course-scoped API foundations

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Create: `backend/tests/test_teacher_courses_api.py`

**Interfaces:** Produces `GET/POST /api/demo/courses`, `GET/PATCH /api/demo/courses/{course_id}`, chapter CRUD/reorder routes, and `POST .../publish|unpublish`.

- [ ] **Step 1: Write endpoint tests** for create/list/read/update, default draft status and first chapter, chapter ownership/ordering, 409 publication guard, successful publish/unpublish, and no state leak between two courses.
- [ ] **Step 2: Run** `cd backend && ../.venv/bin/pytest tests/test_teacher_courses_api.py -q`; expect failure.
- [ ] **Step 3: Introduce a route-local application service backed by `InMemoryCourseRepository`; delete the mutable single-package `STATE` access from new paths, map domain errors to 404/409/422, and retain legacy endpoints only until all callers move.
- [ ] **Step 4: Run tests**; expect pass.
- [ ] **Step 5: Commit** `feat: add course and chapter demo endpoints`.

### Task 4: Reattach generation, material ingestion, provenance and coverage to chapters

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/tests/test_pipeline.py`
- Modify: `backend/tests/test_ingest.py`
- Modify: `backend/tests/test_teacher_courses_api.py`

**Interfaces:** Produces chapter-scoped generate/stream, materials, package read/manual edit, coverage and coverage-fill endpoints.

- [ ] **Step 1: Write failing tests** for generating chapter A without changing chapter B, source/page references surviving readback, per-file degraded result, monotonically progressing chapter SSE frames, and coverage fill remaining draft.
- [ ] **Step 2: Run the targeted tests**; expect failure.
- [ ] **Step 3: Adapt `_run_generation` to accept a course/chapter context, save its `CoursePackage` only into that chapter, create a `generation` version, and persist material reports with that course. Reuse `generate_course`; do not move model work into renderers/routes beyond the existing demo streaming exception.
- [ ] **Step 4: Run targeted tests**; expect pass.
- [ ] **Step 5: Commit** `feat: scope generation and materials to course chapters`.

### Task 5: Preserve patch safety, direct edits and complete version history

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/tests/test_edit.py`
- Modify: `backend/tests/test_teacher_courses_api.py`

**Interfaces:** Produces chapter-scoped edit/stream, patch list/apply/reject, manual package edit, versions and rollback endpoints.

- [ ] **Step 1: Write failing tests** proving proposed patches leave the selected chapter byte-for-byte unchanged, apply changes only that chapter and records a `patch` version/reason/diff, reject changes nothing, manual edit records a `manual` version, and rollback restores the chosen snapshot.
- [ ] **Step 2: Run the targeted tests**; expect failure.
- [ ] **Step 3: Load the package/store from the repository per request; use existing `edit_artifact`, `manual_edit`, `apply_patch`, and `reject_patch`; record history only after successful manual/apply/rollback actions.
- [ ] **Step 4: Run tests**; expect pass.
- [ ] **Step 5: Commit** `feat: add chapter-scoped review and version history`.

### Task 6: Complete teacher content tools and exports

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/tests/test_teacher_endpoints.py`
- Modify: `backend/tests/test_exporters.py`
- Create: `backend/app/services/remediation.py`
- Create: `backend/tests/test_remediation.py`

**Interfaces:** Produces chapter-scoped question, paper, glossary/alt-text, PPTX/DOCX/PDF, remediation and video-job endpoints.

- [ ] **Step 1: Write failing tests** for course/chapter-scoped question and paper regeneration, glossary persistence, Office download headers and deterministic PDF fallback, remediation hypothesis label/Mermaid-first visual brief/check question, and retryable `queued|running|ready|failed` video state from speaker notes.
- [ ] **Step 2: Run the targeted tests**; expect failure.
- [ ] **Step 3: Reuse `generate_questions`, `compose_paper`, `build_glossary`, `describe_visuals` and exporters with chapter package adapters; implement remediation as structured draft IR and video as an in-memory job record, never a text-to-video call.
- [ ] **Step 4: Run tests**; expect pass.
- [ ] **Step 5: Commit** `feat: complete chapter content tools and exports`.

### Task 7: Add student import, invite and analytics endpoints

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/tests/test_teacher_courses_api.py`

**Interfaces:** Produces course-scoped CSV import, invite-code, demo-attempt and analytics endpoints.

- [ ] **Step 1: Write failing tests** that valid CSV rows persist despite invalid rows, errors include original row numbers, invite joins only its course, and analytics returns per-student completion/mean plus most-missed questions.
- [ ] **Step 2: Run** the targeted API tests; expect failure.
- [ ] **Step 3: Parse uploads with Python's `csv.DictReader`, delegate validation/aggregation to `TeacherCourseService`, and return structured valid/invalid counts without exposing raw exceptions.
- [ ] **Step 4: Run tests**; expect pass.
- [ ] **Step 5: Commit** `feat: add course roster and analytics endpoints`.

### Task 8: Create typed course API client and split the teacher UI shell

**Files:**
- Modify: `frontend/lib/api.ts`
- Create: `frontend/components/teacher/CourseList.tsx`
- Create: `frontend/components/teacher/CourseEditor.tsx`
- Create: `frontend/components/teacher/ChapterRail.tsx`
- Modify: `frontend/app/page.tsx`

**Interfaces:** Produces `CourseSummary`, `TeacherCourse`, `TeacherChapter`, typed client calls, selected course/chapter state, and a course-first workspace.

- [ ] **Step 1: Add a failing browser verification** in `tools/ui-verify/verify-teacher-courses.mjs` that creates a course, sees one chapter, adds/reorders a chapter, refreshes and restores the selected draft course.
- [ ] **Step 2: Run** `node tools/ui-verify/verify-teacher-courses.mjs`; expect failure.
- [ ] **Step 3: Add typed fetch methods and split `page.tsx`: course list/create selection lives in the shell; chapter selection/order lives in `ChapterRail`; chapter data is passed to `CourseEditor`; store only selected IDs in local storage, refetch canonical data after mutations.
- [ ] **Step 4: Run `npm run lint` and the browser verification**; expect pass.
- [ ] **Step 5: Commit** `feat: add course-first teacher workspace`.

### Task 9: Move existing authoring/review tools into focused chapter panels

**Files:**
- Create: `frontend/components/teacher/BuildPanel.tsx`
- Create: `frontend/components/teacher/ReviewPanel.tsx`
- Create: `frontend/components/teacher/ToolsPanel.tsx`
- Create: `frontend/components/teacher/HistoryPanel.tsx`
- Modify: `frontend/components/SlideCanvas.tsx`
- Modify: `frontend/components/LessonPlan.tsx`
- Modify: `frontend/components/ReviewMargin.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Extend the browser verification** to assert build progress names the selected chapter, a generated package shows a Draft badge, a proposed patch requires Apply, history records it, and publish/unpublish visibly changes status.
- [ ] **Step 2: Run verification**; expect failure.
- [ ] **Step 3: Extract the existing forms, source markers, coverage, tool progress, slide/plan edit controls and export controls into the panels; wire each to selected chapter endpoints and accessible pending/error/empty states. Keep cards and copy concise rather than adding an AI-chat surface.
- [ ] **Step 4: Run lint and browser verification**; expect pass.
- [ ] **Step 5: Commit** `feat: integrate chapter authoring and review panels`.

### Task 10: Add course classroom panels, accessibility and responsive QA

**Files:**
- Create: `frontend/components/teacher/ClassroomPanel.tsx`
- Modify: `frontend/components/teacher/CourseEditor.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `tools/ui-verify/verify-teacher-courses.mjs`

- [ ] **Step 1: Extend verification** to upload CSV with one invalid row, display retained valid rows and row error, reveal invite code, show analytics plus remediation hypothesis, and navigate every teacher action by keyboard at 320px width.
- [ ] **Step 2: Run verification**; expect failure.
- [ ] **Step 3: Implement roster/import/invite/analytics/remediation/video controls with labeled inputs, live status text, screen-reader labels for assets, no horizontal overflow, and truthful “sample data” labels.
- [ ] **Step 4: Run `npm run lint` and verification**; expect pass.
- [ ] **Step 5: Commit** `feat: complete teacher classroom tools`.

### Task 11: Remove deprecated single-package paths and verify the full slice

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/page.tsx`
- Modify: `backend/tests/test_teacher_endpoints.py`
- Modify: `docs/README.md`

- [ ] **Step 1: Write/adjust regression tests** so all teacher operations use a course and chapter ID; remove legacy route expectations only after replacement coverage exists.
- [ ] **Step 2: Run backend tests**; expect any obsolete-state tests to fail.
- [ ] **Step 3: Delete the singleton package state and legacy UI client calls, document in-memory reset behaviour and the `draft → published → draft` lifecycle, and retain only explicit compatibility redirects if a test proves a live caller needs one.
- [ ] **Step 4: Run** `cd backend && ../.venv/bin/pytest -q`, `cd frontend && npm run lint`, `node tools/ui-verify/verify-teacher-courses.mjs`, and `git diff --check`; expect all pass.
- [ ] **Step 5: Commit** `refactor: replace singleton teacher demo with course workspace`.

## Plan self-review

- Spec coverage: Tasks 1–3 cover course/chapter ownership and publication; 4–6 cover generation through video/export/accessibility/remediation; 7 and 10 cover import, invite and analytics; 5 covers patch integrity/version history; 8–11 cover UI, responsive/accessibility and deprecation.
- No-placeholder check: the implementation sequence, interfaces, test commands and error cases are explicit in every task.
- Type consistency: `CourseRepository` is the storage boundary; `TeacherCourseService` owns lifecycle/cross-course policy; all generation/content operations receive `courseId` and `chapterId`; all roster/analytics operations receive `courseId`.
