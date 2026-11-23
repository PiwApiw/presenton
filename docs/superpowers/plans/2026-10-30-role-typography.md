# Role-Based Typography Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pengguna dapat memilih jenis font dan ukuran font untuk peran Judul, Sub Judul, dan Deskripsi — saat generate maupun di editor — dengan `Auto` sebagai default dan hasil preview identik dengan export.

**Architecture:** Konfigurasi tipografi disimpan sebagai data (`presentations.typography` + `slides.typography`) dan diterapkan saat render: CSS injection untuk slide Smart (`data-text-role`), transformasi layout di memori untuk slide Konva. Export memakai URL presentasi yang sama, sehingga paritas diperoleh tanpa mengubah runtime export.

**Tech Stack:** FastAPI + SQLModel + Alembic + pytest (backend), Next.js 16 + React + Konva + Node `node:test` dengan esbuild (frontend).

**Spec:** `docs/superpowers/specs/2026-10-30-role-typography-design.md`

## Global Constraints

- Backend Python `>=3.11,<3.12`; dependensi hanya lewat `uv` (`uv run --group dev pytest ...`). Jangan menambah dependensi runtime baru.
- Frontend memakai `node --test`; file tes baru berakhiran `.test.mjs` di `servers/nextjs/tests/` dan membundel sumber TS via `esbuild` seperti tes yang sudah ada.
- JSON tipografi selalu berbentuk `{ "version": 1, "roles": { "title": {...}, "subtitle": {...}, "body": {...} } }`; `null` berarti Auto.
- Ukuran font valid 8–200 px (kanvas 1280×720).
- Presentasi/slide tanpa `typography` harus berperilaku persis seperti sebelum fitur ini.
- HTML slide Smart tidak boleh ditulis ulang isinya; satu-satunya mutasi adalah penambahan atribut `data-text-role`.
- URL font yang diterima backend hanya berawalan `/vendor/fonts/` atau `/app_data/fonts/google/` (atau bentuk absolut yang memuat `/app_data/fonts/google/`).
- Otorisasi presentasi mengikuti middleware yang sudah ada; handler baru tidak menambahkan pemeriksaan owner sendiri.
- Commit hanya dibuat bila pengguna menyetujuinya secara eksplisit; setiap task diakhiri dengan perubahan yang bisa diverifikasi walau commit ditunda.

---

### Task 1: Skema tipografi backend

**Files:**
- Create: `servers/fastapi/models/typography.py`
- Test: `servers/fastapi/tests/unit/test_typography_config.py`

**Interfaces:**
- Consumes: tidak ada.
- Produces: `TypographyRoleConfig`, `TypographyRoles`, `TypographyConfig`, `UpdateTypographyRequest`, `ROLE_NAMES`, `parse_typography(value)`, `merge_typography(base, override)`, `is_auto(config)`, `required_families(config)`.

- [ ] **Step 1: Tulis tes yang gagal**

```python
# servers/fastapi/tests/unit/test_typography_config.py
import pytest
from pydantic import ValidationError

from models.typography import (
    TypographyConfig,
    is_auto,
    merge_typography,
    parse_typography,
    required_families,
)


def test_role_fields_are_optional_and_blank_family_becomes_none():
    config = TypographyConfig.model_validate(
        {"roles": {"title": {"family": "   ", "size": None}}}
    )
    assert config.roles.title.family is None
    assert is_auto(config) is True


def test_size_bounds_are_enforced():
    with pytest.raises(ValidationError):
        TypographyConfig.model_validate({"roles": {"title": {"size": 7}}})
    with pytest.raises(ValidationError):
        TypographyConfig.model_validate({"roles": {"title": {"size": 201}}})


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        TypographyConfig.model_validate({"roles": {"title": {"colour": "red"}}})


def test_merge_overrides_only_filled_fields():
    base = TypographyConfig.model_validate(
        {"roles": {"title": {"family": "Inter", "size": 52}}}
    )
    override = TypographyConfig.model_validate({"roles": {"title": {"size": 40}}})
    merged = merge_typography(base, override)
    assert merged.roles.title.family == "Inter"
    assert merged.roles.title.size == 40
    assert merged.roles.body.family is None


def test_merge_with_none_inputs_returns_empty_config():
    merged = merge_typography(None, None)
    assert merged.version == 1
    assert merged.roles.title.size is None


def test_required_families_and_auto_detection():
    config = parse_typography(
        {"roles": {"title": {"family": "Inter"}, "body": {"family": "Manrope"}}}
    )
    assert required_families(config) == {"Inter", "Manrope"}
    assert is_auto(None) is True
    assert is_auto({"roles": {}}) is True
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.typography'`

- [ ] **Step 3: Implementasi minimal**

```python
# servers/fastapi/models/typography.py
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ROLE_NAMES = ("title", "subtitle", "body")


class TypographyRoleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: Optional[str] = Field(default=None, max_length=120)
    size: Optional[int] = Field(default=None, ge=8, le=200)

    @field_validator("family")
    @classmethod
    def _blank_family_to_none(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class TypographyRoles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TypographyRoleConfig = Field(default_factory=TypographyRoleConfig)
    subtitle: TypographyRoleConfig = Field(default_factory=TypographyRoleConfig)
    body: TypographyRoleConfig = Field(default_factory=TypographyRoleConfig)


class TypographyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1] = 1
    roles: TypographyRoles = Field(default_factory=TypographyRoles)


class UpdateTypographyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    typography: Optional[TypographyConfig] = None
    fonts: Optional[dict[str, str]] = None


def parse_typography(value) -> Optional[TypographyConfig]:
    if value is None:
        return None
    if isinstance(value, TypographyConfig):
        return value
    return TypographyConfig.model_validate(value)


def merge_typography(base, override) -> TypographyConfig:
    base_config = parse_typography(base) or TypographyConfig()
    override_config = parse_typography(override) or TypographyConfig()
    merged = {}
    for role in ROLE_NAMES:
        base_role = getattr(base_config.roles, role)
        override_role = getattr(override_config.roles, role)
        merged[role] = TypographyRoleConfig(
            family=(
                override_role.family
                if override_role.family is not None
                else base_role.family
            ),
            size=(
                override_role.size
                if override_role.size is not None
                else base_role.size
            ),
        )
    return TypographyConfig(roles=TypographyRoles(**merged))


def is_auto(config) -> bool:
    parsed = parse_typography(config)
    if parsed is None:
        return True
    return all(
        getattr(parsed.roles, role).family is None
        and getattr(parsed.roles, role).size is None
        for role in ROLE_NAMES
    )


def required_families(config) -> set[str]:
    parsed = parse_typography(config)
    if parsed is None:
        return set()
    return {
        getattr(parsed.roles, role).family
        for role in ROLE_NAMES
        if getattr(parsed.roles, role).family
    }
```

- [ ] **Step 4: Jalankan tes sampai lulus**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_config.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit (setelah disetujui pengguna)**

```bash
git add servers/fastapi/models/typography.py servers/fastapi/tests/unit/test_typography_config.py
git commit -m "feat: add typography schema models"
```

---

### Task 2: Kolom database dan migrasi

**Files:**
- Modify: `servers/fastapi/models/sql/presentation.py` (tambah field + salin di `get_new_presentation`)
- Modify: `servers/fastapi/models/sql/slide.py` (tambah field + salin di `get_new_slide`)
- Create: `servers/fastapi/alembic/versions/a1c4e7b9d2f5_add_typography_columns.py`
- Test: `servers/fastapi/tests/unit/test_typography_columns.py`

**Interfaces:**
- Consumes: tidak ada (kolom JSON biasa).
- Produces: atribut `PresentationModel.typography` dan `SlideModel.typography` bertipe `Optional[dict]`.

- [ ] **Step 1: Tulis tes yang gagal**

```python
# servers/fastapi/tests/unit/test_typography_columns.py
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
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_columns.py -v`
Expected: FAIL — `TypeError: 'typography' is an invalid keyword argument`

- [ ] **Step 3: Tambahkan field ke model dan salin pada method duplikasi**

Di `servers/fastapi/models/sql/presentation.py`, setelah field `community_design_ids`:

```python
    typography: Optional[dict] = Field(sa_column=Column(JSON), default=None)
```

Di dalam `get_new_presentation()`, setelah `community_design_ids=...`:

```python
            typography=copy.deepcopy(self.typography),
```

Di `servers/fastapi/models/sql/slide.py`, setelah field `ui`:

```python
    typography: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
```

Di dalam `get_new_slide()`, setelah `ui=copy.deepcopy(self.ui),`:

```python
            typography=copy.deepcopy(self.typography),
```

- [ ] **Step 4: Buat migrasi Alembic**

```python
# servers/fastapi/alembic/versions/a1c4e7b9d2f5_add_typography_columns.py
"""add typography columns

Revision ID: a1c4e7b9d2f5
Revises: 026c0ba8b35c
Create Date: 2026-10-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c4e7b9d2f5"
down_revision: Union[str, None] = "026c0ba8b35c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table_name)
    return column_name in {column["name"] for column in columns}


def upgrade() -> None:
    if _has_table("presentations") and not _has_column("presentations", "typography"):
        op.add_column(
            "presentations", sa.Column("typography", sa.JSON(), nullable=True)
        )
    if _has_table("slides") and not _has_column("slides", "typography"):
        op.add_column("slides", sa.Column("typography", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_table("slides") and _has_column("slides", "typography"):
        op.drop_column("slides", "typography")
    if _has_table("presentations") and _has_column("presentations", "typography"):
        op.drop_column("presentations", "typography")
```

- [ ] **Step 5: Jalankan tes dan migrasi**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_columns.py -v`
Expected: 2 passed

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit -q`
Expected: tidak ada kegagalan baru dibanding baseline

- [ ] **Step 6: Commit (setelah disetujui pengguna)**

```bash
git add servers/fastapi/models/sql/presentation.py servers/fastapi/models/sql/slide.py servers/fastapi/alembic/versions/a1c4e7b9d2f5_add_typography_columns.py servers/fastapi/tests/unit/test_typography_columns.py
git commit -m "feat: persist typography on presentations and slides"
```

---

### Task 3: Penanda peran untuk slide Smart (backfill)

**Files:**
- Create: `servers/fastapi/services/smart_typography_roles.py`
- Test: `servers/fastapi/tests/unit/test_smart_typography_roles.py`

**Interfaces:**
- Consumes: tidak ada.
- Produces: `ROLE_ATTRIBUTE = "data-text-role"`, `font_size_score(tag, attrs) -> float`, `ensure_role_markers(html: str) -> tuple[str, bool]`.

- [ ] **Step 1: Tulis tes yang gagal**

```python
# servers/fastapi/tests/unit/test_smart_typography_roles.py
from services.smart_typography_roles import ensure_role_markers

SECTION = '<section data-slide-type="content" class="relative h-[720px] w-[1280px]">'
END = "</section>"


def _html(body: str) -> str:
    return f"{SECTION}{body}{END}"


def test_marks_title_subtitle_and_body_by_size():
    html = _html(
        '<div><h1 class="text-5xl font-bold">Quarterly Plan</h1>'
        '<p class="text-3xl">What changed</p>'
        '<div class="text-base">Body copy here</div></div>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    assert 'data-text-role="title"' in result
    assert 'data-text-role="subtitle"' in result
    assert 'data-text-role="body"' in result
    assert "Quarterly Plan" in result


def test_inline_font_size_wins_over_tailwind_class():
    html = _html(
        '<div style="font-size:64px">Big inline</div>'
        '<div class="text-5xl">Class only</div>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    title_index = result.index('data-text-role="title"')
    assert title_index < result.index("Big inline")


def test_is_idempotent_when_roles_already_present():
    html = _html('<h1 data-text-role="title">Title</h1><p data-text-role="body">Body</p>')
    assert ensure_role_markers(html) == (html, False)


def test_ignores_decorative_aria_hidden_and_empty_html():
    html = _html(
        '<div data-decorative="true" class="text-6xl">Decorative</div>'
        '<div aria-hidden="true" class="text-6xl">Hidden</div>'
        '<p class="text-xl">Real copy</p>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    assert 'data-text-role="title"' in result
    decorative_part = result.split('data-decorative="true"')[0]
    assert "text-6xl" in result
    assert 'data-text-role="title"' not in decorative_part
    assert ensure_role_markers("") == ("", False)


def test_label_like_elements_never_become_title():
    html = _html(
        '<div class="text-5xl" data-name="footer_label">Footer</div>'
        '<h2 class="text-3xl">Actual heading</h2>'
    )
    result, changed = ensure_role_markers(html)
    assert changed is True
    footer_tag = result[result.index('data-name="footer_label"') :].split(">")[0]
    assert 'data-text-role="title"' not in footer_tag
    assert result.index('data-text-role="title"') > result.index("Footer")
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_smart_typography_roles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.smart_typography_roles'`

- [ ] **Step 3: Implementasi**

```python
# servers/fastapi/services/smart_typography_roles.py
"""Add data-text-role markers to Smart slide HTML without changing its content."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

ROLE_ATTRIBUTE = "data-text-role"

_SKIP_TAGS = {
    "script",
    "style",
    "svg",
    "path",
    "defs",
    "br",
    "img",
    "hr",
    "canvas",
    "section",
}
_EXCLUDED_NAME = re.compile(r"(footer|page[_-]?number|badge|caption|label|kicker)", re.I)
_INLINE_SIZE = re.compile(r"font-size\s*:\s*([\d.]+)px", re.I)
_ARBITRARY_SIZE = re.compile(r"text-\[(\d+(?:\.\d+)?)px\]")
_TAILWIND_SIZES = {
    "text-xs": 12,
    "text-sm": 14,
    "text-base": 16,
    "text-lg": 18,
    "text-xl": 20,
    "text-2xl": 24,
    "text-3xl": 30,
    "text-4xl": 36,
    "text-5xl": 48,
    "text-6xl": 60,
    "text-7xl": 72,
    "text-8xl": 96,
    "text-9xl": 128,
}
_TAG_SIZES = {"h1": 48, "h2": 36, "h3": 30, "h4": 24, "h5": 20, "h6": 18}


def _attributes(attrs) -> dict[str, str]:
    return {name.lower(): value or "" for name, value in attrs}


def font_size_score(tag: str, attrs: dict[str, str]) -> float:
    inline = _INLINE_SIZE.search(attrs.get("style", ""))
    if inline:
        return float(inline.group(1))
    classes = attrs.get("class", "").split()
    for token in classes:
        arbitrary = _ARBITRARY_SIZE.fullmatch(token)
        if arbitrary:
            return float(arbitrary.group(1))
    for token in classes:
        if token in _TAILWIND_SIZES:
            return float(_TAILWIND_SIZES[token])
    return float(_TAG_SIZES.get(tag, 16))


class _CandidateParser(HTMLParser):
    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=False)
        self._line_offsets = [0]
        for index, character in enumerate(html):
            if character == "\n":
                self._line_offsets.append(index + 1)
        self._stack: list[dict[str, Any]] = []
        self.candidates: list[dict[str, Any]] = []
        self.has_role_attribute = False

    def _absolute_offset(self) -> int:
        line, column = self.getpos()
        return self._line_offsets[line - 1] + column

    def handle_starttag(self, tag, attrs):
        attributes = _attributes(attrs)
        if ROLE_ATTRIBUTE in attributes:
            self.has_role_attribute = True
        self._stack.append(
            {
                "tag": tag,
                "attrs": attributes,
                "offset": self._absolute_offset(),
                "tag_text": self.get_starttag_text() or "",
                "has_text": False,
            }
        )

    def handle_startendtag(self, tag, attrs):
        return

    def handle_data(self, data):
        if data.strip() and self._stack:
            self._stack[-1]["has_text"] = True

    def handle_endtag(self, tag):
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag:
                frame = self._stack.pop(index)
                del self._stack[index:]
                if frame["has_text"]:
                    self.candidates.append(frame)
                return


def _is_eligible(candidate: dict[str, Any]) -> bool:
    attrs = candidate["attrs"]
    if candidate["tag"] in _SKIP_TAGS:
        return False
    if attrs.get("aria-hidden", "").lower() == "true":
        return False
    if attrs.get("data-decorative", "").lower() == "true":
        return False
    classes = attrs.get("class", "").split()
    if "hidden" in classes or "sr-only" in classes:
        return False
    name = f"{attrs.get('data-name', '')} {attrs.get('id', '')}"
    return _EXCLUDED_NAME.search(name) is None


def _assign_roles(candidates: list[dict[str, Any]]) -> dict[int, str]:
    eligible = [candidate for candidate in candidates if _is_eligible(candidate)]
    excluded = [candidate for candidate in candidates if not _is_eligible(candidate)]
    roles = {id(candidate): "body" for candidate in excluded}
    if not eligible:
        return roles

    ranked = sorted(
        enumerate(eligible),
        key=lambda item: (-font_size_score(item[1]["tag"], item[1]["attrs"]), item[0]),
    )
    title = ranked[0][1]
    roles[id(title)] = "title"
    title_size = font_size_score(title["tag"], title["attrs"])
    subtitle_assigned = False
    for _, candidate in ranked[1:]:
        size = font_size_score(candidate["tag"], candidate["attrs"])
        if not subtitle_assigned and title_size * 0.6 <= size < title_size:
            roles[id(candidate)] = "subtitle"
            subtitle_assigned = True
        else:
            roles[id(candidate)] = roles.get(id(candidate), "body")
    return roles


def ensure_role_markers(html: str) -> tuple[str, bool]:
    if not html or "<section" not in html:
        return html, False

    parser = _CandidateParser(html)
    parser.feed(html)
    parser.close()
    if parser.has_role_attribute:
        return html, False

    roles = _assign_roles(parser.candidates)
    insertions: list[tuple[int, str]] = []
    for candidate in parser.candidates:
        role = roles.get(id(candidate))
        if role is None:
            continue
        tag_text = candidate["tag_text"]
        closing = tag_text.rfind(">")
        if closing <= 0 or tag_text[: closing + 1].rstrip().endswith("/>"):
            continue
        insertions.append((candidate["offset"] + closing, f' {ROLE_ATTRIBUTE}="{role}"'))

    if not insertions:
        return html, False

    result = html
    for position, attribute in sorted(insertions, reverse=True):
        result = f"{result[:position]}{attribute}{result[position:]}"
    return result, True
```

- [ ] **Step 4: Jalankan tes sampai lulus**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_smart_typography_roles.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit (setelah disetujui pengguna)**

```bash
git add servers/fastapi/services/smart_typography_roles.py servers/fastapi/tests/unit/test_smart_typography_roles.py
git commit -m "feat: backfill smart slide typography roles"
```

---

### Task 4: Resolusi dan cache Google Fonts

**Files:**
- Create: `servers/fastapi/services/google_fonts.py`
- Modify: `servers/fastapi/api/v1/ppt/endpoints/fonts.py` (tambah `POST /google`)
- Test: `servers/fastapi/tests/unit/test_google_fonts.py`

**Interfaces:**
- Consumes: `utils.asset_directory_utils.absolute_fastapi_asset_url`, `utils.get_env.get_app_data_directory_env`.
- Produces: `GoogleFontNotFound`, `GoogleFontDownloadError`, `slugify_family(family) -> str`, `resolve_google_font(family, weights=(400, 700)) -> dict`, `POST /api/v1/ppt/fonts/google`.

- [ ] **Step 1: Tulis tes yang gagal**

```python
# servers/fastapi/tests/unit/test_google_fonts.py
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
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_google_fonts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.google_fonts'`

- [ ] **Step 3: Implementasi service**

```python
# servers/fastapi/services/google_fonts.py
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
                raise GoogleFontDownloadError(f"Font file for '{normalized}' is too large")
            file_name = f"{weight}.woff2"
            with open(os.path.join(directory, file_name), "wb") as font_file:
                font_file.write(content)
            faces.append(
                {"weight": int(weight), "style": "normal", "url": file_name}
            )
        if not faces:
            raise GoogleFontDownloadError(f"No downloadable weight for '{normalized}'")

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
```

- [ ] **Step 4: Tambahkan endpoint**

Tambahkan di `servers/fastapi/api/v1/ppt/endpoints/fonts.py` (setelah `list_fonts`):

```python
class GoogleFontRequest(BaseModel):
    family: str
    weights: Optional[List[int]] = None


@FONTS_ROUTER.post("/google")
async def resolve_google_font_endpoint(payload: GoogleFontRequest):
    try:
        return await resolve_google_font(
            payload.family, payload.weights or DEFAULT_WEIGHTS
        )
    except GoogleFontNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GoogleFontDownloadError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
```

Tambahkan import di bagian atas file:

```python
from services.google_fonts import (
    DEFAULT_WEIGHTS,
    GoogleFontDownloadError,
    GoogleFontNotFound,
    resolve_google_font,
)
```

- [ ] **Step 5: Jalankan tes sampai lulus**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_google_fonts.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit (setelah disetujui pengguna)**

```bash
git add servers/fastapi/services/google_fonts.py servers/fastapi/api/v1/ppt/endpoints/fonts.py servers/fastapi/tests/unit/test_google_fonts.py
git commit -m "feat: resolve and cache google fonts"
```

---

### Task 5: Layanan validasi dan endpoint penyimpanan tipografi

**Files:**
- Create: `servers/fastapi/services/typography_service.py`
- Modify: `servers/fastapi/api/v1/ppt/endpoints/presentation.py` (parameter `create_presentation`, endpoint `PATCH /{id}/typography`)
- Modify: `servers/fastapi/models/generate_presentation_request.py` (field `typography`, `fonts`)
- Test: `servers/fastapi/tests/unit/test_typography_service.py`
- Test: `servers/fastapi/tests/unit/test_presentation_typography_api.py`
- Test: `servers/fastapi/tests/unit/test_presentation_slide_update_api.py` (tambahan kasus)

**Interfaces:**
- Consumes: `models.typography.*` (Task 1), `PresentationModel.typography` (Task 2), `ensure_role_markers` (Task 3).
- Produces: `is_allowed_font_url(url) -> bool`, `merge_font_urls(existing, incoming) -> dict | None`, `ensure_fonts_resolved(typography, fonts) -> TypographyConfig | None`, `apply_role_markers_to_presentation(session, presentation_id) -> None`, `PATCH /presentation/{id}/typography`.

- [ ] **Step 1: Tulis tes yang gagal**

```python
# servers/fastapi/tests/unit/test_typography_service.py
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


def test_unresolved_family_is_rejected():
    config = TypographyConfig.model_validate(
        {"roles": {"title": {"family": "Inter", "size": 52}}}
    )
    with pytest.raises(HTTPException) as error:
        ensure_fonts_resolved(config, {})
    assert error.value.status_code == 422
    assert ensure_fonts_resolved(
        config, {"Inter": "/vendor/fonts/sans_serif/inter/Inter.ttf"}
    ) == config
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.typography_service'`

- [ ] **Step 3: Implementasi service**

```python
# servers/fastapi/services/typography_service.py
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
        if not is_allowed_font_url(url):
            raise HTTPException(
                status_code=422,
                detail=f"Unsupported font URL for '{family.strip()}'",
            )
        merged[family.strip()] = url.strip()
    return merged or None


def ensure_fonts_resolved(typography, fonts) -> TypographyConfig | None:
    config = parse_typography(typography)
    if config is None:
        return None
    missing = sorted(family for family in required_families(config) if family not in (fonts or {}))
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
```

- [ ] **Step 4: Sambungkan ke endpoint presentasi**

Di `servers/fastapi/api/v1/ppt/endpoints/presentation.py`, tambahkan import:

```python
from models.typography import TypographyConfig, UpdateTypographyRequest
from services.typography_service import (
    apply_role_markers_to_presentation,
    ensure_fonts_resolved,
    merge_font_urls,
)
```

Pada `create_presentation`, tambahkan dua parameter `Body` setelah `community_design_ids`:

```python
    typography: Annotated[Optional[TypographyConfig], Body()] = None,
    fonts: Annotated[Optional[dict[str, str]], Body()] = None,
```

Sebelum `presentation = PresentationModel(...)`, tambahkan:

```python
    merged_fonts = merge_font_urls(None, fonts)
    normalized_typography = ensure_fonts_resolved(typography, merged_fonts)
```

Dan pada konstruktor `PresentationModel(...)` tambahkan:

```python
        fonts=merged_fonts,
        typography=(
            normalized_typography.model_dump() if normalized_typography else None
        ),
```

Tambahkan endpoint baru setelah `delete_presentation`:

```python
@PRESENTATION_ROUTER.patch("/{id}/typography", response_model=PresentationModel)
async def update_presentation_typography(
    id: uuid.UUID,
    payload: UpdateTypographyRequest,
    sql_session: AsyncSession = Depends(get_async_session),
):
    presentation = await sql_session.get(PresentationModel, id)
    if not presentation:
        raise HTTPException(404, "Presentation not found")

    merged_fonts = merge_font_urls(presentation.fonts, payload.fonts)
    if "typography" in payload.model_fields_set:
        config = ensure_fonts_resolved(payload.typography, merged_fonts)
        presentation.typography = config.model_dump() if config else None
    presentation.fonts = merged_fonts
    await sql_session.commit()
    await sql_session.refresh(presentation)

    if presentation.typography is not None:
        await apply_role_markers_to_presentation(sql_session, presentation.id)
    return presentation
```

`model_fields_set` dipakai agar request `{ "fonts": {...} }` hanya menambah font tanpa menghapus tipografi presentasi yang sudah ada.

Pada `models/generate_presentation_request.py`, tambahkan field ke kedua model:

```python
    typography: Optional[dict] = None
    fonts: Optional[dict[str, str]] = None
```

- [ ] **Step 5: Backfill penanda peran saat slide disimpan (cakupan per slide)**

Cakupan per slide ditulis lewat `slide_update`, sehingga backfill dipasang di endpoint itu.

Di `presentation.py`, tambahkan import:

```python
from models.typography import is_auto
from services.smart_typography_roles import ensure_role_markers
```

Pada `update_presentation_slide`, setelah `stored_slide.sqlmodel_update(...)`, tambahkan:

```python
    if (
        stored_slide.html_content
        and stored_slide.typography
        and not is_auto(stored_slide.typography)
    ):
        properties = dict(stored_slide.properties or {})
        if properties.get("typography_roles_version") != 1:
            updated_html, changed = ensure_role_markers(stored_slide.html_content)
            if changed:
                stored_slide.html_content = updated_html
            properties["typography_roles_version"] = 1
            stored_slide.properties = properties
            sql_session.add(stored_slide)
```

Tambahkan dua tes ke `servers/fastapi/tests/unit/test_presentation_slide_update_api.py` (memakai pola `FakeAsyncSession` yang sudah ada di file itu):

```python
def test_slide_update_backfills_role_markers_when_slide_typography_is_set():
    stored = _slide()
    stored.html_content = (
        "<section data-slide-type='content'><h1>Judul</h1></section>"
    )
    incoming = _slide(slide_id=stored.id, presentation_id=stored.presentation)
    incoming.html_content = stored.html_content
    incoming.typography = {"version": 1, "roles": {"title": {"size": 52}}}
    session = FakeAsyncSession(get_results={stored.id: stored})

    asyncio.run(update_presentation_slide(slide=incoming, sql_session=session))

    assert 'data-text-role="title"' in stored.html_content
    assert stored.properties["typography_roles_version"] == 1


def test_slide_update_leaves_html_untouched_when_typography_is_auto():
    stored = _slide()
    stored.html_content = (
        "<section data-slide-type='content'><h1>Judul</h1></section>"
    )
    original = stored.html_content
    incoming = _slide(slide_id=stored.id, presentation_id=stored.presentation)
    incoming.html_content = original
    incoming.typography = {"version": 1, "roles": {"title": {"size": None}}}
    session = FakeAsyncSession(get_results={stored.id: stored})

    asyncio.run(update_presentation_slide(slide=incoming, sql_session=session))

    assert stored.html_content == original
    assert stored.properties == {"accent": "blue"}
```

- [ ] **Step 6: Tes endpoint penyimpanan tipografi**

```python
# servers/fastapi/tests/unit/test_presentation_typography_api.py
import asyncio
import uuid

import pytest
from fastapi import HTTPException

from api.v1.ppt.endpoints.presentation import update_presentation_typography
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
```

- [ ] **Step 7: Jalankan tes sampai lulus**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_service.py tests/unit/test_typography_config.py tests/unit/test_smart_typography_roles.py tests/unit/test_presentation_slide_update_api.py tests/unit/test_presentation_typography_api.py -v`
Expected: semua passed

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit -q`
Expected: tidak ada kegagalan baru

- [ ] **Step 8: Commit (setelah disetujui pengguna)**

```bash
git add servers/fastapi/services/typography_service.py servers/fastapi/api/v1/ppt/endpoints/presentation.py servers/fastapi/models/generate_presentation_request.py servers/fastapi/tests/unit/test_typography_service.py servers/fastapi/tests/unit/test_presentation_typography_api.py servers/fastapi/tests/unit/test_presentation_slide_update_api.py
git commit -m "feat: persist typography through presentation API"
```

---

### Task 6: Prompt Smart dan penerapan penanda saat generate

**Files:**
- Create: `servers/fastapi/utils/llm_calls/typography_prompt.py`
- Modify: `servers/fastapi/utils/llm_calls/generate_smart_presentation.py` (`get_smart_messages`, `generate_smart_presentation`)
- Modify: `servers/fastapi/api/v1/ppt/endpoints/presentation.py` (panggilan `generate_smart_presentation` di sekitar baris 2090)
- Test: `servers/fastapi/tests/unit/test_typography_prompt.py`

**Interfaces:**
- Consumes: `models.typography.TypographyConfig`, `parse_typography`, `is_auto`.
- Produces: `build_typography_prompt(typography) -> str` (string kosong bila semua Auto), parameter `typography` pada `get_smart_messages(...)` dan `generate_smart_presentation(...)`.

- [ ] **Step 1: Tulis tes yang gagal**

```python
# servers/fastapi/tests/unit/test_typography_prompt.py
from models.typography import TypographyConfig
from utils.llm_calls.typography_prompt import build_typography_prompt


def test_auto_typography_produces_no_prompt_block():
    assert build_typography_prompt(None) == ""
    assert build_typography_prompt(TypographyConfig()) == ""


def test_prompt_lists_only_filled_roles_and_requires_markers():
    prompt = build_typography_prompt(
        TypographyConfig.model_validate(
            {"roles": {"title": {"family": "Inter", "size": 52}, "body": {"size": 18}}}
        )
    )
    assert 'title: font "Inter", 52px' in prompt
    assert "body: 18px" in prompt
    assert "subtitle" not in prompt.split("Mark every")[0]
    assert 'data-text-role="title"' in prompt
    assert 'data-decorative="true"' in prompt
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.llm_calls.typography_prompt'`

- [ ] **Step 3: Implementasi builder prompt**

```python
# servers/fastapi/utils/llm_calls/typography_prompt.py
"""Prompt block that tells Smart generation which typography roles to honour."""
from __future__ import annotations

from models.typography import ROLE_NAMES, is_auto, parse_typography


def _describe_role(role: str, config) -> str | None:
    parts = []
    if config.family:
        parts.append(f'font "{config.family}"')
    if config.size:
        parts.append(f"{config.size}px")
    if not parts:
        return None
    return f"- {role}: {', '.join(parts)}"


def build_typography_prompt(typography) -> str:
    config = parse_typography(typography)
    if config is None or is_auto(config):
        return ""

    lines = [
        _describe_role(role, getattr(config.roles, role)) for role in ROLE_NAMES
    ]
    described = [line for line in lines if line]
    if not described:
        return ""

    return (
        "\n\nTypography roles:\n"
        + "\n".join(described)
        + "\n\nMark every text container with data-text-role=\"title\" | "
        "\"subtitle\" | \"body\". Exactly one title per slide. Use subtitle only "
        "for a visible secondary heading. All remaining body copy, card text, "
        "labels, and captions use body. Never add data-text-role to decorative "
        "layers (data-decorative=\"true\").\n"
    )
```

- [ ] **Step 4: Teruskan parameter ke jalur generate Smart**

Di `generate_smart_presentation.py`, tambahkan parameter `typography=None` pada `get_smart_messages(...)` dan `generate_smart_presentation(...)`. Panduan tipografi disisipkan ke `user_prompt`, tepat setelah `SMART_DIRECT_HTML_PROMPT`:

```python
    typography_block = build_typography_prompt(typography)
```

Pada ekspresi `user_prompt`, ubah bagian berikut:

```python
        + SMART_DIRECT_HTML_PROMPT
        + f"""
```

menjadi:

```python
        + SMART_DIRECT_HTML_PROMPT
        + typography_block
        + f"""
```

(`SystemMessage` tetap memakai `SMART_DECK_SYSTEM_PROMPT` tanpa perubahan.)

Tambahkan import di bagian atas:

```python
from utils.llm_calls.typography_prompt import build_typography_prompt
```

Di `presentation.py` pada pemanggilan `generate_smart_presentation(...)` (sekitar baris 2090), tambahkan:

```python
                typography=presentation.typography,
```

Lalu tepat setelah `deck = await generation_task`, jalankan backfill (slide smart sudah di-commit oleh callback checkpoint):

```python
            deck = await generation_task
            await apply_role_markers_to_presentation(sql_session, presentation.id)
```

Tambahkan import `apply_role_markers_to_presentation` dari `services.typography_service` bersama import Task 5.

- [ ] **Step 5: Jalankan tes**

Run: `cd servers/fastapi; uv run --group dev pytest tests/unit/test_typography_prompt.py tests/unit/test_smart_presentation_generation.py -v`
Expected: semua passed (tes smart generation yang lama tetap lulus karena `typography` default `None`)

- [ ] **Step 6: Commit (setelah disetujui pengguna)**

```bash
git add servers/fastapi/utils/llm_calls/typography_prompt.py servers/fastapi/utils/llm_calls/generate_smart_presentation.py servers/fastapi/api/v1/ppt/endpoints/presentation.py servers/fastapi/tests/unit/test_typography_prompt.py
git commit -m "feat: ask smart generation to honour typography roles"
```

---

### Task 7: Utilitas tipografi frontend (merge + CSS)

**Files:**
- Create: `servers/nextjs/components/typography/effective.ts`
- Test: `servers/nextjs/tests/typography-effective.test.mjs`

**Interfaces:**
- Consumes: `cssFontFamilyStack` dari `servers/nextjs/components/slide-editor/text/css-text.ts`.
- Produces: tipe `TypographyRoleName`, `TypographyRoleConfig`, `TypographyConfig`; konstanta `TYPOGRAPHY_ROLES`; fungsi `resolveTypography(presentation?, slide?)`, `isAutoTypography(config)`, `typographyStyleCss(config)`.

- [ ] **Step 1: Tulis tes yang gagal**

```javascript
// servers/nextjs/tests/typography-effective.test.mjs
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

let typography;
let directory;

test.before(async () => {
  directory = await mkdtemp(path.join(tmpdir(), "presenton-typography-"));
  const outfile = path.join(directory, "effective.mjs");
  await build({
    entryPoints: [path.resolve("components/typography/effective.ts")],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    tsconfig: path.resolve("tsconfig.json"),
    logLevel: "silent",
  });
  typography = await import(pathToFileURL(outfile).href);
});

test.after(async () => {
  if (directory) await rm(directory, { recursive: true, force: true });
});

test("slide overrides merge per field over presentation values", () => {
  const resolved = typography.resolveTypography(
    { roles: { title: { family: "Inter", size: 52 }, body: { size: 18 } } },
    { roles: { title: { size: 40 } } },
  );
  assert.equal(resolved.roles.title.family, "Inter");
  assert.equal(resolved.roles.title.size, 40);
  assert.equal(resolved.roles.body.size, 18);
  assert.equal(resolved.roles.subtitle.size, null);
});

test("empty config is auto", () => {
  assert.equal(typography.isAutoTypography(null), true);
  assert.equal(
    typography.isAutoTypography(typography.resolveTypography(null, null)),
    true,
  );
  assert.equal(
    typography.isAutoTypography({ roles: { title: { size: 52 } } }),
    false,
  );
});

test("css only contains filled roles and uses important", () => {
  const css = typography.typographyStyleCss({
    roles: { title: { family: "Inter", size: 52 }, body: { size: 18 } },
  });
  assert.match(css, /\[data-text-role="title"\]/);
  assert.match(css, /font-size:52px !important/);
  assert.match(css, /font-size:18px !important/);
  assert.doesNotMatch(css, /data-text-role="subtitle"/);
  assert.equal(typography.typographyStyleCss(null), "");
});
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/nextjs; node --test tests/typography-effective.test.mjs`
Expected: FAIL — `Could not resolve "components/typography/effective.ts"`

- [ ] **Step 3: Implementasi**

```typescript
// servers/nextjs/components/typography/effective.ts
import { cssFontFamilyStack } from "../slide-editor/text/css-text";

export type TypographyRoleName = "title" | "subtitle" | "body";

export type TypographyRoleConfig = {
  family?: string | null;
  size?: number | null;
};

export type TypographyConfig = {
  version?: 1 | null;
  roles?: Partial<Record<TypographyRoleName, TypographyRoleConfig | null>> | null;
};

export const TYPOGRAPHY_ROLES: TypographyRoleName[] = [
  "title",
  "subtitle",
  "body",
];

const EMPTY_ROLE: TypographyRoleConfig = { family: null, size: null };

function readRole(value: unknown): TypographyRoleConfig {
  if (!value || typeof value !== "object") return EMPTY_ROLE;
  const record = value as Record<string, unknown>;
  const family =
    typeof record.family === "string" && record.family.trim()
      ? record.family.trim()
      : null;
  const size =
    typeof record.size === "number" && Number.isFinite(record.size)
      ? Math.round(record.size)
      : null;
  return { family, size };
}

export function resolveTypography(
  presentation?: TypographyConfig | null,
  slide?: TypographyConfig | null,
): TypographyConfig {
  const roles = {} as Record<TypographyRoleName, TypographyRoleConfig>;
  for (const role of TYPOGRAPHY_ROLES) {
    const base = readRole(presentation?.roles?.[role]);
    const override = readRole(slide?.roles?.[role]);
    roles[role] = {
      family: override.family ?? base.family ?? null,
      size: override.size ?? base.size ?? null,
    };
  }
  return { version: 1, roles };
}

export function isAutoTypography(config?: TypographyConfig | null): boolean {
  return TYPOGRAPHY_ROLES.every((role) => {
    const value = readRole(config?.roles?.[role]);
    return value.family === null && value.size === null;
  });
}

export function typographyStyleCss(config?: TypographyConfig | null): string {
  if (!config) return "";
  return TYPOGRAPHY_ROLES.flatMap((role) => {
    const value = readRole(config.roles?.[role]);
    const declarations: string[] = [];
    if (value.family) {
      declarations.push(
        `font-family:${cssFontFamilyStack(value.family)} !important`,
      );
    }
    if (value.size) {
      declarations.push(`font-size:${value.size}px !important`);
      declarations.push(
        `line-height:${role === "body" ? 1.35 : 1.15} !important`,
      );
    }
    if (declarations.length === 0) return [];
    return [
      `section[data-slide-type] [data-text-role="${role}"]:not([data-decorative="true"]){${declarations.join(";")}}`,
    ];
  }).join("\n");
}
```

- [ ] **Step 4: Jalankan tes sampai lulus**

Run: `cd servers/nextjs; node --test tests/typography-effective.test.mjs`
Expected: 3 passed

- [ ] **Step 5: Commit (setelah disetujui pengguna)**

```bash
git add servers/nextjs/components/typography/effective.ts servers/nextjs/tests/typography-effective.test.mjs
git commit -m "feat: add frontend typography resolution and css"
```

---

### Task 8: Terapkan tipografi pada slide Smart

**Files:**
- Modify: `servers/nextjs/app/(presentation-generator)/components/SmartHtmlSlide.tsx`
- Modify: `servers/nextjs/app/(presentation-generator)/components/SmartHtmlEditor.tsx`
- Modify: `servers/nextjs/app/(presentation-generator)/components/PresentationRender.tsx`
- Modify: `servers/nextjs/app/(presentation-generator)/presentation/components/SlideThumbnailCard.tsx`

**Interfaces:**
- Consumes: `TypographyConfig`, `typographyStyleCss` (Task 7).
- Produces: prop opsional `typography?: TypographyConfig | null` pada `SmartHtmlSlide` dan `SmartHtmlEditor`; semua tempat yang merender `SmartHtmlSlide` dalam konteks presentasi wajib meneruskannya.

- [ ] **Step 1: Tambahkan prop dan suntik CSS**

Di `SmartHtmlSlide.tsx`, ubah signature dokumen dan hook:

```typescript
import {
  typographyStyleCss,
  type TypographyConfig,
} from "@/components/typography/effective";

function previewDocument(
  html: string,
  fonts: unknown,
  typography?: TypographyConfig | null,
) {
  return `<!doctype html>
  <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=1280, initial-scale=1">
      ${fontAssets(fonts)}
      <style>${typographyStyleCss(typography)}</style>
```

Perubahannya hanya dua: tambah parameter `typography` dan satu baris `<style>${typographyStyleCss(typography)}</style>` tepat setelah `${fontAssets(fonts)}`. Sisa string dokumen tidak berubah.

Pada `useSlideFontAssets`, tambahkan parameter dan gabungkan CSS:

```typescript
function useSlideFontAssets(
  fonts: unknown,
  enabled: boolean,
  typography?: TypographyConfig | null,
) {
  useEffect(() => {
    if (!enabled) return;
    const css = [
      localFontOptionsFromUnknown(fonts).map(renderLocalFontFaceCss).join(""),
      typographyStyleCss(typography),
    ].filter(Boolean).join("\n");
    if (!css) return;
    const style = document.createElement("style");
    style.dataset.slideFontAssets = "true";
    style.textContent = css;
    document.head.appendChild(style);
    return () => style.remove();
  }, [enabled, fonts, typography]);
}
```

Tambahkan `typography` ke props `LinuxInPageSmartHtmlSlide`, `IframeSmartHtmlSlide`, dan komponen default, lalu teruskan ke `previewDocument(html, fonts, typography)` dan `useSlideFontAssets(fonts, executeScripts, typography)`.

- [ ] **Step 2: Teruskan prop dari pemanggil dalam konteks presentasi**

Nilai efektif dihitung di pemanggil dari state presentasi (`presentationGeneration.presentationData`) dan `slide.typography`, jadi tidak perlu prop drilling dari halaman.

Pola yang dipakai di setiap pemanggil:

```typescript
import { useSelector } from "react-redux";
import { resolveTypography } from "@/components/typography/effective";
import type { RootState } from "@/store/store";

const presentationTypography = useSelector(
  (state: RootState) =>
    (state.presentationGeneration.presentationData as
      | { typography?: unknown }
      | null)?.typography ?? null,
);
const effectiveTypography = resolveTypography(
  presentationTypography as Parameters<typeof resolveTypography>[0],
  (slide?.typography ?? null) as Parameters<typeof resolveTypography>[1],
);
```

Terapkan pada:

- `components/PresentationRender.tsx`: hitung `effectiveTypography` dari `slide` prop, lalu teruskan `typography={effectiveTypography}` ke `SmartHtmlSlide` dan `SmartHtmlEditor`.
- `presentation/components/SlideThumbnailCard.tsx`: teruskan `typography={effectiveTypography}` ke `SmartHtmlSlide`.
- `presentation/components/chat/chat-widgets.tsx`: teruskan `typography={effectiveTypography}` ke `SmartHtmlSlide` yang dirender di panel chat.

`V1ContentRender` tidak perlu prop baru karena menghitung tipografi sendiri (Task 9). Jangan menambahkan prop pada pemanggilan di `community/*` dan `upload/components/CommunityReferencePicker.tsx` karena tidak memiliki konfigurasi tipografi.

- [ ] **Step 3: Verifikasi kompilasi**

Run: `cd servers/nextjs; npm run lint`
Expected: tidak ada error TypeScript/ESLint pada file yang diubah

- [ ] **Step 4: Commit (setelah disetujui pengguna)**

```bash
git add "servers/nextjs/app/(presentation-generator)/components/SmartHtmlSlide.tsx" "servers/nextjs/app/(presentation-generator)/components/SmartHtmlEditor.tsx" "servers/nextjs/app/(presentation-generator)/components/PresentationRender.tsx" "servers/nextjs/app/(presentation-generator)/presentation/components/SlideThumbnailCard.tsx" "servers/nextjs/app/(presentation-generator)/presentation/components/chat/chat-widgets.tsx"
git commit -m "feat: apply role typography to smart slides"
```

---

### Task 9: Terapkan tipografi pada slide Standard/V2 dan tandai edit manual

**Files:**
- Create: `servers/nextjs/components/typography/apply-to-slide.ts`
- Modify: `servers/nextjs/components/slide-editor/types.ts` (`Font.manual`)
- Modify: `servers/nextjs/components/slide-editor/text/TextToolbar.tsx` (`updateFont`)
- Modify: `servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx` (pakai transform)
- Test: `servers/nextjs/tests/typography-apply-to-slide.test.mjs`

**Interfaces:**
- Consumes: `TypographyConfig`, `resolveTypography` (Task 7).
- Produces: `applyTypographyToSlide(layout, config)`; flag `Font.manual?: boolean | null`.

- [ ] **Step 1: Tulis tes yang gagal**

```javascript
// servers/nextjs/tests/typography-apply-to-slide.test.mjs
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { pathToFileURL } from "node:url";

import { build } from "esbuild";

let module_;
let directory;

test.before(async () => {
  directory = await mkdtemp(path.join(tmpdir(), "presenton-apply-"));
  const outfile = path.join(directory, "apply.mjs");
  await build({
    entryPoints: [path.resolve("components/typography/apply-to-slide.ts")],
    outfile,
    bundle: true,
    platform: "node",
    format: "esm",
    tsconfig: path.resolve("tsconfig.json"),
    logLevel: "silent",
  });
  module_ = await import(pathToFileURL(outfile).href);
});

test.after(async () => {
  if (directory) await rm(directory, { recursive: true, force: true });
});

function layout() {
  return {
    elements: [
      { type: "text", name: "slide_title", font: { family: "Arial", size: 48 } },
      { type: "text", name: "slide_subtitle", font: { family: "Arial", size: 32 } },
      { type: "text", name: "body_copy", font: { family: "Arial", size: 18 } },
      { type: "image", name: "hero", font: { size: 999 } },
    ],
  };
}

test("assigns roles by size and overrides family and size", () => {
  const result = module_.applyTypographyToSlide(layout(), {
    roles: { title: { family: "Inter", size: 52 }, body: { size: 16 } },
  });
  assert.equal(result.elements[0].font.family, "Inter");
  assert.equal(result.elements[0].font.size, 52);
  assert.equal(result.elements[1].font.size, 32);
  assert.equal(result.elements[2].font.size, 16);
  assert.equal(result.elements[3].font.size, 999);
});

test("manual fonts are never overridden", () => {
  const input = layout();
  input.elements[0].font.manual = true;
  const result = module_.applyTypographyToSlide(input, {
    roles: { title: { family: "Inter", size: 52 } },
  });
  assert.equal(result.elements[0].font.family, "Arial");
  assert.equal(result.elements[0].font.size, 48);
});

test("label-like elements never become title", () => {
  const input = {
    elements: [
      { type: "text", name: "footer_label", font: { size: 60 } },
      { type: "text", name: "heading", font: { size: 40 } },
    ],
  };
  const result = module_.applyTypographyToSlide(input, {
    roles: { title: { size: 52 } },
  });
  assert.equal(result.elements[0].font.size, 60);
  assert.equal(result.elements[1].font.size, 52);
});

test("run sizes scale with the base size change", () => {
  const input = {
    elements: [
      {
        type: "text",
        name: "heading",
        font: { size: 40 },
        runs: [{ font: { size: 20 } }],
      },
    ],
  };
  const result = module_.applyTypographyToSlide(input, {
    roles: { title: { size: 80 } },
  });
  assert.equal(result.elements[0].font.size, 80);
  assert.equal(result.elements[0].runs[0].font.size, 40);
});
```

- [ ] **Step 2: Jalankan dan pastikan gagal**

Run: `cd servers/nextjs; node --test tests/typography-apply-to-slide.test.mjs`
Expected: FAIL — `Could not resolve "components/typography/apply-to-slide.ts"`

- [ ] **Step 3: Implementasi transformasi**

```typescript
// servers/nextjs/components/typography/apply-to-slide.ts
import type {
  TypographyConfig,
  TypographyRoleConfig,
  TypographyRoleName,
} from "./effective";

type FontLike = {
  family?: string | null;
  size?: number | null;
  manual?: boolean | null;
};

type SlideNode = {
  type?: string;
  name?: string;
  id?: string;
  font?: FontLike;
  runs?: Array<{ font?: FontLike }>;
  elements?: SlideNode[];
};

const EXCLUDED_ROLE_NAME = /(footer|page[_-]?number|badge|caption|label|kicker)/i;

function collectTextNodes(node: SlideNode, output: SlideNode[]): void {
  if (!node || typeof node !== "object") return;
  if (Array.isArray(node.elements)) {
    for (const child of node.elements) collectTextNodes(child, output);
  }
  if (
    typeof node.type === "string" &&
    node.type.includes("text") &&
    node.font != null
  ) {
    output.push(node);
  }
}

function applyRole(node: SlideNode, config: TypographyRoleConfig): void {
  const previousSize = node.font?.size ?? null;
  if (config.size != null) {
    node.font = { ...node.font, size: config.size };
  }
  if (config.family) {
    node.font = { ...node.font, family: config.family };
  }
  if (config.size != null && previousSize) {
    const ratio = config.size / previousSize;
    node.runs = node.runs?.map((run) =>
      run.font?.size
        ? { ...run, font: { ...run.font, size: Math.round(run.font.size * ratio) } }
        : run,
    );
  }
}

export function applyTypographyToSlide<T>(
  layout: T,
  config?: TypographyConfig | null,
): T {
  if (!config) return layout;

  const clone = structuredClone(layout) as unknown as SlideNode;
  const nodes: SlideNode[] = [];
  collectTextNodes(clone, nodes);

  const editable = nodes.filter((node) => node.font?.manual !== true);
  if (editable.length === 0) return clone as unknown as T;

  const candidates = editable.filter(
    (node) => !EXCLUDED_ROLE_NAME.test(`${node.name ?? ""} ${node.id ?? ""}`),
  );
  const ranked = [...candidates].sort(
    (a, b) => (b.font?.size ?? 0) - (a.font?.size ?? 0),
  );
  const title = ranked[0];
  const titleSize = title?.font?.size ?? 0;
  const subtitle = ranked.find(
    (node) =>
      node !== title &&
      titleSize > 0 &&
      (node.font?.size ?? 0) < titleSize &&
      (node.font?.size ?? 0) >= titleSize * 0.6,
  );

  const assignments = new Map<SlideNode, TypographyRoleName>();
  if (title) assignments.set(title, "title");
  if (subtitle) assignments.set(subtitle, "subtitle");
  for (const node of editable) {
    if (!assignments.has(node)) assignments.set(node, "body");
  }

  for (const [node, role] of assignments) {
    const roleConfig = config.roles?.[role];
    if (roleConfig) applyRole(node, roleConfig);
  }

  return clone as unknown as T;
}
```

- [ ] **Step 4: Tambahkan flag manual pada tipe Font**

Di `servers/nextjs/components/slide-editor/types.ts`, tambahkan ke `export type Font = { ... }`:

```typescript
  /** Set when a user edits this element directly; role typography must not override it. */
  manual?: boolean | null;
```

- [ ] **Step 5: Tandai edit manual di toolbar**

Di `TextToolbar.tsx`, ganti `updateFont` menjadi:

```typescript
  const updateFont = (fontPatch: Partial<Font>) => {
    const marksManual = Object.keys(fontPatch).some((key) =>
      ["family", "size", "bold", "italic", "underline", "color"].includes(key),
    );
    const nextPatch = marksManual ? { ...fontPatch, manual: true } : fontPatch;
    onChange(
      index,
      activeSelectionRange
        ? mergeFontForTextSelection(element, activeSelectionRange, nextPatch)
        : mergeFont(element, nextPatch),
    );
  };
```

- [ ] **Step 6: Pakai transformasi di renderer bersama slide template**

`V1ContentRender` adalah satu-satunya renderer slide template/V2 (dipakai `PresentationRender` untuk editor dan mode present, serta `SlideThumbnailCard` untuk thumbnail), sehingga transformasi dipasang di satu tempat itu.

Di `servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx`, tambahkan import:

```typescript
import { useSelector } from "react-redux";
import { resolveTypography } from "@/components/typography/effective";
import { applyTypographyToSlide } from "@/components/typography/apply-to-slide";
import type { RootState } from "@/store/store";
```

Di dalam komponen, sebelum blok `if (isBlankSlide) { ... }`, tambahkan `useSelector` lalu pindahkan perhitungan layout ke atas early return agar urutan hook tetap stabil:

```typescript
    const presentationTypography = useSelector(
        (state: RootState) =>
            (state.presentationGeneration.presentationData as
                | { typography?: unknown }
                | null
            )?.typography ?? null
    );

    const baseLayout = templateV2Layout ??
        (isBlankSlide ? BLANK_TEMPLATE_V2_LAYOUT : null);

    const typographyConfig = useMemo(
        () =>
            resolveTypography(
                presentationTypography as Parameters<typeof resolveTypography>[0],
                (safeSlide.typography ?? null) as Parameters<typeof resolveTypography>[1]
            ),
        [presentationTypography, safeSlide.typography]
    );

    const typographyLayout = useMemo(
        () => applyTypographyToSlide(baseLayout, typographyConfig),
        [baseLayout, typographyConfig]
    );

    if (isBlankSlide && !isTemplateV2Slide) {
        return <div className="h-full w-full bg-white" />;
    }
```

Hapus blok `if (isBlankSlide) { if (!isTemplateV2Slide) { return <div .../>; } }` dan `const directLayout = ...` yang lama, lalu ganti semua pemakaian `directLayout` menjadi `typographyLayout`. Ada dua tempat yang harus diganti, keduanya menjadi:

```typescript
layout={typographyLayout ?? BLANK_TEMPLATE_V2_LAYOUT}
```

- [ ] **Step 7: Jalankan tes**

Run: `cd servers/nextjs; node --test tests/typography-apply-to-slide.test.mjs tests/typography-effective.test.mjs`
Expected: semua passed

Run: `cd servers/nextjs; npm run lint`
Expected: tidak ada error

- [ ] **Step 8: Commit (setelah disetujui pengguna)**

```bash
git add servers/nextjs/components/typography/apply-to-slide.ts servers/nextjs/components/slide-editor/types.ts servers/nextjs/components/slide-editor/text/TextToolbar.tsx "servers/nextjs/app/(presentation-generator)/components/V1ContentRender.tsx" servers/nextjs/tests/typography-apply-to-slide.test.mjs
git commit -m "feat: apply role typography to layout slides"
```

---

### Task 10: Komponen panel tipografi dan layanan API frontend

**Files:**
- Create: `servers/nextjs/app/(presentation-generator)/typography/components/TypographyEditor.tsx`
- Create: `servers/nextjs/app/(presentation-generator)/services/api/typography.ts`

**Interfaces:**
- Consumes: `resolveTypography`, `TypographyConfig`, `TYPOGRAPHY_ROLES` (Task 7), `LOCAL_FONT_OPTIONS` dan `localFontOptionForFamily` dari `@/components/slide-editor/text/local-fonts`.
- Produces: `TypographyEditor` (props: `value`, `onChange`, `templateFonts`, `scope`, `onFontResolved`, `resolveGoogleFont`), `TypographyService.resolveGoogleFont(family)`, `TypographyService.updatePresentationTypography(id, payload)`.
- Setiap family yang dipilih wajib menghasilkan entri di `fonts` (dikirim lewat `onFontResolved`), sehingga backend lolos validasi `ensure_fonts_resolved`.

- [ ] **Step 1: Tulis layanan API**

```typescript
// servers/nextjs/app/(presentation-generator)/services/api/typography.ts
import { getApiUrl } from "@/utils/api";
import type { TypographyConfig } from "@/components/typography/effective";
import { getHeader } from "./header";

export type GoogleFontFace = { weight: number; style: string; url: string };
export type GoogleFontResponse = {
  family: string;
  url: string;
  faces: GoogleFontFace[];
};

export class TypographyService {
  static async resolveGoogleFont(
    family: string,
  ): Promise<GoogleFontResponse> {
    const response = await fetch(getApiUrl("/api/v1/ppt/fonts/google"), {
      method: "POST",
      headers: getHeader(),
      body: JSON.stringify({ family }),
      cache: "no-cache",
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Gagal memuat Google Font");
    }
    return (await response.json()) as GoogleFontResponse;
  }

  static async updatePresentationTypography(
    presentationId: string,
    payload: {
      typography?: TypographyConfig | null;
      fonts?: Record<string, string>;
    },
  ): Promise<void> {
    const response = await fetch(
      getApiUrl(`/api/v1/ppt/presentation/${presentationId}/typography`),
      {
        method: "PATCH",
        headers: getHeader(),
        body: JSON.stringify(payload),
        cache: "no-cache",
      },
    );
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Gagal menyimpan tipografi");
    }
  }
}
```

- [ ] **Step 2: Tulis komponen panel**

```tsx
// servers/nextjs/app/(presentation-generator)/typography/components/TypographyEditor.tsx
"use client";

import { useMemo, useState } from "react";

import { LOCAL_FONT_OPTIONS, localFontOptionForFamily } from "@/components/slide-editor/text/local-fonts";
import {
  TYPOGRAPHY_ROLES,
  resolveTypography,
  type TypographyConfig,
  type TypographyRoleName,
} from "@/components/typography/effective";

const ROLE_LABELS: Record<TypographyRoleName, string> = {
  title: "Judul",
  subtitle: "Sub Judul",
  body: "Deskripsi",
};

const SIZE_HINTS: Record<TypographyRoleName, number> = {
  title: 96,
  subtitle: 60,
  body: 32,
};

type TypographyEditorProps = {
  value: TypographyConfig | null;
  onChange: (value: TypographyConfig) => void;
  templateFonts?: string[];
  scope?: "presentation" | "slide";
  onFontResolved?: (family: string, url: string) => void;
  resolveGoogleFont?: (
    family: string,
  ) => Promise<{ family: string; url: string }>;
};

export default function TypographyEditor({
  value,
  onChange,
  templateFonts = [],
  scope = "presentation",
  onFontResolved,
  resolveGoogleFont,
}: TypographyEditorProps) {
  const resolved = useMemo(() => resolveTypography(value, null), [value]);
  const [googleFamily, setGoogleFamily] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const families = useMemo(() => {
    const local = LOCAL_FONT_OPTIONS.map((option) => option.family);
    return Array.from(new Set([...templateFonts, ...local])).sort();
  }, [templateFonts]);

  const updateRole = (
    role: TypographyRoleName,
    patch: { family?: string | null; size?: number | null },
  ) => {
    onChange({
      version: 1,
      roles: {
        ...resolved.roles,
        [role]: { ...resolved.roles[role], ...patch },
      },
    });
  };

  const handleFamilyChange = (role: TypographyRoleName, family: string) => {
    const nextFamily = family.trim() || null;
    if (nextFamily) {
      const localOption = localFontOptionForFamily(nextFamily);
      if (localOption) {
        onFontResolved?.(localOption.family, localOption.sourceUrl);
      }
    }
    updateRole(role, { family: nextFamily });
  };

  const useGoogleFont = async () => {
    if (!resolveGoogleFont || !googleFamily.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const font = await resolveGoogleFont(googleFamily.trim());
      onFontResolved?.(font.family, font.url);
      updateRole("title", { family: font.family });
      setGoogleFamily("");
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : "Gagal memuat font");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-xs text-[#6B7280]">
        {scope === "slide"
          ? "Berlaku untuk slide ini. Field kosong mengikuti pengaturan presentasi."
          : "Berlaku untuk seluruh presentasi."}
      </p>

      {TYPOGRAPHY_ROLES.map((role) => {
        const config = resolved.roles[role];
        const sizeTooLarge = (config.size ?? 0) > SIZE_HINTS[role];
        return (
          <div key={role} className="grid grid-cols-[110px_1fr_120px] items-center gap-3">
            <span className="text-sm font-medium">{ROLE_LABELS[role]}</span>

            <select
              className="h-9 rounded-md border border-[#E6E6EC] px-2 text-sm"
              value={config.family ?? ""}
              onChange={(event) => handleFamilyChange(role, event.target.value)}
            >
              <option value="">Auto</option>
              {families.map((family) => (
                <option key={family} value={family}>
                  {family}
                </option>
              ))}
            </select>

            <input
              aria-label={`Ukuran ${ROLE_LABELS[role]}`}
              className="h-9 rounded-md border border-[#E6E6EC] px-2 text-sm"
              placeholder="Auto"
              inputMode="numeric"
              value={config.size ?? ""}
              onChange={(event) => {
                const raw = event.target.value.trim();
                if (!raw) {
                  updateRole(role, { size: null });
                  return;
                }
                const next = Number(raw);
                if (!Number.isFinite(next)) return;
                if (next < 8 || next > 200) {
                  setError("Ukuran font harus antara 8 dan 200 px");
                  return;
                }
                setError(null);
                updateRole(role, { size: Math.round(next) });
              }}
            />

            {sizeTooLarge ? (
              <span className="col-span-3 text-xs text-amber-600">
                Ukuran {ROLE_LABELS[role]} cukup besar; periksa hasil export.
              </span>
            ) : null}
          </div>
        );
      })}

      {resolveGoogleFont ? (
        <div className="flex items-center gap-2">
          <input
            className="h-9 flex-1 rounded-md border border-[#E6E6EC] px-2 text-sm"
            placeholder="Cari Google Fonts (mis. Playfair Display)"
            value={googleFamily}
            onChange={(event) => setGoogleFamily(event.target.value)}
          />
          <button
            type="button"
            className="h-9 rounded-md bg-[#111827] px-3 text-sm text-white disabled:opacity-50"
            disabled={busy || !googleFamily.trim()}
            onClick={useGoogleFont}
          >
            {busy ? "Memuat..." : "Gunakan"}
          </button>
        </div>
      ) : null}

      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
```

- [ ] **Step 3: Verifikasi kompilasi**

Run: `cd servers/nextjs; npm run lint`
Expected: tidak ada error pada dua file baru

- [ ] **Step 4: Commit (setelah disetujui pengguna)**

```bash
git add "servers/nextjs/app/(presentation-generator)/typography/components/TypographyEditor.tsx" "servers/nextjs/app/(presentation-generator)/services/api/typography.ts"
git commit -m "feat: add typography editor panel"
```

---

### Task 11: Sambungkan panel ke halaman upload dan editor presentasi

**Files:**
- Modify: `servers/nextjs/app/(presentation-generator)/upload/type.ts` (`PresentationConfig`)
- Modify: `servers/nextjs/app/(presentation-generator)/upload/components/ConfigurationSelects.tsx`
- Modify: `servers/nextjs/app/(presentation-generator)/services/api/presentation-generation.ts` (`createPresentation`)
- Modify: `servers/nextjs/app/(presentation-generator)/upload/UploadPage.tsx` (config default + payload)
- Modify: `servers/nextjs/app/(presentation-generator)/presentation/components/PresentationHeader.tsx` (tombol)
- Modify: `servers/nextjs/app/(presentation-generator)/presentation/components/PresentationPage.tsx` (state + dialog)
- Modify: `servers/nextjs/app/(presentation-generator)/types/slide.ts` (`Slide.typography`)

**Interfaces:**
- Consumes: `TypographyEditor` (Task 10), `TypographyService` (Task 10), `resolveTypography` (Task 7).
- Produces: `PresentationConfig.typography` dan `PresentationConfig.fonts`; tombol "Tipografi" pada header editor presentasi yang menulis lewat `PATCH /presentation/{id}/typography` (global) atau `slide_update` (per slide).

- [ ] **Step 1: Perluas tipe konfigurasi upload**

```typescript
// servers/nextjs/app/(presentation-generator)/upload/type.ts
import type { TypographyConfig } from "@/components/typography/effective";

export interface PresentationConfig {
  slides: string | null;
  language: LanguageType | null;
  prompt: string;
  tone: ToneType;
  verbosity: VerbosityType;
  instructions: string;
  includeTableOfContents: boolean;
  includeTitleSlide: boolean;
  webSearch: boolean;
  typography: TypographyConfig | null;
  fonts: Record<string, string>;
}
```

Pada objek config default di `UploadPage.tsx`, tambahkan:

```typescript
  typography: null,
  fonts: {},
```

- [ ] **Step 2: Kirim pada request create**

Di `presentation-generation.ts` (`createPresentation`), tambahkan parameter destructuring, tipe, dan body:

```typescript
    typography,
    fonts,
```

```typescript
    typography?: TypographyConfig | null;
    fonts?: Record<string, string>;
```

```typescript
            typography,
            fonts,
```

Tambahkan import di atas file:

```typescript
import type { TypographyConfig } from "@/components/typography/effective";
```

- [ ] **Step 3: Tampilkan panel di halaman upload**

Di `ConfigurationSelects.tsx`, tambahkan import:

```typescript
import TypographyEditor from "../../typography/components/TypographyEditor";
import { TypographyService } from "../../services/api/typography";
```

Tambahkan blok UI di dalam grup pengaturan (setelah kontrol bahasa):

```tsx
<div className="space-y-2">
  <p className="text-sm font-medium">Tipografi</p>
  <TypographyEditor
    scope="presentation"
    value={config.typography}
    templateFonts={[]}
    onChange={(typography) => onConfigChange("typography", typography)}
    resolveGoogleFont={TypographyService.resolveGoogleFont}
    onFontResolved={(family, url) =>
      onConfigChange("fonts", { ...config.fonts, [family]: url })
    }
  />
</div>
```

- [ ] **Step 4: Tambahkan tombol di header dan dialog di editor presentasi**

Di `servers/nextjs/app/(presentation-generator)/types/slide.ts`, tambahkan field pada `interface Slide`:

```typescript
  typography?: import("@/components/typography/effective").TypographyConfig | null;
```

Di `PresentationHeader.tsx`, tambahkan prop `onOpenTypography` pada signature (di samping `generationMode`):

```typescript
const PresentationHeader = ({
  presentation_id,
  isPresentationSaving,
  currentSlide,
  generationMode = "standard",
  onOpenTypography,
}: {
  presentation_id: string;
  isPresentationSaving: boolean;
  currentSlide?: number;
  generationMode?: "standard" | "smart";
  onOpenTypography?: () => void;
}) => {
```

Lalu render tombolnya di baris aksi header, di sebelah tombol ekspor yang sudah ada:

```tsx
        {onOpenTypography ? (
          <button
            type="button"
            className="h-9 rounded-md border border-[#E6E6EC] bg-white px-3 text-sm"
            onClick={onOpenTypography}
          >
            Tipografi
          </button>
        ) : null}
```

Di `PresentationPage.tsx`, tambahkan import:

```tsx
import Modal from "./Modal";
import TypographyEditor from "../../typography/components/TypographyEditor";
import { TypographyService } from "../../services/api/typography";
import { PresentationGenerationApi } from "../../services/api/presentation-generation";
import type { TypographyConfig } from "@/components/typography/effective";
```

Tambahkan state, nilai turunan, dan handler (di dalam komponen, setelah state yang sudah ada):

```tsx
const [typographyOpen, setTypographyOpen] = useState(false);
const [typographyScope, setTypographyScope] = useState<"presentation" | "slide">(
  "presentation",
);
const [typographyDraft, setTypographyDraft] = useState<TypographyConfig | null>(
  null,
);
const [fontsDraft, setFontsDraft] = useState<Record<string, string>>({});

const activeSlide = presentationData?.slides?.[selectedSlide] ?? null;
const savedFonts = (presentationData?.fonts ?? {}) as Record<string, string>;

const openTypography = () => {
  setTypographyScope("presentation");
  setFontsDraft({});
  setTypographyDraft(
    ((presentationData as { typography?: TypographyConfig } | null)?.typography ??
      null),
  );
  setTypographyOpen(true);
};

const selectTypographyScope = (scope: "presentation" | "slide") => {
  setTypographyScope(scope);
  setTypographyDraft(
    scope === "presentation"
      ? ((presentationData as { typography?: TypographyConfig } | null)?.typography ??
          null)
      : ((activeSlide?.typography as TypographyConfig | null | undefined) ?? null),
  );
};

const saveTypography = async () => {
  if (!presentationData) return;
  const mergedFonts = { ...savedFonts, ...fontsDraft };
  if (typographyScope === "presentation") {
    await TypographyService.updatePresentationTypography(presentationData.id, {
      typography: typographyDraft,
      fonts: mergedFonts,
    });
  } else {
    if (Object.keys(fontsDraft).length > 0) {
      await TypographyService.updatePresentationTypography(presentationData.id, {
        fonts: fontsDraft,
      });
    }
    if (activeSlide?.id) {
      await PresentationGenerationApi.updatePresentationSlide({
        ...activeSlide,
        typography: typographyDraft,
      });
    }
  }
  await fetchUserSlides({ clearHistory: false });
  setTypographyOpen(false);
};
```

Render dialog dan teruskan `onOpenTypography` ke header:

```tsx
        <PresentationHeader
          presentation_id={presentation_id}
          isPresentationSaving={isSaving}
          currentSlide={selectedSlide}
          generationMode={isSmartPresentation ? "smart" : "standard"}
          onOpenTypography={openTypography}
        />
```

```tsx
      <Modal
        isOpen={typographyOpen}
        onClose={() => setTypographyOpen(false)}
        title="Tipografi"
      >
        <div className="space-y-4">
          <div className="flex gap-2">
            <button
              type="button"
              className={`h-8 rounded-md px-3 text-sm ${typographyScope === "presentation" ? "bg-[#111827] text-white" : "border border-[#E6E6EC]"}`}
              onClick={() => selectTypographyScope("presentation")}
            >
              Seluruh presentasi
            </button>
            <button
              type="button"
              className={`h-8 rounded-md px-3 text-sm ${typographyScope === "slide" ? "bg-[#111827] text-white" : "border border-[#E6E6EC]"}`}
              onClick={() => selectTypographyScope("slide")}
            >
              Slide ini
            </button>
          </div>

          <TypographyEditor
            value={typographyDraft}
            onChange={setTypographyDraft}
            scope={typographyScope}
            templateFonts={Object.keys(savedFonts)}
            resolveGoogleFont={TypographyService.resolveGoogleFont}
            onFontResolved={(family, url) =>
              setFontsDraft((current) => ({ ...current, [family]: url }))
            }
          />

          <button
            type="button"
            className="h-9 w-full rounded-md bg-[#111827] text-sm text-white"
            onClick={() => void saveTypography()}
          >
            Simpan
          </button>
        </div>
      </Modal>
```

Cakupan per slide dipilih lewat switch di dalam dialog yang sama (tidak perlu mengubah `SlideActionBar`). Saat slide aktif adalah slide Smart, penyimpanan per slide tetap lewat `slide_update` sehingga backfill penanda peran berjalan di backend (Task 5 Step 5).

- [ ] **Step 5: Verifikasi build**

Run: `cd servers/nextjs; npm run lint`
Expected: tidak ada error

Run: `cd servers/nextjs; npm run build`
Expected: build sukses

- [ ] **Step 6: Commit (setelah disetujui pengguna)**

```bash
git add "servers/nextjs/app/(presentation-generator)/upload/type.ts" "servers/nextjs/app/(presentation-generator)/upload/components/ConfigurationSelects.tsx" "servers/nextjs/app/(presentation-generator)/services/api/presentation-generation.ts" "servers/nextjs/app/(presentation-generator)/upload/UploadPage.tsx" "servers/nextjs/app/(presentation-generator)/presentation/components/PresentationHeader.tsx" "servers/nextjs/app/(presentation-generator)/presentation/components/PresentationPage.tsx" "servers/nextjs/app/(presentation-generator)/types/slide.ts"
git commit -m "feat: wire typography controls into upload and editor"
```

---

## Verifikasi Akhir

- [ ] Backend: `cd servers/fastapi; uv run --group dev pytest tests/unit -q` — tidak ada kegagalan.
- [ ] Frontend: `cd servers/nextjs; node --test tests/typography-effective.test.mjs tests/typography-apply-to-slide.test.mjs` — semua lulus.
- [ ] Frontend: `cd servers/nextjs; npm run lint` dan `npm run build` — sukses.
- [ ] Image: `docker compose up -d --build production` lalu `docker compose logs --tail=60 production` — `Migrations run successfully`, tidak ada error.
- [ ] Migrasi: `docker compose exec -T -w /app/servers/fastapi production /opt/venv/bin/python -m alembic heads` — hanya satu head (`a1c4e7b9d2f5`).
- [ ] Regresi bahasa: dropdown bahasa masih menampilkan "Indonesian (Bahasa Indonesia)".
- [ ] Paritas: buat presentasi Smart dengan Judul 52 px / Inter, lalu bandingkan ukuran judul pada preview dan PDF hasil export; keduanya harus sama.
- [ ] Auto: presentasi tanpa tipografi tidak berubah tampilannya dibanding sebelum perubahan.

## Catatan Pelaksanaan

- Tes frontend dijalankan dari direktori `servers/nextjs` karena `esbuild` dan `tsconfig.json` diresolusi relatif terhadap cwd.
- Jika `mergeFont`/`mergeFontForTextSelection` ternyata tidak meneruskan field `manual`, tambahkan penyebaran patch (`{ ...font, ...patch }`) pada fungsi tersebut di `components/slide-editor/text/merge-font.ts` sebelum melanjutkan Task 9.
- Ownership presentasi ditangani middleware yang sudah ada; tidak ada tes owner baru yang diperlukan pada endpoint tipografi.
- Semua commit ditunda sampai pengguna menyetujui.
