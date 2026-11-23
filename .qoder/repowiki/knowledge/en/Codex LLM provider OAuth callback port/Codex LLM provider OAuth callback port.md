---
kind: external_dependency
name: Codex LLM provider OAuth callback port
slug: openai-codex-oauth
category: external_dependency
category_hints:
    - auth_protocol
scope:
    - '**'
---

### Codex authentication flow
- Selecting `LLM=codex` requires a dedicated host port `1455` mapped into the container so OpenAI can redirect the browser back to `localhost:1455` as the OAuth callback endpoint.
- The environment variable `CODEX_MODEL` selects the model; the same port mapping is present in all four compose services (`production`, `production-gpu`, `development`, `development-gpu`).
- This is not a generic OpenAI chat API call — it uses the browser-based OAuth flow with a localhost redirect.