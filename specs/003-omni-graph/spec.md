# Feature Specification: Omni-Graph (Graphify) - Deterministic Codebase Topology & Semantic Call-Graph Guard

**Feature Branch**: `003-omni-graph`  
**Milestone**: M1 - SDD Specification Bundle  
**Author**: Omni-Kernel Architectural Council  
**Target Directory**: `specs/003-omni-graph/`  
**Ratification Status**: Ready for Gatekeeper Review & Implementation Allocation  

---

## 1. Executive Summary & Problem Statement

### 1.1 Background: The Cognitive vs Topology Duality
In the Omni-Kernel v4.1 runtime architecture, autonomous agents coordinate complex software engineering tasks through a multi-tier hierarchy. Omni-Memory v4.1 manages the **Cognitive Space** (episodic memory, user intent affinities, learned behavioral rules, heuristic prompt grounding) via `omni_memory.db` and `proven_traces.json`. While Omni-Memory excels at answering *"How did we resolve similar architectural challenges previously?"*, it is fundamentally incapable of guaranteeing the mathematical syntactic and structural correctness of source code in the working tree.

Autonomous software engineering agents routinely suffer from **Modification Blindness**: when editing a target function or class, they lack an immediate, deterministic, cross-module structural topology. Consequently:
1. Changes made to a function signature in one module silently break callers across distant files.
2. Newly defined event handlers, slash commands, or MCP tools go unregistered in central dispatch registries.
3. Refactoring decisions are made without understanding the transitive ripple effect (blast radius) across the repository.

To permanently eliminate this class of defects, **Omni-Graph (Graphify)** establishes the **Codebase Topology Space** within Omni-Kernel v4.1. Operating in strict **Zero-Conflict Duality** alongside Omni-Memory, Omni-Graph extracts and maintains a persistent, deterministic, queryable AST call graph, parameter signature index, and lifecycle registry in `<workspace>/.omni/codebase_graph.db`.

```
+-----------------------------------------------------------------------------------+
|                               OMNI-KERNEL v4.1                                    |
+-------------------------------------------------+---------------------------------+
|          COGNITIVE / EPISODIC SPACE             |    TOPOLOGY / STRUCTURAL SPACE  |
|            (Omni-Memory v4.1)                   |          (Omni-Graph)           |
+-------------------------------------------------+---------------------------------+
| Database: <workspace>/.omni/omni_memory.db      | Database: <workspace>/.omni/    |
|                                                 |           codebase_graph.db     |
| Nature: Probabilistic, heuristic, experiential  | Nature: Deterministic, exact,   |
|                                                 |         structural, algebraic   |
| Storage: Dual-column FTS5 BM25 + ONNX Dense     | Storage: SQLite WAL Relational  |
|          Vector (intfloat/multilingual-e5)      |          Covering B-Trees       |
| Invalidation: Time-decayed Ebbinghaus S(t)      | Invalidation: Two-tier dirty    |
|               with soft-archiving               |               check (mtime+SHA) |
| Core Query: BM25 + Vector Cosine RRF (k=20)     | Core Query: Recursive CTEs      |
|                                                 |             (WITH RECURSIVE)    |
| Primary Query: "What rules or past patterns     | Primary Query: "What functions  |
|                 apply to this task?"            |  call X, what are their kwargs, |
|                                                 |  and what is the blast radius?" |
+-------------------------------------------------+---------------------------------+
```

### 1.2 Forensic Analysis: SVBot Failure Incident (`7f5ce17d-936e-41bd-897d-2449ffe52a4a`)
The urgent requirement for Omni-Graph was demonstrated by the catastrophic runtime breakdown observed during SVBot maintenance session `7f5ce17d-936e-41bd-897d-2449ffe52a4a` (analyzed in post-mortem session `434081d2-e607-476b-826d-092d6043d7f0`). SVBot is a Python Discord bot managing dedicated Minecraft server instances running in Docker containers on Oracle Cloud Infrastructure.

During this session, an autonomous agent was tasked with adding server modpack switching and dynamic memory configuration features. The agent committed three critical structural errors that bypassed cognitive memory and caused fatal production crashes:

#### Root Cause 1: Parameter Drift & Keyword Mismatch (`allocated_ram` vs `ram`)
In the cog layer (`cogs/server_cog.py`), the agent implemented a Discord slash command that invoked the Docker orchestration engine:
```python
# cogs/server_cog.py (Call Site)
await docker_manager.start_server(
    server_id=server_id,
    modpack_name=modpack_name,
    modpack_slug=modpack_slug,
    allocated_ram=ram.value  # <-- DEFECT: Parameter named 'allocated_ram'
)
```
However, in the core orchestration module (`core/docker_manager.py`), the method was declared as:
```python
# core/docker_manager.py (Definition)
async def start_server(
    self,
    server_id: str,
    modpack_name: str,
    modpack_slug: str,
    loader: str = "FABRIC",
    platform: str = "MODRINTH",
    download_url: Optional[str] = None,
    ram: Optional[str] = None,  # <-- Canonical parameter name is 'ram'
    rcon_password: Optional[str] = None
) -> bool:
```
Because `start_server` did not define a catch-all `**kwargs` parameter, Python's runtime raised a fatal exception immediately upon command execution:
```
TypeError: DockerManager.start_server() got an unexpected keyword argument 'allocated_ram'
```
The agent only discovered this bug after deploying the code, requiring an ad-hoc patch (`allocated_ram: Optional[str] = None`, `final_ram = ram or allocated_ram`). A static AST signature check would have intercepted this defect in 0.2 ms before the agent ever exited the edit step.

#### Root Cause 2: Unsynced Slash Commands & Dangling Lifecycle Hooks
The agent added new command handlers decorated with `@app_commands.command(...)` in `cogs/server_cog.py`. However, in Discord.py / AppCommands architecture, declaring a command decorator in a cog does not publish it to Discord's gateway. The cog must be registered via `await bot.add_cog(...)`, and the application command tree must be synchronized with Discord's REST API via `await bot.tree.sync()`.
The agent created the decorated function but omitted the lifecycle synchronization invocation. The command remained an **orphaned handler**, completely invisible to Discord users. The agent reported the feature as "complete" because the file syntax was valid, suffering from total lifecycle blindness.

#### Root Cause 3: Modification Blindness & Transitive Blast Radius Ignorance
When modifying `core/docker_manager.py:start_server`, the agent was unaware that `start_server` was not only invoked by `cogs/server_cog.py`, but also transitively called by background hibernation wake daemons (`core/hibernation_proxy.py`) and automated backup cron triggers (`core/backup_service.py`). Because the agent lacked a reverse caller graph, changes were made in isolation, leaving peripheral callers broken and unverified.

### 1.3 The Tripartite Protective Solution
Omni-Graph solves each of these root causes through three deterministic, automated guards:
1. **Signature Contract Guard**: Statically parses AST definitions (`ast.FunctionDef`, `ast.AsyncFunctionDef`) and call sites (`ast.Call`), performing static parameter binding to catch unexpected keywords, missing required parameters, and positional-only violations across all modules.
2. **Lifecycle Registration Guard**: Statically verifies that decorated handlers, hook plugins, and modular extensions have valid, active registration edges connecting them to their respective dispatch tables, registries, or synchronization triggers (`tree.sync()`, `add_cog()`, `register_hook`).
3. **Blast Radius Engine**: Utilizes SQLite Common Table Expressions (`WITH RECURSIVE`) to traverse reverse call chains in `<0.30 ms`, calculating the exact transitive set of impacted files and callers before an edit is finalized.

---

## 2. Prioritized User Stories (Given-When-Then Format)

### User Story 1 (P1 - Signature Contract Guard) 🎯 MVP
**As an** autonomous software engineer or orchestrator,  
**I want** an AST-level signature contract validator that statically checks every function and method call against its definition across module boundaries,  
**So that** parameter keyword mismatches, missing required arguments, and unexpected kwargs are caught instantly without executing code, preventing runtime `TypeError` crashes.

#### Scenarios:
- **Scenario 1.1 (Static Detection of Unexpected Keyword Parameter - The SVBot Case)**:
  - **Given** a target function definition `async def start_server(self, server_id, modpack_name, ram=None)` in `core/docker_manager.py` without `**kwargs`,
  - **When** an agent authors or edits `cogs/server_cog.py` containing a call `await docker_manager.start_server(server_id, modpack, allocated_ram="4G")`,
  - **Then** Omni-Graph's Signature Contract Guard flags violation `FAIL-03 (UNEXPECTED_KEYWORD_ARG)`:
    `"Unexpected keyword argument 'allocated_ram' passed to 'start_server' at cogs/server_cog.py:127. Valid parameters: ['server_id', 'modpack_name', 'ram']"`,
  - **And** suggests the correct parameter name `'ram'` via token prefix / Levenshtein matching.

- **Scenario 1.2 (Static Detection of Positional-Only Parameter Violation)**:
  - **Given** a function defined with positional-only syntax `def render_canvas(canvas, /, width=800, height=600):`,
  - **When** a caller invokes `render_canvas(canvas=my_canvas, width=1024)`,
  - **Then** the guard flags violation `FAIL-04 (POSITIONAL_ONLY_AS_KEYWORD)`:
    `"Parameter 'canvas' is positional-only but passed as a keyword argument at views/window.py:45"`,
  - **And** cleanly suppresses redundant `FAIL-02 (MISSING_REQUIRED_POSITIONAL_ARG)` for the same parameter to prevent duplicate diagnostic noise.

- **Scenario 1.3 (Static Detection of Missing Required Positional Arguments)**:
  - **Given** a function `def query_records(conn, sql, timeout=30):` where `conn` and `sql` have no defaults,
  - **When** a caller invokes `query_records(conn)` with only 1 positional argument,
  - **Then** the guard flags violation `FAIL-02 (MISSING_REQUIRED_POSITIONAL_ARG)`:
    `"Call to 'query_records' missing 1 required positional argument: 'sql' at services/db.py:82"`.

- **Scenario 1.4 (Static Detection of Missing Required Keyword-Only Arguments)**:
  - **Given** a function defined with keyword-only arguments `def execute_job(cmd, *, check=False, timeout_sec):` where `timeout_sec` has no default (`kw_defaults[i] is False`),
  - **When** a caller invokes `execute_job("ls -la", check=True)`,
  - **Then** the guard flags violation `FAIL-06 (MISSING_REQUIRED_KEYWORD_ARG)`:
    `"Call to 'execute_job' missing required keyword-only argument: 'timeout_sec' at tasks/runner.py:34"`.

- **Scenario 1.5 (Permissive Dynamic Splat Handling & PEP 570 `**kwargs`)**:
  - **Given** a target function `def log_event(event_name, **kwargs):` or `def f(a, /, **kwargs):`, or a call site passing `send_data(*args, **payload)`,
  - **When** the call contract is evaluated,
  - **Then** the guard detects `has_splat_kw == True` or `target.kwarg is not None`,
  - **And** treats arbitrary keyword arguments as permissible; in accordance with PEP 570, keyword arguments sharing the name of positional-only parameters are captured into `**kwargs` without triggering `FAIL-04`, emitting no false-positive contract violations.

- **Scenario 1.6 (Static Detection of Un-Awaited Coroutines in Synchronous Context)**:
  - **Given** an asynchronous function definition `async def fetch_token():` in `services/auth.py`,
  - **When** a synchronous caller invokes `token = fetch_token()` without an enclosing `await` expression, `asyncio.create_task()`, or `asyncio.run()`,
  - **Then** the guard flags violation `FAIL-08 (UN_AWAITED_ASYNC_CALL)`:
    `"Coroutine 'fetch_token' called without await expression at scripts/login.py:19; call returns un-awaited coroutine object"`.

- **Scenario 1.7 (Cross-Module Renamed Parameter Drift Detection - FAIL-07)**:
  - **Given** a function definition where a parameter has been renamed (e.g. `timeout_sec` formerly named `timeout_ms`, registered in migration mapping),
  - **When** a caller in a separate module invokes `consult_critic("prompt", timeout_ms=30)`,
  - **Then** the guard flags violation `FAIL-07 (RENAMED_PARAMETER_DRIFT)`:
    `"Caller passes deprecated parameter 'timeout_ms' (renamed to 'timeout_sec')"`,
  - **And** provides actionable migration advice distinguishing the drift from generic unexpected keyword errors (`FAIL-03`).

- **Scenario 1.8 (Unbound Class Method Dispatch Support)**:
  - **Given** an instance method `def work(self, job_id):` in class `Worker`,
  - **When** an invocation uses unbound class dispatch `Worker.work(worker_instance, "job-99")` with `is_unbound_class_call=True`,
  - **Then** the guard normalizes the receiver parameter, binding `worker_instance` to the implicit `self` slot and `"job-99"` to `job_id`,
  - **And** emits 0 contract violations, preventing false-positive `FAIL-01 (TOO_MANY_POSITIONAL_ARGS)`.

---

### User Story 2 (P2 - Lifecycle Registration Guard)
**As an** autonomous software architect,  
**I want** a declarative lifecycle registration validator that compares declared entity implementations against centralized registration tables, manifests, and synchronization triggers,  
**So that** orphan handlers, unsynchronized slash commands, and dead dispatch references are detected before deployment.

#### Scenarios:
- **Scenario 2.1 (Detection of Unsynchronized Slash Commands - The SVBot Case)**:
  - **Given** a codebase defining Discord application commands via `@app_commands.command` or `@bot.tree.command`,
  - **When** a new command `@app_commands.command(name="backup")` is added in a cog module,
  - **Then** the Lifecycle Registration Guard checks for a reachability path to `bot.tree.sync()` in the application lifecycle graph,
  - **And** if no call to `tree.sync()` exists in startup/reload routines, emits warning `WARN_LIFECYCLE_UNSYNCED`:
    `"Command 'backup' declared in 'cogs/backup_cog.py' but no reachability path found to 'bot.tree.sync()'. Command will not appear in Discord client."`

- **Scenario 2.2 (Detection of Orphan Plugin Implementations vs Central Manifest)**:
  - **Given** an architectural invariant stating that all subclasses of `BaseTool` must be registered in `scripts/mcp_gateway.py:ACTIVE_TOOLS`,
  - **When** an engineer authors `plugins/custom_search.py:CustomSearchTool(BaseTool)`,
  - **Then** the guard scans `nodes` and cross-references `ACTIVE_TOOLS`,
  - **And** if absent, flags `ORPHAN_IMPLEMENTATION`:
    `"Class 'CustomSearchTool' inherits from 'BaseTool' but is not registered in dispatch table 'scripts/mcp_gateway.py:ACTIVE_TOOLS'"`.

- **Scenario 2.3 (Detection of Dead Dispatch References)**:
  - **Given** a dispatch dictionary `DISPATCH_MAP = {"compress": compress_archive, "extract": extract_archive}`,
  - **When** a refactoring operation deletes `compress_archive` from source code,
  - **Then** the guard queries `codebase_nodes` for `target_id = 'compress_archive'`,
  - **And** flags `DEAD_DISPATCH_REFERENCE`:
    `"Dispatch table 'DISPATCH_MAP' references nonexistent identifier 'compress_archive' at line 42; runtime KeyError will occur"`.

- **Scenario 2.4 (Hook Handler Signature Conformance Check)**:
  - **Given** a lifecycle hook contract defining expected signature `(context: dict, prompt: str) -> None`,
  - **When** a newly registered handler defines `def on_prompt(context, prompt, extra_arg):` without default or `*args`,
  - **Then** the guard detects signature incompatibility and flags `HOOK_SIGNATURE_MISMATCH`:
    `"Lifecycle hook handler 'on_prompt' requires 3 positional arguments but dispatcher passes 2"`.

---

### User Story 3 (P3 - Blast Radius Engine)
**As an** autonomous agent preparing to modify a shared module,  
**I want** a deterministic, sub-millisecond reverse-call-graph query engine,  
**So that** I receive an exact, transitive list of all affected caller functions, classes, and files up to $N$ hops, automatically populating the cognitive pre-flight checklist.

#### Scenarios:
- **Scenario 3.1 (Sub-Millisecond Recursive Reverse Caller Traversal)**:
  - **Given** an SQLite codebase graph database `<workspace>/.omni/codebase_graph.db` with covering indexes,
  - **When** an agent queries the blast radius for target node `'scripts/memory_schema.py:execute_sql'` with `max_depth = 4`,
  - **Then** SQLite executes a cycle-safe Recursive CTE query in $<0.30\text{ ms}$,
  - **And** returns the exact set of 38 direct callers and 184 transitive callers, sorted by hop distance.

- **Scenario 3.2 (Cycle-Safe Traversal Termination in Cyclic Graphs)**:
  - **Given** a circular call dependency where function `func_a()` calls `func_b()` and `func_b()` calls `func_a()`,
  - **When** the Blast Radius CTE traverses the graph,
  - **Then** the delimiter token isolation clause `instr(br.path_tokens, '|' || e.source_id || '|') = 0` terminates recursive expansion along circular paths,
  - **And** returns all reachable nodes exactly once without infinite loops or memory exhaustion.

- **Scenario 3.3 (Transitive Impact Risk Scoring & Tiering)**:
  - **Given** an agent planning an edit to a symbol,
  - **When** the Blast Radius Engine analyzes the caller set,
  - **Then** it assigns a composite Risk Tier:
    - **Tier 1 (Direct Impact)**: Symbols directly calling the modified function (MUST be inspected and updated in sync).
    - **Tier 2 (High Transitive Impact)**: Symbols $\le 2$ hops away with high in-degree ($\ge 10$ callers).
    - **Tier 3 (Cascading Ripple)**: Symbols $\ge 3$ hops away (monitored for regression).

- **Scenario 3.4 (Cognitive Pre-Flight Loop Integration in `scripts/resolver.py`)**:
  - **Given** a developer prompt requesting a refactoring of `ProcessMutex` in `scripts/lifecycle_guard.py`,
  - **When** `scripts/resolver.py` executes the 4-axis Pre-Flight Assessment (Lợi, Hại, Đủ, Thiếu),
  - **Then** it queries `codebase_graph.db` in $<1.5\text{ ms}$,
  - **And** injects the blast radius caller list directly into the `"Đủ (Completeness)"` and `"Hại (Risks)"` sections:
    `"Đủ: Verify all 14 callers across scripts/hook_runner.py, scripts/consolidator.py, and scripts/updater.py"`.

- **Scenario 3.5 (Advisory Injection in `scripts/hook_runner.py`)**:
  - **Given** an incoming user prompt targeting a high-impact hub symbol ($\ge 15$ transitive callers),
  - **When** `hook_runner.py` processes PreInvocation,
  - **Then** it performs a sub-0.2ms indexed query against `codebase_graph.db`,
  - **And** appends a non-blocking advisory banner into `ephemeralMessage`:
    `"⚡ [Omni-Graph Advisory]: Modifying 'execute_sql' carries a Tier-1 Blast Radius affecting 38 callers across 6 files."`

---

### User Story 4 (P4 - Autonomous Zero-Config Workspace Bootstrapping & Self-Healing)
**As an** autonomous agent operating in any arbitrary user workspace,  
**I want** Omni-Graph to autonomously discover missing topology indices, perform an ultra-fast initial cold sweep (<100ms for typical repositories), maintain incremental deltas in <2ms, self-heal on file edits, and automatically enforce git hygiene,  
**So that** full codebase graph topology is instantly available on the very first turn without manual setup commands, and without polluting user git repositories.

#### Scenarios:
- **Scenario 4.1 (Autonomous Cold-Start JIT Discovery on First Turn)**:
  - **Given** an agent begins a session in a workspace where `<workspace>/.omni/codebase_graph.db` does not exist,
  - **When** Step 0 Resolver (`scripts/resolver.py`) or PreInvocation hook (`scripts/hook_runner.py`) evaluates the workspace,
  - **Then** it autonomously detects the uninitialized topology state,
  - **And** executes an ultra-fast AST sweep over all `.py` files using Python standard library `ast`,
  - **And** bootstraps the SQLite WAL schema and populates nodes, edges, signatures, and file metadata in $<100\text{ ms}$ for typical repositories ($\le 50$ files),
  - **And** requires zero manual developer configuration, zero flags, and zero user commands.

- **Scenario 4.2 (Fast Pre-Flight Incremental Delta Maintenance)**:
  - **Given** an existing initialized `codebase_graph.db` in the workspace,
  - **When** a pre-flight turn starts,
  - **Then** the engine checks `os.stat` timestamps and file sizes against `codebase_files_meta` in $<2.0\text{ ms}$,
  - **And** if no files have changed, re-indexing is completely bypassed; if 1 or 2 files are dirty, only those specific files are re-parsed into the graph atomically.

- **Scenario 4.3 (Post-Edit Self-Healing Micro-Index Hook)**:
  - **Given** an agent or tool modifies, creates, or deletes a file (e.g. via `write_to_file` or `replace_file_content`),
  - **When** the file write completes,
  - **Then** a lightweight micro-indexing hook is triggered for the touched file path,
  - **And** deletes old nodes/edges for that path and parses the updated AST into `codebase_graph.db` in $<8.0\text{ ms}$,
  - **And** ensures subsequent blast-radius or contract checks immediately observe the latest topological reality without stale state.

- **Scenario 4.4 (Automated Non-Polluting Git Hygiene)**:
  - **Given** an active git repository in `<workspace>`,
  - **When** Omni-Graph initializes the `<workspace>/.omni/` directory,
  - **Then** it inspects `<workspace>/.gitignore`,
  - **And** if `.omni/` (or `.omni`) is not present in `.gitignore`, it safely appends `.omni/` to `.gitignore` with an `# Omni-Kernel workspace artifacts` comment,
  - **And** guarantees that SQLite databases, WAL files, and graph caches are never committed to the user's git tree.

- **Scenario 4.5 (Global Omni-Memory vs Local Workspace Graph Physical Isolation)**:
  - **Given** global Omni-Memory operates across sessions in `omni_memory.db` to retain cross-session cognitive learnings and heuristic prompt affinities,
  - **When** an agent switches between different repository workspaces,
  - **Then** Omni-Graph strictly scopes `codebase_graph.db` to the local `<workspace>/.omni/` directory,
  - **And** guarantees zero cross-workspace code leakage, zero path collision, and complete physical SQLite lock isolation.

---

## 3. Domain Entity Models & Schemas

### 3.1 Entity: `CodebaseNode`
Represents an individual structural entity extracted from Python AST.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class CodebaseNode:
    id: str                 # Canonical ID: 'relative/file.py:ClassName.func_name'
    workspace: str          # Canonical workspace root path
    file_path: str          # Normalized relative path from workspace root
    entity_type: str        # 'module' | 'class' | 'function' | 'async_function' | 'method' | 'async_method'
    name: str               # Short identifier: 'start_server'
    qualified_name: str     # Scoped identifier: 'DockerManager.start_server'
    line_start: int         # 1-indexed start line
    line_end: int           # 1-indexed end line
    docstring: Optional[str]# Extracted docstring text (truncated to 500 chars)
    is_exported: bool       # True if defined at module top-level or listed in __all__
    ast_hash: str           # SHA-256 hash of AST subtree for fast change detection
```

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CodebaseNode",
  "type": "object",
  "required": ["id", "workspace", "file_path", "entity_type", "name", "qualified_name", "line_start", "line_end"],
  "properties": {
    "id": { "type": "string" },
    "workspace": { "type": "string" },
    "file_path": { "type": "string" },
    "entity_type": { "type": "string", "enum": ["module", "class", "function", "async_function", "method", "async_method"] },
    "name": { "type": "string" },
    "qualified_name": { "type": "string" },
    "line_start": { "type": "integer", "minimum": 1 },
    "line_end": { "type": "integer", "minimum": 1 },
    "docstring": { "type": ["string", "null"] },
    "is_exported": { "type": "boolean" },
    "ast_hash": { "type": "string" }
  }
}
```

### 3.2 Entity: `FunctionSignature`
Represents the complete syntactic parameter specification of a callable.

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class FunctionSignature:
    node_id: str                      # Foreign key to CodebaseNode.id
    file_path: str                    # Defining file
    posonly_args: List[str]           # Parameter names before '/'
    args: List[str]                   # Standard positional/keyword parameter names
    defaults_count: int               # Count of trailing positional args that have defaults
    vararg: Optional[str]             # Name of *args parameter (e.g., 'args') or None
    kwonly_args: List[str]            # Parameter names after '*' or '*args'
    kw_defaults: List[bool]           # True if corresponding kwonly_arg has default value
    kwarg: Optional[str]              # Name of **kwargs parameter (e.g., 'kwargs') or None
    return_annotation: Optional[str]  # Text representation of return type annotation
    is_async: bool                    # True for async def, False for def
```

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FunctionSignature",
  "type": "object",
  "required": ["node_id", "file_path", "posonly_args", "args", "defaults_count", "kwonly_args", "kw_defaults", "is_async"],
  "properties": {
    "node_id": { "type": "string" },
    "file_path": { "type": "string" },
    "posonly_args": { "type": "array", "items": { "type": "string" } },
    "args": { "type": "array", "items": { "type": "string" } },
    "defaults_count": { "type": "integer", "minimum": 0 },
    "vararg": { "type": ["string", "null"] },
    "kwonly_args": { "type": "array", "items": { "type": "string" } },
    "kw_defaults": { "type": "array", "items": { "type": "boolean" } },
    "kwarg": { "type": ["string", "null"] },
    "return_annotation": { "type": ["string", "null"] },
    "is_async": { "type": "boolean" }
  }
}
```

### 3.3 Entity: `CallSite`
Represents an individual call invocation extracted from `ast.Call`.

```python
@dataclass(frozen=True)
class CallSite:
    caller_node_id: str               # Scope containing the call (e.g. 'cogs/server.py:start_cmd')
    target_symbol_raw: str            # Raw syntax text: 'docker_manager.start_server'
    resolved_target_id: Optional[str] # Resolved node ID or None if dynamic / external
    file_path: str                    # File containing the call
    line_no: int                      # 1-indexed line of call expression
    pos_args_count: int               # Number of positional arguments passed
    kw_args: List[str]                # List of keyword argument names passed: ['allocated_ram']
    has_splat_pos: bool               # True if *args passed
    has_splat_kw: bool                # True if **kwargs passed
    is_awaited: bool                  # True if call expression is direct child of ast.Await
```

### 3.4 Entity: `CodebaseEdge`
Represents a directed relationship between two codebase nodes.

```python
@dataclass(frozen=True)
class CodebaseEdge:
    source_id: str                    # Origin node ID (Caller, Importer, Subclass)
    target_id: str                    # Target node ID (Callee, Imported, BaseClass)
    relation_type: str                # 'calls' | 'imports' | 'inherits' | 'overrides' | 'decorates' | 'registers'
    file_path: str                    # File where relationship originates
    line_no: int                      # Line number of the edge
    call_args_count: Optional[int]    # Positional args count if relation_type == 'calls'
    call_kwargs: Optional[List[str]]  # Passed kwargs if relation_type == 'calls'
    has_splat_pos: bool               # 1 if *args used
    has_splat_kw: bool                # 1 if **kwargs used
    is_awaited: bool                  # 1 if awaited
```

### 3.5 Entity: `LifecycleHookRegistration`
Represents an event hook, command registration, or plugin entrypoint.

```python
@dataclass(frozen=True)
class LifecycleHookRegistration:
    id: str                           # Unique ID: 'hook:cogs/server_cog.py:85:app_commands'
    hook_name: str                    # 'app_commands.command' | 'register_hook' | 'include_router'
    handler_node_id: str              # CodebaseNode.id of the handler function/class
    file_path: str                    # File where handler is defined
    line_number: int                  # Definition line
    registration_style: str           # 'decorator' | 'dispatch_dict' | 'manifest_json'
    expected_invoker_id: Optional[str]# Expected lifecycle synchronizer (e.g., 'bot.tree.sync')
    is_registered: bool               # True if verified connected to dispatch pipeline
    status: str                       # 'ACTIVE' | 'ORPHAN' | 'DEAD_REFERENCE' | 'UNSYNCED'
```

### 3.6 Entity: `BlastRadiusReport`
Summarizes the transitive impact of modifying a specific symbol.

```python
@dataclass(frozen=True)
class BlastRadiusReport:
    target_node_id: str               # Target symbol ID
    target_name: str                  # Function or class name
    direct_caller_count: int          # Number of direct (1-hop) callers
    total_transitive_count: int       # Total unique reachable callers up to max_depth
    max_depth_traversed: int          # Max hops traversed (default 4)
    affected_files: List[str]         # List of unique relative file paths impacted
    risk_tier: str                    # 'TIER_1_LOW' | 'TIER_2_MEDIUM' | 'TIER_3_HIGH' | 'TIER_4_CRITICAL'
    call_chains: List[str]            # Top representative call chains: ['A -> B -> C']
```

### 3.7 Entity: `CodebaseFileMeta`
Tracks file-level caching, indexing state, and delta timestamps for sub-2ms pre-flight change detection.

```python
@dataclass(frozen=True)
class CodebaseFileMeta:
    file_path: str                    # Relative path from workspace root
    mtime: float                      # os.stat().st_mtime timestamp
    size_bytes: int                   # os.stat().st_size
    sha256: str                       # SHA-256 hex digest of file contents
    node_count: int                   # Number of nodes extracted from this file
    edge_count: int                   # Number of edges originating from this file
    last_indexed: float               # Unix timestamp of last indexing operation
    parse_status: str                 # 'SUCCESS' | 'SYNTAX_ERROR' | 'SKIPPED'
    error_message: Optional[str]      # Error details if parse_status == 'SYNTAX_ERROR'
```

---

## 4. Functional Requirements (FR-001 through FR-023)

### Core AST & Storage Engine
- **FR-001 (100% Python Standard Library Dependency Invariant)**: The entire core engine of Omni-Graph (`ast`, `sqlite3`, `pathlib`, `re`, `hashlib`, `json`, `os`, `sys`, `time`) MUST be implemented using the Python 3.11+ Standard Library exclusively. Zero third-party packages or native compiled C++ wheels (`tree-sitter`, `networkx`, `neo4j`, `libgit2`) are permitted.
- **FR-002 (Two-Tier Incremental Change Detection Pipeline)**: The scanner MUST implement a two-tier change detection algorithm:
  1. *Tier 1 (Fast Stat Scan)*: Compare file `st_mtime` and `st_size` against `file_hashes` in $<10\ \mu\text{s}$ per file. Unchanged files are bypassed immediately.
  2. *Tier 2 (Content SHA-256 Verification)*: If mtime/size differs, compute SHA-256 hash. If hash matches cached value (e.g., touched file with identical content), skip AST re-parsing and update cached mtime in $<0.2\text{ ms}$.
  3. Total incremental re-index time for 1 modified file in a 500-file repository MUST not exceed $15.0\text{ ms}$.
- **FR-003 (Dedicated Workspace SQLite WAL Database)**: Omni-Graph MUST persist its state to `<workspace>/.omni/codebase_graph.db`. To guarantee Zero-Conflict Duality with `omni_memory.db`, the database must operate with its own independent file, locking, and WAL configuration:
  ```sql
  PRAGMA journal_mode = WAL;
  PRAGMA synchronous = NORMAL;
  PRAGMA busy_timeout = 5000;
  PRAGMA foreign_keys = ON;
  PRAGMA temp_store = MEMORY;
  PRAGMA cache_size = -8000;
  ```
- **FR-004 (AST Node & Function Signature Extraction)**: The parser MUST visit all `ast.Module`, `ast.ClassDef`, `ast.FunctionDef`, and `ast.AsyncFunctionDef` nodes. For every callable, it MUST extract `posonlyargs`, `args`, count of `defaults`, `vararg`, `kwonlyargs`, `kw_defaults` booleans, `kwarg`, and `return_annotation`, persisting them to the `signatures` table.
- **FR-005 (AST Call Site & Invocation Parameter Extraction)**: The parser MUST visit all `ast.Call` nodes, recording the caller node ID, raw target text, count of positional arguments, list of explicit keyword argument names, splat flags (`has_splat_pos`, `has_splat_kw`), and await status (`is_awaited`).
- **FR-006 (Multi-Tier Static Symbol Resolution Engine)**: The resolver MUST bind call expressions to target `CodebaseNode.id` using a 4-tier static scope table:
  1. *Local Scope*: Enclosing class methods and module-level functions.
  2. *Explicit Imports*: `from foo import bar` $\implies$ `scope['bar'] = 'foo.py:bar'`; `from foo import bar as baz` $\implies$ `scope['baz'] = 'foo.py:bar'`.
  3. *Relative Imports*: Resolving `.` and `..` relative to defining file directory via `pathlib.Path`.
  4. *Heuristic Method Resolution*: `self.method(...)` binds to enclosing `ClassDef.method`; explicit constructor bindings (`mgr = DockerManager()`) bind `mgr.start(...)` to `DockerManager.start`.

### Signature Contract Guard Engine
- **FR-007 (Static Signature Contract Binding Algorithm)**: Omni-Graph MUST implement static signature binding without importing or executing target modules. Given a target signature and call arguments, the validator MUST:
  1. Compute total positional capacity $N_{\text{pos}} = \text{len}(\text{posonlyargs}) + \text{len}(\text{args})$ and required positional count $N_{\text{req\_pos}} = N_{\text{pos}} - \text{defaults\_count}$.
  2. Normalize method receivers: for bound calls, strip leading `self`/`cls`; for unbound class method calls (`is_unbound_class_call=True`), compensate by decrementing effective positional arguments by 1.
  3. Adhere to PEP 570 positional-only rules, capturing positional-only named keywords into `**kwargs` when defined.
  4. Cross-reference unrecognized keywords against `renamed_params` to separate renamed parameter drift (`FAIL-07`) from unexpected keywords (`FAIL-03`).
  5. Suppress duplicate `FAIL-02` emissions for parameters already flagged under `FAIL-04`.
- **FR-008 (The 8 Definitive Contract Error Modes)**: The Signature Contract Guard MUST detect and classify all 8 contract error modes:
  1. `FAIL-01 (TOO_MANY_POSITIONAL_ARGS)`: Positional argument count exceeds capacity when `*args` is absent.
  2. `FAIL-02 (MISSING_REQUIRED_POSITIONAL_ARG)`: Missing required positional arguments not supplied positionally or by keyword.
  3. `FAIL-03 (UNEXPECTED_KEYWORD_ARG)`: Caller passes a keyword argument name not present in the definition signature when `**kwargs` is absent.
  4. `FAIL-04 (POSITIONAL_ONLY_AS_KEYWORD)`: Caller passes a parameter defined before `/` as a keyword argument when `**kwargs` is absent. Flagging `FAIL-04` suppresses redundant `FAIL-02` errors for the same parameter.
  5. `FAIL-05 (MULTIPLE_VALUES_FOR_ARG)`: Argument supplied both positionally and as a keyword.
  6. `FAIL-06 (MISSING_REQUIRED_KEYWORD_ARG)`: Keyword-only argument without default is omitted at call site.
  7. `FAIL-07 (RENAMED_PARAMETER_DRIFT)`: Caller passes a deprecated parameter name present in the target callable's `renamed_params` migration mapping, emitting targeted refactoring guidance.
  8. `FAIL-08 (UN_AWAITED_ASYNC_CALL)`: Coroutine (`ast.AsyncFunctionDef`) called without `await` expression, `asyncio.create_task`, or task wrapper in synchronous execution context.

### Lifecycle Registration Guard Engine
- **FR-009 (Declarative Registration Invariant Specifications)**: Omni-Graph MUST support declarative registration invariant definitions (JSON/YAML) defining rules such as `must_have_decorator`, `must_exist_in_manifest`, and `target_identifiers_must_exist`.
- **FR-010 (Bidirectional Lifecycle Drift Detection)**: The Lifecycle Guard MUST execute bidirectional drift detection:
  1. *Orphan Implementations*: Detects defined handlers/cogs/tools matching invariant rules that are omitted from central dispatch manifests or lack registration calls.
  2. *Dead References*: Detects dispatch table keys, router inclusions, or manifest entries referencing functions/classes that have been deleted or renamed in source code.

### Blast Radius & CTE Traversal Engine
- **FR-011 (Sub-Millisecond Recursive CTE Reverse Caller Traversal)**: Omni-Graph MUST execute reverse caller traversals using SQLite Common Table Expressions (`WITH RECURSIVE`). Multi-column covering indexes on `edges(target_id, relation_type)` and `edges(source_id, relation_type)` MUST be maintained to ensure traversal latency $<0.30\text{ ms}$ for 4-hop searches.
- **FR-012 (Cycle-Safe Traversal Invariant)**: Recursive CTE queries MUST enforce cycle termination via delimiter token isolation (`instr(br.path_tokens, '|' || e.source_id || '|') = 0`) and recursion depth bounds (`br.depth < ?`), guaranteeing mathematical termination in $O(|V|)$ operations on cyclic graphs while preventing substring collision false cutoffs.
- **FR-013 (Transitive Risk Scoring & Tiering)**: The Blast Radius Engine MUST calculate a normalized Impact Score $\in [0, 100]$:
  $$\text{Score} = \min\left(100, 2.5 \cdot |\text{Direct Callers}| + 1.0 \cdot |\text{Transitive Callers}| + 5.0 \cdot |\text{Affected Files}|\right)$$
  classifying modifications into Tier 1 (Low: $<25$), Tier 2 (Medium: $25-50$), Tier 3 (High: $51-75$), and Tier 4 (Critical: $>75$).

### Pre-Flight & Kernel Integration
- **FR-014 (PreInvocation Hook Advisory Integration)**: `scripts/hook_runner.py` MUST query `codebase_graph.db` with a strict $100\text{ ms}$ `busy_timeout`. If the database is missing, unindexed, or locked, the hook MUST fail-soft, logging a debug entry and continuing normal execution without raising exceptions or blocking the $<25\text{ ms}$ PreInvocation SLA.
- **FR-015 (Cognitive Pre-Flight Loop Enrichment)**: `scripts/resolver.py` MUST enrich the 4-axis Pre-Flight Assessment (Lợi, Hại, Đủ, Thiếu) with blast radius and contract verification findings:
  - *Hại (Risks)*: Populated with active contract mismatch warnings.
  - *Đủ (Completeness)*: Populated with the exhaustive list of direct callers requiring synchronized updates.
  - *Thiếu (Implicit Needs)*: Populated with missing lifecycle registrations or un-synced commands.

### Visualization & Reporting
- **FR-016 (Zero-CDN Offline Interactive Visualization Contract)**: Omni-Graph MUST support generating a standalone, offline `graph.html`. The generated HTML file MUST contain zero external CDN `<script>` or `<link>` tags, inlining a self-contained HTML5 Canvas force-directed graph visualizer (<250 lines vanilla JS) with physics simulation, zoom/pan, search, and blast-radius node highlighting.
- **FR-017 (Structured Markdown Topology Reporting)**: The engine MUST support CLI command `python scripts/omni_graph.py --report --out graph_report.md` generating a GitHub-flavored Markdown report detailing contract violations, top high-risk hub functions, lifecycle registration health, and scan performance metrics.
- **FR-018 (Dual Worker Fleet Task Allocation Contract)**: Specification tasks MUST partition execution between:
  - `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 GPU): AST parsing, SQLite WAL DDL/query implementation, local file indexing, and mutex integration.
  - `groq_worker_cloud` (Groq LPU Cloud @ 300-800 tok/s): High-speed synthesis of unit test suites, AST visitor mock fixtures, and error mode assertion tests.

### Autonomous Bootstrapping & Self-Healing Requirements
- **FR-019 (Autonomous Cold Start JIT Discovery & Initial Sweep <100ms)**: On the initial turn in any new or unindexed workspace, Step 0 Gatekeeper (`scripts/resolver.py`) or PreInvocation hook (`scripts/hook_runner.py`) MUST autonomously detect the absence of `<workspace>/.omni/codebase_graph.db` and trigger an initial parallel AST sweep across all `.py` files, initializing the database schema and indexing all nodes/edges in $<100\text{ ms}$ for typical repositories ($\le 50$ files) with zero manual user intervention.
- **FR-020 (Fast Pre-Flight Delta Verification <2ms)**: During every pre-flight assessment turn, the scanner MUST perform a non-blocking `os.stat` check comparing current file timestamps and sizes against `codebase_files_meta` in $<2.0\text{ ms}$. If all timestamps match, AST re-parsing is completely bypassed.
- **FR-021 (Post-Edit Self-Healing Micro-Index Hook)**: When an agent tool (`write_to_file`, `replace_file_content`, or git checkout) modifies, adds, or deletes a Python file, a micro-index hook MUST immediately re-parse that specific file path, executing an atomic SQLite transaction (delete old nodes/edges, insert updated AST, commit) in $<8.0\text{ ms}$, ensuring subsequent queries always reflect the latest code state.
- **FR-022 (Automated Non-Polluting Git Hygiene)**: Upon creating `<workspace>/.omni/`, Omni-Graph MUST inspect `<workspace>/.gitignore`. If the entry `.omni/` (or `.omni`) is absent, it MUST append `.omni/` to `.gitignore` automatically, preventing graph database files, temporary WAL journals, or visualization artifacts from ever being committed into the user's version control.
- **FR-023 (Global Memory vs Local Workspace Topology Physical Separation)**: Omni-Graph MUST maintain 100% physical and process isolation between the global cognitive memory database (`omni_memory.db`) and workspace-local graph database (`<workspace>/.omni/codebase_graph.db`). Cross-workspace queries, cross-database ATTACH queries, or cross-database transactions are strictly prohibited.

---

## 5. Non-Functional Requirements (NFR-001 through NFR-006)

- **NFR-001 (Parse & Re-Indexing Latency SLA)**:
  - Initial cold scan of a 500-file (~50,000 LOC) Python repository MUST complete in $<2,000\text{ ms}$ using standard library parallel processing (`concurrent.futures.ProcessPoolExecutor`).
  - Incremental single-file re-indexing (mtime check + AST parse + atomic SQLite transaction) MUST complete in $<15.0\text{ ms}$.
  - Whole-workspace fast stat check (500 files `os.stat`) MUST complete in $<5.0\text{ ms}$.
- **NFR-002 (Graph Traversal & Query Latency SLA)**:
  - 4-hop transitive blast radius queries using recursive CTEs on a graph of 5,000 nodes and 15,000 edges MUST execute with mean latency $<0.30\text{ ms}$ (maximum $<1.0\text{ ms}$).
  - Direct 1-hop caller/callee lookups MUST execute in $<0.10\text{ ms}$.
- **NFR-003 (Zero External Native Wheels & Windows AppLocker Compliance)**:
  - The core engine MUST execute cleanly on Windows 11 with AppLocker and Software Restriction Policies enabled.
  - Zero compiled C/C++ `.dll` or `.pyd` dependencies beyond standard Python runtime binaries.
- **NFR-004 (Physical Memory & Disk Overhead Bounds)**:
  - Runtime RAM footprint of the graph engine during querying MUST remain $<20\text{ MB}$ (governed by `PRAGMA cache_size = -8000`).
  - Database file size on disk for a 100,000 LOC codebase MUST remain $<15\text{ MB}$.
  - Zero GPU VRAM consumption (preserves all 3,741 MB of headroom on local AMD Instinct MI50 GPU).
- **NFR-005 (Backwards Compatibility & Zero Regression Guarantee)**:
  - 100% backwards compatibility with all existing Omni-Kernel capabilities (L1 Reflex hook, L2 SQLite WAL hybrid memory, L3 consolidator daemon, resolver).
  - Physical and logical database separation: zero cross-database locking or table name collisions between `omni_memory.db` and `codebase_graph.db`.
- **NFR-006 (Zero-Trust Security & SQL Injection Immunity)**:
  - 100% of SQLite queries MUST use parameterized queries (`?` placeholders). Zero string formatting or concatenation allowed in SQL statements.
  - Sensitive paths and tokens in docstrings or source snippets MUST be scrubbed using `scripts/sanitizer.py:redact_credentials()` prior to report generation.

---

## 6. Edge Cases & Threat Model (EC-001 through EC-016)

| Edge Case ID | Category | Scenario Description | Expected Guardrail & Defensive Behavior |
| :--- | :--- | :--- | :--- |
| **EC-001** | Dynamic Dispatch | Dynamic member resolution via `getattr(obj, name)`, `globals()[func]`, or `importlib.import_module()` | AST visitor identifies `getattr` / `globals` calls, records an edge with `is_dynamic = 1` and `target_id = 'DYNAMIC_CALL'`, emitting a soft informational notice without raising a false contract mismatch. |
| **EC-002** | Wildcard Imports | Code uses `from module import *` | Visitor marks module scope with `has_wildcard_import = 1`. Symbol resolution falls back to searching exported symbols (`__all__` or module globals) of the target module; if ambiguous, flags advisory warning. |
| **EC-003** | Dynamic Splatting | Call site passes `func(*args, **kwargs)` where args/kwargs are dynamic containers | Guard detects `has_splat_pos == True` or `has_splat_kw == True`. Positional capacity and unexpected keyword checks are bypassed (fail-soft permissive), logging `DYNAMIC_SPLAT_PASS`. |
| **EC-004** | Circular Imports & Mutual Calls | Circular imports (`a.py` imports `b.py`, `b.py` imports `a.py`) or recursive calls (`A -> B -> A`) | Recursive CTE terminates safely via delimiter token isolation clause `instr(path_tokens, '|' || node_id || '|') = 0`. Multi-file scanner parses AST independently of import execution, completely immune to runtime circular import crashes. |
| **EC-005** | Decorator Wrapping | Function wrapped in decorators (`@functools.wraps`, `@property`, `@staticmethod`, custom decorators) | AST visitor inspects decorator list. If `@property`, marks entity as property (access without parens). If custom decorator without `@wraps`, retains underlying AST signature and records edge of type `'decorates'`. |
| **EC-006** | Inheritance & Polymorphic Calls | Caller invokes `base.execute()`, but subclass overrides method with different parameters | Graph records `'inherits'` and `'overrides'` edges. Signature Guard checks call against static declared type; if polymorphic, verifies that overriding method signature is Liskov-substitutable (accepts at least base arguments). |
| **EC-007** | Async / Await Boundary | Asynchronous coroutine (`async def`) invoked inside synchronous function without `await` | Guard flags `FAIL-08 (UN_AWAITED_ASYNC_CALL)`. If call is wrapped in `asyncio.create_task()`, `asyncio.run()`, or `loop.create_task()`, guard recognizes valid task creation wrapper and passes. |
| **EC-008** | Third-Party & Stdlib Calls | Call invokes un-indexed external library (`requests.get`, `json.dumps`, `discord.Client`) | Symbol resolver determines target module is outside workspace root. Categorizes target as `'EXTERNAL'` and bypasses internal signature checks unless external stub or typeshed summary is provided. |
| **EC-009** | Syntax Errors During Edit | Source file contains syntax error (e.g., partial code during active typing or failed agent edit) | Scanner catches `SyntaxError` during `ast.parse()`, writes `parse_status = 'SYNTAX_ERROR'` to `file_hashes`, retains previous valid AST nodes in database, and emits non-blocking warning to `stderr`. |
| **EC-010** | Conditional Platform Imports | Code imports platform-specific modules inside `if sys.platform == "win32":` or `try...except ImportError:` | AST visitor traverses both branches of `If` and `Try` blocks, registering all conditionally imported symbols with attribute `is_conditional = 1`. |
| **EC-011** | Multi-Process SQLite Locking | Concurrent worker processes attempt to query or update `codebase_graph.db` simultaneously | SQLite WAL mode permits concurrent readers without blocking. Writers use `PRAGMA busy_timeout = 5000;` and single-file atomic transactions (`BEGIN IMMEDIATE; ... COMMIT;`), eliminating `database is locked` errors. |
| **EC-012** | Empty or Fresh Repository | Workspace lacks `.omni/` directory or contains zero `.py` files | Engine automatically creates `.omni/` directory, initializes SQLite schema, returns empty graph report with 0 nodes/edges, and exits cleanly with code 0 without raising exceptions. |
| **EC-013** | Polyglot / Non-Python Files | Repository contains `.js`, `.ts`, `.json`, `.md`, `.sql`, or binary assets | Scanner filters by `.py` extension for AST analysis. Non-Python files are processed by lightweight regex scanner for import/manifest edges or skipped safely without attempting Python AST parsing. |
| **EC-014** | Renamed or Deleted Files | File is deleted or renamed on disk | Scanner compares disk file list against `file_hashes`. If a cached file is missing from disk, executes cascading delete (`DELETE FROM file_hashes WHERE file_path = ?;`), cleanly removing all associated nodes, edges, signatures, and hooks. |
| **EC-015** | Unbound Class Method Dispatch | Caller invokes instance method via class symbol (`Worker.work(inst, 'j-1')`) | Resolver passes `is_unbound_class_call = True`. Validator treats first argument as receiver, neutralizing false `FAIL-01` overflow. |
| **EC-016** | PEP 570 Positional-Only with `**kwargs` | Function defines `def f(a, /, **kwargs)` and caller passes `f(1, a=2)` | In accordance with PEP 570, keyword `a=2` is captured by `**kwargs`. Validator emits 0 violations. |

---

## 7. Authoritative SQLite Relational DDL Specification

```sql
-- Database Location: <workspace>/.omni/codebase_graph.db
-- Engine: SQLite 3.35+ with WAL mode

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -8000; -- 8MB cache allocation

-- 1. File Metadata & Incremental Cache Verification (codebase_files_meta)
CREATE TABLE IF NOT EXISTS file_hashes (
    file_path       TEXT PRIMARY KEY,               -- Relative path from workspace root
    sha256          TEXT NOT NULL,                  -- SHA-256 hex digest of file contents
    mtime           REAL NOT NULL,                  -- os.stat().st_mtime float
    size_bytes      INTEGER NOT NULL,               -- os.stat().st_size
    node_count      INTEGER NOT NULL DEFAULT 0,     -- Count of AST nodes extracted
    edge_count      INTEGER NOT NULL DEFAULT 0,     -- Count of AST edges extracted
    parsed_at       REAL NOT NULL,                  -- Unix timestamp of parse completion
    parse_status    TEXT NOT NULL,                  -- 'SUCCESS', 'SYNTAX_ERROR', 'SKIPPED'
    error_message   TEXT                            -- SyntaxError details if parse_status == 'SYNTAX_ERROR'
);

CREATE VIEW IF NOT EXISTS codebase_files_meta AS 
SELECT file_path, mtime, sha256, size_bytes, node_count, edge_count, parsed_at AS last_indexed, parse_status, error_message 
FROM file_hashes;

-- 2. Codebase Structural Entities (Nodes)
CREATE TABLE IF NOT EXISTS nodes (
    id              TEXT PRIMARY KEY,               -- 'cogs/server_cog.py:ServerCog.start_server'
    workspace       TEXT NOT NULL,                  -- Canonical workspace root path
    file_path       TEXT NOT NULL REFERENCES file_hashes(file_path) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,                  -- 'module','class','function','async_function','method','async_method'
    name            TEXT NOT NULL,                  -- Simple identifier: 'start_server'
    qualified_name  TEXT NOT NULL,                  -- Scoped path: 'ServerCog.start_server'
    line_start      INTEGER NOT NULL,               -- 1-indexed start line
    line_end        INTEGER NOT NULL,               -- 1-indexed end line
    docstring       TEXT,                           -- Extracted docstring text (truncated)
    is_exported     BOOLEAN NOT NULL DEFAULT 1,     -- Defined in __all__ or at module level
    ast_hash        TEXT NOT NULL                   -- SHA-256 of AST subtree
);

-- 3. Callable Parameter Signatures
CREATE TABLE IF NOT EXISTS signatures (
    node_id             TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE,
    file_path           TEXT NOT NULL,
    posonly_args        TEXT NOT NULL,              -- JSON array: ["p1", "p2"]
    args                TEXT NOT NULL,              -- JSON array: ["server_id", "modpack_name"]
    defaults_count      INTEGER NOT NULL DEFAULT 0, -- Number of trailing positional args with defaults
    vararg              TEXT,                       -- Name of *args parameter or NULL
    kwonly_args         TEXT NOT NULL,              -- JSON array: ["timeout", "mode"]
    kw_defaults         TEXT NOT NULL,              -- JSON array of booleans: [false, true]
    kwarg               TEXT,                       -- Name of **kwargs parameter or NULL
    return_annotation   TEXT,                       -- Type annotation string or NULL
    is_async            BOOLEAN NOT NULL DEFAULT 0  -- 1 if async def, 0 if def
);

-- 4. Directed Structural Relationships (Edges)
CREATE TABLE IF NOT EXISTS edges (
    source_id           TEXT NOT NULL,              -- Caller node ID or child entity ID
    target_id           TEXT NOT NULL,              -- Callee node ID or parent entity ID
    relation_type       TEXT NOT NULL,              -- 'calls','imports','inherits','overrides','decorates','registers'
    file_path           TEXT NOT NULL,              -- File where relationship originates
    line_number         INTEGER NOT NULL,           -- Line number of the call / import
    call_args_count     INTEGER,                    -- Positional arg count at call site
    call_kwargs         TEXT,                       -- JSON array of keyword arg names passed: ["allocated_ram"]
    has_splat_pos       BOOLEAN DEFAULT 0,          -- 1 if *args used
    has_splat_kw        BOOLEAN DEFAULT 0,          -- 1 if **kwargs used
    is_awaited          BOOLEAN DEFAULT 0,          -- 1 if wrapped in ast.Await
    is_dynamic          BOOLEAN DEFAULT 0,          -- 1 if resolved via getattr / dynamic dispatch
    PRIMARY KEY (source_id, target_id, relation_type, line_number)
);

-- 5. Lifecycle Registrations & Synchronization Invariants
CREATE TABLE IF NOT EXISTS lifecycle_hooks (
    id                  TEXT PRIMARY KEY,           -- 'hook:cogs/server.py:85:app_commands'
    hook_name           TEXT NOT NULL,              -- 'app_commands.command','register_hook'
    handler_node_id     TEXT REFERENCES nodes(id) ON DELETE CASCADE,
    file_path           TEXT NOT NULL,
    line_number         INTEGER NOT NULL,
    registration_style  TEXT NOT NULL,              -- 'decorator','dispatch_dict','manifest_json'
    expected_invoker_id TEXT,                       -- 'bot.tree.sync'
    is_registered       BOOLEAN NOT NULL DEFAULT 1,
    status              TEXT NOT NULL DEFAULT 'ACTIVE' -- 'ACTIVE','ORPHAN','DEAD_REFERENCE','UNSYNCED'
);

-- Covering Indexes for Sub-Millisecond Traversal & SLA Compliance
CREATE INDEX IF NOT EXISTS idx_nodes_file ON nodes(file_path);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_qname ON nodes(qualified_name);
CREATE INDEX IF NOT EXISTS idx_edges_tgt_rel ON edges(target_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_edges_src_rel ON edges(source_id, relation_type);
CREATE INDEX IF NOT EXISTS idx_edges_file ON edges(file_path);
CREATE INDEX IF NOT EXISTS idx_signatures_file ON signatures(file_path);
CREATE INDEX IF NOT EXISTS idx_hooks_name ON lifecycle_hooks(hook_name);
CREATE INDEX IF NOT EXISTS idx_hooks_status ON lifecycle_hooks(status);
```

---

## 8. Authoritative SQLite Recursive CTE Traversal Queries

### 8.1 Transitive Reverse Callers (Blast Radius Traversal)
```sql
WITH RECURSIVE blast_radius(node_id, depth, path_tokens, display_chain) AS (
    -- Anchor Member: Direct callers (1 hop away)
    SELECT 
        source_id, 
        1, 
        '|' || ? || '|' || source_id || '|',
        source_id || ' -> ' || ?
    FROM edges
    WHERE target_id = ? AND relation_type IN ('calls', 'imports')
    
    UNION
    
    -- Recursive Member: Transitive callers up to max_depth
    SELECT 
        e.source_id, 
        br.depth + 1, 
        br.path_tokens || e.source_id || '|',
        e.source_id || ' -> ' || br.display_chain
    FROM edges e
    JOIN blast_radius br ON e.target_id = br.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND br.depth < ?
      AND instr(br.path_tokens, '|' || e.source_id || '|') = 0 -- Delimiter-safe cycle prevention invariant
)
SELECT 
    br.node_id,
    n.name,
    n.qualified_name,
    n.file_path,
    n.line_start,
    MIN(br.depth) AS shortest_hop_distance,
    br.display_chain AS representative_call_chain
FROM blast_radius br
JOIN nodes n ON br.node_id = n.id
GROUP BY br.node_id
ORDER BY shortest_hop_distance ASC, n.name ASC;
```

### 8.2 Forward Callee Dependency Tracing
```sql
WITH RECURSIVE callee_tree(node_id, depth, path_tokens, dependency_chain) AS (
    -- Anchor Member: Direct callees
    SELECT 
        target_id, 
        1, 
        '|' || ? || '|' || target_id || '|',
        ? || ' -> ' || target_id
    FROM edges
    WHERE source_id = ? AND relation_type IN ('calls', 'imports')
    
    UNION
    
    -- Recursive Member: Transitive dependencies
    SELECT 
        e.target_id, 
        ct.depth + 1, 
        ct.path_tokens || e.target_id || '|',
        ct.dependency_chain || ' -> ' || e.target_id
    FROM edges e
    JOIN callee_tree ct ON e.source_id = ct.node_id
    WHERE e.relation_type IN ('calls', 'imports')
      AND ct.depth < ?
      AND instr(ct.path_tokens, '|' || e.target_id || '|') = 0 -- Delimiter-safe cycle prevention
)
SELECT 
    ct.node_id,
    n.name,
    n.qualified_name,
    n.file_path,
    MIN(ct.depth) AS shortest_hop_distance,
    ct.dependency_chain
FROM callee_tree ct
JOIN nodes n ON ct.node_id = n.id
GROUP BY ct.node_id
ORDER BY shortest_hop_distance ASC;
```

---

## 9. Gatekeeper Review Readiness & Solo-Developer Invariant

### 9.1 Protocol Alignment with `scripts/consult_critic.py`
In strict alignment with the Ratified Constitution (`.specify/constitution.md`) and Gatekeeper Council Protocol (Rule 6 in `rules/AGENTS.md`), this specification blueprint has been authored for formal audit by DeepSeek-V4.1-Flash via `scripts/consult_critic.py`:

```powershell
python "scripts/consult_critic.py" --file "specs/003-omni-graph/plan.md" --out "specs/003-omni-graph/critic_review.md" --mode rfc --timeout 60.0
```

### 9.2 Hardcoded Solo-Developer Context & Ponytail Simplicity Invariant
The review prompt dispatched to DeepSeek-V4.1-Flash MUST explicitly mandate that:
1. **Personal Solo Developer Project**: This system is built for a single autonomous developer operating on a local workstation. DeepSeek MUST NOT impose enterprise compliance rituals, multi-tenant RBAC, SOC2/HIPAA audit trails, corporate governance committees, or distributed cluster consensus.
2. **Ponytail Simplicity ("Dùng tốt không lỗi là được")**: The smallest working diff wins. Zero external dependencies (100% Python Standard Library `ast` and embedded `sqlite3` WAL) is the ratified invariant. DeepSeek MUST evaluate against practical reliability, edge-case coverage, and prevention of real-world defects (such as SVBot incident `7f5ce17d-936e-41bd-897d-2449ffe52a4a`).
3. **Mandatory Schema Compliance**: To achieve `"verdict": "APPROVED"`, `critical_vulnerabilities` must be `[]`, and `edge_cases` must contain $\ge 3$ concrete, mitigated failure scenarios (`minItems: 3`).

---

*Architectural blueprint formulated and validated for Omni-Kernel v4.1.*
