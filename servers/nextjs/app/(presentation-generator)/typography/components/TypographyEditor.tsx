"use client";

import { useMemo, useState } from "react";

import {
  LOCAL_FONT_OPTIONS,
  localFontOptionForFamily,
} from "@/components/slide-editor/text/local-fonts";
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
  // Size inputs need a free-form draft: rejecting out-of-range keystrokes would
  // block typing values whose first digit is below 8 (12, 16, 20, ...).
  const [sizeDrafts, setSizeDrafts] = useState<
    Partial<Record<TypographyRoleName, string>>
  >({});

  const families = useMemo(() => {
    const local = LOCAL_FONT_OPTIONS.map((option) => option.family);
    // Keep stored families (for example a resolved Google Font) selectable so
    // the <select> shows the current value instead of falling back to Auto.
    const selected = TYPOGRAPHY_ROLES.map(
      (role) => resolved.roles[role].family,
    ).filter((family): family is string => Boolean(family));
    return Array.from(new Set([...templateFonts, ...local, ...selected])).sort();
  }, [resolved, templateFonts]);

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
      const emptyRoles = TYPOGRAPHY_ROLES.filter(
        (role) => !resolved.roles[role].family,
      );
      const targets: TypographyRoleName[] =
        emptyRoles.length > 0 ? emptyRoles : ["title"];
      const roles = { ...resolved.roles };
      targets.forEach((role) => {
        roles[role] = { ...roles[role], family: font.family };
      });
      onChange({ version: 1, roles });
      setGoogleFamily("");
    } catch (exception) {
      setError(
        exception instanceof Error ? exception.message : "Gagal memuat font",
      );
    } finally {
      setBusy(false);
    }
  };

  const handleSizeChange = (role: TypographyRoleName, raw: string) => {
    setSizeDrafts((current) => ({ ...current, [role]: raw }));
    const trimmed = raw.trim();
    if (!trimmed) {
      setError(null);
      updateRole(role, { size: null });
      return;
    }
    const next = Number(trimmed);
    if (!Number.isFinite(next)) return;
    if (next < 8 || next > 200) {
      setError("Ukuran font harus antara 8 dan 200 px");
      return;
    }
    setError(null);
    updateRole(role, { size: Math.round(next) });
  };

  const handleSizeBlur = (role: TypographyRoleName) => {
    const draft = sizeDrafts[role];
    if (draft === undefined) return;
    const trimmed = draft.trim();
    const next = Number(trimmed);
    if (!trimmed || !Number.isFinite(next) || next < 8 || next > 200) {
      setError(
        trimmed ? "Ukuran font harus antara 8 dan 200 px" : null,
      );
    }
    setSizeDrafts((current) => {
      const rest = { ...current };
      delete rest[role];
      return rest;
    });
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
          <div
            key={role}
            className="grid grid-cols-[110px_1fr_120px] items-center gap-3"
          >
            <span className="text-sm font-medium">{ROLE_LABELS[role]}</span>

            <select
              aria-label={`Font ${ROLE_LABELS[role]}`}
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
              value={sizeDrafts[role] ?? config.size ?? ""}
              onChange={(event) => handleSizeChange(role, event.target.value)}
              onBlur={() => handleSizeBlur(role)}
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
            aria-label="Cari Google Fonts"
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