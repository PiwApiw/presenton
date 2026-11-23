---
kind: frontend_style
name: 'Next.js Frontend Styling: Tailwind + shadcn/ui + CSS Variables Theme'
category: frontend_style
scope:
    - '**'
source_files:
    - servers/nextjs/tailwind.config.ts
    - servers/nextjs/app/globals.css
    - servers/nextjs/components.json
    - servers/nextjs/postcss.config.mjs
    - servers/nextjs/package.json
    - servers/nextjs/components/ui/button.tsx
    - servers/nextjs/components/ui/dialog.tsx
    - servers/nextjs/components/ui/select.tsx
    - servers/nextjs/components/ui/chart.tsx
---

## System Overview

The frontend lives in `servers/nextjs` (a Next.js 16 app) and uses a **Tailwind CSS v3** pipeline with **shadcn/ui** (New York style, base color `zinc`) as the component foundation. Visual identity is driven by **CSS custom properties** (HSL values) defined in `app/globals.css`, with dark mode toggled via the `.dark` class selector.

### Core Stack
- **Framework**: Next.js 16.2.6 (App Router)
- **Styling**: Tailwind CSS 3.4 (`postcss.config.mjs` only wires `tailwindcss`; no PostCSS plugins beyond that)
- **Component library**: shadcn/ui configured via `components.json` (`style: "new-york"`, `baseColor: "zinc"`, `cssVariables: true`, RSC enabled)
- **Theming**: `next-themes` for light/dark toggle; CSS variables under `:root` and `.dark`
- **Animation**: `tailwindcss-animate` plugin + Radix UI primitives
- **Typography**: `@tailwindcss/typography` (`prose prose-slate`), plus two self-hosted fonts — Manrope and Syne
- **Icons**: `lucide-react` + `@radix-ui/react-icons`
- **State/UI helpers**: `class-variance-authority`, `clsx`, `tailwind-merge` (standard shadcn pattern)

## Key Files

| File | Role |
|---|---|
| `servers/nextjs/tailwind.config.ts` | Extends Tailwind theme with HSL-based color tokens, border radii, keyframes/animations, and font families (`syne`, `manrope`) |
| `servers/nextjs/app/globals.css` | Root CSS: `@font-face` declarations, CSS variable design tokens (light/dark palettes), global animations, markdown/prose overrides, print styles, scrollbar customization |
| `servers/nextjs/components.json` | shadcn/ui configuration (schema URL, New York style, RSC, aliases `@/components`, `@/components/ui`, `@/lib/utils`) |
| `servers/nextjs/postcss.config.mjs` | Minimal PostCSS config — only `tailwindcss` plugin |
| `servers/nextjs/package.json` | Declares all styling dependencies (`tailwindcss`, `tailwindcss-animate`, `@tailwindcss/typography`, `next-themes`, `sonner`, `recharts`, etc.) |
| `servers/nextjs/components/ui/*.tsx` | ~30 shadcn-generated primitive components (button, dialog, select, table, chart, sonner, skeleton, etc.) |

## Architecture & Conventions

### Design Tokens via CSS Variables
All colors are exposed as HSL variables on `:root` and `.dark`:
- Semantic tokens: `--background`, `--foreground`, `--card`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--chart-1..5`
- Spacing/radius token: `--radius` (0.5rem), extended in Tailwind as `lg`, `md`, `sm` via `calc(var(--radius) - Npx)`
- Font tokens: `--font-syne`, `--font-manrope` mapped to Tailwind's `fontFamily.syne` / `fontFamily.manrope`

Components reference these via `hsl(var(--token))` in `tailwind.config.ts`, so changing a single CSS variable re-themes the entire app.

### Dark Mode Strategy
- `tailwind.config.ts` sets `darkMode: ["class"]` — dark mode is activated by adding the `.dark` class to `<html>` or `<body>` (managed by `next-themes`).
- No `prefers-color-scheme` media query is used; it is opt-in via the class.

### Component Library Pattern
- Primitive UI components live in `components/ui/` and follow the shadcn convention of using `class-variance-authority` + `twMerge` for variant-driven classes.
- Components wrap Radix UI primitives (`@radix-ui/react-*`) and expose Tailwind utility classes rather than custom CSS.
- The `components.json` alias `ui` maps to `@/components/ui`, so imports look like `import { Button } from "@/components/ui/button"`.

### Typography
- Base body font is `Manrope` (with Syne fallback); both are loaded via `@font-face` in `globals.css` from `/vendor/fonts/...`.
- Markdown content uses `@tailwindcss/typography` with the `prose-slate` preset, overridden in `globals.css` for editor-specific heading sizes.

### Animations
- Global keyframes in `globals.css`: typing effect, blinking cursor, activity-dot-flow, slideUp/slideDown, rippleEffect, slideEditDiagonalGlare, generating-slides-background orbit, presenton splash surface/wordmark reveal.
- Tailwind animation extension adds `accordion-down` / `accordion-up` (Radix accordion integration).
- `prefers-reduced-motion` media queries disable animations for accessibility.

### Responsive Strategy
- No custom breakpoints or container queries in `tailwind.config.ts`; relies on Tailwind's default responsive prefixes (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`).
- Print styles in `globals.css` use `@media print` to force color-adjust and strip backdrop-blur for PDF export.

### Custom Scrollbars
- `custom_scrollbar` class provides a thin 6px scrollbar with rounded thumb and track, styled for WebKit and Firefox (`scrollbar-width: thin`, `scrollbar-color`).

## Conventions Observed

- **Colors are never hardcoded as hex in component JSX**; they go through Tailwind utilities derived from CSS variables (e.g. `bg-background`, `text-primary`). Hardcoded colors appear only in `globals.css` for low-level browser defaults (selection color, number input spinners, scrollbar thumb).
- **Dark/light variants** are expressed as paired CSS variables under `:root` and `.dark`, not as separate class rules.
- **shadcn/ui components** are treated as source files (not npm packages) and live under `components/ui/`, generated via the shadcn CLI and tracked in version control.
- **Font loading** uses `font-display: swap` and loads from the Next.js `/vendor/fonts/` public path.
- **Animations** are centralized in `globals.css` as named `@keyframes` and referenced via Tailwind's `animation:` extension where appropriate.
- **Accessibility**: animations respect `prefers-reduced-motion`; focus ring uses the `--ring` token consistently.
- **Markdown rendering** goes through `prose prose-slate` with explicit overrides for editor headings and code blocks.

## Rules Enforced by Tooling

- `tailwind.config.ts` declares `darkMode: ["class"]`, so dark mode must be toggled via the `.dark` class (enforced by Tailwind).
- `components.json` pins shadcn/ui to `style: "new-york"`, `baseColor: "zinc"`, `cssVariables: true`, and RSC mode — new components added via the shadcn CLI will conform to this schema.
- `postcss.config.mjs` only enables the `tailwindcss` plugin; no other PostCSS transforms run, keeping the pipeline minimal.
- Tailwind's `content` glob in `tailwind.config.ts` scans `pages/**`, `components/**`, and `app/**` (excluding `app/privacy-policy/**`) for class usage during build, so unused classes are purged.