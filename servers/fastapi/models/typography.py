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
