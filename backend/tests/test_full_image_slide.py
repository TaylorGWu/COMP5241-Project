"""Image-led reference slides keep screenshots large and retain provenance text."""
import io

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.exporters.pptx import slide_deck_to_pptx, SLIDE_WIDTH
from app.schemas.ir import Project, ProjectMeta, Slide, SlideDeck


def test_diagram_layout_with_raster_uses_a_full_width_figure(tmp_path):
    image_path = tmp_path / 'capture.png'
    Image.new('RGB', (1440, 650), '#ffffff').save(image_path)
    slide = Slide(id='ref', order=1, layout='diagram', title='A reference interface',
        bullets=['Source: example.test · captured 29 Oct 2026.'], origin='teacher',
        speaker_notes='Public screenshot, not a claim of private product testing.',
        visuals=[{'id': 'v1', 'kind': 'illustration', 'assetId': 'image1', 'spec': {'capture': True, 'display': 'full'}}])
    project = Project(id='p', meta=ProjectMeta(title='References', audience='Reviewers', duration_min=5))
    output = Presentation(io.BytesIO(slide_deck_to_pptx(project, SlideDeck(artifact_id='deck', slides=[slide]), asset_paths={'image1': image_path})))
    picture = next(shape for shape in output.slides[0].shapes if shape.shape_type == MSO_SHAPE_TYPE.PICTURE)
    assert picture.width > SLIDE_WIDTH * .85
    assert picture.left > 0 and picture.left + picture.width <= SLIDE_WIDTH
    text = '\n'.join(shape.text for shape in output.slides[0].shapes if shape.has_text_frame)
    assert 'Source: example.test' in text
    assert output.slides[0].notes_slide.notes_text_frame.text == slide.speaker_notes
