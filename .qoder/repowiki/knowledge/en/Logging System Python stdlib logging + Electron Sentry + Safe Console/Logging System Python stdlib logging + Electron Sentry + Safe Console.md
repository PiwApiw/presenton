---
kind: logging_system
name: 'Logging System: Python stdlib logging + Electron Sentry + Safe Console'
category: logging_system
scope:
    - '**'
source_files:
    - servers/fastapi/api/lifespan.py
    - electron/app/sentry/main.ts
    - electron/app/preloads/sentry.ts
    - electron/app/utils/safe-console.ts
---

## Overview

The Presenton monorepo uses three distinct logging/reporting mechanisms, one per runtime:

| Runtime | Mechanism | Purpose |
|---|---|---|
| FastAPI (Python) | `logging` from the Python standard library | Application diagnostics and request lifecycle |
| Electron main/renderer (TypeScript) | `@sentry/electron` (main + renderer) | Error tracking, breadcrumbs, traces, replays |
| Electron IPC / child-process stdout/stderr | `electron/app/utils/safe-console.ts` | Robust console output that survives broken pipes |

There is no shared structured-logging framework across runtimes; each side logs in its own style.

## FastAPI Backend — `logging` module

### Initialization

All log configuration lives in `servers/fastapi/api/lifespan.py`. The `_configure_application_logging()` function runs at application startup and:

1. Reads `LOG_LEVEL` (default `INFO`, uppercased).
2. Sets the root logger level via `getattr(logging, raw, logging.INFO)`.
3. Reuses any handlers already attached to `uvicorn.error` (so Uvicorn's default stderr handler is preserved).
4. Falls back to `logging.basicConfig(level=level)` if no handlers are visible.

This means there is **no custom formatter, no file sink, no JSON structure** — all output goes through whatever handler Uvicorn provides (stderr by default).

### Logger usage pattern

Across `servers/fastapi/`, modules follow a consistent pattern:

```python
import logging
LOGGER = logging.getLogger(__name__)   # or logger = logging.getLogger(__name__)
LOGGER.info(...)
LOGGER.warning(...)
```

Observed in endpoints (`api/v1/ppt/endpoints/outlines.py`, `slide.py`, `template.py`, `api/v2/ppt/endpoints/presentation.py`), services (`services/async_tasks.py`, `services/chat/chat_memory_store.py`, `services/document_conversion_service.py`, `services/documents_loader.py`), bootstrap (`api/v1/auth/bootstrap.py`), and the MCP server (`mcp_server.py`).

### Log levels used

- `info` — normal operational events (migration completion, template import, provider checks).
- `warning` — recoverable issues (missing optional assets, failed optional operations).
- `error` — not heavily used in the sampled files; failures tend to raise exceptions rather than log them.
- `debug` — not observed in the scanned files.

### Structured fields

No structured logging (e.g., JSON payloads with keys like `request_id`, `user_id`) is present. Messages are plain strings; correlation data is not embedded in log lines.

## Electron — Sentry for error telemetry

### Main process

`electron/app/sentry/main.ts` initializes `@sentry/electron/main` via `initMainSentry()`. Key behaviors:

- DSN is hardcoded.
- Enabled/disabled via `SENTRY_ENABLED` (default `true`).
- Environment derived from `SENTRY_ENVIRONMENT` → `NODE_ENV` → `app.isPackaged ? "production" : "development"`.
- Release string defaults to `presenton-electron@<app.getVersion()>`.
- Tracing sample rate controlled by `SENTRY_TRACES_SAMPLE_RATE` (0.2 packaged, 1.0 dev).
- PII disabled by default (`SENTRY_SEND_DEFAULT_PII=false`).
- Logs enabled by default (`SENTRY_ENABLE_LOGS=true`).
- Tags set: `process.type="main"`, `electron.version`, `chromium.version`, `node.version`, `os.platform`, `os.arch`.
- A `runtime` context carries app version, platform, arch, and packaged flag.
- Helper functions: `setMainSentryRuntimeContext`, `captureMainException`, `addMainBreadcrumb`.

### Renderer process

`electron/app/preloads/sentry.ts` initializes `@sentry/electron/renderer` via `initRendererSentry()` (called eagerly at import). It supports:

- `SENTRY_ENABLED` (default `true`).
- `SENTRY_ENABLE_TRACING` → enables `browserTracingIntegration`.
- `SENTRY_ENABLE_REPLAY` → enables `replayIntegration`.
- `SENTRY_ENABLE_FEEDBACK` → enables `feedbackIntegration`.
- Separate sample rates: `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_REPLAYS_SESSION_SAMPLE_RATE`, `SENTRY_REPLAYS_ON_ERROR_SAMPLE_RATE`.
- Tag `process.type="renderer"`.

Both initializers guard against double-initialization with an `isSentryInitialized` flag and swallow initialization/capture errors so Sentry misconfiguration cannot crash the app.

## Electron — Safe Console

`electron/app/utils/safe-console.ts` wraps `console.log`, `console.warn`, and `console.error` to survive broken pipe / destroyed stream conditions common when Electron's child processes terminate abruptly.

It:

- Installs once via `installSafeConsole()` (idempotent via `installed` flag).
- Subscribes to `process.stdout.on('error')` and `process.stderr.on('error')`.
- Ignores known pipe/stream errors (`EPIPE`, `ERR_STREAM_DESTROYED`, `ERR_STREAM_WRITE_AFTER_END`, messages matching `/broken pipe/i`, `/write after end/i`, `/stream has been destroyed/i`).
- For unexpected stream errors, reports them via the original `console.error` as `[SafeConsole] stdout/stderr stream error:`.
- Exposes `safeStdoutWrite`, `safeStderrWrite`, `safeLog`, `safeWarn`, `safeError` for direct use without going through `console`.

This is used instead of a full logging library because it only needs to be robust against stream teardown, not provide levels or sinks.

## Next.js frontend

The Next.js app under `servers/nextjs/` does **not** have a dedicated logging module. Diagnostic output goes directly to `console.log` / `console.warn` / `console.error` scattered throughout components and hooks (e.g., `ImageEditor.tsx`, `TemplateV2PromptOverlay.tsx`, `useTemplateSummaries.ts`, `SettingPage.tsx`). There is no centralized logger abstraction in this codebase.

## Conventions and constraints

- **FastAPI**: Each module creates its own logger via `logging.getLogger(__name__)`; there is no shared logger instance. Log level is configured centrally in `lifespan.py` and honors the `LOG_LEVEL` environment variable.
- **Electron**: Sentry is initialized exactly once per process type (main/renderer) and can be fully disabled via `SENTRY_ENABLED`; all Sentry calls are wrapped in try/catch blocks so failures are silently ignored.
- **Electron IPC streams**: Direct writes to `process.stdout`/`process.stderr` should go through `safeStdoutWrite`/`safeStderrWrite` (or `safeLog`/`safeWarn`/`safeError`) to avoid throwing on broken pipes.
- **No cross-runtime structured logging**: Fields such as request IDs, user identifiers, or trace IDs are not propagated into log lines between the Electron shell, FastAPI backend, and Next.js frontend.
- **No file-based log rotation or external log sink** is implemented in the repository; output is terminal/stderr driven.