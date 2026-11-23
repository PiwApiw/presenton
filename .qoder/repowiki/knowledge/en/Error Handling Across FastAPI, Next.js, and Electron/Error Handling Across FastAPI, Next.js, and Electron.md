---
kind: error_handling
name: Error Handling Across FastAPI, Next.js, and Electron
category: error_handling
scope:
    - '**'
source_files:
    - servers/fastapi/models/api_error_model.py
    - servers/fastapi/utils/provider_error_messages.py
    - servers/fastapi/utils/image_generation_error.py
    - servers/fastapi/utils/llm_client_error_handler.py
    - servers/fastapi/api/middlewares.py
    - servers/fastapi/api/main.py
    - servers/nextjs/models/errors.ts
    - servers/nextjs/utils/error_helpers.ts
    - servers/nextjs/utils/apiErrorMessages.ts
    - servers/nextjs/app/(presentation-generator)/services/api/api-error-handler.ts
    - servers/nextjs/app/global-error.tsx
    - electron/app/sentry/main.ts
---

## Overview

Presenton is a multi-process monorepo (Electron shell + FastAPI backend + Next.js frontend) that uses three distinct but coordinated error-handling strategies:

1. **FastAPI backend**: `fastapi.HTTPException` as the primary transport error type, with provider-specific subclasses and centralized message normalization.
2. **Next.js frontend**: custom `ApiError` / `ApiResponseError` classes plus an `ApiResponseHandler` that translates HTTP responses into typed client errors with retryability metadata.
3. **Electron main process**: Sentry (`@sentry/electron/main`) for crash/exception capture, with environment-gated initialization.

There is no global exception handler registered via `add_exception_handler`; instead, each layer catches and transforms exceptions at its boundary.

## FastAPI Backend

### Core types
- `models/api_error_model.APIErrorModel` — a Pydantic model representing `{status_code, detail}` with a `from_exception` factory that maps `HTTPException` to its status/detail and otherwise defaults to `500`.
- `utils/image_generation_error.ImageGenerationHTTPException(HTTPException)` — extends `HTTPException` with an extra `provider_code` attribute; used by image-generation code paths.

### Provider error normalization
- `utils/provider_error_messages.py` centralizes user-facing messages: `INVALID_API_KEY_MESSAGE`, `IMAGE_MODERATION_MESSAGE`, `GENERIC_PROVIDER_ERROR_MESSAGE`. It exposes `safe_provider_error_detail()` and `safe_llm_provider_error_detail()`, which inspect `status_code`, `code`, `error_type`, and `message` against regex patterns (e.g. `_INVALID_API_KEY_PATTERNS`) to map raw provider payloads into safe, localized strings. This prevents leaking raw JSON/error bodies from OpenAI/Google/etc. to the client.
- `utils/image_generation_error.openai_error_detail()` extracts `code`/`type`/`body` from `openai.APIError` and delegates to `safe_provider_error_detail("OpenAI", ...)`.
- `utils/llm_client_error_handler.handle_llm_client_exceptions()` is the single entry point for LLM client errors. It handles `HTTPException`, `LLMAIBaseError`, `openai.APIError`, and `google.genai.errors.APIError`, printing a traceback and returning an `HTTPException` whose `detail` goes through `safe_llm_provider_error_detail`. For the Codex provider it also rewrites 401/403 into a special `CHATGPT_AUTH_REQUIRED_PREFIX` + `X-Presenton-Auth-Action: codex-reauth` header so the frontend can trigger re-auth.

### Middleware-based error responses
- `api/middlewares.py::SessionAuthMiddleware` returns `starlette.responses.JSONResponse` directly for auth failures: `428 Login setup is required`, `401 Unauthorized`, `403 Admin browser session required`, and `404 Asset not found`. These bypass route handlers entirely.
- `api/main.py` mounts `UserConfigEnvUpdateMiddleware` and `SessionAuthMiddleware` globally and adds a per-request `static_icon_fallback_middleware` that turns missing `/static/icons/*` 404s into a placeholder SVG.

No global `@app.exception_handler` is registered in `api/main.py`; unhandled exceptions bubble to Starlette's default 500 handler.

## Next.js Frontend

### Client-side error types
- `models/errors.ts::ApiError` — minimal class holding only `detail`, used by the `wrap_errors` helper.
- `app/(presentation-generator)/services/api/api-error-handler.ts::ApiResponseError(Error)` — richer error carrying `status`, optional `code`, and `retryable: boolean`. Thrown from `ApiResponseHandler.handleResponse`.

### Response handling pipeline
- `ApiResponseHandler.handleResponse` / `handleResponseWithResult` parse non-OK responses, extract messages via `extractApiErrorMessage`, detect ChatGPT re-auth flows via `isChatGptAuthRequiredResponse`, and throw `ApiResponseError` with a `retryable` flag derived from `extractApiErrorMetadata` (which marks 408/425/429/500/502/503/504 as retryable).
- `utils/apiErrorMessages.ts` mirrors the backend's sanitization logic: `normalizeApiErrorDetail` flattens nested FastAPI validation arrays, `sanitizeApiErrorMessage` replaces raw provider payloads (JSON, HTML, `<doctype`) and known auth/safety-block patterns with friendly messages (`INVALID_API_KEY_MESSAGE`, `SAFETY_BLOCK_MESSAGE`).
- `utils/error_helpers.wrap_errors` is a decorator-like wrapper around server-side functions that re-throws `ApiError` unchanged and wraps other exceptions as `ApiError("Internal server error: …")`.

### Global UI error page
- `app/global-error.tsx` renders Next.js's built-in `NextError` component with `statusCode={0}` and logs the error via `console.error`. No Sentry integration here.

## Electron Main Process

- `electron/app/sentry/main.ts` provides `initMainSentry`, `captureMainException`, `addMainBreadcrumb`, and `setMainSentryRuntimeContext`. Initialization is gated by `SENTRY_ENABLED` (defaulting to true), with `SENTRY_TRACES_SAMPLE_RATE` clamped to `[0, 1]`. DSN is hardcoded. All Sentry calls are wrapped in try/catch so Sentry failures cannot crash the app.
- Runtime context tags include Electron/Chromium/Node versions, OS/platform, packaged state, and Presenton app version.

## Cross-cutting Conventions Observed

- **Provider error messages are never sent verbatim to clients.** Both backend (`safe_provider_error_detail`) and frontend (`sanitizeApiErrorMessage`) independently normalize raw provider payloads into user-friendly text, guarding against leaking internal JSON or HTML error pages.
- **Authentication errors are normalized to a common shape.** Invalid API key / authentication errors are detected by multiple heuristics (regex on `code`/`error_type`/`message`, `status_code == 401`, literal tokens like `invalid_api_key`, `authentication_error`) and mapped to `INVALID_API_KEY_MESSAGE`.
- **Safety/moderation blocks are surfaced separately** from generic provider errors, with a dedicated `IMAGE_MODERATION_MESSAGE` for image generation.
- **Codex provider gets special-cased 401/403 handling**, rewriting them into a `CHATGPT_AUTH_REQUIRED_PREFIX` detail and adding `X-Presenton-Auth-Action: codex-reauth` so the frontend can prompt re-login.
- **Retryability is propagated from server to client** via a `code`/`retryable` field extracted from the response body and attached to `ApiResponseError`.
- **Sentry is opt-in and isolated:** both Electron and FastAPI initialize Sentry lazily and swallow any initialization/capture failures so they do not affect application behavior.