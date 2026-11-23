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
