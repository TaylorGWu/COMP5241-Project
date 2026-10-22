"""In-memory ownership model for the teacher-course prototype.

The repository deliberately knows only how courses own ordered chapters.  AI
generation, publishing and analytics stay in higher-level services so this
store can later be replaced by a database implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from itertools import count
from collections.abc import Callable
from typing import Any, Literal, Protocol


CourseStatus = Literal["draft", "published"]
ChapterStatus = Literal["empty", "generating", "draft", "ready", "failed"]


def _next_number(items: dict[str, Any], prefix: str) -> int:
    """Find the largest numeric demo id while tolerating malformed local state."""
    numbers = [
        int(item_id.removeprefix(prefix))
        for item_id in items
        if item_id.startswith(prefix) and item_id.removeprefix(prefix).isdigit()
    ]
    return max(numbers, default=0)


@dataclass
class Course:
    id: str
    title: str
    description: str
    audience: str
    language: str
    duration_min: int
    status: CourseStatus = "draft"
    chapter_ids: list[str] = field(default_factory=list)
    learning_objectives: list[dict[str, str]] = field(default_factory=list)
    student_ids: list[str] = field(default_factory=list)
    # Catalogue metadata mirrors the compact, scannable course identity that
    # teachers and learners need before opening the curriculum.
    course_code: str = ""
    subject: str = "Software Engineering"
    level: str = "Undergraduate"
    # The parsed syllabus belongs to the course, not to any one chapter.  It is
    # folded into each chapter-generation request as teacher-provided context.
    syllabus_filename: str | None = None
    syllabus_text: str = ""
    syllabus_status: str | None = None
    syllabus_chars: int = 0


@dataclass
class Chapter:
    id: str
    course_id: str
    title: str
    order: int
    summary: str = ""
    status: ChapterStatus = "empty"
    package: Any | None = None
    materials: list[Any] = field(default_factory=list)
    patch_ids: list[str] = field(default_factory=list)
    version_ids: list[str] = field(default_factory=list)


@dataclass
class CourseVersion:
    id: str
    course_id: str
    chapter_id: str | None
    kind: str
    reason: str
    changed_fields: list[str]
    before: dict[str, Any]
    after: dict[str, Any]


@dataclass
class Enrollment:
    id: str
    course_id: str
    student_name: str
    email: str


@dataclass
class Attempt:
    id: str
    course_id: str
    student_id: str
    completion_percent: int
    answers: dict[str, bool] = field(default_factory=dict)


class CourseRepository(Protocol):
    def create_course(self, *, title: str, description: str, audience: str, language: str, duration_min: int, course_code: str = "", subject: str = "Software Engineering", level: str = "Undergraduate", learning_objectives: list[dict[str, str]] | None = None) -> Course: ...

    def get_course(self, course_id: str) -> Course: ...

    def get_chapter(self, course_id: str, chapter_id: str) -> Chapter: ...


class InMemoryCourseRepository:
    """A deterministic store with strict course/chapter ownership checks."""

    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self._courses: dict[str, Course] = {}
        self._chapters: dict[str, Chapter] = {}
        self._course_numbers = count(1)
        self._chapter_numbers = count(1)
        self._on_change = on_change

    def set_on_change(self, callback: Callable[[], None] | None) -> None:
        self._on_change = callback

    def _changed(self) -> None:
        if self._on_change is not None:
            self._on_change()

    @staticmethod
    def _snapshot_value(value: Any) -> Any:
        """Convert IR models and dataclasses into JSON-safe demo state."""
        if hasattr(value, "model_dump"):
            return value.model_dump(by_alias=True)
        if is_dataclass(value):
            return {
                item.name: InMemoryCourseRepository._snapshot_value(
                    getattr(value, item.name)
                )
                for item in fields(value)
            }
        if isinstance(value, dict):
            return {str(key): InMemoryCourseRepository._snapshot_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [InMemoryCourseRepository._snapshot_value(item) for item in value]
        return value

    def snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Return the course and chapter state required to survive dev reloads."""
        return {
            "courses": [self._snapshot_value(course) for course in self._courses.values()],
            "chapters": [self._snapshot_value(chapter) for chapter in self._chapters.values()],
        }

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> "InMemoryCourseRepository":
        """Restore a previously written local demo snapshot; malformed rows are skipped."""
        repo = cls()
        courses = snapshot.get("courses", [])
        chapters = snapshot.get("chapters", [])
        if not isinstance(courses, list) or not isinstance(chapters, list):
            return repo
        for raw in courses:
            if isinstance(raw, dict):
                try:
                    course = Course(**raw)
                except (TypeError, ValueError):
                    continue
                repo._courses[course.id] = course
        for raw in chapters:
            if isinstance(raw, dict):
                try:
                    chapter = Chapter(**raw)
                except (TypeError, ValueError):
                    continue
                if chapter.course_id in repo._courses:
                    repo._chapters[chapter.id] = chapter
        repo._course_numbers = count(_next_number(repo._courses, "course-") + 1)
        repo._chapter_numbers = count(_next_number(repo._chapters, "chapter-") + 1)
        return repo

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
        course = Course(
            id=f"course-{next(self._course_numbers)}",
            title=title.strip(),
            description=description.strip(),
            audience=audience.strip(),
            language=language.strip() or "zh-HK",
            duration_min=duration_min,
            course_code=course_code.strip(),
            subject=subject.strip() or "Software Engineering",
            level=level.strip() or "Undergraduate",
            learning_objectives=list(learning_objectives or []),
        )
        self._courses[course.id] = course
        # 课程可先有一个明确的起始草稿，但它不是不可改的「第一章」。
        # 教师可以改名、再新增章节；这样既减少空白页，又保留课程优先的结构。
        self.create_chapter(course.id, title="Chapter 0")
        self._changed()
        return course

    def list_courses(self) -> list[Course]:
        return list(self._courses.values())

    def get_course(self, course_id: str) -> Course:
        try:
            return self._courses[course_id]
        except KeyError as error:
            raise KeyError(f"course {course_id} was not found") from error

    def update_course(self, course_id: str, **changes: Any) -> Course:
        course = self.get_course(course_id)
        allowed = {
            "title", "description", "audience", "language", "duration_min",
            "learning_objectives", "course_code", "subject", "level", "status", "syllabus_filename", "syllabus_text",
            "syllabus_status", "syllabus_chars", "student_ids",
        }
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"cannot update {sorted(unexpected)}")
        for key, value in changes.items():
            if key == "title" and not str(value).strip():
                raise ValueError("title is required")
            if key == "duration_min" and int(value) <= 0:
                raise ValueError("duration_min must be positive")
            setattr(course, key, value.strip() if key in {"title", "description", "audience", "language", "course_code", "subject", "level"} else value)
        self._changed()
        return course

    def create_chapter(self, course_id: str, *, title: str, summary: str = "") -> Chapter:
        course = self.get_course(course_id)
        if not title.strip():
            raise ValueError("chapter title is required")
        chapter = Chapter(
            id=f"chapter-{next(self._chapter_numbers)}",
            course_id=course.id,
            title=title.strip(),
            summary=summary.strip(),
            order=len(course.chapter_ids) + 1,
        )
        self._chapters[chapter.id] = chapter
        course.chapter_ids.append(chapter.id)
        self._changed()
        return chapter

    def get_chapter(self, course_id: str, chapter_id: str) -> Chapter:
        self.get_course(course_id)
        try:
            chapter = self._chapters[chapter_id]
        except KeyError as error:
            raise KeyError(f"chapter {chapter_id} was not found") from error
        if chapter.course_id != course_id:
            raise KeyError(f"chapter {chapter_id} does not belong to course {course_id}")
        return chapter

    def update_chapter(self, course_id: str, chapter_id: str, **changes: Any) -> Chapter:
        chapter = self.get_chapter(course_id, chapter_id)
        allowed = {"title", "summary", "status", "package", "materials", "patch_ids", "version_ids"}
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"cannot update {sorted(unexpected)}")
        for key, value in changes.items():
            if key == "title" and not str(value).strip():
                raise ValueError("chapter title is required")
            setattr(chapter, key, value.strip() if key in {"title", "summary"} else value)
        self._changed()
        return chapter

    def reorder_chapters(self, course_id: str, chapter_ids: list[str]) -> list[Chapter]:
        course = self.get_course(course_id)
        if set(chapter_ids) != set(course.chapter_ids) or len(chapter_ids) != len(course.chapter_ids):
            raise ValueError("chapter_ids must contain every chapter exactly once")
        course.chapter_ids = list(chapter_ids)
        chapters = [self.get_chapter(course_id, chapter_id) for chapter_id in chapter_ids]
        for index, chapter in enumerate(chapters, start=1):
            chapter.order = index
        self._changed()
        return chapters

    def delete_chapter(self, course_id: str, chapter_id: str) -> None:
        course = self.get_course(course_id)
        self.get_chapter(course_id, chapter_id)
        if len(course.chapter_ids) == 1:
            raise ValueError("cannot delete the last chapter")
        course.chapter_ids.remove(chapter_id)
        del self._chapters[chapter_id]
        self.reorder_chapters(course_id, course.chapter_ids)
        self._changed()
