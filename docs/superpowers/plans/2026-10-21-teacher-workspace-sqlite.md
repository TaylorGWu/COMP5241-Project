# Teacher Workspace SQLite Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the teacher demo's temporary JSON and process-only state with a zero-configuration local SQLite workspace that survives a backend restart.

**Architecture:** Keep the existing `CourseRepository`, `PatchStore`, and `TeacherCourseService` boundaries. Add synchronous `sqlite3` implementations for local development: course/chapter IR is stored as JSON, while patches, versions, enrolments, attempts, and invite counters have explicit tables. The demo router opens a database at an ignored local path (or `TEACHER_WORKSPACE_DB`), performs a one-time import of the legacy JSON snapshot only when the database is empty, and keeps all existing HTTP contracts unchanged.

**Tech Stack:** Python 3.12 standard-library `sqlite3`, FastAPI, Pydantic JSON serialisation, pytest.

**Spec:** `docs/design/course-generation-design.md`

## Global Constraints

- IR remains the only course-content truth source; renderers/exporters do not call a model.
- AI-proposed patches remain `proposed` until the instructor explicitly applies them.
- Store no API keys, model clients, live streams, or rendered media bytes in SQLite.
- SQLite is local developer persistence only; it does not replace the planned PostgreSQL production store.
- The local database must be created automatically and ignored by Git, with no teammate setup beyond starting the backend.
- Existing `/api/demo/*` request/response contracts remain compatible.

---

### Task 1: Add a SQLite course and classroom-state repository

**Files:**
- Create: `backend/app/services/sqlite_workspace.py`
- Modify: `backend/app/services/course_repository.py`
- Test: `backend/tests/test_sqlite_workspace.py`

**Interfaces:**
- Consumes: `Course`, `Chapter`, `CourseVersion`, `Enrollment`, `Attempt`, and `CourseRepository` from `course_repository.py`.
- Produces: `SQLiteCourseRepository(path: Path)` with the same public course/chapter operations as `InMemoryCourseRepository`, plus `SQLiteTeacherStateRepository` methods for versions, enrolments, attempts, and invite allocation.

- [ ] **Step 1: Write failing SQLite restart tests**

```python
def test_sqlite_repository_restores_course_and_chapter_after_reopen(tmp_path):
    path = tmp_path / "teacher.db"
    first = SQLiteCourseRepository(path)
    course = first.create_course(title="Git", description="", audience="Beginners", language="zh-HK", duration_min=45)
    chapter = first.get_chapter(course.id, course.chapter_ids[0])
    first.update_chapter(course.id, chapter.id, status="ready", package={"slideDeck": {"slides": []}})

    restored = SQLiteCourseRepository(path)
    assert restored.get_chapter(course.id, chapter.id).package == {"slideDeck": {"slides": []}}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../.venv/bin/pytest tests/test_sqlite_workspace.py::test_sqlite_repository_restores_course_and_chapter_after_reopen -q`

Expected: FAIL because `SQLiteCourseRepository` does not exist.

- [ ] **Step 3: Implement schema creation and course/chapter operations**

```python
class SQLiteCourseRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise_schema()

    def create_course(...) -> Course: ...
    def get_course(self, course_id: str) -> Course: ...
    def create_chapter(self, course_id: str, *, title: str, summary: str = "") -> Chapter: ...
    def update_chapter(self, course_id: str, chapter_id: str, **changes: Any) -> Chapter: ...
```

Use short-lived connections, `PRAGMA foreign_keys = ON`, transaction commits, and JSON encoding for IR/material data.

- [ ] **Step 4: Run the focused repository tests**

Run: `../.venv/bin/pytest tests/test_sqlite_workspace.py -q`

Expected: PASS.

- [ ] **Step 5: Add restart tests for version, roster, attempt, and invite state**

```python
def test_sqlite_teacher_state_restores_version_roster_attempt_and_invite(tmp_path):
    ...
    assert restored.versions(course.id)[0].reason == "Instructor published course"
    assert restored.students(course.id)[0].email == "ada@example.com"
    assert restored.analytics(course.id)["averageScore"] == 100
    assert restored.create_invite(course.id).endswith("-2")
```

- [ ] **Step 6: Implement the teacher-state persistence adapter and run tests**

Run: `../.venv/bin/pytest tests/test_sqlite_workspace.py -q`

Expected: PASS.

### Task 2: Persist AI review patches without weakening confirmation semantics

**Files:**
- Modify: `backend/app/services/patches.py`
- Modify: `backend/app/services/teacher_courses.py`
- Test: `backend/tests/test_sqlite_patches.py`
- Test: `backend/tests/test_teacher_courses.py`

**Interfaces:**
- Consumes: `PatchStore` protocol and `TeacherCourseService` lifecycle methods.
- Produces: `SQLitePatchStore(path: Path)` and an optional state-store dependency for `TeacherCourseService`.

- [ ] **Step 1: Write the failing patch-restart test**

```python
def test_sqlite_patch_store_reopens_proposed_patch_without_applying_it(tmp_path):
    path = tmp_path / "teacher.db"
    proposed = SQLitePatchStore(path).propose(
        artifact_id="chapter-1", kind="slide", target_id="s1",
        payload={"title": "Reviewed title"}, reason="Clearer wording", diff="...",
    )

    restored = SQLitePatchStore(path).get(proposed.id)
    assert restored.status == "proposed"
    assert restored.payload == {"title": "Reviewed title"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../.venv/bin/pytest tests/test_sqlite_patches.py::test_sqlite_patch_store_reopens_proposed_patch_without_applying_it -q`

Expected: FAIL because `SQLitePatchStore` does not exist.

- [ ] **Step 3: Implement `SQLitePatchStore` against the workspace database**

Implement `propose`, `get`, `list`, `mark`, and `replace`; serialise `payload` as JSON and reject changes to non-proposed patches exactly as the in-memory store does.

- [ ] **Step 4: Run patch and confirmation tests**

Run: `../.venv/bin/pytest tests/test_sqlite_patches.py tests/test_patches.py -q`

Expected: PASS; a proposed patch remains separate from the chapter package until the existing apply path is invoked.

### Task 3: Wire the demo application to one local database and migrate legacy JSON once

**Files:**
- Modify: `backend/app/api/routes/demo.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_teacher_courses_api.py`
- Test: `backend/tests/test_demo_workspace_sqlite.py`

**Interfaces:**
- Consumes: `SQLiteCourseRepository`, `SQLiteTeacherStateRepository`, and `SQLitePatchStore`.
- Produces: `TEACHER_WORKSPACE_DB` path resolution, `reset_course_workspace()` test isolation, and chapter activation that obtains its patch store from SQLite.

- [ ] **Step 1: Write failing API tests for database isolation and restart survival**

```python
async def test_course_and_proposed_patch_survive_workspace_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "TEACHER_WORKSPACE_DB", tmp_path / "workspace.db")
    ...
    demo.reload_course_workspace()
    assert (await request("GET", f"/api/demo/courses/{course_id}")).status_code == 200
    assert (await request("GET", f"/api/demo/patches?artifact_id={chapter_id}")).json()["patches"][0]["status"] == "proposed"
```

- [ ] **Step 2: Run the API test to verify it fails**

Run: `../.venv/bin/pytest tests/test_demo_workspace_sqlite.py -q`

Expected: FAIL because the router still uses `DEMO_WORKSPACE_PATH` and in-memory patch stores.

- [ ] **Step 3: Replace JSON bootstrapping with SQLite bootstrapping**

```python
TEACHER_WORKSPACE_DB = Path(os.environ.get("TEACHER_WORKSPACE_DB", "backend/.local/teacher-workspace.db"))

def _load_course_workspace() -> TeacherCourseService:
    workspace = SQLiteTeacherWorkspace(TEACHER_WORKSPACE_DB)
    workspace.import_legacy_snapshot_if_empty(DEMO_WORKSPACE_PATH)
    return TeacherCourseService(workspace.courses, workspace.teacher_state)
```

Keep a read-only, one-time import from the old temp JSON only when the SQLite workspace has no courses. Remove the JSON write path. Ensure every activated/generated chapter gets `SQLitePatchStore(TEACHER_WORKSPACE_DB)` rather than a process-only store.

- [ ] **Step 4: Update fixtures and run API tests**

Run: `../.venv/bin/pytest tests/test_teacher_courses_api.py tests/test_demo_workspace_sqlite.py -q`

Expected: PASS; test databases are in `tmp_path` and cannot touch a developer's local workspace.

### Task 4: Document local usage and verify regressions

**Files:**
- Modify: `.gitignore`
- Modify: `backend/README.md`
- Test: `backend/tests/test_sqlite_workspace.py`

**Interfaces:**
- Consumes: the automatic default database path and optional `TEACHER_WORKSPACE_DB` override.
- Produces: clear zero-setup local-running instructions and Git-safe developer state.

- [ ] **Step 1: Write a failing test for the default path contract**

```python
def test_default_workspace_path_is_local_and_has_no_credentials(monkeypatch):
    monkeypatch.delenv("TEACHER_WORKSPACE_DB", raising=False)
    assert demo.resolve_teacher_workspace_path().as_posix().endswith("backend/.local/teacher-workspace.db")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `../.venv/bin/pytest tests/test_demo_workspace_sqlite.py::test_default_workspace_path_is_local_and_has_no_credentials -q`

Expected: FAIL because the path resolver does not exist.

- [ ] **Step 3: Add ignored-state and setup documentation**

Add `backend/.local/` to `.gitignore`. In `backend/README.md`, document automatic creation, the optional path override, and that deleting the database resets local demo state; do not add a destructive reset command.

- [ ] **Step 4: Run full backend verification**

Run: `../.venv/bin/pytest -q`

Expected: PASS.

- [ ] **Step 5: Run static and frontend regression checks**

Run: `cd ../frontend && npm run test && npx tsc --noEmit && npm run build`

Expected: PASS.

- [ ] **Step 6: Inspect changes before committing**

Run: `git diff --check && git status --short`

Expected: no whitespace errors and only SQLite-persistence files changed.
