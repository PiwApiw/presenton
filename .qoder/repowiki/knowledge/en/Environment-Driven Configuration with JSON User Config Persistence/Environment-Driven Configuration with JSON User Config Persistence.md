---
kind: configuration_system
name: Environment-Driven Configuration with JSON User Config Persistence
category: configuration_system
scope:
    - '**'
source_files:
    - start.js
    - scripts/user-config-env.cjs
    - electron/app/utils/user-config-env.ts
    - electron/app/utils/user-config-store.ts
    - servers/fastapi/utils/get_env.py
    - docker-compose.yml
    - servers/nextjs/app/ConfigurationInitializer.tsx
---

## Approach

Presenton uses a **12-factor-style environment-variable configuration** model. There is no `.env` file loader, no YAML/TOML config schema library, and no centralized `Config` object. Instead:

- Every runtime setting is an uppercase `ENV_VAR` read directly from `process.env` (Node) or `os.getenv` (Python).
- A shared normalization/merging script (`scripts/user-config-env.cjs`) converts raw env vars into a typed user-config JSON document.
- The resulting document is persisted to disk as `app_data/userConfig.json` (with a `.bak` backup), and both the Electron shell and the FastAPI backend read it at startup.
- The Next.js frontend never reads env vars; it fetches its view of configuration from the backend via `/api/user-config` (admin) or `/api/runtime-config` (regular user).

No external configuration framework is used — only stdlib modules (`fs`, `path`, `os`, `crypto`).

## Key Files and Packages

| File | Role |
|---|---|
| `start.js` | Top-level orchestrator: creates `APP_DATA_DIRECTORY`, writes `userConfig.json`, spawns FastAPI + Next.js + Nginx + optional Ollama. Enforces `APP_DATA_DIRECTORY` as required. |
| `scripts/user-config-env.cjs` | Canonical env→config normalizer, shared by Node (start.js, Electron) and Python (via `scripts/user-config-env.test.mjs`). Defines `USER_CONFIG_ENV_KEYS`, `BOOLEAN_CONFIG_KEYS`, `VALID_LLM_PROVIDERS`. |
| `electron/app/utils/user-config-env.ts` | Electron-side shim that dynamically loads the shared CJS module (from dev path or `process.resourcesPath`) and exposes `syncUserConfigFromEnv()`. |
| `electron/app/utils/user-config-store.ts` | Atomic, lock-backed JSON file reader/writer for `userConfig.json` (lock file `<path>.lock`, backup `<path>.bak`, temp `<path>.<pid>.<ts>.<hex>.tmp`). |
| `servers/fastapi/utils/get_env.py` | Python accessor layer: one `get_<var>_env()` function per env var, plus typed helpers like `is_truthy`, `get_presentation_generation_mode`. |
| `docker-compose.yml` | Single source of truth for which env vars are passed to the container (three profiles: `production`, `production-gpu`, `development`, `development-gpu`). |
| `servers/nextjs/app/ConfigurationInitializer.tsx` | Frontend bootstrap: calls `/api/v1/auth/status`, then `/api/user-config` or `/api/runtime-config`, validates provider settings, and redirects unconfigured admins to `/`. |
| `nginx.conf` | Reverse proxy wiring; not a config format but part of the runtime surface. |

## Architecture and Conventions

### Two-layer configuration

1. **Process env → normalized JSON** (`buildUserConfigFromEnv(existingConfig, process.env)`):
   - Filters env vars through `USER_CONFIG_ENV_KEYS` (a whitelist of ~95 keys covering LLM providers, image providers, web search, reasoning, Mem0, Liteparse, Sentry, etc.).
   - Applies type coercion in `normalizeConfigTypes`: boolean-like strings (`"1"/"true"/"yes"/"on"` → `true`; `"0"/"false"/"no"/"off"` → `false`), integer conversion for `LLM_MAX_OUTPUT_TOKENS` / `LLM_REASONING_BUDGET_TOKENS`, comma-split array for `OPENROUTER_PROVIDER_ORDER`.
   - Runs `normalizeImageConfig`, which auto-detects `IMAGE_PROVIDER` from available credentials (openai_compatible, open_webui, comfyui, pexels, pixabay, gpt-image-1.5, gemini_flash) and migrates legacy `dall-e-3` → `gpt-image-2`.
   - Sanitizes existing config against `VALID_LLM_PROVIDERS` (ollama, openai, deepseek, google, vertex, azure, bedrock, openrouter, fireworks, together, cerebras, anthropic, litellm, lmstudio, custom, codex).

2. **Persisted JSON → runtime accessors**:
   - `start.js` reads `userConfig.json` (or `.bak`) and merges env-derived values on top before writing back atomically.
   - FastAPI's `get_env.py` reads env vars directly (not the JSON file) so server behavior reflects the process environment even if the persisted file is stale.
   - Electron's `user-config-store.ts` provides the durable persistence layer used by the desktop app's UI.

### Environment variable categories

The repo documents env vars implicitly through their usage:

- **Runtime switches**: `PRESENTATION_GENERATION_MODE` (`standard`|`smart`|`both`, default `both`), `PRESENTON_COMMUNITY_ENABLED` (default true), `DISABLE_AUTH`, `ENABLE_PARALLEL_IMAGE_GENERATION` (default true), `MIGRATE_DATABASE_ON_STARTUP` (default `true`), `START_OLLAMA`, `PRESENTON_ELECTRON`, `PRESENTON_PUBLIC_URL`, `NEXT_PUBLIC_FAST_API`, `FAST_API_INTERNAL_URL`, `APP_DATA_DIRECTORY` (required), `TEMP_DIRECTORY`, `USER_CONFIG_PATH`, `DATABASE_URL`.
- **LLM providers** (one group per provider): `LLM`, `OPENAI_*`, `DEEPSEEK_*`, `GOOGLE_*`, `VERTEX_*`, `AZURE_OPENAI_*`, `BEDROCK_*`, `OPENROUTER_*`, `FIREWORKS_*`, `TOGETHER_*`, `CEREBRAS_*`, `ANTHROPIC_*`, `OLLAMA_*`, `CUSTOM_*`, `LITELLM_*`, `LMSTUDIO_*`, `CODEX_*`.
- **Image generation**: `IMAGE_PROVIDER`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `COMFYUI_*`, `OPEN_WEBUI_IMAGE_*`, `OPENAI_COMPAT_IMAGE_*`, `GPT_IMAGE_2_QUALITY`, `GPT_IMAGE_1_5_QUALITY`, `DALL_E_3_QUALITY` (legacy migration only).
- **Reasoning/web search**: `DISABLE_THINKING`, `EXTENDED_REASONING`, `LLM_GENERATION_PROFILE`, `LLM_REASONING_*`, `WEB_GROUNDING`, `WEB_SEARCH_PROVIDER`, `WEB_SEARCH_MAX_RESULTS`, `SEARXNG_BASE_URL`, `TAVILY_API_KEY`, `EXA_API_KEY`, `BRAVE_SEARCH_API_KEY`, `SERPER_API_KEY`.
- **Observability**: `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_SEND_DEFAULT_PII`, `DISABLE_ANONYMOUS_TRACKING`.
- **Mem0/Liteparse**: `MEM0_*`, `LITEPARSE_*`.
- **Auth override**: `AUTH_USERNAME`, `AUTH_PASSWORD`, `AUTH_OVERRIDE_FROM_ENV`, `RESET_AUTH`.

### Docker compose as the canonical env manifest

`docker-compose.yml` lists every env var with `${VAR:-default}` syntax across four service blocks (`production`, `production-gpu`, `development`, `development-gpu`). This is the primary documentation surface for operators. Defaults are duplicated in `get_env.py` where the Python side needs a non-empty fallback (e.g. `MIGRATE_DATABASE_ON_STARTUP=true`, `ENABLE_PARALLEL_IMAGE_GENERATION=true`).

### Electron vs. Node orchestrator

- `start.js` runs when Presenton is launched as a standalone Node process. It sets `process.env.USER_CONFIG_PATH = <app_data>/userConfig.json`, then calls `setupUserConfigFromEnv()` which merges env into the persisted JSON.
- When running inside Electron, `electron/app/utils/user-config-env.ts::syncUserConfigFromEnv()` performs the same merge into the Electron-managed user config path, preserving an existing UI-managed config when no env was supplied.

### Frontend configuration flow

`ConfigurationInitializer.tsx` bootstraps the UI by:
1. Calling `/api/v1/auth/status` to determine admin vs. user role.
2. Admins fetch `/api/user-config` (full config); regular users fetch `/api/runtime-config` (redacted). Both go through `normalizeLLMConfig`.
3. If configured, it optionally checks Ollama model availability and redirects to `/upload`.
4. On every route change (except `/settings*` and `/pdf-maker*`), it revalidates provider configuration.

## Conventions and Constraints

- **All runtime configuration comes from environment variables.** No `.env` files are loaded; there is no dotenv dependency anywhere in the tree.
- **Environment variable names are uppercase, underscore-separated, and prefixed by feature area** (e.g. `OPENAI_API_KEY`, `BEDROCK_REGION`, `WEB_SEARCH_PROVIDER`). New variables should follow this naming pattern.
- **Boolean env vars use a consistent truthy/falsy set**: `"1"|"true"|"yes"|"on"` → true; `"0"|"false"|"no"|"off"` → false. This is enforced by `_is_truthy` in `get_env.py` and `parseBooleanLike` in `user-config-env.cjs`.
- **Only whitelisted env vars are accepted** by the user-config merger. `USER_CONFIG_ENV_KEYS` in `scripts/user-config-env.cjs` is the authoritative list; any new config key must be added there to be recognized.
- **LLM provider names are validated against `VALID_LLM_PROVIDERS`**. Unknown values are silently dropped during config build.
- **`APP_DATA_DIRECTORY` is mandatory** — `start.js` throws `"APP_DATA_DIRECTORY is required"` if unset.
- **User config persistence is atomic**: writes go to a temp file named `<path>.<pid>.<timestamp>.<random>.tmp`, then `renameSync` replaces the target; a `.bak` copy is maintained.
- **Concurrent access to `userConfig.json` is serialized** via a file-based lock (`<path>.lock`) with a 5-second timeout and stale-lock cleanup after 30 seconds, implemented in `electron/app/utils/user-config-store.ts`.
- **Defaults are declared in two places**: `docker-compose.yml` (for deployment) and `get_env.py` (for Python runtime behavior). Adding a new env var requires updating both.
- **The frontend never reads env vars directly**; it always goes through the backend API, ensuring secrets are redacted for non-admin users.
- **Legacy migration is handled in code**: `dall-e-3` is mapped to `gpt-image-2` and `DALL_E_3_QUALITY` is deleted from the config during normalization.