"""In-memory ownership model for the teacher-course prototype.

The repository deliberately knows only how courses own ordered chapters.  AI
generation, publishing and analytics stay in higher-level services so this
store can later be replaced by a database implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import count
from typing import Any, Literal, Protocol


CourseStatus = Literal["draft", "published"]
ChapterStatus = Literal["empty", "generating", "draft", "ready", "failed"]


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
    def create_course(self, *, title: str, description: str, audience: str, language: str, duration_min: int) -> Course: ...

    def get_course(self, course_id: str) -> Course: ...

    def get_chapter(self, course_id: str, chapter_id: str) -> Chapter: ...


class InMemoryCourseRepository:
    """A deterministic store with strict course/chapter ownership checks."""

    def __init__(self) -> None:
        self._courses: dict[str, Course] = {}
        self._chapters: dict[str, Chapter] = {}
        self._course_numbers = count(1)
        self._chapter_numbers = count(1)

    def create_course(
        self,
        *,
        title: str,
        description: str,
        audience: str,
        language: str,
        duration_min: int,
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
        )
        self._courses[course.id] = course
        # 课程可先有一个明确的起始草稿，但它不是不可改的「第一章」。
        # 教师可以改名、再新增章节；这样既减少空白页，又保留课程优先的结构。
        self.create_chapter(course.id, title="Chapter 0")
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
            "learning_objectives", "status", "syllabus_filename", "syllabus_text",
            "syllabus_status", "syllabus_chars",
        }
        unexpected = set(changes) - allowed
        if unexpected:
            raise ValueError(f"cannot update {sorted(unexpected)}")
        for key, value in changes.items():
            if key == "title" and not str(value).strip():
                raise ValueError("title is required")
            if key == "duration_min" and int(value) <= 0:
                raise ValueError("duration_min must be positive")
            setattr(course, key, value.strip() if key in {"title", "description", "audience", "language"} else value)
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
        return chapter

    def reorder_chapters(self, course_id: str, chapter_ids: list[str]) -> list[Chapter]:
        course = self.get_course(course_id)
        if set(chapter_ids) != set(course.chapter_ids) or len(chapter_ids) != len(course.chapter_ids):
            raise ValueError("chapter_ids must contain every chapter exactly once")
        course.chapter_ids = list(chapter_ids)
        chapters = [self.get_chapter(course_id, chapter_id) for chapter_id in chapter_ids]
        for index, chapter in enumerate(chapters, start=1):
            chapter.order = index
        return chapters

    def delete_chapter(self, course_id: str, chapter_id: str) -> None:
        course = self.get_course(course_id)
        self.get_chapter(course_id, chapter_id)
        if len(course.chapter_ids) == 1:
            raise ValueError("cannot delete the last chapter")
        course.chapter_ids.remove(chapter_id)
        del self._chapters[chapter_id]
        self.reorder_chapters(course_id, course.chapter_ids)
