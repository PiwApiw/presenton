# Local Model Support (Ollama)

<cite>
**Referenced Files in This Document**
- [supported_ollama_models.py](file://servers/fastapi/constants/supported_ollama_models.py)
- [ollama.py](file://servers/fastapi/utils/ollama.py)
- [ollama_model_status.py](file://servers/fastapi/models/ollama_model_status.py)
- [ollama_model_metadata.py](file://servers/fastapi/models/ollama_model_metadata.py)
- [endpoints/ollama.py](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py)
- [get_env.py](file://servers/fastapi/utils/get_env.py)
- [model_availability.py](file://servers/fastapi/utils/model_availability.py)
- [providerUtils.ts](file://servers/nextjs/utils/providerUtils.ts)
- [ConfigurationInitializer.tsx](file://servers/nextjs/app/ConfigurationInitializer.tsx)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
This document explains Presenton’s local model support through Ollama integration. It covers how to set up the Ollama server, pull models, manage runtime behavior, and monitor model availability. It also documents supported models, compatibility requirements, configuration options for local deployment, memory/GPU considerations, fallback strategies when local models fail, and troubleshooting guidance.

## Project Structure
Presenton integrates with Ollama via a FastAPI backend and a Next.js frontend:
- Backend exposes Ollama endpoints for listing available models, pulling models, and returning supported library models.
- The backend validates that the selected Ollama model is already pulled before enabling generation.
- The frontend caches available Ollama models, resolves URLs, and provides fallbacks between Docker host and localhost.

```mermaid
graph TB
subgraph "Frontend (Next.js)"
UI["UI Components"]
ProviderUtils["providerUtils.ts<br/>Model cache & URL resolution"]
end
subgraph "Backend (FastAPI)"
Router["/api/v1/ppt/ollama/*<br/>Endpoints"]
Utils["utils/ollama.py<br/>HTTP client to Ollama"]
Models["models/*<br/>Status & Metadata"]
Constants["constants/supported_ollama_models.py<br/>Supported catalog"]
Env["utils/get_env.py<br/>OLLAMA_URL / OLLAMA_MODEL"]
Avail["utils/model_availability.py<br/>Startup validation"]
end
Ollama["Ollama Server<br/>http://localhost:11434"]
UI --> ProviderUtils
ProviderUtils --> Router
Router --> Utils
Utils --> Ollama
Router --> Models
Router --> Constants
Router --> Env
Avail --> Utils
Avail --> Env
```

**Diagram sources**
- [endpoints/ollama.py:10-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L10-L36)
- [ollama.py:45-142](file://servers/fastapi/utils/ollama.py#L45-L142)
- [supported_ollama_models.py:304-354](file://servers/fastapi/constants/supported_ollama_models.py#L304-L354)
- [get_env.py:100-101](file://servers/fastapi/utils/get_env.py#L100-L101)
- [model_availability.py:205-215](file://servers/fastapi/utils/model_availability.py#L205-L215)
- [providerUtils.ts:7-17](file://servers/nextjs/utils/providerUtils.ts#L7-L17)

**Section sources**
- [endpoints/ollama.py:10-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L10-L36)
- [ollama.py:45-142](file://servers/fastapi/utils/ollama.py#L45-L142)
- [supported_ollama_models.py:304-354](file://servers/fastapi/constants/supported_ollama_models.py#L304-L354)
- [get_env.py:100-101](file://servers/fastapi/utils/get_env.py#L100-L101)
- [model_availability.py:205-215](file://servers/fastapi/utils/model_availability.py#L205-L215)
- [providerUtils.ts:7-17](file://servers/nextjs/utils/providerUtils.ts#L7-L17)

## Core Components
- Supported model catalog: A curated list of tested Ollama models with labels, values, sizes, and a “tested” flag.
- Ollama client utilities: Functions to resolve Ollama URL, list models, and stream model pulls.
- API endpoints: REST routes to get supported/available/library models and to pull models via SSE.
- Environment configuration: OLLAMA_URL and OLLAMA_MODEL environment variables.
- Availability validation: Startup checks ensuring the selected Ollama model exists locally.
- Frontend helpers: Caching, URL normalization, and fallback between Docker host and localhost.

Key responsibilities:
- Catalog management and formatting of model metadata.
- Safe HTTP communication with Ollama and robust error handling.
- Streaming progress updates during model downloads.
- Pre-flight validation to prevent using unpulled models.

**Section sources**
- [supported_ollama_models.py:5-314](file://servers/fastapi/constants/supported_ollama_models.py#L5-L314)
- [ollama.py:16-42](file://servers/fastapi/utils/ollama.py#L16-L42)
- [endpoints/ollama.py:13-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L13-L36)
- [get_env.py:100-101](file://servers/fastapi/utils/get_env.py#L100-L101)
- [model_availability.py:205-215](file://servers/fastapi/utils/model_availability.py#L205-L215)
- [providerUtils.ts:286-332](file://servers/nextjs/utils/providerUtils.ts#L286-L332)

## Architecture Overview
The following sequence shows how Presenton lists and pulls models from Ollama.

```mermaid
sequenceDiagram
participant FE as "Frontend"
participant API as "FastAPI /ollama/*"
participant U as "utils/ollama.py"
participant OL as "Ollama Server"
FE->>API : GET /api/v1/ppt/ollama/models/available
API->>U : list_available_ollama_models()
U->>OL : GET /api/tags
OL-->>U : JSON { models }
U-->>API : List[OllamaModelStatus]
API-->>FE : 200 OK
FE->>API : POST /api/v1/ppt/ollama/models/pull?model_name=...
API->>U : pull_ollama_model(model_name)
U->>OL : POST /api/pull { name, stream : true }
OL-->>U : SSE events (status/progress/complete/error)
U-->>API : Stream text/event-stream
API-->>FE : Streamed events
```

**Diagram sources**
- [endpoints/ollama.py:21-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L21-L36)
- [ollama.py:90-201](file://servers/fastapi/utils/ollama.py#L90-L201)

## Detailed Component Analysis

### Supported Model Catalog
- Defines families of models (Llama, Gemma, DeepSeek, Qwen, GPT-OSS, Gemma4, Qwen3.5).
- Each entry includes label, value, size, and a tested flag.
- Aggregates into a single supported catalog and supports appending locally pulled experimental models.

```mermaid
classDiagram
class OllamaModelMetadata {
+string label
+string value
+string size
+bool tested
}
class SupportedCatalog {
+TESTED_OLLAMA_MODELS
+SUPPORTED_OLLAMA_MODELS
+get_supported_ollama_models(pulled_models)
+format_ollama_model_size(size_bytes)
}
SupportedCatalog --> OllamaModelMetadata : "uses"
```

**Diagram sources**
- [ollama_model_metadata.py:4-8](file://servers/fastapi/models/ollama_model_metadata.py#L4-L8)
- [supported_ollama_models.py:304-354](file://servers/fastapi/constants/supported_ollama_models.py#L304-L354)

**Section sources**
- [supported_ollama_models.py:5-314](file://servers/fastapi/constants/supported_ollama_models.py#L5-L314)
- [supported_ollama_models.py:317-354](file://servers/fastapi/constants/supported_ollama_models.py#L317-L354)

### Ollama Client Utilities
- URL resolution: Validates and normalizes Ollama URL; defaults to localhost if unset.
- Listing models: Calls /api/tags, maps responses to OllamaModelStatus, and handles errors.
- Pulling models: Streams /api/pull events and emits SSE-compatible messages.

```mermaid
flowchart TD
Start(["Function Entry"]) --> ResolveURL["Resolve Ollama URL"]
ResolveURL --> ValidateURL{"URL Valid?"}
ValidateURL --> |No| ErrInvalid["Raise HTTP 400 Invalid URL"]
ValidateURL --> |Yes| CallTags["GET /api/tags"]
CallTags --> TagsOK{"Response 200?"}
TagsOK --> |No| HandleErr["Map to HTTP 503 or 502"]
TagsOK --> |Yes| MapModels["Map to OllamaModelStatus[]"]
MapModels --> ReturnList["Return models"]
```

**Diagram sources**
- [ollama.py:45-59](file://servers/fastapi/utils/ollama.py#L45-L59)
- [ollama.py:90-142](file://servers/fastapi/utils/ollama.py#L90-L142)

**Section sources**
- [ollama.py:45-59](file://servers/fastapi/utils/ollama.py#L45-L59)
- [ollama.py:90-142](file://servers/fastapi/utils/ollama.py#L90-L142)
- [ollama.py:149-201](file://servers/fastapi/utils/ollama.py#L149-L201)

### API Endpoints
- GET /models/supported: Returns supported models plus any locally pulled ones.
- GET /models/available: Returns currently available models on the Ollama server.
- GET /models/library: Returns the curated library catalog.
- POST /models/pull: Streams model download progress via SSE.

```mermaid
sequenceDiagram
participant FE as "Frontend"
participant EP as "FastAPI Endpoints"
participant U as "utils/ollama.py"
FE->>EP : GET /models/supported
EP->>U : list_available_ollama_models()
U-->>EP : List[OllamaModelStatus]
EP-->>FE : List[OllamaModelMetadata]
FE->>EP : POST /models/pull?model_name=...
EP->>U : pull_ollama_model(model_name)
U-->>EP : SSE events
EP-->>FE : text/event-stream
```

**Diagram sources**
- [endpoints/ollama.py:13-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L13-L36)
- [ollama.py:90-201](file://servers/fastapi/utils/ollama.py#L90-L201)

**Section sources**
- [endpoints/ollama.py:13-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L13-L36)

### Environment Configuration
- OLLAMA_URL: Base URL for the Ollama server.
- OLLAMA_MODEL: Required when LLM provider is set to Ollama; must match an available model.

```mermaid
flowchart TD
Start(["App Startup"]) --> ReadEnv["Read OLLAMA_URL / OLLAMA_MODEL"]
ReadEnv --> CheckProvider{"LLM == 'ollama'?"}
CheckProvider --> |No| Skip["Skip Ollama checks"]
CheckProvider --> |Yes| ValidateModel["Check OLLAMA_MODEL exists locally"]
ValidateModel --> Available{"Model available?"}
Available --> |No| Error["Raise exception with guidance"]
Available --> |Yes| Proceed["Proceed"]
```

**Diagram sources**
- [get_env.py:100-101](file://servers/fastapi/utils/get_env.py#L100-L101)
- [model_availability.py:205-215](file://servers/fastapi/utils/model_availability.py#L205-L215)

**Section sources**
- [get_env.py:100-101](file://servers/fastapi/utils/get_env.py#L100-L101)
- [model_availability.py:205-215](file://servers/fastapi/utils/model_availability.py#L205-L215)

### Frontend Integration and Fallback Strategy
- Default URLs: Uses localhost by default; supports Docker host resolution.
- Cache: Caches available models for a short TTL to reduce network calls.
- Fallback: If Docker-host URL fails outside Electron, falls back to localhost.

```mermaid
flowchart TD
Start(["Fetch Available Models"]) --> Normalize["Normalize Ollama URL"]
Normalize --> TryPreferred["Try preferred URL"]
TryPreferred --> Success{"Success?"}
Success --> |Yes| ReturnPreferred["Return models + resolvedUrl"]
Success --> |No| CheckFallback{"Should try localhost fallback?"}
CheckFallback --> |Yes| TryLocal["Try http://localhost:11434"]
TryLocal --> ReturnLocal["Return models + usedFallback=true"]
CheckFallback --> |No| ThrowError["Throw error"]
```

**Diagram sources**
- [providerUtils.ts:7-17](file://servers/nextjs/utils/providerUtils.ts#L7-L17)
- [providerUtils.ts:286-332](file://servers/nextjs/utils/providerUtils.ts#L286-L332)

**Section sources**
- [providerUtils.ts:7-17](file://servers/nextjs/utils/providerUtils.ts#L7-L17)
- [providerUtils.ts:286-332](file://servers/nextjs/utils/providerUtils.ts#L286-L332)

### Model Status Monitoring and Automatic Management
- Available models endpoint returns current state of pulled models.
- Supported models endpoint merges curated catalog with locally pulled models.
- Pull endpoint streams progress events for real-time monitoring.

```mermaid
classDiagram
class OllamaModelStatus {
+string name
+string parameters
+int size
+int downloaded
+string status
+bool done
+string error
}
class OllamaModelMetadata {
+string label
+string value
+string size
+bool tested
}
```

**Diagram sources**
- [ollama_model_status.py:5-12](file://servers/fastapi/models/ollama_model_status.py#L5-L12)
- [ollama_model_metadata.py:4-8](file://servers/fastapi/models/ollama_model_metadata.py#L4-L8)

**Section sources**
- [ollama_model_status.py:5-12](file://servers/fastapi/models/ollama_model_status.py#L5-L12)
- [ollama_model_metadata.py:4-8](file://servers/fastapi/models/ollama_model_metadata.py#L4-L8)
- [endpoints/ollama.py:13-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L13-L36)

## Dependency Analysis
- Endpoints depend on utils.ollama for HTTP operations and on constants.supported_ollama_models for catalog data.
- Availability validation depends on utils.get_env for configuration and utils.ollama for live checks.
- Frontend providerUtils depends on backend endpoints and implements its own caching and fallback logic.

```mermaid
graph LR
EP["endpoints/ollama.py"] --> U["utils/ollama.py"]
EP --> C["constants/supported_ollama_models.py"]
MA["utils/model_availability.py"] --> U
MA --> E["utils/get_env.py"]
FE["servers/nextjs/utils/providerUtils.ts"] --> EP
```

**Diagram sources**
- [endpoints/ollama.py:1-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L1-L36)
- [model_availability.py:1-46](file://servers/fastapi/utils/model_availability.py#L1-L46)
- [providerUtils.ts:1-17](file://servers/nextjs/utils/providerUtils.ts#L1-L17)

**Section sources**
- [endpoints/ollama.py:1-36](file://servers/fastapi/api/v1/ppt/endpoints/ollama.py#L1-L36)
- [model_availability.py:1-46](file://servers/fastapi/utils/model_availability.py#L1-L46)
- [providerUtils.ts:1-17](file://servers/nextjs/utils/providerUtils.ts#L1-L17)

## Performance Considerations
- Network timeouts: Listing models uses a short timeout to avoid long waits when Ollama is unreachable.
- Streaming pulls: Model pulls use streaming without a global timeout to accommodate large downloads.
- Frontend caching: Available models are cached for a short TTL to reduce repeated requests.
- Resource usage: Larger models require more RAM and potentially GPU acceleration depending on Ollama’s configuration.

Recommendations:
- Use smaller parameter variants (e.g., 1B–8B) for constrained environments.
- Ensure sufficient disk space for model files and adequate RAM for model loading.
- Monitor Ollama logs for out-of-memory or GPU-related issues.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Ollama unreachable:
  - Symptom: Errors indicating inability to connect to Ollama.
  - Resolution: Verify Ollama is running and reachable; when running Presenton in Docker, use host.docker.internal instead of localhost.
- Invalid Ollama URL:
  - Symptom: HTTP 400 invalid URL.
  - Resolution: Provide a valid http(s) URL with a hostname.
- Forbidden access:
  - Symptom: HTTP 403 when listing models.
  - Resolution: Check Ollama configuration and authentication settings.
- Selected model not available:
  - Symptom: Startup validation fails because OLLAMA_MODEL is not present locally.
  - Resolution: Pull the model first, then verify it appears in available models.
- Frontend connectivity:
  - Symptom: Cannot reach backend or Ollama from UI.
  - Resolution: Confirm backend is reachable; check URL resolution and fallback behavior.

Operational tips:
- Use /models/available to inspect current models and sizes.
- Use /models/pull to stream progress and diagnose download failures.
- Use /models/supported to see curated models plus any locally pulled ones.

**Section sources**
- [ollama.py:62-71](file://servers/fastapi/utils/ollama.py#L62-L71)
- [ollama.py:90-142](file://servers/fastapi/utils/ollama.py#L90-L142)
- [model_availability.py:205-215](file://servers/fastapi/utils/model_availability.py#L205-L215)
- [providerUtils.ts:286-332](file://servers/nextjs/utils/providerUtils.ts#L286-L332)

## Conclusion
Presenton’s Ollama integration provides a robust path to run local models with clear configuration, strong validation, and helpful tooling for model discovery and downloading. By leveraging the supported model catalog, streaming pull progress, and startup availability checks, users can reliably deploy local LLMs while maintaining resilience through URL fallbacks and informative error handling. For optimal performance, choose model sizes appropriate to your hardware and ensure Ollama is properly configured for your environment.