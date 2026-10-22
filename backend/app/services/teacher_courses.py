"""Lifecycle and classroom policies for in-memory teacher courses."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Any, Protocol

from app.services.course_repository import Attempt, Course, CourseRepository, CourseVersion, Enrollment


class TeacherStateRepository(Protocol):
    """Small persistence boundary for service-owned classroom/audit state."""

    def load(self) -> dict[str, Any]: ...

    def save(self, snapshot: dict[str, Any]) -> None: ...


class TeacherCourseService:
    def __init__(
        self,
        repository: CourseRepository,
        *,
        state_store: TeacherStateRepository | None = None,
    ) -> None:
        self.repository = repository
        self._state_store = state_store
        self._versions: dict[str, list[CourseVersion]] = {}
        self._enrollments: dict[str, list[Enrollment]] = {}
        self._attempts: dict[str, list[Attempt]] = {}
        self._version_number = 1
        self._enrollment_number = 1
        self._attempt_number = 1
        self._invite_number = 1
        if self._state_store is not None:
            self._restore(self._state_store.load())

    @staticmethod
    def _next_number(items: list[Any], prefix: str) -> int:
        numbers = [
            int(item.id.removeprefix(prefix))
            for item in items
            if item.id.startswith(prefix) and item.id.removeprefix(prefix).isdigit()
        ]
        return max(numbers, default=0) + 1

    def _restore(self, snapshot: dict[str, Any]) -> None:
        def restore_group(name: str, factory: type[Any]) -> dict[str, list[Any]]:
            raw_group = snapshot.get(name, {})
            if not isinstance(raw_group, dict):
                return {}
            restored: dict[str, list[Any]] = {}
            for course_id, rows in raw_group.items():
                if not isinstance(course_id, str) or not isinstance(rows, list):
                    continue
                items: list[Any] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    try:
                        items.append(factory(**row))
                    except TypeError:
                        continue
                restored[course_id] = items
            return restored

        self._versions = restore_group("versions", CourseVersion)
        self._enrollments = restore_group("enrollments", Enrollment)
        self._attempts = restore_group("attempts", Attempt)
        counters = snapshot.get("counters", {})
        if not isinstance(counters, dict):
            counters = {}
        self._version_number = int(counters.get("version", 1))
        self._enrollment_number = int(counters.get("enrollment", 1))
        self._attempt_number = int(counters.get("attempt", 1))
        self._invite_number = int(counters.get("invite", 1))
        if not counters:
            self._version_number = self._next_number(
                [item for values in self._versions.values() for item in values], "version-"
            )
            self._enrollment_number = self._next_number(
                [item for values in self._enrollments.values() for item in values], "student-"
            )
            self._attempt_number = self._next_number(
                [item for values in self._attempts.values() for item in values], "attempt-"
            )

    def snapshot(self) -> dict[str, Any]:
        return {
            "versions": {course_id: [asdict(item) for item in values] for course_id, values in self._versions.items()},
            "enrollments": {course_id: [asdict(item) for item in values] for course_id, values in self._enrollments.items()},
            "attempts": {course_id: [asdict(item) for item in values] for course_id, values in self._attempts.items()},
            "counters": {
                "version": self._version_number,
                "enrollment": self._enrollment_number,
                "attempt": self._attempt_number,
                "invite": self._invite_number,
            },
        }

    def _persist(self) -> None:
        if self._state_store is not None:
            self._state_store.save(self.snapshot())

    def create_course(self, *, title: str, description: str, audience: str, duration_min: int, language: str = "zh-HK", course_code: str = "", subject: str = "Software Engineering", level: str = "Undergraduate", learning_objectives: list[dict[str, str]] | None = None) -> Course:
        return self.repository.create_course(title=title, description=description, audience=audience, language=language, duration_min=duration_min, course_code=course_code, subject=subject, level=level, learning_objectives=learning_objectives)

    def publish(self, course_id: str) -> Course:
        course = self.repository.get_course(course_id)
        chapters = [self.repository.get_chapter(course_id, chapter_id) for chapter_id in course.chapter_ids]
        if not any(chapter.status == "ready" and chapter.package is not None for chapter in chapters):
            raise ValueError("a course needs one ready chapter before publish")
        before = {"status": course.status}
        course = self.repository.update_course(course_id, status="published")
        self.record_version(course_id, None, kind="publish", reason="Instructor published course", changed_fields=["status"], before=before, after={"status": course.status})
        return course

    def unpublish(self, course_id: str) -> Course:
        course = self.repository.get_course(course_id)
        before = {"status": course.status}
        course = self.repository.update_course(course_id, status="draft")
        self.record_version(course_id, None, kind="unpublish", reason="Instructor withdrew course", changed_fields=["status"], before=before, after={"status": course.status})
        return course

    def record_version(self, course_id: str, chapter_id: str | None, *, kind: str, reason: str, changed_fields: list[str], before: dict[str, Any], after: dict[str, Any]) -> CourseVersion:
        self.repository.get_course(course_id)
        if chapter_id is not None:
            self.repository.get_chapter(course_id, chapter_id)
        version = CourseVersion(id=f"version-{self._version_number}", course_id=course_id, chapter_id=chapter_id, kind=kind, reason=reason, changed_fields=list(changed_fields), before=deepcopy(before), after=deepcopy(after))
        self._version_number += 1
        self._versions.setdefault(course_id, []).append(version)
        self._persist()
        return version

    def versions(self, course_id: str, chapter_id: str | None = None) -> list[CourseVersion]:
        self.repository.get_course(course_id)
        return [item for item in self._versions.get(course_id, []) if chapter_id is None or item.chapter_id in {chapter_id, None}]

    def rollback(self, course_id: str, chapter_id: str, version_id: str) -> CourseVersion:
        version = next((item for item in self.versions(course_id, chapter_id) if item.id == version_id), None)
        if version is None:
            raise KeyError(f"version {version_id} was not found")
        chapter = self.repository.get_chapter(course_id, chapter_id)
        before = {"package": deepcopy(chapter.package)}
        package = deepcopy(version.after.get("package"))
        self.repository.update_chapter(course_id, chapter_id, package=package, status="ready" if package is not None else "empty")
        return self.record_version(course_id, chapter_id, kind="rollback", reason=f"Restored {version_id}", changed_fields=["package"], before=before, after={"package": package})

    def import_students(self, course_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        course = self.repository.get_course(course_id)
        imported: list[Enrollment] = []
        errors: list[dict[str, Any]] = []
        for row in rows:
            row_number = int(row.get("row", 0))
            name = str(row.get("name", "")).strip()
            email = str(row.get("email", "")).strip()
            if not name:
                errors.append({"row": row_number, "message": "name is required"})
                continue
            if not email or "@" not in email:
                errors.append({"row": row_number, "message": "email is invalid"})
                continue
            enrollment = Enrollment(id=f"student-{self._enrollment_number}", course_id=course_id, student_name=name, email=email)
            self._enrollment_number += 1
            self._enrollments.setdefault(course_id, []).append(enrollment)
            course.student_ids.append(enrollment.id)
            imported.append(enrollment)
        self.repository.update_course(course_id, student_ids=course.student_ids)
        self._persist()
        return {"imported": len(imported), "errors": errors, "students": imported}

    def create_invite(self, course_id: str) -> str:
        self.repository.get_course(course_id)
        invite = f"invite-{course_id}-{self._invite_number}"
        self._invite_number += 1
        self._persist()
        return invite

    def students(self, course_id: str) -> list[Enrollment]:
        """Return the class roster, including learners who have not started yet."""
        self.repository.get_course(course_id)
        return list(self._enrollments.get(course_id, []))

    def record_attempt(self, course_id: str, student_id: str, *, completion_percent: int, answers: dict[str, bool]) -> Attempt:
        self.repository.get_course(course_id)
        if not 0 <= completion_percent <= 100:
            raise ValueError("completion_percent must be between 0 and 100")
        attempt = Attempt(id=f"attempt-{self._attempt_number}", course_id=course_id, student_id=student_id, completion_percent=completion_percent, answers=dict(answers))
        self._attempt_number += 1
        self._attempts.setdefault(course_id, []).append(attempt)
        self._persist()
        return attempt

    def analytics(self, course_id: str) -> dict[str, Any]:
        self.repository.get_course(course_id)
        attempts = self._attempts.get(course_id, [])
        latest = {attempt.student_id: attempt for attempt in attempts}
        students = [{"studentId": attempt.student_id, "completionPercent": attempt.completion_percent, "score": self._score(attempt)} for attempt in latest.values()]
        scores = [student["score"] for student in students]
        missed: dict[str, int] = {}
        for attempt in attempts:
            for question_id, correct in attempt.answers.items():
                if not correct:
                    missed[question_id] = missed.get(question_id, 0) + 1
        return {"students": students, "averageScore": round(sum(scores) / len(scores), 2) if scores else 0, "mostMissed": [{"questionId": question_id, "wrongCount": count} for question_id, count in sorted(missed.items(), key=lambda item: (-item[1], item[0]))]}

    @staticmethod
    def _score(attempt: Attempt) -> int:
        if not attempt.answers:
            return 0
        return round(100 * sum(attempt.answers.values()) / len(attempt.answers))
