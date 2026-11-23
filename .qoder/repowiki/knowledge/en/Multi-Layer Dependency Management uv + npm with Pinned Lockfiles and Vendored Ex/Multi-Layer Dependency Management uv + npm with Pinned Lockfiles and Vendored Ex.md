---
kind: dependency_management
name: 'Multi-Layer Dependency Management: uv + npm with Pinned Lockfiles and Vendored Export Runtime'
category: dependency_management
scope:
    - '**'
source_files:
    - servers/fastapi/pyproject.toml
    - servers/fastapi/uv.lock
    - .github/workflows/test-all.yml
    - package.json
    - electron/package.json
    - servers/nextjs/package.json
    - scripts/sync-presentation-export.cjs
    - electron/scripts/sync-export-runtime.cjs
    - scripts/package-metadata.test.mjs
---

## Overview

Presenton is a monorepo that manages dependencies across three distinct layers, each using the tool best suited to its language:

1. **Python (FastAPI backend)** — managed by `uv` (Astral) with `pyproject.toml` as the manifest and `uv.lock` as the fully pinned lockfile.
2. **Node.js (Electron shell, Next.js frontend, root scripts)** — managed by `npm` with `package.json` manifests and `package-lock.json` lockfiles at both the repo root and per-package (`electron/package.json`, `servers/nextjs/package.json`).
3. **Presentation export runtime** — a separate Node package (`@presenton/export-core`) that is not installed from a registry but vendored locally via a dedicated sync script.

There is no top-level monorepo orchestrator (no `pnpm-workspace.yaml`, no `lerna`, no `nx`, no `turborepo`). Each sub-project is an independent dependency graph.

## Python Dependencies (FastAPI)

- Manifest: `servers/fastapi/pyproject.toml` declares runtime `dependencies` (e.g. `fastapi[standard]>=0.116.1`, `alembic>=1.14.0`, `openai>=1.98.0`, `mem0ai[nlp]>=0.1.115`, `llmai==0.3.15`) and dev-only `dependency-groups.dev` (`pytest`, `pytest-cov`).
- Lockfile: `servers/fastapi/uv.lock` pins every transitive dependency to exact versions and includes SHA-256 hashes for wheels/sdists; it also records `requires-python = "==3.11.*"`.
- Resolver strategy: `[tool.uv] index-strategy = "unsafe-best-match"` — this explicitly opts into uv's least-restrictive resolution order rather than the default first-found policy.
- Build system: `setuptools.build_meta` with `setuptools>=77` and `wheel`; packages are discovered under `api*`, `enums*`, `models*`, `services*`, `constants*`, `utils*`, `templates*`.
- Python version pinning: `.python-version` in `servers/fastapi` and CI `setup-python@v5` with `python-version: "3.11"` enforce the same constraint.
- No private PyPI registry or `pip.conf`/`.netrc` configuration was found; all sources resolve to `https://pypi.org/simple`.

## Node.js Dependencies (Electron + Next.js + Root)

- Root `package.json` only declares two runtime deps (`@llamaindex/liteparse`, `sharp`) plus scripts for template conversion and presentation-export syncing; its `package-lock.json` locks the full tree.
- `electron/package.json` declares Electron-specific deps (`electron-builder`, `@sentry/electron`, `tailwindcss`, `sharp`, etc.) and uses `postinstall: electron-builder install-app-deps` to rebuild native addons per platform.
- `servers/nextjs/package.json` declares the Next.js app dependencies (`next 16.2.6`, `react 19.2.6`, Radix UI, TipTap, Mermaid, etc.) and has an explicit `overrides.brace-expansion = "2.0.2"` to patch a known vulnerability in a transitive dependency.
- All three `package-lock.json` files are committed and used via `npm ci` in CI, ensuring reproducible installs.
- No `.npmrc`, no custom registry, no `--registry` flags were found — all packages come from the public npm registry.

## Vendored Presentation Export Runtime

The heavy-lifting presentation export logic lives in a separate package `@presenton/export-core` that is **not** pulled from npm during normal builds. Instead:

- The desired version is declared centrally in `package.json` as `presentationExportVersion: "v1.0.34"` and mirrored in `electron/package.json` as `exportVersion: "v1.0.34"`.
- `scripts/sync-presentation-export.cjs` reads these fields, downloads the matching archive of `@presenton/export-core`, unpacks it into a local directory, and rewrites `package.json` to depend on it via a `file:` protocol path.
- Two npm scripts expose this: `sync:presentation-export` (normal) and `check:presentation-export` (`--check-only` mode). A force flag (`--force`, `EXPORT_RUNTIME_VERSION=latest`) allows overriding the pinned version.
- Tests in `scripts/package-metadata.test.mjs` assert that `electronPackage.exportVersion` equals `rootPackage.presentationExportVersion`, enforcing the two declarations stay in sync.
- The Electron build pipeline (`electron/scripts/sync-export-runtime.cjs`, invoked via `npm run setup:export-runtime`) runs this sync before packaging, so the bundled desktop app ships with the vendored runtime.

This is a deliberate architectural choice: the export core is treated as a separately-versioned artifact whose source is controlled by the Presenton team, decoupled from the rest of the dependency graph.

## CI Enforcement

`.github/workflows/test-all.yml` enforces reproducibility:

- FastAPI jobs use `astral-sh/setup-uv@v6` with `cache-dependency-glob: servers/fastapi/uv.lock`, then run `uv sync --locked --dev` (the `--locked` flag fails if the lockfile drifts from `pyproject.toml`).
- Next.js jobs use `npm ci` with `cache-dependency-path: servers/nextjs/package-lock.json`.
- Root-level tests call `npm test` which invokes `scripts/sync-presentation-export.cjs` and then `scripts/sync-presentation-export.cjs --check-only` to verify the vendored runtime matches the declared version.

## Conventions Observed

- Python deps use `>=` lower bounds in `pyproject.toml` but are fully pinned by `uv.lock` consumed with `--locked` in CI — loose constraints in the manifest, strict resolution in the lockfile.
- One exception: `llmai==0.3.15` is pinned with `==` directly in `pyproject.toml`, indicating a dependency that must not be upgraded without explicit review.
- Node deps use caret ranges (`^`) in `package.json` and are locked by committed `package-lock.json` files consumed via `npm ci`.
- Vulnerability patches are applied via `overrides` in `servers/nextjs/package.json` rather than forking the vulnerable package.
- The vendored `@presenton/export-core` is the only non-registry dependency; it is kept in sync through a scripted process with automated tests asserting version parity between root and Electron manifests.
- No private registries, no `GOPRIVATE`, no vendored Go modules — the repository contains no Go code.