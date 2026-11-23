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
