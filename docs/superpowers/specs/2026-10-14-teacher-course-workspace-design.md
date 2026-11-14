# Teacher course workspace (in-memory) — design

## Status and decision

This specification implements the instructor-side items 7–23 in
[`docs/moscow.md`](../../moscow.md) as an **in-memory, single-process
prototype**. It intentionally does not add authentication, PostgreSQL, ARQ, or
real student accounts in this iteration. The public behaviour and service
boundaries will be designed so a database-backed repository can replace the
in-memory repository without changing the UI flow.

The core correction is domain ownership:

```text
Course (the instructor's publishable unit)
  └─ Chapter (an ordered teaching unit)
       ├─ CoursePackage / lesson plan / slide deck
       ├─ Question bank and exam papers
       ├─ Material references and generated assets
       └─ Version and patch history
```

A chapter is never a course. Existing generated `CoursePackage` objects become
the content of one chapter in a `Course`; they no longer represent the whole
teacher workspace.

## Product scope

The course overview requires instructors to customise or create mini-courses,
refine materials and activities, publish deliberately, and inspect learner
participation. This design preserves the project-wide rules:

- AI returns structured IR only; renderers/exporters remain deterministic.
- AI output is always draft content. Publishing is an explicit instructor
  operation.
- An AI edit creates a proposed patch first; only an explicit apply operation
  changes chapter content.
- Each item that can fail independently (file, chapter, visual, export) returns
  a recoverable result rather than breaking the entire course.
- Model calls continue through the configured router/fake models; no model name
  is placed in route or UI code.

This is a prototype data store, not a reason to relax those product rules.

## Architecture

### Domain types

`Course` is the aggregate root.

```text
Course
  id, title, description, audience, language, status
  learningObjectives[], chapterIds[], studentIds[]
  createdAt, updatedAt, publishedAt

Chapter
  id, courseId, title, summary, order, status
  package: CoursePackage | null
  materials[], questionSet, examPaper
  versionIds[], patchIds[]

CourseVersion
  id, courseId, chapterId, kind (manual | patch | generation | publish)
  reason, changedFields[], before, after, createdAt

Enrollment / Attempt (demo analytics data)
  id, courseId, studentName, completionPercent, answeredQuestions[]
```

Course status is `draft | published`; chapters are `empty | generating | draft
| ready | failed`. Publishing validates that a course has at least one usable
chapter and marks the course, never the AI job, as published. Unpublishing
returns it to draft without deleting chapters, attempts, or history.

### Repository and services

Create a small `CourseRepository` protocol and an `InMemoryCourseRepository`.
The repository owns indexes and CRUD; it does not contain generation,
exporting, or FastAPI code. A `TeacherCourseService` owns cross-chapter rules:
course creation, ordering, publication checks, versioning, student import,
and analytics aggregation.

Existing focused services (`pipeline`, `patches`, `questions`, `paper`,
`glossary`, and exporters) remain focused. Adapters map one chapter package to
their inputs and persist their results through the repository. The existing
global demo state will be removed from teacher workflow paths, preventing one
browser action from replacing every other course's content.

## API contract

All endpoints remain under `/api/demo` while storage is in memory. They use
course-oriented paths and return typed JSON. 404 means an unknown course or
chapter; 409 means a valid operation is unavailable in its current state;
422 means invalid submitted fields.

| Operation | Endpoint |
| --- | --- |
| list/create courses | `GET/POST /courses` |
| read/update course | `GET/PATCH /courses/{courseId}` |
| publish/unpublish course | `POST /courses/{courseId}/publish`, `/unpublish` |
| add/reorder/update/delete chapters | `POST/ PATCH/ DELETE /courses/{courseId}/chapters...` |
| generate a chapter package + SSE progress | `POST /courses/{courseId}/chapters/{chapterId}/generate[/stream]` |
| upload/list source materials | `POST/GET /courses/{courseId}/materials` |
| chapter preview and manual content edit | `GET/PATCH /courses/{courseId}/chapters/{chapterId}/package` |
| propose/apply/reject AI patch | chapter-scoped `edit`, `patches/{id}/apply`, `patches/{id}/reject` |
| coverage / fill a gap | chapter-scoped `coverage`, `coverage/fill` |
| question bank and exam paper | chapter-scoped `questions`, `paper` |
| glossary and visual descriptions | chapter-scoped `glossary` |
| Office exports | chapter-scoped `export/*` |
| version list/rollback | chapter-scoped `versions`, `versions/{id}/rollback` |
| student CSV/invite and analytics | course-scoped `students/import`, `invite`, `analytics` |
| remediation / narrated-video job | chapter-scoped `remediation`, `video` |

The first version deliberately uses a deterministic, in-memory job record for
generation and video progress. Existing streaming generation remains allowed
only because this is the already-documented demo namespace; normal completion
and error frames are retained, and each job is scoped to one chapter.

## UI flow

The instructor landing screen becomes a course workspace, not a single
generation form.

1. **Course list:** cards distinguish draft from published courses, show chapter
   count, last edit, and a concise readiness cue.
2. **Create course:** teacher supplies title, description, audience, language,
   duration and objectives. Creation makes an empty draft course with one empty
   first chapter.
3. **Course editor:** a left chapter rail supports add, rename, delete, and
   reordering. The main pane gives each selected chapter tabs for Build,
   Preview, Questions, Paper, Accessibility, History, and Analytics.
4. **Build:** instructor supplies chapter-specific topic and goal(s), optionally
   uploads material, and starts generation. Step-level progress identifies the
   current chapter and stage. Generated content stays visibly labelled Draft.
5. **Review:** direct edits create a manual version. Conversational edits show a
   field-level proposal and reason; accept/reject controls make the change
   explicit.
6. **Publish:** preview validates all chapters and asks for a deliberate
   publish. A published course can be withdrawn, returning it to Draft.
7. **Classroom view:** import feedback identifies malformed CSV rows without
   discarding valid rows. Analytics displays per-student completion, average
   MCQ score and most-missed questions; it labels demo records as sample data
   when no real attempt exists.

The UI reuses the existing slide canvas, lesson-plan, review-margin, and
teacher tool components after splitting their currently coupled state into
course, selected chapter, and request state. Empty states and error messages
must always offer a next action (create a chapter, retry, edit manually, or
review invalid CSV rows).

## Feature mapping

| `moscow.md` items | Implementation and acceptance boundary |
| --- | --- |
| 7–11 | Generation, granular progress, provenance, proposed patches, and coverage are chapter-scoped and remain structured IR. |
| 12 | Upload accepts PDF/PPTX/DOCX/text; each file records parse/OCR status and page-aware references. A failed file does not prevent generation. |
| 13–14 | Questions derive from selected course/chapter objectives; paper composition reports unmet score, coverage, or difficulty constraints honestly. |
| 15 | Analytics may request a draft remediation kit: explanation, deterministic Mermaid-first visual brief, check question, and an explicitly labelled hypothesis. |
| 16 | Glossary entries and image alt text persist inside package/asset IR and are editable. |
| 17 | Video is a draft job created from slide speaker notes; its state can be viewed/retried. No text-to-video model is introduced. |
| 18–19 | Courses contain ordered chapters; title/description and all chapter content are editable. Draft is default; published courses alone are catalog-visible; unpublish preserves data. |
| 20 | PPTX, lesson-plan DOCX, exam-paper DOCX, and a deterministic PDF fallback export the chapter's current IR. |
| 21 | Generation, manual edit, accepted patch, publish, and rollback each record a reason, changed fields, before/after snapshots, and timestamp. |
| 22 | In-memory enrollments and attempts aggregate completion, MCQ mean, and mistake frequency by course. |
| 23 | CSV import validates each row independently; invite codes attach students to exactly one course and are surfaced in the workspace. |

## Error handling and invariants

- A patch may never mutate a chapter package before `apply` is called.
- An AI-generated chapter may not change a course from draft to published.
- Publishing with no ready chapter returns a human-readable conflict; it never
  silently creates a placeholder course.
- Deleting a chapter does not delete other chapters or course history. Removing
  the final chapter is disallowed until a replacement is added.
- A regenerated question set invalidates an exam paper that references its old
  IDs; the UI explains why.
- CSV import preserves valid rows and returns row-numbered invalid entries.
- Export failure, material parse failure, asset failure, and one chapter's
  generation failure remain isolated and retryable.

## Tests and evidence

Backend tests will cover the repository/service lifecycle and endpoint wiring:

- course creation, ordered chapter ownership, editing, publication, withdrawal,
  and catalog visibility;
- no cross-course state bleed;
- generate/patch/apply/rollback create correct version history and proposed
  patches do not alter package contents;
- coverage, sources, questions, papers, glossary, exports, materials, CSV,
  invite, analytics, remediation, and video state are scoped to their course or
  chapter;
- malformed CSV, impossible paper constraints, invalid operations, and isolated
  generator failures return useful recoverable errors;
- agent tests assert tool-call sequence rather than generated prose.

Frontend checks will exercise course creation, chapter switching, draft badge,
publish/unpublish, progress display, confirmation before applying a patch, and
state restoration after a refresh. The final usability-test script should ask
an instructor/TA to make and publish a two-chapter course, correct an AI
proposal, and identify one action from the analytics view; observed evidence
must not be claimed until those sessions actually happen.

## Delivery sequence

1. Establish domain schemas, repository, course/chapter routes, and migrate
   existing teacher UI state onto a selected chapter.
2. Reattach existing generation/edit/coverage/material/export behaviour to that
   chapter and add publication plus version history.
3. Complete question, paper, accessibility, analytics, CSV/invite,
   remediation, and video-job interfaces with deterministic demo adapters.
4. Simplify/rename components, remove duplicate global state, add full tests,
   then run backend and frontend verification.

## Deferred production work

Replacing `InMemoryCourseRepository` with SQLAlchemy/PostgreSQL, JWT/RBAC,
ARQ-backed durable jobs, real storage, external invitations, and real student
attempt persistence are explicit follow-up work. The in-memory boundary exists
so this migration is additive rather than another teacher-side rewrite.
