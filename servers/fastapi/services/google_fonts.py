"""Resolve Google Fonts families into locally cached woff2 files."""
from __future__ import annotations

import json
import os
import re
import shutil
from typing import Sequence

import httpx

from utils.asset_directory_utils import absolute_fastapi_asset_url
from utils.get_env import get_app_data_directory_env

DEFAULT_WEIGHTS = (400, 700)
_CSS_URL = "https://fonts.googleapis.com/css2?family={family}:wght@{weights}&display=swap"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_FACE_BLOCK = re.compile(r"@font-face\s*\{(.*?)\}", re.DOTALL)
_FONT_WEIGHT = re.compile(r"font-weight\s*:\s*(\d+)")
_FONT_URL = re.compile(r"url\((https://[^)]+?)\)")
_SLUG_INVALID = re.compile(r"[^a-z0-9]+")


class GoogleFontError(Exception):
    """Base error for Google Fonts resolution."""


class GoogleFontNotFound(GoogleFontError):
    """The requested family is not available on Google Fonts."""


class GoogleFontDownloadError(GoogleFontError):
    """A font file could not be downloaded."""


def slugify_family(family: str) -> str:
    slug = _SLUG_INVALID.sub("-", family.strip().lower()).strip("-")
    return slug[:60] or "font"


def google_font_directory(slug: str) -> str:
    app_data = get_app_data_directory_env() or "/tmp/presenton"
    return os.path.join(app_data, "fonts", "google", slug)


async def _http_get(url: str, *, binary: bool = False):
    async with httpx.AsyncClient(
        timeout=10.0, headers={"User-Agent": _USER_AGENT}
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content if binary else response.text


def _parse_faces(css: str) -> dict[int, str]:
    faces: dict[int, str] = {}
    for block in _FACE_BLOCK.findall(css):
        weight = _FONT_WEIGHT.search(block)
        url = _FONT_URL.search(block)
        if weight and url:
            faces.setdefault(int(weight.group(1)), url.group(1))
    return faces


async def resolve_google_font(
    family: str, weights: Sequence[int] = DEFAULT_WEIGHTS
) -> dict:
    normalized = " ".join(family.split())
    if not normalized:
        raise GoogleFontNotFound("Font family is required")

    slug = slugify_family(normalized)
    directory = google_font_directory(slug)
    manifest_path = os.path.join(directory, "manifest.json")
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as manifest_file:
            return json.load(manifest_file)["response"]

    css = await _http_get(
        _CSS_URL.format(
            family=normalized.replace(" ", "+"),
            weights=";".join(str(weight) for weight in weights),
        )
    )
    sources = _parse_faces(css)
    if not sources:
        raise GoogleFontNotFound(f"Google Fonts has no family named '{normalized}'")

    os.makedirs(directory, exist_ok=True)
    try:
        faces = []
        for weight in weights:
            url = sources.get(int(weight))
            if not url:
                continue
            content = await _http_get(url, binary=True)
            if len(content) > 5 * 1024 * 1024:
                raise GoogleFontDownloadError(
                    f"Font file for '{normalized}' is too large"
                )
            file_name = f"{weight}.woff2"
            with open(os.path.join(directory, file_name), "wb") as font_file:
                font_file.write(content)
            faces.append(
                {"weight": int(weight), "style": "normal", "url": file_name}
            )
        if not faces:
            raise GoogleFontDownloadError(
                f"No downloadable weight for '{normalized}'"
            )

        response = {
            "family": normalized,
            "url": absolute_fastapi_asset_url(
                f"/app_data/fonts/google/{slug}/{faces[0]['weight']}.woff2"
            ),
            "faces": [
                {
                    **face,
                    "url": absolute_fastapi_asset_url(
                        f"/app_data/fonts/google/{slug}/{face['url']}"
                    ),
                }
                for face in faces
            ],
        }
        with open(manifest_path, "w", encoding="utf-8") as manifest_file:
            json.dump({"response": response}, manifest_file)
        return response
    except Exception as exc:
        shutil.rmtree(directory, ignore_errors=True)
        if isinstance(exc, GoogleFontError):
            raise
        raise GoogleFontDownloadError(str(exc)) from exc
