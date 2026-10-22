from __future__ import annotations

from app.services.sqlite_workspace import SQLiteCourseRepository, SQLiteTeacherStateRepository
from app.services.teacher_courses import TeacherCourseService


def test_sqlite_repository_restores_course_and_chapter_after_reopen(tmp_path):
    """A backend restart must not erase the teacher's generated chapter IR."""
    path = tmp_path / "teacher-workspace.db"
    first = SQLiteCourseRepository(path)
    course = first.create_course(
        title="Git collaboration",
        description="A short course",
        audience="Beginners",
        language="zh-HK",
        duration_min=45,
    )
    chapter = first.get_chapter(course.id, course.chapter_ids[0])
    first.update_chapter(
        course.id,
        chapter.id,
        status="ready",
        package={"slideDeck": {"slides": [{"id": "s1", "title": "Branch"}]}},
    )

    restored = SQLiteCourseRepository(path)
    reloaded_course = restored.get_course(course.id)
    reloaded_chapter = restored.get_chapter(course.id, chapter.id)

    assert reloaded_course.chapter_ids == [chapter.id]
    assert reloaded_chapter.status == "ready"
    assert reloaded_chapter.package == {
        "slideDeck": {"slides": [{"id": "s1", "title": "Branch"}]}
    }


def test_sqlite_repository_keeps_course_chapter_order_after_reopen(tmp_path):
    """A restart must retain the chapter order chosen by the instructor."""
    path = tmp_path / "teacher-workspace.db"
    repository = SQLiteCourseRepository(path)
    course = repository.create_course(
        title="Git collaboration",
        description="",
        audience="Beginners",
        language="zh-HK",
        duration_min=45,
    )
    first_id = course.chapter_ids[0]
    second = repository.create_chapter(course.id, title="Branching")
    repository.reorder_chapters(course.id, [second.id, first_id])

    restored = SQLiteCourseRepository(path)

    assert restored.get_course(course.id).chapter_ids == [second.id, first_id]
    assert [
        restored.get_chapter(course.id, chapter_id).order
        for chapter_id in restored.get_course(course.id).chapter_ids
    ] == [1, 2]


def test_sqlite_teacher_state_restores_audit_roster_attempt_and_invite(tmp_path):
    """Classroom evidence must survive the same restart as the course IR."""
    path = tmp_path / "teacher-workspace.db"
    repository = SQLiteCourseRepository(path)
    service = TeacherCourseService(repository, state_store=SQLiteTeacherStateRepository(path))
    course = service.create_course(
        title="Git collaboration",
        description="",
        audience="Beginners",
        language="zh-HK",
        duration_min=45,
    )
    service.record_version(
        course.id,
        None,
        kind="course-update",
        reason="Clarified outcomes",
        changed_fields=["learning_objectives"],
        before={"learning_objectives": []},
        after={"learning_objectives": [{"id": "LO1", "text": "Explain branches"}]},
    )
    service.import_students(course.id, [{"row": 2, "name": "Ada", "email": "ada@example.com"}])
    service.record_attempt(course.id, "student-1", completion_percent=100, answers={"q1": True})
    assert service.create_invite(course.id).endswith("-1")

    restored = TeacherCourseService(
        SQLiteCourseRepository(path), state_store=SQLiteTeacherStateRepository(path)
    )

    assert restored.versions(course.id)[0].reason == "Clarified outcomes"
    assert restored.students(course.id)[0].email == "ada@example.com"
    assert restored.analytics(course.id)["averageScore"] == 100
    assert restored.create_invite(course.id).endswith("-2")
