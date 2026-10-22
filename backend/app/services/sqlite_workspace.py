"""Local SQLite persistence for the teacher-course workspace.

The production design targets PostgreSQL, but the teacher prototype needs a
zero-configuration store that every teammate can run locally.  Course content
remains IR JSON; this module does not render content or call a model.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, Iterator

from app.services.course_repository import Chapter, Course


def _json_value(value: Any) -> Any:
    """Turn IR/Pydantic/dataclass values into JSON-safe local state."""
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True)
    if is_dataclass(value):
        return {item.name: _json_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


class SQLiteCourseRepository:
    """A local implementation of the existing course/chapter repository API.

    Each method opens a short-lived connection so a development-server reload
    sees committed work immediately.  This is intentionally synchronous: the
    existing course service and FastAPI demo routes are synchronous at this
    storage boundary, and SQLite keeps teammate setup to zero.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialise_schema(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS courses (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chapters (
                    id TEXT PRIMARY KEY,
                    course_id TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chapters_by_course_position
                    ON chapters(course_id, position);
                """
            )

    @staticmethod
    def _encode(value: Any) -> str:
        return json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _decode_course(raw: str) -> Course:
        return Course(**json.loads(raw))

    @staticmethod
    def _decode_chapter(raw: str) -> Chapter:
        return Chapter(**json.loads(raw))

    @staticmethod
    def _next_id(connection: sqlite3.Connection, table: str, prefix: str) -> str:
        rows = connection.execute(f"SELECT id FROM {table}").fetchall()
        next_number = max(
            (
                int(str(row["id"])[len(prefix):])
                for row in rows
                if str(row["id"]).startswith(prefix)
                and str(row["id"])[len(prefix):].isdigit()
            ),
            default=0,
        ) + 1
        return f"{prefix}{next_number}"

    @staticmethod
    def _require_course(connection: sqlite3.Connection, course_id: str) -> Course:
        row = connection.execute(
            "SELECT payload_json FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"course {course_id} was not found")
        return SQLiteCourseRepository._decode_course(row["payload_json"])

    def _save_course(self, connection: sqlite3.Connection, course: Course) -> None:
        connection.execute(
            "UPDATE courses SET payload_json = ? WHERE id = ?",
            (self._encode(course), course.id),
        )

    def _require_chapter(
        self, connection: sqlite3.Connection, course_id: str, chapter_id: str
    ) -> Chapter:
        self._require_course(connection, course_id)
        row = connection.execute(
            "SELECT course_id, payload_json FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"chapter {chapter_id} was not found")
        if row["course_id"] != course_id:
            raise KeyError(f"chapter {chapter_id} does not belong to course {course_id}")
        return self._decode_chapter(row["payload_json"])

    def create_course(
        self,
        *,
        title: str,
        description: str,
        audience: str,
        language: str,
        duration_min: int,
        course_code: str = "",
        subject: str = "Software Engineering",
        level: str = "Undergraduate",
        learning_objectives: list[dict[str, str]] | None = None,
    ) -> Course:
        if not title.strip():
            raise ValueError("title is required")
        if duration_min <= 0:
            raise ValueError("duration_min must be positive")
        with self._connection() as connection:
            course_id = self._next_id(connection, "courses", "course-")
            chapter_id = self._next_id(connection, "chapters", "chapter-")
            course = Course(
                id=course_id,
                title=title.strip(),
                description=description.strip(),
                audience=audience.strip(),
                language=language.strip() or "zh-HK",
                duration_min=duration_min,
                chapter_ids=[chapter_id],
                course_code=course_code.strip(),
                subject=subject.strip() or "Software Engineering",
                level=level.strip() or "Undergraduate",
                learning_objectives=list(learning_objectives or []),
            )
            chapter = Chapter(id=chapter_id, course_id=course_id, title="Chapter 0", order=1)
            connection.execute(
                "INSERT INTO courses(id, payload_json) VALUES (?, ?)",
                (course.id, self._encode(course)),
            )
            connection.execute(
                "INSERT INTO chapters(id, course_id, position, payload_json) VALUES (?, ?, ?, ?)",
                (chapter.id, course.id, chapter.order, self._encode(chapter)),
            )
            return course

    def list_courses(self) -> list[Course]:
        with self._connection() as connection:
            rows = connection.execute("SELECT payload_json FROM courses ORDER BY id").fetchall()
            return [self._decode_course(row["payload_json"]) for row in rows]

    def is_empty(self) -> bool:
        with self._connection() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM courses").fetchone()
            return int(row["total"]) == 0

    def import_legacy_snapshot(self, snapshot: dict[str, Any]) -> bool:
        """Import the old temp JSON once, without overwriting a SQLite workspace."""
        raw_courses = snapshot.get("courses", [])
        raw_chapters = snapshot.get("chapters", [])
        if not isinstance(raw_courses, list) or not isinstance(raw_chapters, list):
            return False
        with self._connection() as connection:
            count = connection.execute("SELECT COUNT(*) AS total FROM courses").fetchone()
            if int(count["total"]) != 0:
                return False
            courses: dict[str, Course] = {}
            chapters: list[Chapter] = []
            for raw in raw_courses:
                if not isinstance(raw, dict):
                    continue
                try:
                    course = Course(**raw)
                except (TypeError, ValueError):
                    continue
                courses[course.id] = course
            for raw in raw_chapters:
                if not isinstance(raw, dict):
                    continue
                try:
                    chapter = Chapter(**raw)
                except (TypeError, ValueError):
                    continue
                if chapter.course_id in courses:
                    chapters.append(chapter)
            if not courses:
                return False
            for course in courses.values():
                connection.execute(
                    "INSERT INTO courses(id, payload_json) VALUES (?, ?)",
                    (course.id, self._encode(course)),
                )
            for chapter in chapters:
                connection.execute(
                    "INSERT INTO chapters(id, course_id, position, payload_json) VALUES (?, ?, ?, ?)",
                    (chapter.id, chapter.course_id, chapter.order, self._encode(chapter)),
                )
            return True

    def get_course(self, course_id: str) -> Course:
        with self._connection() as connection:
            return self._require_course(connection, course_id)

    def update_course(self, course_id: str, **changes: Any) -> Course:
        allowed = {
            "title", "description", "audience", "language", "duration_min",
            "learning_objectives", "course_code", "subject", "level", "status",
            "syllabus_filename", "syllabus_text", "syllabus_status", "syllabus_chars",
            "student_ids",
        }
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"cannot update {sorted(unexpected)}")
        with self._connection() as connection:
            course = self._require_course(connection, course_id)
            for key, value in changes.items():
                if key == "title" and not str(value).strip():
                    raise ValueError("title is required")
                if key == "duration_min" and int(value) <= 0:
                    raise ValueError("duration_min must be positive")
                setattr(
                    course,
                    key,
                    value.strip()
                    if key in {"title", "description", "audience", "language", "course_code", "subject", "level"}
                    else value,
                )
            self._save_course(connection, course)
            return course

    def create_chapter(self, course_id: str, *, title: str, summary: str = "") -> Chapter:
        if not title.strip():
            raise ValueError("chapter title is required")
        with self._connection() as connection:
            course = self._require_course(connection, course_id)
            chapter = Chapter(
                id=self._next_id(connection, "chapters", "chapter-"),
                course_id=course.id,
                title=title.strip(),
                summary=summary.strip(),
                order=len(course.chapter_ids) + 1,
            )
            course.chapter_ids.append(chapter.id)
            self._save_course(connection, course)
            connection.execute(
                "INSERT INTO chapters(id, course_id, position, payload_json) VALUES (?, ?, ?, ?)",
                (chapter.id, course.id, chapter.order, self._encode(chapter)),
            )
            return chapter

    def get_chapter(self, course_id: str, chapter_id: str) -> Chapter:
        with self._connection() as connection:
            return self._require_chapter(connection, course_id, chapter_id)

    def update_chapter(self, course_id: str, chapter_id: str, **changes: Any) -> Chapter:
        allowed = {"title", "summary", "status", "package", "materials", "patch_ids", "version_ids"}
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"cannot update {sorted(unexpected)}")
        with self._connection() as connection:
            chapter = self._require_chapter(connection, course_id, chapter_id)
            for key, value in changes.items():
                if key == "title" and not str(value).strip():
                    raise ValueError("chapter title is required")
                setattr(chapter, key, value.strip() if key in {"title", "summary"} else value)
            connection.execute(
                "UPDATE chapters SET payload_json = ? WHERE id = ?",
                (self._encode(chapter), chapter.id),
            )
            return chapter

    def reorder_chapters(self, course_id: str, chapter_ids: list[str]) -> list[Chapter]:
        with self._connection() as connection:
            course = self._require_course(connection, course_id)
            if set(chapter_ids) != set(course.chapter_ids) or len(chapter_ids) != len(course.chapter_ids):
                raise ValueError("chapter_ids must contain every chapter exactly once")
            course.chapter_ids = list(chapter_ids)
            self._save_course(connection, course)
            chapters: list[Chapter] = []
            for order, chapter_id in enumerate(chapter_ids, start=1):
                chapter = self._require_chapter(connection, course_id, chapter_id)
                chapter.order = order
                connection.execute(
                    "UPDATE chapters SET position = ?, payload_json = ? WHERE id = ?",
                    (order, self._encode(chapter), chapter.id),
                )
                chapters.append(chapter)
            return chapters

    def delete_chapter(self, course_id: str, chapter_id: str) -> None:
        with self._connection() as connection:
            course = self._require_course(connection, course_id)
            self._require_chapter(connection, course_id, chapter_id)
            if len(course.chapter_ids) == 1:
                raise ValueError("cannot delete the last chapter")
            course.chapter_ids.remove(chapter_id)
            self._save_course(connection, course)
            connection.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
            for order, remaining_id in enumerate(course.chapter_ids, start=1):
                chapter = self._require_chapter(connection, course_id, remaining_id)
                chapter.order = order
                connection.execute(
                    "UPDATE chapters SET position = ?, payload_json = ? WHERE id = ?",
                    (order, self._encode(chapter), chapter.id),
                )


class SQLiteTeacherStateRepository:
    """Persist classroom/audit state owned by :class:`TeacherCourseService`."""

    _KEY = "teacher-course-service"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS teacher_state (
                    state_key TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL
                )
                """
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def load(self) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM teacher_state WHERE state_key = ?", (self._KEY,)
            ).fetchone()
        if row is None:
            return {}
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, snapshot: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO teacher_state(state_key, payload_json) VALUES (?, ?)
                ON CONFLICT(state_key) DO UPDATE SET payload_json = excluded.payload_json
                """,
                (self._KEY, json.dumps(_json_value(snapshot), ensure_ascii=False, separators=(",", ":"))),
            )
