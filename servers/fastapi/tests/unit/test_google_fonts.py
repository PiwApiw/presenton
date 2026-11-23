import asyncio
import json
from pathlib import Path

import pytest

from services import google_fonts

CSS = """
@font-face { font-family: 'Playfair Display'; font-weight: 400; src: url(https://fonts.gstatic.com/a.woff2) format('woff2'); }
@font-face { font-family: 'Playfair Display'; font-weight: 700; src: url(https://fonts.gstatic.com/b.woff2) format('woff2'); }
"""


def test_resolves_downloads_and_caches(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("NEXT_PUBLIC_FAST_API", raising=False)
    calls: list[str] = []

    async def fake_get(url: str, *, binary: bool = False):
        calls.append(url)
        if binary:
            return b"font-bytes"
        return CSS

    monkeypatch.setattr(google_fonts, "_http_get", fake_get)

    first = asyncio.run(google_fonts.resolve_google_font("Playfair Display"))
    assert first["family"] == "Playfair Display"
    assert [face["weight"] for face in first["faces"]] == [400, 700]
    assert first["url"].startswith("/app_data/fonts/google/playfair-display/")
    assert (tmp_path / "fonts" / "google" / "playfair-display" / "400.woff2").read_bytes() == b"font-bytes"
    manifest = json.loads(
        (tmp_path / "fonts" / "google" / "playfair-display" / "manifest.json").read_text()
    )
    assert manifest["response"]["family"] == "Playfair Display"

    calls.clear()
    second = asyncio.run(google_fonts.resolve_google_font("Playfair Display"))
    assert second == first
    assert calls == []


def test_unknown_family_raises_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIRECTORY", str(tmp_path))

    async def fake_get(url: str, *, binary: bool = False):
        return "<html>not a font</html>"

    monkeypatch.setattr(google_fonts, "_http_get", fake_get)
    with pytest.raises(google_fonts.GoogleFontNotFound):
        asyncio.run(google_fonts.resolve_google_font("Does Not Exist"))


def test_download_failure_cleans_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA_DIRECTORY", str(tmp_path))

    async def fake_get(url: str, *, binary: bool = False):
        if binary:
            raise RuntimeError("network down")
        return CSS

    monkeypatch.setattr(google_fonts, "_http_get", fake_get)
    with pytest.raises(google_fonts.GoogleFontDownloadError):
        asyncio.run(google_fonts.resolve_google_font("Playfair Display"))
    assert not (tmp_path / "fonts" / "google" / "playfair-display").exists()
