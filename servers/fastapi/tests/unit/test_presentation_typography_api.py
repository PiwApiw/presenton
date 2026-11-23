import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from api.v1.ppt.endpoints.presentation import (
    _presentation_response_data,
    update_presentation_typography,
)
from models.presentation_with_slides import PresentationWithSlides
from models.sql.presentation import PresentationModel, PresentationVersion
from models.typography import UpdateTypographyRequest
from tests.conftest import FakeAsyncSession


def _presentation(**overrides) -> PresentationModel:
    presentation = PresentationModel(
        id=uuid.uuid4(),
        version=PresentationVersion.V2_STANDARD,
        content="Prompt",
        n_slides=3,
        language="en",
        generation_mode="standard",
        fonts={"Inter": "/vendor/fonts/sans_serif/inter/Inter.ttf"},
    )
    for key, value in overrides.items():
        setattr(presentation, key, value)
    return presentation


def test_fonts_only_request_keeps_existing_typography():
    presentation = _presentation(
        typography={
            "version": 1,
            "roles": {"title": {"family": "Inter", "size": 52}},
        }
    )
    session = FakeAsyncSession(get_results={presentation.id: presentation})
    payload = UpdateTypographyRequest(
        fonts={"Manrope": "/app_data/fonts/google/manrope/400.woff2"}
    )

    asyncio.run(
        update_presentation_typography(
            id=presentation.id, payload=payload, sql_session=session
        )
    )

    assert presentation.typography == {
        "version": 1,
        "roles": {"title": {"family": "Inter", "size": 52}},
    }
    assert presentation.fonts["Manrope"] == "/app_data/fonts/google/manrope/400.woff2"
    assert presentation.fonts["Inter"] == "/vendor/fonts/sans_serif/inter/Inter.ttf"


def test_unknown_family_is_rejected():
    presentation = _presentation()
    session = FakeAsyncSession(get_results={presentation.id: presentation})
    payload = UpdateTypographyRequest.model_validate(
        {"typography": {"roles": {"title": {"family": "Manrope"}}}}
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            update_presentation_typography(
                id=presentation.id, payload=payload, sql_session=session
            )
        )
    assert error.value.status_code == 422


def test_font_url_outside_allowed_prefix_is_rejected():
    presentation = _presentation()
    session = FakeAsyncSession(get_results={presentation.id: presentation})
    payload = UpdateTypographyRequest.model_validate(
        {"fonts": {"Evil": "https://evil.example/font.ttf"}}
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            update_presentation_typography(
                id=presentation.id, payload=payload, sql_session=session
            )
        )
    assert error.value.status_code == 422


def test_missing_presentation_returns_404():
    session = FakeAsyncSession()
    payload = UpdateTypographyRequest.model_validate(
        {"typography": {"roles": {"title": {"size": 52}}}}
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            update_presentation_typography(
                id=uuid.uuid4(), payload=payload, sql_session=session
            )
        )
    assert error.value.status_code == 404


def test_resaving_existing_font_entries_is_allowed():
    presentation = _presentation(
        fonts={"Poppins": "https://fonts.googleapis.com/css2?family=Poppins"}
    )
    session = FakeAsyncSession(get_results={presentation.id: presentation})
    payload = UpdateTypographyRequest.model_validate(
        {
            "typography": {"roles": {"title": {"family": "Poppins", "size": 52}}},
            "fonts": {
                "Poppins": "https://fonts.googleapis.com/css2?family=Poppins",
                "Manrope": "/app_data/fonts/google/manrope/400.woff2",
            },
        }
    )

    asyncio.run(
        update_presentation_typography(
            id=presentation.id, payload=payload, sql_session=session
        )
    )

    assert presentation.fonts["Poppins"] == (
        "https://fonts.googleapis.com/css2?family=Poppins"
    )
    assert presentation.fonts["Manrope"] == "/app_data/fonts/google/manrope/400.woff2"
    assert presentation.typography["roles"]["title"] == {
        "family": "Poppins",
        "size": 52,
    }


def test_auto_typography_does_not_rewrite_smart_html():
    presentation = _presentation(generation_mode="smart")
    session = FakeAsyncSession(get_results={presentation.id: presentation})
    payload = UpdateTypographyRequest.model_validate(
        {
            "typography": {
                "roles": {
                    "title": {"family": None, "size": None},
                    "subtitle": {"family": None, "size": None},
                    "body": {"family": None, "size": None},
                }
            }
        }
    )

    asyncio.run(
        update_presentation_typography(
            id=presentation.id, payload=payload, sql_session=session
        )
    )

    # Only the request's own commit happens: no bootstrap pass over slide HTML.
    assert session.commit_count == 1


def test_presentation_response_exposes_typography():
    presentation = _presentation(
        typography={
            "version": 1,
            "roles": {"title": {"family": "Inter", "size": 52}},
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    response = PresentationWithSlides(
        **_presentation_response_data(presentation), slides=[]
    )

    # The API model must carry the column, otherwise Pydantic drops it and the
    # frontend always renders Auto.
    assert response.typography == {
        "version": 1,
        "roles": {"title": {"family": "Inter", "size": 52}},
    }
