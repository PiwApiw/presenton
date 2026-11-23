# Export System

<cite>
**Referenced Files in This Document**
- [export_task_service.py](file://servers/fastapi/services/export_task_service.py)
- [export_utils.py](file://servers/fastapi/utils/export_utils.py)
- [pptx_font_utils.py](file://servers/fastapi/templates/pptx_font_utils.py)
- [fonts_and_slides_preview.py](file://servers/fastapi/templates/fonts_and_slides_preview.py)
- [export_handlers.ts](file://electron/app/ipc/export_handlers.ts)
- [export-chromium.ts](file://electron/app/utils/export-chromium.ts)
- [run-bundled-presentation-export.ts](file://servers/nxtjs/lib/run-bundled-presentation-export.ts)
- [route.ts](file://servers/nextjs/app/api/export-presentation/file/route.ts)
- [run-presentation-export.mjs](file://scripts/run-presentation-export.mjs)
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
This document explains Presenton’s export system that converts presentations into PowerPoint (PPTX) and PDF formats. It covers the end-to-end pipeline from slide data processing to final file generation, the Chromium-based rendering engine used for consistent output across platforms, font embedding and asset handling, asynchronous task management, progress and error handling strategies, customization options, template preservation, compatibility considerations, performance optimizations, and troubleshooting guidance.

The system is composed of:
- A FastAPI service layer that orchestrates exports and conversion tasks.
- An Electron desktop integration that spawns a Node.js export runtime with a pinned Chromium build.
- A Node.js export runtime entrypoint that performs rendering and file generation.
- Utilities for PPTX font analysis and slide preview rendering.
- Next.js API routes for serving exported files securely.

## Project Structure
The export system spans multiple layers:
- FastAPI services manage task execution, environment setup, security scoping, and result validation.
- Electron IPC handlers coordinate desktop-side spawning, logging, and download flow.
- The Node.js export runtime is invoked via a runner script and uses a bundled export-core package.
- Font utilities analyze PPTX content to determine required fonts and variants.
- Preview utilities convert PPTX layouts to images using the same rendering pipeline.
- Next.js provides secure endpoints for downloading generated exports.

```mermaid
graph TB
Client["Client or Desktop App"] --> FastAPI["FastAPI Service Layer"]
FastAPI --> Runtime["Node.js Export Runtime<br/>runner.mjs + export-core"]
Runtime --> Chromium["Chromium Rendering Engine"]
Runtime --> Output["Exported File<br/>PDF or PPTX"]
FastAPI --> Fonts["PPTX Font Utilities"]
FastAPI --> Preview["Slide Preview Renderer"]
NextJS["Next.js Export File Route"] --> Client
```

**Diagram sources**
- [export_task_service.py:122-201](file://servers/fastapi/services/export_task_service.py#L122-L201)
- [export_handlers.ts:74-111](file://electron/app/ipc/export_handlers.ts#L74-L111)
- [run-presentation-export.mjs:97-112](file://scripts/run-presentation-export.mjs#L97-L112)
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

**Section sources**
- [export_task_service.py:122-201](file://servers/fastapi/services/export_task_service.py#L122-L201)
- [export_handlers.ts:74-111](file://electron/app/ipc/export_handlers.ts#L74-L111)
- [run-presentation-export.mjs:97-112](file://scripts/run-presentation-export.mjs#L97-L112)
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

## Core Components
- ExportTaskService: Orchestrates all export operations, manages child process execution, validates outputs, scopes artifacts by owner, and ensures safe file permissions.
- Presentation export URL builder: Constructs presentation export URLs with optional FastAPI base URL and cookie headers for authenticated desktop flows.
- PPTX font utilities: Analyzes PPTX XML to extract used fonts, theme mappings, placeholders, chart fonts, and embedded font details.
- Slide preview renderer: Converts PPTX layouts to images using JSON-to-image rendering with font injection and dimension derivation.
- Electron export handlers: Spawn the export runtime, capture logs, handle errors, and move results to user downloads.
- Bundled export runtime resolver: Locates the runner script and checks availability of the bundled export-core package.
- Next.js export file route: Serves exported files with strict path validation and ownership checks.

**Section sources**
- [export_task_service.py:122-201](file://servers/fastapi/services/export_task_service.py#L122-L201)
- [export_utils.py:27-75](file://servers/fastapi/utils/export_utils.py#L27-L75)
- [pptx_font_utils.py:271-307](file://servers/fastapi/templates/pptx_font_utils.py#L271-L307)
- [fonts_and_slides_preview.py:763-831](file://servers/fastapi/templates/fonts_and_slides_preview.py#L763-L831)
- [export_handlers.ts:74-111](file://electron/app/ipc/export_handlers.ts#L74-L111)
- [run-bundled-presentation-export.ts:40-47](file://servers/nxtjs/lib/run-bundled-presentation-export.ts#L40-L47)
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

## Architecture Overview
The export pipeline follows a clear sequence:
1. Client or desktop app requests an export (PDF or PPTX).
2. FastAPI builds an export URL and invokes ExportTaskService.export_from_url.
3. ExportTaskService spawns the Node.js export runtime with a bounded child process, passing a task payload.
4. The runtime renders slides using Chromium and writes the final file to a scoped temp directory.
5. Results are validated, moved under the owner’s export directory, and made readable.
6. Next.js serves the exported file through a secure endpoint when requested.

```mermaid
sequenceDiagram
participant Client as "Client/Desktop"
participant FastAPI as "FastAPI Service"
participant Runtime as "Node.js Export Runtime"
participant Chromium as "Chromium"
participant FS as "Filesystem"
participant Next as "Next.js Route"
Client->>FastAPI : Request export (PDF/PPTX)
FastAPI->>FastAPI : Build export URL and cookie header
FastAPI->>Runtime : Spawn runner.mjs with task payload
Runtime->>Chromium : Render slides and assets
Chromium-->>Runtime : Rendered content
Runtime->>FS : Write exported file
Runtime-->>FastAPI : Response with file path
FastAPI->>FS : Move to owner-scoped exports dir
FastAPI-->>Client : Return export path
Client->>Next : GET /api/export-presentation/file?name=...
Next->>FS : Validate and serve file
FS-->>Next : File bytes
Next-->>Client : Download response
```

**Diagram sources**
- [export_utils.py:27-75](file://servers/fastapi/utils/export_utils.py#L27-L75)
- [export_task_service.py:420-453](file://servers/fastapi/services/export_task_service.py#L420-L453)
- [export_task_service.py:294-352](file://servers/fastapi/services/export_task_service.py#L294-L352)
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

## Detailed Component Analysis

### Export Task Service
ExportTaskService is the central orchestrator for all export operations. Responsibilities include:
- Resolving the export package root and runner entrypoint.
- Building Node.js environment variables for app data, temp directories, Puppeteer cache, and Chromium executable selection.
- Spawning bounded child processes with timeouts, capturing stdout/stderr safely, and validating return codes.
- Validating and resolving output paths within allowed roots (app data and temp directories).
- Scoping conversion artifacts per owner and rewriting asset URLs to backend-served paths.
- Moving final exports to the owner’s export directory and ensuring readable permissions.

Key methods and behaviors:
- _build_node_env: Sets APP_DATA_DIRECTORY, TEMP_DIRECTORY, PUPPETEER_TMP_DIR, PUPPETEER_CACHE_DIR, ASSETS_BASE_URL, and enforces Electron Chromium constraints.
- _run_bounded_child: Creates subprocesses with bounded text buffers, handles timeouts, kills processes on timeout, and returns structured results.
- export_from_url: Invokes the runtime with export parameters, resolves output, moves to owner scope, and sets permissions.
- convert_pptx_to_html: Converts PPTX to HTML with localized image assets and scoped artifact directories.
- render_html_to_image / render_json_to_image / render_jsons_to_images / render_htmls_to_images: Renders single or batch images with fallback logic for unsupported task types.
- convert_pptx_to_json: Converts PPTX to JSON layout representation with asset URL absolutization and scoping.
- _absolutize_conversion_asset_urls: Rewrites relative asset paths to backend-served URLs based on session and root naming.
- _move_export_to_owner: Moves exports into the owner-scoped directory while preventing path traversal and cross-user access.
- _scope_conversion_artifacts: Ensures conversion outputs reside under the correct owner-scoped path and rewrites internal references.

```mermaid
flowchart TD
Start(["Export Task Entry"]) --> EnsureRuntime["Ensure runtime and package exist"]
EnsureRuntime --> CreateTemp["Create owner-scoped temp directory"]
CreateTemp --> SpawnChild["Spawn Node.js runner with task payload"]
SpawnChild --> DrainStreams["Drain stdout/stderr into bounded buffers"]
DrainStreams --> CheckReturnCode{"Return code == 0?"}
CheckReturnCode --> |No| RaiseError["Raise HTTPException with stderr/stdout snippet"]
CheckReturnCode --> |Yes| ReadResponse["Read response JSON"]
ReadResponse --> ResolvePath["Resolve trusted output path"]
ResolvePath --> ScopeArtifacts["Scope conversion artifacts to owner"]
ScopeArtifacts --> MoveExport["Move export to owner directory"]
MoveExport --> SetPermissions["Set directory and file permissions"]
SetPermissions --> End(["Return export path"])
```

**Diagram sources**
- [export_task_service.py:203-222](file://servers/fastapi/services/export_task_service.py#L203-L222)
- [export_task_service.py:294-352](file://servers/fastapi/services/export_task_service.py#L294-L352)
- [export_task_service.py:771-802](file://servers/fastapi/services/export_task_service.py#L771-L802)
- [export_task_service.py:804-857](file://servers/fastapi/services/export_task_service.py#L804-L857)

**Section sources**
- [export_task_service.py:122-201](file://servers/fastapi/services/export_task_service.py#L122-L201)
- [export_task_service.py:294-352](file://servers/fastapi/services/export_task_service.py#L294-L352)
- [export_task_service.py:420-453](file://servers/fastapi/services/export_task_service.py#L420-L453)
- [export_task_service.py:455-517](file://servers/fastapi/services/export_task_service.py#L455-L517)
- [export_task_service.py:519-683](file://servers/fastapi/services/export_task_service.py#L519-L683)
- [export_task_service.py:685-724](file://servers/fastapi/services/export_task_service.py#L685-L724)
- [export_task_service.py:726-768](file://servers/fastapi/services/export_task_service.py#L726-L768)
- [export_task_service.py:771-857](file://servers/fastapi/services/export_task_service.py#L771-L857)

### Presentation Export URL Builder and Utility
The utility constructs export URLs for the PDF maker interface, optionally including FastAPI base URL and cookie headers for authenticated desktop sessions. It then calls ExportTaskService.export_from_url with sanitized filenames and memory logging.

```mermaid
sequenceDiagram
participant Caller as "Caller"
participant Utils as "export_utils"
participant Service as "ExportTaskService"
Caller->>Utils : export_presentation(id, title, format, cookie_header)
Utils->>Utils : Build export URL with fastapiUrl and cookie fragment
Utils->>Service : export_from_url(url, title, format, fastapi_url, cookie_header)
Service-->>Utils : PresentationExportTaskResult(path)
Utils-->>Caller : PresentationAndPath(presentation_id, path)
```

**Diagram sources**
- [export_utils.py:27-75](file://servers/fastapi/utils/export_utils.py#L27-L75)
- [export_task_service.py:420-453](file://servers/fastapi/services/export_task_service.py#L420-L453)

**Section sources**
- [export_utils.py:27-75](file://servers/fastapi/utils/export_utils.py#L27-L75)

### PPTX Font Utilities
These utilities analyze PPTX files to determine which fonts are used, including theme typefaces, placeholder styles, chart fonts, and embedded font metadata. They support:
- Extracting font names from OXML nodes.
- Mapping theme major/minor fonts.
- Collecting font variants (regular, bold, italic, bold_italic) from run properties and defaults.
- Iterating slide shapes, layouts, masters, and charts.
- Extracting embedded font details and handling corrupted or unreadable fonts gracefully.

```mermaid
classDiagram
class FontDetail {
+string file
+int size_bytes
+string error
+string family_name
+string full_name
+int weight_class
+string format
}
class PptxFontUtils {
+extract_used_fonts_from_pptx()
+extract_raw_fonts_and_embedded_details()
+extract_used_font_variants_from_pptx()
+normalize_font_family_name()
+get_static_font_catalog()
}
PptxFontUtils --> FontDetail : "produces"
```

**Diagram sources**
- [pptx_font_utils.py:39-74](file://servers/fastapi/templates/pptx_font_utils.py#L39-L74)
- [pptx_font_utils.py:271-307](file://servers/fastapi/templates/pptx_font_utils.py#L271-L307)
- [pptx_font_utils.py:365-800](file://servers/fastapi/templates/pptx_font_utils.py#L365-L800)

**Section sources**
- [pptx_font_utils.py:271-307](file://servers/fastapi/templates/pptx_font_utils.py#L271-L307)
- [pptx_font_utils.py:365-800](file://servers/fastapi/templates/pptx_font_utils.py#L365-L800)

### Slide Preview Renderer
The preview renderer converts PPTX layouts to images using the same rendering pipeline as exports:
- Derives canvas dimensions from PPTX slide size.
- Converts PPTX to JSON layouts via ExportTaskService.convert_pptx_to_json.
- Injects local font CSS and stylesheet URLs into the rendering task.
- Calls ExportTaskService.render_jsons_to_images with width/height and fonts.
- Validates that the number of rendered images matches the number of layouts.

```mermaid
flowchart TD
Start(["Render PPTX Slides to Images"]) --> Dimensions["Derive width/height from PPTX"]
Dimensions --> ConvertJSON["Convert PPTX to JSON layouts"]
ConvertJSON --> PrepareFonts["Prepare local font CSS and stylesheet URLs"]
PrepareFonts --> RenderImages["Call render_jsons_to_images(data, width, height, fonts)"]
RenderImages --> ValidateCount{"Image count matches layout count?"}
ValidateCount --> |No| RaiseError["Raise HTTPException"]
ValidateCount --> |Yes| ReturnPaths["Return list of image paths"]
```

**Diagram sources**
- [fonts_and_slides_preview.py:184-197](file://servers/fastapi/templates/fonts_and_slides_preview.py#L184-L197)
- [fonts_and_slides_preview.py:763-831](file://servers/fastapi/templates/fonts_and_slides_preview.py#L763-L831)
- [export_task_service.py:578-622](file://servers/fastapi/services/export_task_service.py#L578-L622)

**Section sources**
- [fonts_and_slides_preview.py:184-197](file://servers/fastapi/templates/fonts_and_slides_preview.py#L184-L197)
- [fonts_and_slides_preview.py:763-831](file://servers/fastapi/templates/fonts_and_slides_preview.py#L763-L831)

### Electron Export Handlers
Electron coordinates desktop-side export workflows:
- Builds the export URL with NEXT_PUBLIC_URL and optional NEXT_PUBLIC_FAST_API.
- Spawns the packaged runner.mjs with a task payload containing url, format, title, fastapiUrl, and cookieHeader.
- Captures stdout/stderr into bounded buffers, tracks process lifecycle, and logs breadcrumbs.
- Reads the response file, resolves the exported file path, moves it to the user’s downloads directory, and shows a background notification.
- Handles errors and records detailed diagnostics.

```mermaid
sequenceDiagram
participant UI as "Desktop UI"
participant IPC as "Electron IPC"
participant Runner as "runner.mjs"
participant FS as "Downloads Dir"
UI->>IPC : Trigger export (id, title, format)
IPC->>Runner : Spawn with task payload
Runner-->>IPC : Write response.json with file path
IPC->>FS : Move exported file to downloads
IPC-->>UI : Success message and breadcrumb
```

**Diagram sources**
- [export_handlers.ts:74-111](file://electron/app/ipc/export_handlers.ts#L74-L111)
- [export_handlers.ts:141-175](file://electron/app/ipc/export_handlers.ts#L141-L175)
- [export_handlers.ts:358-442](file://electron/app/ipc/export_handlers.ts#L358-L442)

**Section sources**
- [export_handlers.ts:74-111](file://electron/app/ipc/export_handlers.ts#L74-L111)
- [export_handlers.ts:141-175](file://electron/app/ipc/export_handlers.ts#L141-L175)
- [export_handlers.ts:358-442](file://electron/app/ipc/export_handlers.ts#L358-L442)

### Chromium Configuration and Bundled Runtime
The Electron side selects a pinned Chromium build for consistent rendering:
- Uses environment variables and packaged metadata to resolve browser type and build ID.
- Falls back to checked-in pins for development or partially packaged trees.
- Ensures the bundled export-core package exists and is synchronized during build.

```mermaid
flowchart TD
Config["resolveExportBrowserConfig()"] --> EnvCheck{"Environment or package metadata set?"}
EnvCheck --> |Yes| UseBuildId["Use configured or packaged build ID"]
EnvCheck --> |No| Fallback["Fallback to checked-in macOS pins"]
UseBuildId --> Runtime["Bundled Chromium runtime"]
Fallback --> Runtime
```

**Diagram sources**
- [export-chromium.ts:42-62](file://electron/app/utils/export-chromium.ts#L42-L62)
- [run-bundled-presentation-export.ts:40-47](file://servers/nxtjs/lib/run-bundled-presentation-export.ts#L40-L47)

**Section sources**
- [export-chromium.ts:42-62](file://electron/app/utils/export-chromium.ts#L42-L62)
- [run-bundled-presentation-export.ts:40-47](file://servers/nxtjs/lib/run-bundled-presentation-export.ts#L40-L47)

### Next.js Export File Route
The Next.js route serves exported files securely:
- Requires APP_DATA_DIRECTORY to be set.
- Validates the requested filename against path traversal patterns.
- Enforces ownership rules for user-scoped exports.
- Returns appropriate MIME types for PDF, PPTX, and ZIP.

```mermaid
flowchart TD
Request["GET /api/export-presentation/file?name=..."] --> ValidateName["Validate name parameter"]
ValidateName --> OwnershipCheck{"Ownership allowed?"}
OwnershipCheck --> |No| Deny["Return null or error"]
OwnershipCheck --> |Yes| Serve["Serve file with correct MIME type"]
```

**Diagram sources**
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

**Section sources**
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

## Dependency Analysis
The export system has clear boundaries and dependencies:
- FastAPI depends on ExportTaskService for orchestration and on font utilities for analysis.
- Electron IPC depends on the packaged runner.mjs and export-core package.
- The Node.js runtime depends on Chromium for rendering and writes files to scoped directories.
- Next.js depends on filesystem access and environment configuration to serve exports.

```mermaid
graph LR
FastAPI["FastAPI Services"] --> ExportTaskService["ExportTaskService"]
FastAPI --> FontUtils["PPTX Font Utilities"]
Electron["Electron IPC"] --> Runner["runner.mjs"]
Runner --> ExportCore["@presenton/export-core"]
Runner --> Chromium["Chromium"]
NextJS["Next.js Route"] --> FS["Filesystem"]
```

**Diagram sources**
- [export_task_service.py:122-201](file://servers/fastapi/services/export_task_service.py#L122-L201)
- [export_handlers.ts:102-111](file://electron/app/ipc/export_handlers.ts#L102-L111)
- [run-presentation-export.mjs:97-112](file://scripts/run-presentation-export.mjs#L97-L112)
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

**Section sources**
- [export_task_service.py:122-201](file://servers/fastapi/services/export_task_service.py#L122-L201)
- [export_handlers.ts:102-111](file://electron/app/ipc/export_handlers.ts#L102-L111)
- [run-presentation-export.mjs:97-112](file://scripts/run-presentation-export.mjs#L97-L112)
- [route.ts:14-48](file://servers/nextjs/app/api/export-presentation/file/route.ts#L14-L48)

## Performance Considerations
- Bounded child processes: Subprocess stdout/stderr are drained into bounded buffers to prevent unbounded memory growth.
- Timeout enforcement: Child processes are killed after a configurable timeout to avoid hanging exports.
- Memory logging: Memory snapshots are logged around spawn and exit points for observability.
- Batch rendering: JSON-to-images and HTML-to-images support batch rendering to reduce overhead; fallback logic ensures robustness if batch tasks are unavailable.
- Asset localization: Image assets are converted to data URIs when needed to avoid network calls during headless rendering.
- Owner scoping: Conversion artifacts are moved to owner-scoped directories to minimize contention and improve cleanup.
- Permission hardening: Output directories and files are set to restrictive modes to prevent unintended access.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Export runtime not found: Ensure runner.mjs and export-core dist/index.js exist at the resolved export directory.
- Invalid JSON output: Validate that the runtime produces well-formed JSON responses; check stderr/stdout snippets for errors.
- Path outside allowed roots: Outputs must reside under APP_DATA_DIRECTORY or TEMP_DIRECTORY; verify scoping logic and environment variables.
- Missing APP_DATA_DIRECTORY: Required for PPTX-to-HTML export and conversion artifacts; ensure it is set before invoking exports.
- Electron Chromium unavailable: In Electron mode, a pinned Chromium executable must be present; otherwise, the export refuses to proceed.
- HTML-to-images fallback: If batch HTML-to-images is unavailable or fails, the service falls back to one task per HTML document.
- File permission errors: After export completion, the service attempts to set directory and file permissions; failures raise HTTP exceptions.

**Section sources**
- [export_task_service.py:203-222](file://servers/fastapi/services/export_task_service.py#L203-L222)
- [export_task_service.py:323-350](file://servers/fastapi/services/export_task_service.py#L323-L350)
- [export_task_service.py:243-267](file://servers/fastapi/services/export_task_service.py#L243-L267)
- [export_task_service.py:154-201](file://servers/fastapi/services/export_task_service.py#L154-L201)
- [export_task_service.py:624-683](file://servers/fastapi/services/export_task_service.py#L624-L683)
- [export_task_service.py:269-278](file://servers/fastapi/services/export_task_service.py#L269-L278)

## Conclusion
Presenton’s export system provides a robust, secure, and consistent pipeline for generating PDF and PPTX exports. It leverages a bounded Node.js runtime with pinned Chromium for reliable rendering, comprehensive font analysis for accurate typography, and strict filesystem scoping for multi-user safety. The architecture supports batch rendering, fallback mechanisms, and detailed diagnostics, making it suitable for large presentations and diverse deployment environments. Proper configuration of environment variables, runtime packages, and Chromium binaries is essential for optimal performance and reliability.

[No sources needed since this section summarizes without analyzing specific files]