"""A reusable fixed slide layout, not a midterm-only HTML exception."""
import io

import pytest
from pydantic import ValidationError
from pptx import Presentation

from app.schemas.ir import Slide, SlideDeck, Project, ProjectMeta
from app.exporters.pptx import slide_deck_to_pptx
from app.services.tools import SLIDE_SCHEMA


def board(**changes):
    return Slide.model_validate({
        'id': 's1', 'order': 1, 'layout': 'statusBoard', 'title': 'Teacher progress',
        'statusGroups': [
            {'title': 'Must', 'items': [{'label': 'Course editing', 'status': 'complete'}]},
            {'title': 'Should', 'items': [{'label': 'PDF export', 'status': 'partial'}]},
            {'title': 'Could', 'items': [{'label': 'Team integration', 'status': 'unverified'}]},
        ], **changes,
    })


def test_status_groups_round_trip_without_becoming_bullets():
    slide = board()
    assert slide.bullets == []
    assert slide.status_groups[2].items[0].status == 'unverified'
    assert Slide.model_validate(slide.model_dump(by_alias=True)) == slide


@pytest.mark.parametrize('changes', [
    {'statusGroups': []},
    {'statusGroups': [{'title': 'Must', 'items': [{'label': 'False certainty', 'status': '100%'}]}]},
    {'statusGroups': [{'title': 'Too many', 'items': [{'label': str(n), 'status': 'partial'} for n in range(7)]}]},
])
def test_status_board_rejects_missing_or_unbounded_content(changes):
    with pytest.raises(ValidationError):
        board(**changes)


def test_pptx_preserves_each_group_label_and_explicit_status():
    slide = board()
    project = Project(id='p', meta=ProjectMeta(title='Progress', audience='Reviewers', duration_min=5))
    deck = SlideDeck(artifact_id='deck', slides=[slide])
    exported = Presentation(io.BytesIO(slide_deck_to_pptx(project, deck)))
    texts = [shape.text for shape in exported.slides[0].shapes if shape.has_text_frame]
    for value in ['Must', 'Should', 'Could', 'Course editing', 'PDF export', 'Team integration', 'Complete', 'Partial', 'To confirm']:
        assert any(value in text for text in texts), value
    assert '100%' not in '\n'.join(texts)


def test_generation_tool_exposes_the_same_structured_layout():
    assert 'statusBoard' in SLIDE_SCHEMA['properties']['layout']['enum']
    assert 'statusGroups' in SLIDE_SCHEMA['properties']
