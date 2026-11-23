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
