---
kind: build_system
name: Presenton Monorepo Build & Distribution System
category: build_system
scope:
    - '**'
source_files:
    - Dockerfile
    - docker-compose.yml
    - .github/workflows/docker-release.yml
    - .github/workflows/test-all.yml
    - .github/workflows/electron-linux-ubuntu22.yml
    - .github/workflows/sync-releaes-to-r2.yml
    - start.js
    - electron/package.json
    - electron/build.js
    - servers/fastapi/pyproject.toml
    - nginx.conf
---

## Overview

Presenton is a multi-language monorepo (Node/Electron, Python FastAPI, Next.js) with three parallel build/distribution paths:

1. **Containerized server** — Docker image built from `Dockerfile`, orchestrated by `docker-compose.yml`.
2. **Desktop app** — Electron application packaged via `electron-builder` in `electron/build.js`.
3. **CI/CD pipelines** — GitHub Actions workflows under `.github/workflows/`.

There is no top-level Makefile; orchestration lives in Node scripts (`start.js`, `electron/package.json` scripts) and Dockerfiles.

## Container Build (`Dockerfile`)

The production image uses a **multi-stage BuildKit** pipeline with four stages:

- `fastapi-builder` (python:3.11-slim-trixie): builds FastAPI deps via `uv export --frozen` then installs them into `/opt/venv`. Also pre-installs `en_core_web_sm` spaCy model and warms HuggingFace/FastEmbed caches.
- `nextjs-builder` (node:22-bookworm-slim): runs `npm ci` + `npm run build` producing Next.js standalone output.
- `assets-builder` (node:22-bookworm-slim): installs pinned `@llamaindex/liteparse@1.5.2` and runs `scripts/sync-presentation-export.cjs --force` to fetch the bundled presentation-export runtime.
- `runtime` (python:3.11-slim-trixie): final image that assembles all artifacts, installs Chromium (pinned via `CHROMIUM_VERSION` / `CHROMIUM_SNAPSHOT` ARGs), Nginx, ImageMagick, Tesseract (optional via `INSTALL_TESSERACT=true`), fonts, and Node 22.

Key conventions:
- Dependency manifests are locked: `servers/fastapi/uv.lock`, `servers/nextjs/package-lock.json`, `electron/package-lock.json`, root `package-lock.json`.
- Cache mounts use `--mount=type=cache,target=/root/.cache/{uv,npm}` for reproducible incremental builds.
- The entrypoint is `CMD ["node", "/app/start.js"]`, which boots Nginx, FastAPI, Next.js, optional Ollama, and an MCP server in one process tree.
- `EXPOSE 80`; host port mapped through `PRESENTON_HTTP_HOST_PORT` in compose.

`docker-compose.yml` defines four services: `production`, `production-gpu` (NVIDIA device reservation), `development`, `development-gpu`. All share the same environment variable surface (~120 variables covering LLM providers, image generation, web search, auth, Mem0, LiteParse, etc.). Development services bind-mount source code and named volumes for `node_modules`, `document-extraction-liteparse`, and `presentation-export`.

## Desktop App Build (`electron/`)

### Entry points

- `electron/package.json` declares scripts for dev, build, and distribution.
- `electron/build.js` is the custom `electron-builder` configuration (appId `com.presenton.presenton`, Team ID `S6W5C54KL6`).

### Build pipeline

The canonical full build is `npm run build:all` (or `build:all:mac:signed` / `build:all:mas-dev` / `build:all:mas`):

1. `clean-build`
2. `setup:env` → installs root deps, runs `uv sync` in FastAPI, `npm install` in Next.js, then `setup:desktop-runtime` + `prepare:imagemagick`
3. TypeScript compile (`tsc`)
4. PyInstaller build of FastAPI binary via `uv run --with pyinstaller python -m PyInstaller server.spec` (output copied into `electron/resources/fastapi/`)
5. Next.js build via `scripts/build-nextjs-resources.cjs`
6. Electron packaging via `node build.js`

Pre-packaging steps invoked per target:
- `copy-templates.cjs` — copies `templates/` into the app bundle
- `generate-version.cjs` — writes version metadata
- `sync-export-runtime.cjs` — fetches pinned `@presenton/export-core` runtime (version pinned in `package.json.exportVersion = "v1.0.34"`)
- `prepare-export-chromium.cjs` — pins Chromium snapshot (`exportChromiumBuildId = "149.0.7827.196"`, macOS-specific IDs in `exportMacChromiumBuildIds`)
- `prepare-imagemagick.cjs` — bundles ImageMagick binaries

### Packaging targets

| Target | Command | Output |
|---|---|---|
| Linux | `electron-linux-ubuntu22.yml` CI | `.deb`, `.AppImage` |
| macOS DMG | `npm run dist` or `build:electron:mac:signed` | `.dmg` |
| Mac App Store | `build:electron:mas` / `mas-dev` | MAS distribution/dev packages |
| Windows | default electron-builder | NSIS installer, `.appx` |

Electron-builder config in `build.js` sets:
- `asar: true`, with `resources/**` and `node_modules/**` unpacked (LiteParse runner needs real package dirs).
- macOS: hardened runtime, entitlements, optional notarization (`shouldNotarizeDirectMacBuild` controlled by `PRESENTON_SKIP_NOTARIZATION`), custom `signDirectMacApp` hook that adds `timestamp=none` for non-binary nested resources.
- Linux: `AppImage`, `deb` with `after-install.tpl` post-install script.
- Windows: NSIS (oneClick=false, perMachine=false, allowElevation=true) and AppX.

### Signing & notarization

`build.js` enforces several preflight checks:
- MAS builds require both an Apple Distribution / 3rd Party Mac Developer Application identity AND a 3rd Party Mac Developer Installer identity in the keychain.
- Direct signed DMG builds (`PRESENTON_REQUIRE_MAC_SIGNING=1`) require either Apple ID credentials (`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`), API key credentials (`APPLE_API_KEY`, `APPLE_API_KEY_ID`, `APPLE_API_ISSUER`), or a keychain profile (`APPLE_KEYCHAIN_PROFILE`).
- Codesign timestamp failures are retried up to `PRESENTON_CODESIGN_TIMESTAMP_RETRIES` (default 4) with exponential backoff.
- Provisioning profiles are resolved from `electron/build/AppleDevelopment.provisionprofile`, `AppleDev.provisionprofile`, `AppDev.provisionprofile`, `MacAppStore.provisionprofile`, `AppDistri.provisionprofile`.

### Runtime resource validation

`assertSourceBundleResourcesReady()` and `assertPackagedBundleResourcesReady()` verify that the bundle contains:
- FastAPI binary (`fastapi.exe` on Windows, `fastapi` elsewhere)
- LLMAI models metadata (`_internal/llmai/data/models.json`)
- Next.js standalone server (`server.js`)
- Export task runner (`export/runner.mjs`)
- Export Core package (`export/node_modules/@presenton/export-core/dist/index.js`)
- Sharp native runtime for the current platform

## CI/CD Pipelines

### `test-all.yml` (runs on push/PR to `main`)
Three parallel jobs:
1. **test-repository-tools**: `npm ci` + `npm test` (root-level scripts tests) + `npm run sync:presentation-export` + `npm run check:presentation-export`.
2. **test-fastapi**: Python 3.11 + uv, `uv sync --locked --dev`, pytest with SQLite DB at `/tmp/presenton-test.db`, env vars disable tracking/image generation.
3. **test-nextjs**: Node 20, `npm ci`, `npm test`, `npm run lint`, `npm run build`, Cypress component tests (`cypress run --component --browser electron`).

### `docker-release.yml` (manual dispatch or on release publish)
- Builds multi-arch images (`linux/amd64`, `linux/arm64`) using `docker/setup-qemu-action` + `docker/setup-buildx-action`.
- Pushes to `ghcr.io/presenton/presenton` with tag `dev` on dispatch or `<release-tag>` on release.
- Uses GHCR cache (`type=gha`) and verifies both architectures are present via `docker buildx imagetools inspect`.

### `electron-linux-ubuntu22.yml` (branch `electron-linux-ubuntu22` only)
- Ubuntu 22.04 runner, Node 20, Python 3.11, uv.
- Installs `build-essential`, `fakeroot`, `libarchive-tools`, `rpm`.
- Runs `npm run build:all` in `electron/` (with `CI=false`, `CSC_IDENTITY_AUTO_DISCOVERY=false`).
- Verifies `.deb` and `.AppImage` exist in `electron/dist/`.
- Publishes artifacts as a temporary prerelease to `presenton/presenton-export` repo tagged `presenton-electron-linux-ubuntu-22`.

### `sync-releaes-to-r2.yml`
Mirrors published releases to Cloudflare R2 (artifact mirroring).

## Versioning Strategy

- Desktop app version: `electron/package.json.version` (e.g. `0.9.11-beta`); used as artifact filename via `${version}` in electron-builder config.
- Bundled export runtime version: `electron/package.json.exportVersion` (e.g. `v1.0.34`), fetched by `sync-export-runtime.cjs`.
- Chromium snapshot versions: `electron/package.json.exportChromiumBuildId` + `exportMacChromiumBuildIds`.
- Docker image tags: release tag or moving `dev` tag.
- App Store short version/build derived from `package.json.version` unless overridden by `PRESENTON_APP_STORE_VERSION` / `PRESENTON_APP_STORE_BUILD`.

## Runtime Entrypoint (`start.js`)

The container's `CMD node /app/start.js` performs:
1. Ensures `APP_DATA_DIRECTORY` exists with subdirs `exports`, `images`, `uploads`, `fonts`, `templates`, `pptx-to-html`, `pptx-to-json`.
2. Writes user config from environment via `scripts/user-config-env.cjs` (atomic write with `.bak` fallback).
3. Optionally installs Ollama if `START_OLLAMA=true` and binary not found.
4. Syncs presentation-export runtime via `scripts/sync-presentation-export.cjs` (fails in prod, auto-syncs in dev).
5. Starts Nginx, FastAPI (`server.py --port 8000 --reload <dev?>`), Next.js (standalone server in prod, `next dev` in dev), and MCP server (`mcp_server.py --port 8001`).
6. Waits for readiness: FastAPI HTTP probe on `/api/v1/auth/status`, Next.js stdout match for `Ready in\s+\d+` / `started server on`.
7. Forwards child stdio, suppresses startup URL lines in prod, prints banner via `scripts/presenton-terminal-banner.mjs`.
8. On SIGINT/SIGTERM, kills all managed processes and exits.