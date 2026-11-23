"""Validation and persistence helpers for role-based typography."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.sql.presentation import PresentationModel
from models.sql.slide import SlideModel
from models.typography import (
    TypographyConfig,
    parse_typography,
    required_families,
)
from services.smart_typography_roles import ensure_role_markers

_ALLOWED_PREFIXES = ("/vendor/fonts/", "/app_data/fonts/google/")
_ABSOLUTE_APP_DATA_MARKER = "/app_data/fonts/google/"


def is_allowed_font_url(url: str) -> bool:
    if not isinstance(url, str) or not url.strip():
        return False
    if url.startswith(_ALLOWED_PREFIXES):
        return True
    return url.startswith(("http://", "https://")) and _ABSOLUTE_APP_DATA_MARKER in url


def merge_font_urls(existing, incoming) -> dict | None:
    merged = dict(existing or {})
    for family, url in (incoming or {}).items():
        if not isinstance(family, str) or not family.strip():
            raise HTTPException(
                status_code=422, detail="Font family names must be non-empty strings"
            )
        key = family.strip()
        trimmed = url.strip() if isinstance(url, str) else url
        # Entries already stored on the presentation are trusted: clients echo the
        # whole registry back, and older rows hold URLs this validator rejects.
        if key in merged and merged[key] == trimmed:
            continue
        if not is_allowed_font_url(url):
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported font URL for '{key}'",
            )
        merged[key] = trimmed
    return merged or None


def ensure_fonts_resolved(typography, fonts) -> TypographyConfig | None:
    config = parse_typography(typography)
    if config is None:
        return None
    missing = sorted(
        family for family in required_families(config) if family not in (fonts or {})
    )
    if missing:
        raise HTTPException(
            status_code=422, detail={"unresolved_font_families": missing}
        )
    return config


async def apply_role_markers_to_presentation(
    session: AsyncSession, presentation_id: uuid.UUID
) -> None:
    presentation = await session.get(PresentationModel, presentation_id)
    if presentation is None or presentation.generation_mode != "smart":
        return
    slides = (
        await session.scalars(
            select(SlideModel).where(SlideModel.presentation == presentation_id)
        )
    ).all()
    for slide in slides:
        if not slide.html_content:
            continue
        properties = dict(slide.properties or {})
        if properties.get("typography_roles_version") == 1:
            continue
        updated_html, changed = ensure_role_markers(slide.html_content)
        if changed:
            slide.html_content = updated_html
            properties["typography_roles_version"] = 1
            slide.properties = properties
            session.add(slide)
    await session.commit()
