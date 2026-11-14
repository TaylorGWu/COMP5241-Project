"""Quiz options and instructions must remain separate across IR and export."""
import io

import pytest
from pptx import Presentation

from app.exporters.pptx import slide_deck_to_pptx
from app.schemas.ir import Project, ProjectMeta, Slide, SlideDeck


def quiz(**changes):
    return Slide.model_validate({"id": "s3", "order": 3, "layout": "quiz", "title": "Which sentence states the need?", "bullets": ['A. A calendar.', 'B. Knowing availability.', 'C. A spreadsheet.', 'D. A mobile app.', 'Pick one, then name the transcript phrase that supports your choice.'], **changes})


def test_legacy_quiz_has_four_options_and_a_separate_instruction():
    slide = quiz()
    assert slide.bullets == ["A calendar.", "Knowing availability.", "A spreadsheet.", "A mobile app."]
    assert slide.quiz_instruction == "Pick one, then name the transcript phrase that supports your choice."
    assert Slide.model_validate(slide.model_dump(by_alias=True)) == slide


@pytest.mark.parametrize("bullets", [
    ["Choose the best database for the workload.", "Keep the existing service.", "All of the above."],
    ["A. A variable named A.", "B. Choose one option in the settings menu.", "C. None of the above."],
])
def test_option_meaning_is_not_removed_by_instruction_detection(bullets):
    slide = quiz(bullets=bullets)
    assert len(slide.bullets) == len(bullets)
    assert slide.quiz_instruction == ""
    assert "Choose" in " ".join(slide.bullets)


def test_nonquiz_bullets_are_unchanged():
    slide = quiz(layout="bullets")
    assert slide.bullets[0] == "A. A calendar."
    assert len(slide.bullets) == 5


def test_explicit_instruction_is_preserved_with_clean_options():
    slide = quiz(bullets=["One", "Two", "Three"], quizInstruction="Choose one and explain why.")
    assert slide.bullets == ["One", "Two", "Three"]
    assert slide.quiz_instruction == "Choose one and explain why."


@pytest.mark.parametrize("instruction", [
    "Decide which one a tester could run and mark pass or fail, then say what is missing from the others.",
    "Pick the pair that correctly labels A and B, then say what you would write for C.",
])
def test_other_explicit_trailing_answer_prompts_are_not_options(instruction):
    slide = quiz(bullets=["A first answer", "A second answer", instruction])
    assert slide.bullets == ["A first answer", "A second answer"]
    assert slide.quiz_instruction == instruction


def test_instruction_removal_does_not_invalidate_existing_animation():
    slide = quiz(animation={"steps": [{"kind": "reveal", "target": "bullet:4", "atMs": 0}, {"kind": "reveal", "target": "bullet:1", "atMs": 700}]})
    assert [step.target for step in slide.animation.steps] == ["bullet:1"]


def test_pptx_numbers_choices_once_and_does_not_number_the_instruction():
    slide = quiz()
    deck = SlideDeck(artifact_id="deck", slides=[slide])
    project = Project(id="p", meta=ProjectMeta(title="Requirements", audience="Beginners", duration_min=25))
    presentation = Presentation(io.BytesIO(slide_deck_to_pptx(project, deck)))
    lines = [paragraph.text for shape in presentation.slides[0].shapes if shape.has_text_frame for paragraph in shape.text_frame.paragraphs]
    assert "A. A calendar." in lines
    assert "B. Knowing availability." in lines
    assert "D. A mobile app." in lines
    assert "Pick one, then name the transcript phrase that supports your choice." in lines
    assert not any(line.startswith("E.") or line.startswith("A. A.") for line in lines)
    option_frame = next(shape for shape in presentation.slides[0].shapes if shape.has_text_frame and "A. A calendar." in shape.text)
    assert "Pick one" not in option_frame.text
