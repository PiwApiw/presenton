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

/** A config where every role is present and normalised. */
export type ResolvedTypography = {
  version: 1;
  roles: Record<TypographyRoleName, TypographyRoleConfig>;
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
): ResolvedTypography {
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

/**
 * Prefix every rule of a stylesheet with a container selector. The role CSS is
 * unscoped by design (an iframe or a single-slide document needs no prefix),
 * but documents that paint several slides side by side must scope it or the
 * last mounted slide wins for every role.
 */
export function scopeTypographyCss(css: string, scopeSelector: string): string {
  if (!css) return "";
  return css
    .split("\n")
    .map((rule) => {
      const brace = rule.indexOf("{");
      if (brace < 0) return "";
      return `${scopeSelector} ${rule.slice(0, brace)}{${rule.slice(brace + 1)}`;
    })
    .filter(Boolean)
    .join("\n");
}
