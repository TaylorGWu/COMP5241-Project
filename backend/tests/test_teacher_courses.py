from __future__ import annotations

import pytest

from app.services.course_repository import InMemoryCourseRepository
from app.services.teacher_courses import TeacherCourseService


def _service() -> TeacherCourseService:
    return TeacherCourseService(InMemoryCourseRepository())


def test_draft_course_requires_a_ready_chapter_before_publish():
    service = _service()
    course = service.create_course(title="Git", description="", audience="Beginners", duration_min=45)

    with pytest.raises(ValueError, match="ready chapter"):
        service.publish(course.id)


def test_publish_and_unpublish_are_recorded_in_history():
    service = _service()
    course = service.create_course(title="Git", description="", audience="Beginners", duration_min=45)
    chapter_id = course.chapter_ids[0]
    service.repository.update_chapter(course.id, chapter_id, status="ready", package={"slides": []})

    service.publish(course.id)
    service.unpublish(course.id)

    assert service.repository.get_course(course.id).status == "draft"
    assert [entry.kind for entry in service.versions(course.id, chapter_id)] == ["publish", "unpublish"]


def test_rollback_restores_a_version_snapshot():
    service = _service()
    course = service.create_course(title="Git", description="", audience="Beginners", duration_min=45)
    chapter_id = course.chapter_ids[0]
    version = service.record_version(
        course.id, chapter_id, kind="manual", reason="Clarify the opening", changed_fields=["package"],
        before={"package": {"title": "old"}}, after={"package": {"title": "new"}},
    )
    service.repository.update_chapter(course.id, chapter_id, package={"title": "later"})

    service.rollback(course.id, chapter_id, version.id)

    assert service.repository.get_chapter(course.id, chapter_id).package == {"title": "new"}


def test_import_keeps_valid_students_and_reports_bad_rows():
    service = _service()
    course = service.create_course(title="Git", description="", audience="Beginners", duration_min=45)

    result = service.import_students(course.id, [
        {"row": 2, "name": "Ada", "email": "ada@example.test"},
        {"row": 3, "name": "", "email": "broken"},
    ])

    assert result["imported"] == 1
    assert result["errors"] == [{"row": 3, "message": "name is required"}]


def test_analytics_aggregates_completion_scores_and_missed_questions():
    service = _service()
    course = service.create_course(title="Git", description="", audience="Beginners", duration_min=45)
    service.import_students(course.id, [{"row": 2, "name": "Ada", "email": "ada@example.test"}])
    service.record_attempt(course.id, "student-1", completion_percent=80, answers={"q1": True, "q2": False})

    report = service.analytics(course.id)

    assert report["students"][0]["completionPercent"] == 80
    assert report["averageScore"] == 50
    assert report["mostMissed"][0] == {"questionId": "q2", "wrongCount": 1}
