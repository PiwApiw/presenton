# Streaming Response Handling

<cite>
**Referenced Files in This Document**
- [sse_response.py](file://servers/fastapi/models/sse_response.py)
- [sse.py](file://servers/fastapi/utils/sse.py)
- [outlines.py](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py)
- [presentation.py](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py)
- [useOutlineStreaming.ts](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts)
- [usePresentationStreaming.ts](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts)
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
This document explains how Server-Sent Events streaming responses are used during presentation generation. It covers the SSE schema models, the server-side streaming endpoints for outline and slide generation, the client-side event handling patterns, error recovery strategies, and the `safe_sse_stream` utility that ensures reliable event delivery.

The goal is to help both backend developers and frontend engineers understand:
- What event types are emitted.
- How payloads evolve from initial status through incremental chunks to a final completion payload.
- How errors are surfaced and recovered from.
- How clients should parse, merge, and finalize streamed data.

## Project Structure
The streaming implementation spans FastAPI backend models, utilities, API endpoints, and Next.js hooks:

```mermaid
graph TB
subgraph "FastAPI Backend"
SSEModels["SSE Models<br/>models/sse_response.py"]
SSEReceiver["Safe Stream Utility<br/>utils/sse.py"]
OutlineEndpoint["Outline Streaming Endpoint<br/>api/v1/ppt/endpoints/outlines.py"]
PresentationEndpoint["Presentation Streaming Endpoint<br/>api/v1/ppt/endpoints/presentation.py"]
end
subgraph "Next.js Frontend"
OutlineHook["Outline Streaming Hook<br/>hooks/useOutlineStreaming.ts"]
PresentationHook["Presentation Streaming Hook<br/>hooks/usePresentationStreaming.ts"]
end
OutlineEndpoint --> SSEModels
PresentationEndpoint --> SSEModels
OutlineEndpoint --> SSEReceiver
PresentationEndpoint --> SSEReceiver
OutlineHook --> OutlineEndpoint
PresentationHook --> PresentationEndpoint
```

**Diagram sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)
- [sse.py:10-38](file://servers/fastapi/utils/sse.py#L10-L38)
- [outlines.py:84-276](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L84-L276)
- [presentation.py:2320-2485](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L2320-L2485)
- [useOutlineStreaming.ts:105-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L105-L243)
- [usePresentationStreaming.ts:298-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L298-L489)

**Section sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)
- [sse.py:10-38](file://servers/fastapi/utils/sse.py#L10-L38)
- [outlines.py:84-276](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L84-L276)
- [presentation.py:2320-2485](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L2320-L2485)
- [useOutlineStreaming.ts:105-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L105-L243)
- [usePresentationStreaming.ts:298-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L298-L489)

## Core Components
The core SSE components define the wire format and safe delivery guarantees:

- **SSEResponse**: Base model that serializes an SSE frame with `event` and `data`.
- **SSEStatusResponse**: Emits a typed status update.
- **SSETraceResponse**: Emits optional trace information.
- **SSEErrorResponse**: Emits structured error information, including optional metadata such as source, HTTP status code, error type, retryability, and slide progress.
- **SSECompleteResponse**: Emits the final result payload under a dynamic key.

These models all serialize into standard SSE frames using the `to_string()` method.

```mermaid
classDiagram
class SSEResponse {
+string event
+string data
+to_string() string
}
class SSEStatusResponse {
+string status
+to_string() string
}
class SSETraceResponse {
+object trace
+to_string() string
}
class SSEErrorResponse {
+string detail
+string source
+int status_code
+string error_type
+bool retryable
+int completed_slides
+int total_slides
+to_string() string
}
class SSECompleteResponse {
+string key
+object value
+to_string() string
}
SSEStatusResponse --> SSEResponse : "serializes to"
SSETraceResponse --> SSEResponse : "serializes to"
SSEErrorResponse --> SSEResponse : "serializes to"
SSECompleteResponse --> SSEResponse : "serializes to"
```

**Diagram sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)

**Section sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)

## Architecture Overview
The streaming architecture connects FastAPI endpoints to Next.js hooks via SSE:

```mermaid
sequenceDiagram
participant Client as "Next.js Hook"
participant FastAPI as "FastAPI Endpoint"
participant LLM as "LLM / Slide Generation"
participant DB as "Database"
Client->>FastAPI : "GET /api/v1/ppt/outlines/stream/{id}"
FastAPI->>Client : "status : Preparing your presentation outline"
FastAPI->>LLM : "generate_ppt_outline(...)"
LLM-->>FastAPI : "OutlineGenerationStatus"
FastAPI->>Client : "status message"
LLM-->>FastAPI : "partial JSON chunk"
FastAPI->>Client : "chunk : partial outline JSON"
FastAPI->>DB : "normalize and persist outlines"
FastAPI->>Client : "complete : presentation with outlines"
Client->>FastAPI : "GET /api/v1/ppt/presentation/stream/{id}"
FastAPI->>Client : "chunk : slides array start"
FastAPI->>LLM : "get_slide_content_from_type_and_outline(...)"
LLM-->>FastAPI : "slide content"
FastAPI->>Client : "chunk : slide JSON"
FastAPI->>Client : "slide_assets : slide index and updated slide"
FastAPI->>DB : "persist slides and assets"
FastAPI->>Client : "complete : full presentation with slides"
```

**Diagram sources**
- [outlines.py:112-263](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L112-L263)
- [presentation.py:2320-2472](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L2320-L2472)

**Section sources**
- [outlines.py:112-263](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L112-L263)
- [presentation.py:2320-2472](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L2320-L2472)

## Detailed Component Analysis

### SSE Schema Models
The SSE schema models define the typed events sent over the stream:

| Model | Purpose | Key Fields | Payload Type Field |
|---|---|---|---|
| `SSEResponse` | Base SSE frame serializer | `event`, `data` | N/A |
| `SSEStatusResponse` | Progress/status updates | `status` | `type: "status"` |
| `SSETraceResponse` | Optional tracing/debug info | `trace` | `type: "trace"` |
| `SSEErrorResponse` | Error reporting | `detail`, optional `source`, `status_code`, `error_type`, `retryable`, `completed_slides`, `total_slides` | `type: "error"` |
| `SSECompleteResponse` | Final result | `key`, `value` | `type: "complete"` |

All models serialize to an SSE frame where the `data` field contains a JSON object with a `type` discriminator. The `SSECompleteResponse` uses a dynamic key so callers can attach different final payloads (for example, `presentation`).

**Section sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)

### Safe SSE Stream Utility
The `safe_sse_stream` utility wraps an async generator and provides:

- Graceful handling of client cancellation.
- Logging when the stream fails after response has started.
- Optional cleanup callback execution on error.
- Conversion of exceptions into a structured `SSEErrorResponse`.
- Optional structured metadata injection via `error_metadata`.

```mermaid
flowchart TD
Start(["Start safe_sse_stream"]) --> Iterate["Iterate over async stream"]
Iterate --> Chunk{"Chunk available?"}
Chunk --> |Yes| Yield["Yield chunk to client"]
Yield --> Iterate
Chunk --> |No| End(["Stream finished"])
Iterate --> Cancelled{"Cancelled by client?"}
Cancelled --> |Yes| LogCancel["Log cancellation"] --> End
Cancelled --> |No| Exception{"Exception occurred?"}
Exception --> |Yes| Cleanup["Run optional on_error cleanup"]
Cleanup --> Metadata["Build error metadata if provided"]
Metadata --> EmitError["Emit SSEErrorResponse"]
EmitError --> End
Exception --> |No| Iterate
```

**Diagram sources**
- [sse.py:10-38](file://servers/fastapi/utils/sse.py#L10-L38)

**Section sources**
- [sse.py:10-38](file://servers/fastapi/utils/sse.py#L10-L38)

### Outline Streaming Endpoint
The outline streaming endpoint performs these steps:

1. Loads the presentation and prepares web search configuration.
2. Creates a temporary directory and loads additional documents when present.
3. Builds outline messages and stores generation context.
4. Streams outline generation results:
   - Emits `SSEStatusResponse` for status updates.
   - Emits `SSEErrorResponse` for explicit HTTP exceptions.
   - Emits `SSEResponse` with `type: "chunk"` containing partial JSON.
5. Parses accumulated text into JSON, normalizes it, validates slide count, trims overshoot, persists outlines, and emits `SSECompleteResponse` with the updated presentation.

```mermaid
sequenceDiagram
participant Client as "Frontend"
participant Outlines as "Outline Endpoint"
participant Docs as "Documents Loader"
participant Memory as "Memory Service"
participant LLM as "Outline Generator"
participant DB as "Database"
Client->>Outlines : "stream_outlines(id)"
Outlines->>Outlines : "prepare temp dir and web search config"
Outlines->>Docs : "load_documents(temp_dir)"
Docs-->>Outlines : "documents"
Outlines->>Memory : "store_generation_context(...)"
Outlines->>LLM : "generate_ppt_outline(...)"
LLM-->>Outlines : "OutlineGenerationStatus"
Outlines->>Client : "SSEStatusResponse(status)"
LLM-->>Outlines : "partial JSON chunk"
Outlines->>Client : "SSEResponse(type=chunk)"
Outlines->>Outlines : "accumulate and parse JSON"
Outlines->>DB : "normalize, validate, persist outlines"
Outlines->>Client : "SSECompleteResponse(key=presentation)"
```

**Diagram sources**
- [outlines.py:112-263](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L112-L263)

**Section sources**
- [outlines.py:112-263](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L112-L263)

### Presentation Streaming Endpoint
The presentation streaming endpoint generates slides and their assets:

1. Emits a chunk opening the slides array.
2. For each slide:
   - Generates slide content.
   - Creates a slide model.
   - Adds placeholder assets and applies template UI.
   - Starts asset generation tasks concurrently.
   - Emits a chunk with the slide JSON.
   - Emits `slide_assets` events as assets finish.
3. Waits for remaining asset events.
4. Gathers generated assets and persists slides and assets.
5. Emits `SSECompleteResponse` with the full presentation including slides.

```mermaid
sequenceDiagram
participant Client as "Frontend"
participant Presentation as "Presentation Endpoint"
participant SlideGen as "Slide Content Generator"
participant Assets as "Asset Tasks"
participant DB as "Database"
Client->>Presentation : "stream_presentation(id)"
Presentation->>Client : "chunk : slides array start"
loop For each slide
Presentation->>SlideGen : "get_slide_content_from_type_and_outline(...)"
SlideGen-->>Presentation : "slide content"
Presentation->>Assets : "create_task(process_slide_and_fetch_assets)"
Presentation->>Client : "chunk : slide JSON"
Assets-->>Presentation : "asset task done"
Presentation->>Client : "slide_assets : slide_index, slide, warnings"
end
Presentation->>DB : "delete old slides, commit new slides and assets"
Presentation->>Client : "complete : full presentation"
```

**Diagram sources**
- [presentation.py:2320-2472](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L2320-L2472)

**Section sources**
- [presentation.py:2320-2472](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L2320-L2472)

### Client-Side Handling Patterns

#### Outline Streaming Hook
The outline streaming hook:

- Connects via `EventSource` to `/api/v1/ppt/outlines/stream/{presentationId}`.
- Listens for the `response` event.
- Parses JSON payloads and dispatches state updates.
- Handles:
  - `status`: updates user-facing status message.
  - `chunk`: accumulates partial JSON, repairs it, parses, limits outlines, and updates the store.
  - `complete`: finalizes outlines, stops streaming, and closes the connection.
  - `error`: triggers retry logic or authentication reflow.
- Implements retry with exponential backoff and connection error handling.

```mermaid
flowchart TD
Open["Open EventSource"] --> Listen["Listen for 'response' event"]
Listen --> Parse["Parse JSON payload"]
Parse --> Valid{"Valid JSON?"}
Valid --> |No| Retry["scheduleRetry(reason)"]
Retry --> Reconnect{"Retry allowed?"}
Reconnect --> |Yes| Open
Reconnect --> |No| Fail["Reset state and notify error"]
Valid --> Dispatch["Dispatch by data.type"]
Dispatch --> Status{"type=status"}
Status --> UpdateStatus["Update statusMessage"]
Dispatch --> Chunk{"type=chunk"}
Chunk --> Accumulate["Accumulate partial JSON"]
Accumulate --> Repair["Repair and parse JSON"]
Repair --> UpdateOutlines["Limit and dispatch outlines"]
Dispatch --> Complete{"type=complete"}
Complete --> Finalize["Finalize outlines and close stream"]
Dispatch --> Error{"type=error"}
Error --> HandleError["Handle auth or retry"]
```

**Diagram sources**
- [useOutlineStreaming.ts:105-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L105-L243)

**Section sources**
- [useOutlineStreaming.ts:105-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L105-L243)

#### Presentation Streaming Hook
The presentation streaming hook:

- Connects via `EventSource` to `/api/v1/ppt/presentation/stream/{presentationId}`.
- Parses JSON payloads and handles multiple event types:
  - `generation_metrics`: updates token usage and timing metrics.
  - `fonts`: updates fonts in presentation data.
  - `slide_html`: merges incoming slide HTML and normalized slide data.
  - `chunk`: accumulates partial JSON, parses streamed slide objects, merges slides, and may preload template V2 presentation data.
  - `complete`: finalizes the presentation.
  - `error`: triggers retry logic or failure finalization.
- Uses JSON repair and careful merging to preserve resolved assets while updating slides incrementally.

```mermaid
flowchart TD
Open["Open EventSource"] --> Listen["Listen for 'response' event"]
Listen --> Parse["Parse JSON payload"]
Parse --> Metrics{"type=generation_metrics"}
Metrics --> UpdateMetrics["Update generation metrics"]
Parse --> Fonts{"type=fonts"}
Fonts --> UpdateFonts["Update presentation fonts"]
Parse --> SlideHTML{"type=slide_html"}
SlideHTML --> MergeSlide["Normalize and merge slide"]
Parse --> Chunk{"type=chunk"}
Chunk --> Accumulate["Accumulate partial JSON"]
Accumulate --> ParseSlide["Parse streamed slide chunk"]
ParseSlide --> MergeSlides["Merge slides and update store"]
Parse --> Complete{"type=complete"}
Complete --> Finalize["Finalize presentation"]
Parse --> Error{"type=error"}
Error --> RetryOrFail["Retry or finalize failure"]
```

**Diagram sources**
- [usePresentationStreaming.ts:298-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L298-L489)

**Section sources**
- [usePresentationStreaming.ts:298-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L298-L489)

## Dependency Analysis
The streaming pipeline depends on several modules:

```mermaid
graph LR
SSEModels["models/sse_response.py"] --> Outlines["api/v1/ppt/endpoints/outlines.py"]
SSEModels --> Presentation["api/v1/ppt/endpoints/presentation.py"]
SSEReceiver["utils/sse.py"] --> Outlines
SSEReceiver --> Presentation
Outlines --> OutlineHook["hooks/useOutlineStreaming.ts"]
Presentation --> PresentationHook["hooks/usePresentationStreaming.ts"]
```

**Diagram sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)
- [sse.py:10-38](file://servers/fastapi/utils/sse.py#L10-L38)
- [outlines.py:14-37](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L14-L37)
- [presentation.py:60-98](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L60-L98)
- [useOutlineStreaming.ts:105-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L105-L243)
- [usePresentationStreaming.ts:298-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L298-L489)

**Section sources**
- [sse_response.py:6-56](file://servers/fastapi/models/sse_response.py#L6-L56)
- [sse.py:10-38](file://servers/fastapi/utils/sse.py#L10-L38)
- [outlines.py:14-37](file://servers/fastapi/api/v1/ppt/endpoints/outlines.py#L14-L37)
- [presentation.py:60-98](file://servers/fastapi/api/v1/ppt/endpoints/presentation.py#L60-L98)
- [useOutlineStreaming.ts:105-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L105-L243)
- [usePresentationStreaming.ts:298-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L298-L489)

## Performance Considerations
- **Incremental rendering**: Both outline and presentation streams emit partial data so the UI can render progressively rather than waiting for the entire result.
- **Concurrent asset generation**: Slide asset generation runs in parallel with slide content generation, improving throughput.
- **JSON repair**: The frontend uses JSON repair to tolerate incomplete JSON fragments during streaming.
- **Backpressure awareness**: The outline endpoint yields control to the event loop between chunks to avoid blocking.
- **Metadata tracking**: Generation metrics allow the frontend to track token usage and performance without polling.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and recommended handling:

- **Invalid SSE payload**:
  - Cause: Malformed JSON in the `data` field.
  - Action: Retry with backoff; if retries exhausted, reset state and show an error.
  - Evidence: Both outline and presentation hooks implement retry logic around JSON parsing failures.

- **Connection lost**:
  - Cause: Network interruption or server restart.
  - Action: Use `EventSource.onerror` to schedule retry; reset accumulated state only when necessary.

- **Server error during streaming**:
  - Cause: LLM provider failure, validation error, or unexpected exception.
  - Action: Parse `type: "error"` payload; use `retryable` and `source` fields to decide whether to retry or fail fast.
  - Evidence: `SSEErrorResponse` includes structured fields like `source`, `status_code`, `error_type`, `retryable`, and slide progress.

- **Incomplete outline JSON**:
  - Cause: LLM output arrives incrementally.
  - Action: Accumulate chunks, repair JSON, and parse only when valid; continue accumulating otherwise.
  - Evidence: Outline hook accumulates chunks and uses JSON repair before parsing.

- **Missing or partial slide assets**:
  - Cause: Asset generation fails or takes longer than slide content generation.
  - Action: Track `slide_assets` events per slide index; merge updated slides and warnings; finalize after all assets are received.
  - Evidence: Presentation endpoint emits `slide_assets` events and tracks warnings per slide.

**Section sources**
- [useOutlineStreaming.ts:111-243](file://servers/nexjs/app/(presentation-generator)/outline/hooks/useOutlineStreaming.ts#L111-L243)
- [usePresentationStreaming.ts:304-489](file://servers/nextjs/app/(presentation-generator)/presentation/hooks/usePresentationStreaming.ts#L304-L489)
- [sse_response.py:32-45](file://servers/fastapi/models/sse_response.py#L32-L45)
- [sse.py:24-38](file://servers/fastapi/utils/sse.py#L24-L38)

## Conclusion
The streaming response system combines typed SSE models, robust error handling, and incremental client updates to deliver a responsive presentation generation experience. The `safe_sse_stream` utility ensures that errors are converted into structured events and that cleanup happens reliably. Clients handle status updates, partial chunks, asset updates, and final completion, with retry and recovery strategies for resilience.

[No sources needed since this section summarizes without analyzing specific files]