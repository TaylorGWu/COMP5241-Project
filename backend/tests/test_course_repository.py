from __future__ import annotations

import pytest

from app.services.course_repository import InMemoryCourseRepository


def _course(repo: InMemoryCourseRepository, title: str = "Git basics"):
    return repo.create_course(
        title=title,
        description="A short course",
        audience="Beginners",
        language="zh-HK",
        duration_min=45,
    )


def test_new_course_starts_as_draft_with_one_empty_chapter():
    course = _course(InMemoryCourseRepository())

    assert course.status == "draft"
    assert course.chapter_ids


def test_chapters_are_ordered_and_belong_to_their_course():
    repo = InMemoryCourseRepository()
    course = _course(repo)
    first = repo.get_chapter(course.id, course.chapter_ids[0])
    second = repo.create_chapter(course.id, title="Branching")

    assert [first.order, second.order] == [1, 2]
    assert second.course_id == course.id


def test_reordering_chapters_renumbers_them_contiguously():
    repo = InMemoryCourseRepository()
    course = _course(repo)
    first_id = course.chapter_ids[0]
    second = repo.create_chapter(course.id, title="Branching")

    reordered = repo.reorder_chapters(course.id, [second.id, first_id])

    assert [chapter.id for chapter in reordered] == [second.id, first_id]
    assert [chapter.order for chapter in reordered] == [1, 2]


def test_final_chapter_cannot_be_deleted():
    repo = InMemoryCourseRepository()
    course = _course(repo)

    with pytest.raises(ValueError, match="last chapter"):
        repo.delete_chapter(course.id, course.chapter_ids[0])


def test_chapter_cannot_be_read_through_another_course():
    repo = InMemoryCourseRepository()
    first = _course(repo, "Git basics")
    second = _course(repo, "AI agents")

    with pytest.raises(KeyError):
        repo.get_chapter(second.id, first.chapter_ids[0])
