import pytest
from fastapi import HTTPException

from models.typography import TypographyConfig
from services.typography_service import (
    ensure_fonts_resolved,
    is_allowed_font_url,
    merge_font_urls,
)


def test_allowed_font_urls():
    assert is_allowed_font_url("/vendor/fonts/sans_serif/inter/Inter.ttf")
    assert is_allowed_font_url("/app_data/fonts/google/playfair-display/400.woff2")
    assert is_allowed_font_url(
        "http://localhost:8000/app_data/fonts/google/playfair-display/400.woff2"
    )
    assert not is_allowed_font_url("/etc/passwd")
    assert not is_allowed_font_url("")


def test_merge_font_urls_adds_without_removing():
    merged = merge_font_urls(
        {"Inter": "/vendor/fonts/sans_serif/inter/Inter.ttf"},
        {"Manrope": "/app_data/fonts/google/manrope/400.woff2"},
    )
    assert merged == {
        "Inter": "/vendor/fonts/sans_serif/inter/Inter.ttf",
        "Manrope": "/app_data/fonts/google/manrope/400.woff2",
    }


def test_merge_rejects_unsupported_url():
    with pytest.raises(HTTPException) as error:
        merge_font_urls({}, {"Inter": "https://evil.example/font.ttf"})
    assert error.value.status_code == 422


def test_merge_keeps_already_stored_urls_without_revalidating():
    stored = {"Poppins": "https://fonts.googleapis.com/css2?family=Poppins"}

    merged = merge_font_urls(
        stored,
        {
            "Poppins": "https://fonts.googleapis.com/css2?family=Poppins",
            "Manrope": "/app_data/fonts/google/manrope/400.woff2",
        },
    )

    assert merged == {
        "Poppins": "https://fonts.googleapis.com/css2?family=Poppins",
        "Manrope": "/app_data/fonts/google/manrope/400.woff2",
    }


def test_merge_still_rejects_a_changed_url_for_a_known_family():
    with pytest.raises(HTTPException) as error:
        merge_font_urls(
            {"Inter": "/vendor/fonts/sans_serif/inter/Inter.ttf"},
            {"Inter": "https://evil.example/font.ttf"},
        )
    assert error.value.status_code == 422


def test_unresolved_family_is_rejected():
    config = TypographyConfig.model_validate(
        {"roles": {"title": {"family": "Inter", "size": 52}}}
    )
    with pytest.raises(HTTPException) as error:
        ensure_fonts_resolved(config, {})
    assert error.value.status_code == 422
    assert (
        ensure_fonts_resolved(
            config, {"Inter": "/vendor/fonts/sans_serif/inter/Inter.ttf"}
        )
        == config
    )
