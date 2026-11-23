# Asynchronous Task Processing

<cite>
**Referenced Files in This Document**
- [router.py](file://servers/fastapi/api/v1/async_tasks/router.py)
- [async_task.py](file://servers/fastapi/models/sql/async_task.py)
- [async_task_status.py](file://servers/fastapi/enums/async_task_status.py)
- [async_tasks.py](file://servers/fastapi/services/async_tasks.py)
- [export_task_service.py](file://servers/fastapi/services/export_task_service.py)
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
This document explains the asynchronous task processing system used for long-running operations such as presentation exports and conversions. It covers the full lifecycle from task submission to completion, including job queuing via database persistence, status tracking, progress monitoring through polling, payload structure and validation, error handling patterns, execution pipeline details, timeout management, resource cleanup, and API endpoints for managing tasks.

## Project Structure
The asynchronous task subsystem is implemented in the FastAPI backend:
- API router exposes endpoints for listing and checking async task status.
- A SQL model persists task metadata and results.
- An enum defines allowed task statuses.
- A service provides recovery logic for interrupted background jobs.
- A dedicated export service orchestrates external Node-based export workloads with strict timeouts and secure path handling.

```mermaid
graph TB
Client["Client"] --> API["FastAPI Async Tasks Router"]
API --> DB["AsyncTaskModel (SQLAlchemy/SQLModel)"]
API --> Recovery["Interrupted Task Recovery Service"]
API --> ExportSvc["Export Task Service"]
ExportSvc --> Runtime["Node Export Runtime"]
```

**Diagram sources**
- [router.py:14-84](file://servers/fastapi/api/v1/async_tasks/router.py#L14-L84)
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)
- [export_task_service.py:122-128](file://servers/fastapi/services/export_task_service.py#L122-L128)

**Section sources**
- [router.py:14-84](file://servers/fastapi/api/v1/async_tasks/router.py#L14-L84)
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)
- [async_task_status.py:4-7](file://servers/fastapi/enums/async_task_status.py#L4-L7)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)
- [export_task_service.py:122-128](file://servers/fastapi/services/export_task_service.py#L122-L128)

## Core Components
- Async Task API Router: Provides endpoints to list tasks and check a task’s current status.
- Async Task Model: Defines the persistent schema for tasks, including identifiers, owner, type, status, message, error, data, payload, and timestamps.
- Async Task Status Enum: Enumerates allowed statuses for tasks.
- Interrupted Task Recovery Service: Marks pending tasks as failed when the server restarts before they complete.
- Export Task Service: Executes external export/conversion workloads with bounded timeouts, secure path resolution, and output scoping.

Key responsibilities:
- Expose stable REST endpoints for clients to poll task state.
- Persist task metadata and results for durability across restarts.
- Ensure safe execution boundaries for external processes.
- Provide robust error reporting and recovery mechanisms.

**Section sources**
- [router.py:14-84](file://servers/fastapi/api/v1/async_tasks/router.py#L14-L84)
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)
- [async_task_status.py:4-7](file://servers/fastapi/enums/async_task_status.py#L4-L7)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)
- [export_task_service.py:122-128](file://servers/fastapi/services/export_task_service.py#L122-L128)

## Architecture Overview
The asynchronous task architecture combines a simple polling model with durable persistence and secure process execution:

```mermaid
sequenceDiagram
participant Client as "Client"
participant API as "Async Tasks Router"
participant DB as "AsyncTaskModel"
participant Recovery as "Recovery Service"
participant Export as "Export Task Service"
participant Runtime as "Node Export Runtime"
Client->>API : Submit long-running task (external flow)
Note over Client,API : Submission typically occurs via other APIs that create AsyncTaskModel rows
Client->>API : GET /api/v1/async-tasks/status/{id}
API->>DB : Read task by id
DB-->>API : Task record
API-->>Client : Task status + data (with resolved links)
Client->>API : GET /api/v1/async-tasks?type=...&status=...
API->>DB : Query filtered/paginated tasks
DB-->>API : List of tasks
API-->>Client : Paginated task list
API->>Recovery : On startup, fail interrupted PENDING tasks
Recovery->>DB : Update interrupted tasks to ERROR
```

**Diagram sources**
- [router.py:20-84](file://servers/fastapi/api/v1/async_tasks/router.py#L20-L84)
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)

## Detailed Component Analysis

### Async Task API Router
Responsibilities:
- List tasks with filtering by type, status, creation time range, ordering, pagination.
- Retrieve a single task by ID and return its current state.
- Transform result URLs into absolute MCP links where applicable.

Key behaviors:
- Filtering supports type, status, created_at_from/created_at_to aliases.
- Ordering supports created_at or updated_at, ascending or descending.
- Pagination uses limit and offset with enforced bounds.
- Single-task endpoint returns the serialized model and resolves any embedded data links.

```mermaid
flowchart TD
Start(["Request"]) --> CheckList{"Is request for list?"}
CheckList --> |Yes| BuildQuery["Build query with filters<br/>type, status, created_at_from/to,<br/>order_by, order, limit, offset"]
BuildQuery --> ExecuteList["Execute SELECT on AsyncTaskModel"]
ExecuteList --> ReturnList["Return list[AsyncTaskModel]"]
CheckList --> |No| GetStatus["GET /status/{id}"]
GetStatus --> LoadTask["Load task by id"]
LoadTask --> Exists{"Task exists?"}
Exists --> |No| NotFound["HTTP 404 No async task found"]
Exists --> |Yes| Serialize["Serialize model<br/>resolve data links"]
Serialize --> ReturnTask["Return AsyncTaskModel"]
```

**Diagram sources**
- [router.py:20-84](file://servers/fastapi/api/v1/async_tasks/router.py#L20-L84)

**Section sources**
- [router.py:20-84](file://servers/fastapi/api/v1/async_tasks/router.py#L20-L84)

### Async Task Model
Responsibilities:
- Define the persistent representation of an asynchronous task.
- Provide default values for IDs and timestamps.
- Include fields for task metadata, payload, and result data.
- Serialize status consistently for JSON responses.

Important fields:
- id: Unique task identifier.
- owner_id: Optional owner reference for isolation.
- type: Task category/type string.
- status: Current lifecycle state.
- message: Human-readable status message.
- error: Structured error information.
- data: Result payload (e.g., exported file references).
- payload: Original task input (excluded from serialization).
- created_at/updated_at: Timestamps for lifecycle tracking.

```mermaid
classDiagram
class AsyncTaskModel {
+string id
+uuid owner_id
+string type
+string status
+string message
+dict error
+dict data
+dict payload
+datetime created_at
+datetime updated_at
+serialize_status(status) string
}
```

**Diagram sources**
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)

**Section sources**
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)

### Async Task Status Enum
Responsibilities:
- Define the canonical set of task states.

States:
- pending: Task has been submitted but not yet started.
- completed: Task finished successfully.
- error: Task failed with recorded error details.

```mermaid
stateDiagram-v2
[*] --> pending
pending --> completed : "success"
pending --> error : "failure"
completed --> [*]
error --> [*]
```

**Diagram sources**
- [async_task_status.py:4-7](file://servers/fastapi/enums/async_task_status.py#L4-L7)

**Section sources**
- [async_task_status.py:4-7](file://servers/fastapi/enums/async_task_status.py#L4-L7)

### Interrupted Task Recovery Service
Responsibilities:
- Detect tasks left in pending state after a server restart.
- Mark them as failed with a specific error detail so clients can stop polling.

Behavior:
- Queries all tasks with status pending.
- Updates each to error with a standardized error object and timestamp.
- Commits changes and logs the number of recovered tasks.

```mermaid
flowchart TD
Start(["Startup Recovery"]) --> QueryPending["Select tasks where status = pending"]
QueryPending --> HasTasks{"Any pending tasks?"}
HasTasks --> |No| End(["Done"])
HasTasks --> |Yes| MarkError["Set status = error<br/>set message and error details<br/>update timestamp"]
MarkError --> Commit["Commit session"]
Commit --> Log["Log count of interrupted tasks"]
Log --> End
```

**Diagram sources**
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)

**Section sources**
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)

### Export Task Service
Responsibilities:
- Orchestrate external Node-based export/conversion workloads securely.
- Enforce timeouts, validate outputs, scope artifacts per owner, and ensure readable permissions.
- Provide high-level methods for URL export, PPTX conversion, HTML/image rendering, and batch image generation.

Key capabilities:
- Timeout enforcement via bounded subprocess execution.
- Secure path resolution to prevent arbitrary filesystem access.
- Owner-scoped artifact directories and URL rewriting.
- Fallback strategies for unsupported runtime features.
- Environment setup for app data, temp directories, and Puppeteer cache.

```mermaid
flowchart TD
Entry(["Export Task Service Method"]) --> Validate["Validate inputs and dimensions"]
Validate --> EnsureRuntime["Ensure runtime entrypoint and package exist"]
EnsureRuntime --> CreateTemp["Create owner-scoped temp directory"]
CreateTemp --> Spawn["Spawn Node process with bounded env and timeout"]
Spawn --> Monitor["Monitor stdout/stderr with bounded buffers"]
Monitor --> TimeoutCheck{"Timed out?"}
TimeoutCheck --> |Yes| Kill["Kill process and raise timeout error"]
TimeoutCheck --> |No| ParseOutput["Parse response JSON and resolve output path"]
ParseOutput --> ScopeArtifacts["Scope artifacts to owner and rewrite paths"]
ScopeArtifacts --> Permissions["Ensure output directory/file permissions"]
Permissions --> Return(["Return result paths"])
```

**Diagram sources**
- [export_task_service.py:294-418](file://servers/fastapi/services/export_task_service.py#L294-L418)
- [export_task_service.py:420-453](file://servers/fastapi/services/export_task_service.py#L420-L453)
- [export_task_service.py:519-576](file://servers/fastapi/services/export_task_service.py#L519-L576)
- [export_task_service.py:578-683](file://servers/fastapi/services/export_task_service.py#L578-L683)
- [export_task_service.py:685-724](file://servers/fastapi/services/export_task_service.py#L685-L724)
- [export_task_service.py:726-857](file://servers/fastapi/services/export_task_service.py#L726-L857)

**Section sources**
- [export_task_service.py:122-128](file://servers/fastapi/services/export_task_service.py#L122-L128)
- [export_task_service.py:294-418](file://servers/fastapi/services/export_task_service.py#L294-L418)
- [export_task_service.py:420-453](file://servers/fastapi/services/export_task_service.py#L420-L453)
- [export_task_service.py:519-576](file://servers/fastapi/services/export_task_service.py#L519-L576)
- [export_task_service.py:578-683](file://servers/fastapi/services/export_task_service.py#L578-L683)
- [export_task_service.py:685-724](file://servers/fastapi/services/export_task_service.py#L685-L724)
- [export_task_service.py:726-857](file://servers/fastapi/services/export_task_service.py#L726-L857)

## Dependency Analysis
The following diagram shows how components depend on each other:

```mermaid
graph LR
Router["Async Tasks Router"] --> Model["AsyncTaskModel"]
Router --> StatusEnum["AsyncTaskStatus"]
Router --> Recovery["Interrupted Task Recovery"]
Router --> Utils["MCP Public URLs Utility"]
Recovery --> Model
ExportSvc["Export Task Service"] --> Env["Environment & Paths"]
ExportSvc --> Runtime["Node Export Runtime"]
```

**Diagram sources**
- [router.py:8-11](file://servers/fastapi/api/v1/async_tasks/router.py#L8-L11)
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)
- [async_task_status.py:4-7](file://servers/fastapi/enums/async_task_status.py#L4-L7)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)
- [export_task_service.py:122-128](file://servers/fastapi/services/export_task_service.py#L122-L128)

**Section sources**
- [router.py:8-11](file://servers/fastapi/api/v1/async_tasks/router.py#L8-L11)
- [async_task.py:16-61](file://servers/fastapi/models/sql/async_task.py#L16-L61)
- [async_task_status.py:4-7](file://servers/fastapi/enums/async_task_status.py#L4-L7)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)
- [export_task_service.py:122-128](file://servers/fastapi/services/export_task_service.py#L122-L128)

## Performance Considerations
- Polling efficiency: Use the list endpoint with appropriate filters (type, status, created_at range) and pagination to minimize payload size and reduce load.
- Timeouts: The export service enforces a configurable timeout for child processes; tune this based on workload expectations.
- Resource scoping: Owner-scoped temporary directories and artifact movement reduce cross-user interference and improve cleanup reliability.
- Output permissions: Ensuring correct file/directory modes avoids I/O errors during subsequent reads.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Task remains pending after restart:
  - Cause: Server restarted while a background task was still running.
  - Resolution: The recovery service marks such tasks as error with a specific message; clients should treat these as failed and resubmit if necessary.
- Export task times out:
  - Cause: External Node process exceeded the configured timeout.
  - Resolution: Increase timeout configuration or optimize the workload; inspect stderr/stdout snippets included in error details.
- Invalid or missing output path:
  - Cause: Export runtime did not produce a valid path or produced a path outside allowed roots.
  - Resolution: Verify environment variables (APP_DATA_DIRECTORY, TEMP_DIRECTORY), ensure runtime files are present, and confirm output paths are within allowed directories.
- Permission errors on output:
  - Cause: Unable to set required permissions on output directory/file.
  - Resolution: Ensure the service has write access to the target directories and adjust OS permissions accordingly.

**Section sources**
- [async_tasks.py:13-19](file://servers/fastapi/services/async_tasks.py#L13-L19)
- [async_tasks.py:22-52](file://servers/fastapi/services/async_tasks.py#L22-L52)
- [export_task_service.py:354-418](file://servers/fastapi/services/export_task_service.py#L354-L418)
- [export_task_service.py:243-278](file://servers/fastapi/services/export_task_service.py#L243-L278)

## Conclusion
The asynchronous task system provides a durable, secure, and observable mechanism for long-running operations. Clients submit work through application flows that persist task records, then poll the provided endpoints to track progress. The export service ensures safe execution boundaries, robust error reporting, and proper resource cleanup. With clear status models and recovery logic, the system gracefully handles interruptions and failures, enabling reliable end-to-end workflows.

[No sources needed since this section summarizes without analyzing specific files]