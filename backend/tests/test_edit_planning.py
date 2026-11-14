"""The diagnostic phase must stay read-only before the teacher runs an action."""

from app.schemas.ir import CoursePackage, LearningObjective, Project, ProjectMeta, Slide, SlideDeck
from app.services.edit_planning import plan_edit
import pytest


def test_inserted_slide_is_targeted_by_stable_id_not_page_number_or_density():
    package = CoursePackage(
        project=Project(id="p", meta=ProjectMeta(title="Test", audience="Beginners", duration_min=30)),
        slide_deck=SlideDeck(artifact_id="deck", slides=[
            Slide(id="s3", order=4, layout="bullets", title="Old third", bullets=["a", "b", "c", "d"]),
            Slide(id="s-new-uuid", order=3, layout="bullets", title="Inserted third", bullets=[]),
        ]),
    )
    before = package.model_dump_json()
    for request in ["Make this clearer", "For slide 3 (s-new-uuid) only, plan a short concept animation"]:
        plan = plan_edit(package, request, slide_id="s-new-uuid")
        assert plan.slide_id == "s-new-uuid"
        assert len(plan.actions) == 1
        assert plan.actions[0].target_id == "s-new-uuid"
        assert "s-new-uuid" in plan.actions[0].prompt
    assert package.model_dump_json() == before
    with pytest.raises(KeyError):
        plan_edit(package, "Make this clearer", slide_id="deleted")


def test_edit_plan_is_read_only_and_course_specific():
    package = CoursePackage(
        project=Project(id="p1", meta=ProjectMeta(title="Git", audience="beginners", duration_min=45), learning_objectives=[LearningObjective(id="LO1", text="Explain branches"), LearningObjective(id="LO2", text="Review a pull request")]),
        slide_deck=SlideDeck(artifact_id="deck", slides=[Slide(id="s1", order=1, layout="bullets", title="Branches", bullets=["one", "two", "three", "four"], objective_ids=["LO1"])]),
    )
    before = package.model_dump_json()

    plan = plan_edit(package, "Make this clearer for beginners")

    assert package.model_dump_json() == before
    assert any(action.target_id == "s1" for action in plan.actions)
    assert any("LO2" in finding.detail for finding in plan.findings)
    assert all(action.prompt for action in plan.actions)


def test_animation_request_plans_one_current_slide_patch_only():
    package = CoursePackage(
        project=Project(id="p1", meta=ProjectMeta(title="Git", audience="beginners", duration_min=45), learning_objectives=[LearningObjective(id="LO1", text="Explain branches")]),
        slide_deck=SlideDeck(artifact_id="deck", slides=[
            Slide(id="s1", order=1, layout="bullets", title="Branches", bullets=["one"]),
            Slide(id="s2", order=2, layout="diagram", title="Merge", bullets=["two"], objective_ids=["LO1"]),
        ]),
    )

    plan = plan_edit(
        package,
        "For slide 2 (s2) only, plan a short concept animation. Only propose an animation patch that reveals existing content.",
    )

    assert len(plan.actions) == 1
    assert plan.actions[0].id == "animate-s2"
    assert plan.actions[0].target_id == "s2"
    assert "animation patch only" in plan.actions[0].prompt
