import uuid

from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.slide import SlideModel


def test_models_expose_typography_columns():
    assert "typography" in PresentationModel.__table__.c
    assert "typography" in SlideModel.__table__.c


def test_new_presentation_and_slide_copy_typography():
    typography = {"version": 1, "roles": {"title": {"family": "Inter", "size": 52}}}
    presentation = PresentationModel(
        version=PresentationVersion.V2_STANDARD,
        content="deck",
        n_slides=1,
        language="English",
        typography=typography,
    )
    copy_of_presentation = presentation.get_new_presentation()
    assert copy_of_presentation.typography == typography
    assert copy_of_presentation.typography is not presentation.typography

    slide = SlideModel(
        presentation=uuid.uuid4(),
        layout_group="general",
        layout="general",
        index=0,
        content={"title": "x"},
        typography=typography,
    )
    copy_of_slide = slide.get_new_slide(presentation=uuid.uuid4())
    assert copy_of_slide.typography == typography
