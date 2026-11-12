# Feature Specification: DSH Empirical Peer Auditor (Omni-Auditor v4.2)

**Feature Branch**: `004-dsh-empirical-auditor`  
**Created**: 2026-11-10  
**Status**: Ratified (Approved by DeepSeek-V4.1-Flash Gatekeeper, Exit Code 0)  
**Input Documents**:
- `ORIGINAL_REQUEST.md` (Requirements R1, R2, R3, R4 & Acceptance Criteria)
- `PROJECT_DEEPSEEK_V41_AUDITOR.md` (Strict Architecture Gatekeeper Blueprint)
- `.specify/constitution.md` (Omni-Kernel v4.2 Constitution)
- `scripts/consult_critic.py` (Zero-Dependency DeepSeek Gatekeeper Client)
- `scripts/dsh_auditor.py` (DSH Headless Empirical Bridge Prototype)
- Reference SDD: `specs/002-deepseek-v41-auditor/spec.md`, `specs/003-omni-graph/spec.md`

---

## 1. Executive Summary & Problem Statement

### 1.1 The Dual-Model Paradigm: Cognitive Gatekeeper vs. Empirical Reality Auditor
In autonomous multi-agent software engineering within Omni-Kernel v4.2, architectural verification and code verification require two fundamentally distinct cognitive modes that cannot be unified in a single agent or a purely cognitive model:

1. **The Cognitive Gatekeeper (`consult_critic.py` powered by DeepSeek-V4.1-Flash API)**:
   - Operates in the **Cognitive & Semantic Space**.
   - Performs static, zero-runtime architectural red-teaming, specification review (RFC/FRC analysis), and adversarial logic critique.
   - Leverages a native 1,000,000-token context window to inspect cross-module design contracts, constitutional invariants, API schemas, and data boundary hazards.
   - Evaluates: *"Is this architectural proposal logically sound, free from blind spots, and aligned with constitutional constraints?"*

2. **The Empirical Reality Auditor (DeepSeek Harness `dsh.cmd` via Headless Execution)**:
   - Operates in the **Physical & Runtime Codebase Space**.
   - Performs dynamic, active runtime code execution, running real shell commands (`pwsh`, `cmd`, `bash`), linters (`ruff`, `mypy`), compilers, and integration test suites.
   - Directly probes live operating system resources, database files, process tables, socket listeners, and concurrency locks on the host filesystem.
   - Evaluates: *"Does this code actually compile, execute, and pass assertions under real operating system conditions without deadlocks, file contention, or memory leaks?"*

```
+---------------------------------------------------------------------------------------------------+
|                                        OMNI-KERNEL v4.2                                           |
+---------------------------------------------------------------------------------------------------+
|                              EXECUTIVE ORCHESTRATOR & PLANNER                                     |
|                             (Google Antigravity / Gemini Model)                                   |
+-------------------------------------------------+-------------------------------------------------+
|              COGNITIVE GATEKEEPER               |            EMPIRICAL REALITY AUDITOR            |
|     `consult_critic.py` (DeepSeek-V4.1-Flash)   |       `dsh.cmd` (DeepSeek Harness Headless)     |
+-------------------------------------------------+-------------------------------------------------+
| Domain: Static Architecture & Design Review     | Domain: Active Runtime Code Execution & Testing |
| Channel: Direct Cloud HTTPS REST API            | Channel: Local Headless CLI Subprocess (`dsh`)   |
| Medium: Markdown Specifications (RFC/FRC/Diffs) | Medium: Real OS Filesystem, Git, & SQLite DBs   |
| Execution: Zero-Execution Cognitive Reasoning   | Execution: Real-time shell commands (`pwsh`)    |
| Core Question: "Is this design logically sound?"| Core Question: "Does this code run & pass?"     |
+-------------------------------------------------+-------------------------------------------------+
```

This establishes an expanded **Four-Tier Separation of Powers (Tam Quyền Phân Lập Mở Rộng)**:
- **Executive & Planner (Google Antigravity / Agy)**: Mission decomposition, code authoring, user UX.
- **Cognitive Gatekeeper (`consult_critic.py`)**: Theoretical soundness, invariant verification, edge-case red-teaming.
- **Empirical Reality Auditor (`dsh.cmd` / `scripts/dsh_auditor.py`)**: Physical code execution, concurrency stress-testing, regression validation.
- **Tri-Worker Fleet (`local_worker_mi50`, `groq_worker_cloud`, `gemini_worker_cloud`)**: Tactical code mutation, boilerplate generation, large-context refactoring.

### 1.2 Pathology & Failure Modes of Single-Agent Development
When autonomous engineering systems rely solely on a single agent or internal subagents of identical model weights, they consistently succumb to four severe failure modes:

1. **The "Illusion of Completion" (Ảo tưởng hoàn thành)**:
   - An agent writes code, inspects its own generated syntax, and concludes: *"Implementation is complete and verified."*
   - In reality, the code was never executed. Hidden syntax errors, missing standard library imports, or subtle runtime type mismatches remain undiscovered until human review or production crash.

2. **Phantom Dependencies & Environment Desynchronization**:
   - The planner assumes third-party packages or environment variables exist based on generic training priors (e.g., assuming `uvloop`, `orjson`, or custom binaries are installed on Windows).
   - Only an active execution agent running `python -c "import ..."` can deterministically ground claims against host reality.

3. **Runtime Concurrency Hazards & OS Locking**:
   - Multi-threaded or multi-process systems (such as SQLite WAL databases, file-based IPC, or web servers) behave differently under real OS kernel scheduling than in abstract code reviews.
   - SQLite WAL concurrency limits (`database is locked`), busy timeouts, and Windows NTFS file handle locks (`WinError 32: The process cannot access the file because it is being used by another process`) cannot be predicted with 100% certainty by cognitive reasoning alone without empirical stress testing.

4. **Sycophantic Echo-Chamber Self-Review**:
   - When an agent harness spawns duplicate subagents of the same family to verify its own work, the reviewer shares identical blind spots, politely validating flawed code rather than attempting to break it.
   - An independent harness (DeepSeek Harness) running a completely different model family (`deepseek-flash`) acts as a genuine adversarial peer.

### 1.3 Empirical Grounding: The SQLite Concurrency Case Study
The necessity and efficacy of the DSH Empirical Peer Auditor was empirically verified on this host workspace across a real two-turn audit cycle examining SQLite Write-Ahead Logging (WAL) concurrency contention (`scratch/test_concurrency_issue.py`).

#### Empirical Case Study Context:
- **Environment**: Windows 11, Python 3.12, NTFS filesystem.
- **Test Target**: `scratch/test_concurrency_issue.py`.
- **Target Logic**: 5 concurrent worker threads performing read-modify-write cycles on a shared SQLite table `counters (id INTEGER PRIMARY KEY, count INTEGER)`.
- **Flaw in Code**: Each worker thread opened a connection with `timeout=0.01` (10 ms busy timeout) while holding an exclusive `BEGIN IMMEDIATE` transaction for `0.05` s (50 ms sleep), with `PRAGMA journal_mode` left at default `delete` rather than `wal`, and lacking deterministic connection cleanup in `finally` blocks.

#### 🔴 Turn 1: Deadlock Reproduction & Forensic Diagnosis
- **Timestamp**: `1794335606989` to `1794335623220` (Total Duration: **16.23 seconds**).
- **Session ID**: `session-17573175-f9d3-43e3-92b2-9c29d7c8d8fa`.
- **Model**: `deepseek-flash` (DeepSeek Official Provider).
- **CLI Command Executed**:
  ```powershell
  dsh.cmd --profile headless --permission-mode danger-full-access --approval-policy never --json "Run the Python script scratch/test_concurrency_issue.py via PowerShell. Observe the output and tell me if it fails and why."
  ```
- **Autonomous Tool Execution Sequence by DSH**:
  1. `pwsh`: Executed `python scratch/test_concurrency_issue.py 2>&1` -> Captured output:
     ```
     FAILED: 4 thread(s) encountered errors:
       Worker 1: database is locked
       Worker 2: database is locked
       Worker 4: database is locked
       Worker 3: database is locked
     EXIT_CODE=1
     ```
  2. `read`: Inspected full source code of `scratch/test_concurrency_issue.py`.
  3. `pwsh`: Probed database state directly:
     ```powershell
     python -c "import sqlite3; c=sqlite3.connect('scratch/test_wal.db'); print('journal_mode:', c.execute('PRAGMA journal_mode').fetchone()[0]); print('count:', c.execute('SELECT count FROM counters WHERE id=1').fetchone()[0])"
     ```
     Observed: `journal_mode: delete, count: 1` (4 increments lost).
  4. `pwsh`: Created isolated probe script `scratch/_tmp_check.py` to test hypothesis with `timeout=5.0` -> Confirmed 5/5 threads succeed.
- **Forensic Diagnosis by DSH**:
  > *"The failure is a self-inflicted SQLite lock-timeout mismatch in `worker()`: `sqlite3.connect(DB_PATH, timeout=0.01)` (10 ms busy timeout) vs `time.sleep(0.05)` inside `BEGIN IMMEDIATE` (50 ms exclusive write lock hold). Since 50 ms ≫ 10 ms, the losing 4 threads hit `OperationalError: database is locked`. Furthermore, `PRAGMA journal_mode` reports `delete`, not `wal`. Connections are not closed on exception, causing connection leaks."*
- **Turn 1 Metrics**:
  - Duration: 16.23s | Input Tokens: 198 | Output Tokens: 833 | Cache Read: 7,808 tokens | Total Tokens: 8,839.

#### 🟢 Turn 2: Stateful Session Resume & Patch Verification
- **Timestamp**: `1794335646420` to `1794335659618` (Total Duration: **13.20 seconds**, meeting the $<14\text{s}$ SLA).
- **Session Continuation**: Reused `--session-id session-17573175-f9d3-43e3-92b2-9c29d7c8d8fa`.
- **Agy Action**: Applied patch setting `PRAGMA journal_mode=WAL`, `timeout=5.0`, and wrapping in `try ... finally: conn.close()`.
- **CLI Command Executed**:
  ```powershell
  dsh.cmd --profile headless --permission-mode danger-full-access --approval-policy never --session-id session-17573175-f9d3-43e3-92b2-9c29d7c8d8fa --json "I have updated scratch/test_concurrency_issue.py: enabled WAL mode, set timeout=5.0, and ensured conn.close() in finally block. Please re-run scratch/test_concurrency_issue.py via PowerShell and verify if it succeeds now."
  ```
- **Autonomous Tool Execution Sequence by DSH**:
  1. `read`: Verified the source code modifications in `scratch/test_concurrency_issue.py`.
  2. `pwsh`: Re-ran `python scratch/test_concurrency_issue.py 2>&1` -> Captured output:
     ```
     SUCCESS: All 5 threads completed cleanly. Final count = 5
     EXIT_CODE=0
     ```
  3. `pwsh`: Re-verified `PRAGMA journal_mode` was `wal` and ran a second repeated verification to ensure determinism.
- **Verification Verdict by DSH**:
  > *"SUCCESS: All 5 threads completed cleanly. Final count = 5 | EXIT_CODE=0. Verified details: Exit code 0 (previously 1); Errors collected: none; Final count: 5; PRAGMA journal_mode: wal. Repeated run: identical clean result."*
- **Turn 2 Metrics**:
  - Duration: 13.20s | Input Tokens: 180 | Output Tokens: 490 | Cache Read: 10,496 tokens (**94.0% Cache Hit Rate**) | Total Tokens: 11,166.

#### Empirical Case Study Comparison Matrix:

| Metric / Dimension | Turn 1: Deadlock Reproduction | Turn 2: Patch Verification | Empirical Gain / Outcome |
|---|---|---|---|
| **Audit Objective** | Reproduce & diagnose SQLite concurrency lock | Verify WAL + timeout=5.0 + deterministic close | Complete defect lifecycle resolved |
| **Execution Status** | `FAILED (Exit Code: 1)` | `SUCCESS (Exit Code: 0)` | 100% Pass rate verified |
| **Elapsed Wall-Clock Time** | **16.23s** | **13.20s** | **18.7% faster; meets $<14\text{s}$ SLA** |
| **Autonomous Tools Used** | `pwsh` (x3), `read` (x1), probe creation | `read` (x1), `pwsh` (x2) | Fully autonomous zero-human loop |
| **Context Cache Hit** | 7,808 tokens | 10,496 tokens | **94.0% Cache Hit via `--session-id`** |
| **Total Tokens Billed** | 8,839 tokens | 11,166 tokens | Low cost, high context retention |
| **Filesystem Safety Hazard**| Created `scratch/_tmp_check.py` | Verified without file pollution | Emphasizes need for DWR Tier 2 |

### 1.4 Scope Boundaries & Non-Goals
- **In-Scope (Milestone 2 Deliverables)**:
  1. Complete, formal FRC and SDD specification governing DSH Empirical Peer Auditor.
  2. Architectural specification of Dynamic Workspace Resolver (DWR) spanning 3 tiers (In-Place, Scratch Sandbox, Shadow Git Worktree) and 7-category decision matrix.
  3. Protocol specification of Dual-Agent Mutual Exclusion & Mutation Provenance Protocol (MMPP) spanning Mutex Lockfile, SHA-256 Fingerprint Ledger, and Context Injection.
  4. Zero-dependency module architecture and class designs for `scripts/dsh_auditor.py`.
  5. 21 Functional Requirements (FR-001 through FR-021) and 6 Non-Functional Requirements (NFR-001 through NFR-006).
  6. 15 Exhaustive Edge Cases & Concrete Mitigations (EC-001 through EC-015).
  7. Independent Gatekeeper Review Plan via `consult_critic.py` (DeepSeek-V4.1-Flash).
- **Non-Goals (Explicitly Out-of-Scope for Milestone 2)**:
  1. Authoring execution code in `scripts/dsh_auditor.py` (strictly allocated to Milestone 3 per R1.2 in `ORIGINAL_REQUEST.md`).
  2. Modifying `DeepSeek Harness.exe` or its internal Electron package files (`app.asar`).
  3. Modifying `consult_critic.py` (which is already ratified and operational).
  4. Enterprise distributed clustering or multi-machine orchestration (DSH runs strictly on local host).

---

## 2. Prioritized User Stories (Given-When-Then Format)

### User Story 1 (P1 - Core Headless DSH Subprocess Dispatch & NDJSON Parsing) 🎯 MVP
**As an** autonomous orchestrator (Agy) or developer,  
**I want** to dispatch empirical testing tasks to DeepSeek Harness via its headless CLI (`dsh.cmd`) and parse the resulting NDJSON event stream in real time,  
**So that** I receive structured execution data (tool calls, stdout/stderr, thinking reasoning, and conclusive evaluation) without opening a GUI or manual intervention.

- **Why this priority**: Core execution primitive. All downstream workspace routing and safety protocols depend on reliable subprocess dispatch and streaming event extraction.
- **Independent Test**: Execute `python scripts/dsh_auditor.py --task "Get-Date" --tier tier_1_in_place --json` and verify clean JSON output with `exit_code: 0` in $<10\text{s}$.

#### Acceptance Scenarios:
1. **Scenario 1.1 (Clean Headless Dispatch & NDJSON Event Capture)**:
   - **Given** a valid shell verification task (e.g., `"Run pytest on tests/test_tier1.py"`),
   - **When** the auditor client executes `dsh.cmd --profile headless --permission-mode danger-full-access --approval-policy never --json -`,
   - **And** feeds the prompt through `stdin`,
   - **Then** the client captures streaming NDJSON lines, deserializes `session`, `status`, `thinking`, `tool_call`, `tool_result`, `text`, and `final` events,
   - **And** returns a structured `AuditResult` object containing the tool execution trace and overall verdict.

2. **Scenario 1.2 (Subprocess Execution Timeout Guardrail)**:
   - **Given** an empirical test script that hangs indefinitely in an infinite loop or deadlock,
   - **When** the execution time exceeds `task.timeout_sec` (e.g., 60 seconds),
   - **Then** the auditor client forcefully terminates the process tree using Windows `taskkill /F /T /PID <pid>`,
   - **And** releases all held locks, returning `AuditResult(success=False, error="EXECUTION_TIMEOUT")` with collected partial diagnostics.

---

### User Story 2 (P1 - Dynamic Workspace Resolver: Tier Routing)
**As an** autonomous orchestrator (Agy),  
**I want** the system to automatically assign an appropriate workspace isolation tier (In-Place, Scratch Sandbox, or Shadow Git Worktree) based on the task risk category,  
**So that** read-only verification is fast, concurrency reproduction does not pollute the repository, and speculative refactoring never damages the working copy.

- **Why this priority**: Essential to avoid file pollution, Git staging contamination, and accidental modification of source files during audit.
- **Independent Test**: Dispatch tasks of category `STATIC_AUDIT`, `DB_CONCURRENCY`, and `REFACTOR_EVAL`; verify correct CWD, `--add-dir` flags, and Git worktree provisioning.

#### Acceptance Scenarios:
1. **Scenario 2.1 (Tier 1 In-Place Verification with Mutation Prohibition)**:
   - **Given** an audit task classified as `STATIC_AUDIT` or `TEST_EXISTING`,
   - **When** DWR provisions Tier 1,
   - **Then** `cwd` is set to `<repo_root>`,
   - **And** if any source file changes between pre-run and post-run SHA-256 scans, the system detects `VIOLATION_TIER1_UNAUTHORIZED_MUTATION`, rolls back the modified files via Git, and reports failure.

2. **Scenario 2.2 (Tier 2 Scratch Sandbox with `--add-dir` Mounting & Evidence Retention)**:
   - **Given** an audit task classified as `DB_CONCURRENCY` or `BUG_REPRODUCE`,
   - **When** DWR provisions Tier 2,
   - **Then** it creates `scratch/dsh_sandbox_<session_id>_<timestamp>/` as `cwd` and appends `--add-dir "<repo_root>"`,
   - **And** if the audit passes, the sandbox directory is cleanly deleted,
   - **And** if the audit fails, the entire sandbox (including `*.db`, `*.db-wal`, and repro scripts) is preserved for forensic inspection.

3. **Scenario 2.3 (Tier 3 Shadow Git Worktree with Patch Extraction)**:
   - **Given** an audit task classified as `REFACTOR_EVAL` or `SPECULATIVE_FIX`,
   - **When** DWR provisions Tier 3,
   - **Then** it creates a detached Git worktree at `scratch/shadow_worktrees/dsh_shadow_<session_id>/`,
   - **And** allows DSH to mutate source files within the shadow worktree,
   - **And** upon completion, extracts a unified diff patch to `scratch/patches/dsh_patch_<session_id>.patch`,
   - **And** removes the worktree cleanly with `git worktree remove --force` without affecting Agy's working tree.

---

### User Story 3 (P1 - Dual-Agent Mutual Exclusion & Mutation Provenance Protocol)
**As a** system engineer maintaining multi-agent stability,  
**I want** a 3-layer protection protocol (Lockfile, SHA-256 Ledger, Context Injection) active during DSH execution,  
**So that** Agy and DSH never overwrite each other's files simultaneously and every file change has clear cryptographic provenance.

- **Why this priority**: Guarantees zero race conditions, prevents blind overwrites, and ensures complete traceability of changes made by either agent.
- **Independent Test**: Attempt concurrent lock acquisition; verify atomic rejection. Modify a file in DSH and inspect `.agy_provenance.jsonl` record.

#### Acceptance Scenarios:
1. **Scenario 3.1 (Atomic Mutex Lockfile Acquisition & Stale Recovery)**:
   - **Given** DSH begins executing an audit in Tier 1 or Tier 2,
   - **When** `LockManager.acquire()` is called,
   - **Then** it atomically acquires `<repo_root>/.dsh_audit.lock` via pre-staged atomic rename `os.rename(tmp_path, lock_path)` (invoking Win32 `MoveFileW`),
   - **And** if a stale lockfile exists whose PID is confirmed dead via Windows `ctypes.windll.kernel32.OpenProcess`, or an orphaned 0-byte lockfile older than 5.0 seconds is detected, it automatically reclaims the lock safely.

2. **Scenario 3.2 (SHA-256 Fingerprint Delta & Provenance Ledger Logging)**:
   - **Given** an audit task that mutates permitted files,
   - **When** DSH completes its execution,
   - **Then** `ProvenanceLedger` compares post-run SHA-256 digests against pre-run snapshots,
   - **And** appends an immutable JSON record to `.agy_provenance.jsonl` detailing file path, before/after hashes, author (`dsh`), and timestamp.

3. **Scenario 3.3 (Context Injection Header Boundary Enforcement)**:
   - **Given** an audit prompt from Agy,
   - **When** `ContextInjector` constructs the final input string,
   - **Then** it prepends an immutable Context Injection Header declaring the active Tier, read-only paths (`GEMINI.md`, `hooks.json`, `.agents/*`), and Agy's recent file modifications.

---

### User Story 4 (P2 - Stateful Multi-Turn Session Continuation)
**As an** orchestrator iterating through multi-turn bug-fixing cycles,  
**I want** to reuse an existing session ID (`--session-id <id>`) across sequential audit calls,  
**So that** DSH maintains full conversational memory, diagnostic history, and achieves $>90\%$ context cache hit rates.

- **Why this priority**: Significantly reduces latency (from 16.2s to 13.2s) and token cost by leveraging DeepSeek Prompt Caching across iterative fix-verify loops.
- **Independent Test**: Dispatch Turn 1 (failure repro), capture `sessionId`, dispatch Turn 2 with `--session-id <id>`, verify cache read tokens $>90\%$ and session history preserved.

#### Acceptance Scenarios:
1. **Scenario 4.1 (Prompt Cache Hit on Stateful Continuation)**:
   - **Given** a completed Turn 1 with session ID `session-xxxx`,
   - **When** Turn 2 is dispatched with `--session-id session-xxxx`,
   - **Then** DSH resumes the session context without re-ingesting the initial code files,
   - **And** the status usage event reports `cacheReadTokens / totalTokens >= 0.90`.

---

### User Story 5 (P2 - Independent Gatekeeper Architecture Review via `consult_critic.py`)
**As a** system architect validating specification compliance,  
**I want** `specs/004-dsh-empirical-auditor/spec.md` independently audited by DeepSeek-V4.1-Flash via `consult_critic.py`,  
**So that** architectural flaws, missing Windows edge cases, and scope violations are detected without Gemini self-review bias.

- **Why this priority**: Enforces the Constitutional Gatekeeper invariant (Council Gate) before task implementation begins.
- **Independent Test**: Execute `python scripts/consult_critic.py --file specs/004-dsh-empirical-auditor/spec.md --out specs/004-dsh-empirical-auditor/gatekeeper_review.md --mode rfc` and inspect exit code and findings.

---

## 3. Core Concepts & DSH CLI Execution Model

### 3.1 Binary Location & Electron-as-Node Runtime
DeepSeek Harness is deployed on the host environment as a compiled Electron desktop application. However, its command-line interface operates via a dedicated Node.js bridge embedded in its runtime distribution:

- **Canonical CLI Path**:
  `C:\Users\vuhuu\AppData\Local\Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd`
- **Internal Execution Wrapper (`dsh.cmd`)**:
  ```cmd
  @echo off
  setlocal DisableDelayedExpansion
  set "ELECTRON_RUN_AS_NODE=1"
  "%~dp0..\..\..\..\DeepSeek Harness.exe" --expose-internals "%~dp0..\..\..\app.asar\dsh\node_modules\@deepseek-ai\dsh-desktop-host\lib\cli.js" %*
  exit /b %errorlevel%
  ```
- **Runtime Properties**:
  - Setting `ELECTRON_RUN_AS_NODE=1` bypasses the entire Electron Chromium GUI stack.
  - Spawns as a lean Node.js process executing `cli.js` directly from the unpacked ASAR archive.
  - Cold start time: $<1.2\text{ s}$; Warm execution turnaround: $<300\text{ ms}$.
  - Memory consumption: $\approx 45\text{ MB}$ to $85\text{ MB}$ RSS.

### 3.2 Headless Flags & CLI Parameter Contract
Invoking `dsh.cmd --profile headless --help` defines the headless execution contract:

| Flag Name | Argument / Type | Description & Operational Behavior | Auditor Usage Contract |
|---|---|---|---|
| `--profile` | `headless` | Activates non-interactive headless runner. Answers one task and exits. | **Mandatory** on all calls |
| `--permission-mode` | `read-only` \| `workspace-write` \| `danger-full-access` | Controls filesystem write permissions. `danger-full-access` allows full shell/FS access. | Set to `danger-full-access` (guarded by MMPP) or `workspace-write` |
| `--approval-policy` | `ask` \| `never` | Interactive approval policy. `never` automatically denies actions requiring user prompts, ensuring non-blocking automated execution. | **Mandatory `never`** |
| `--session-id` | `<uuid_or_string>` | Adopts an existing persisted session. If ID is unknown, DSH returns an error. If omitted, DSH generates a new session UUID. | Omit on Turn 1; supply on Turn 2+ |
| `--add-dir` | `<absolute_path>` | Mounts an additional physical absolute directory under `workspace-write` (repeatable flag). | Primary mechanism for **Tier 2 Scratch Sandbox** |
| `--json` | *(flag)* | Emits newline-delimited JSON run events (NDJSON) to `stdout` instead of final message only. Diagnostics go to `stderr`. | **Mandatory** for programmatic stream parsing |
| `task` | `"-"` or `"<string>"` | The task instruction string. Passing `"-"` instructs DSH to read task text from standard input (`stdin`). | **Mandatory `"-"` + pipe via stdin** to eliminate Windows command line escaping bugs |

#### The Stdin Pipe Standard (`"-"`):
On Windows, passing large prompts or code snippets via command-line arguments (`dsh "prompt..."`) suffers from:
1. Windows `CreateProcess` command-line length limit of 8,191 characters.
2. `cmd.exe` quote stripping, double-quote corruption, and newline truncation.
By passing `"-"` as the task argument and piping UTF-8 encoded text through `proc.stdin`, the auditor client achieves:
- **Unlimited prompt length** (supporting large context injections).
- **Zero quote escaping errors** (verbatim code snippets and JSON strings remain intact).
- **Zero shell injection vulnerabilities**.

### 3.3 NDJSON Event Stream Grammar & Schemas
When `--json` is specified, DSH emits streaming events as single-line JSON objects to `stdout`. The event stream strictly adheres to the following lifecycle state machine:

```
[Process Start]
       │
       ▼
   `session` (Session ID & CWD)
       │
       ▼
   `status` (phase: "turn_start", turn: 1)
       │
       ▼
   `status` (phase: "step_start", turn: 1, step: N)
       │
       ├───────────────────────────────────────────┐
       ▼                                           ▼
   `thinking` (CoT reasoning stream)         `tool_call` (Dispatched command)
       │                                           │
       ▼                                           ▼
   `text` (Markdown assistant response)      `tool_result` (Host execution output)
       │                                           │
       └─────────────────────┬─────────────────────┘
                             ▼
   `status` (phase: "step_end", turn: 1, step: N, usage: {tokens})
       │
       ├─► (Repeat step_start ... step_end if multiple steps needed)
       │
       ▼
   `status` (phase: "turn_end", turn: 1, reason: {"kind": "completed"})
       │
       ▼
   `final` (Aggregated conclusive verdict & markdown text)
       │
[Process Exit 0]
```

#### JSON Schemas for All 8 Event Types:

```json
// 1. session event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "sessionId", "cwd"],
  "properties": {
    "type": { "const": "session" },
    "sessionId": { "type": "string" },
    "cwd": { "type": "string" }
  }
}

// 2. status event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "phase", "turn"],
  "properties": {
    "type": { "const": "status" },
    "phase": { "enum": ["turn_start", "step_start", "step_end", "turn_end"] },
    "turn": { "type": "integer" },
    "step": { "type": "integer" },
    "usage": {
      "type": "object",
      "properties": {
        "inputTokens": { "type": "integer" },
        "outputTokens": { "type": "integer" },
        "cacheReadTokens": { "type": "integer" },
        "cacheWriteTokens": { "type": "integer" },
        "totalTokens": { "type": "integer" }
      }
    },
    "reason": {
      "type": "object",
      "properties": {
        "kind": { "type": "string" }
      }
    }
  }
}

// 3. thinking event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "text"],
  "properties": {
    "type": { "const": "thinking" },
    "text": { "type": "string" }
  }
}

// 4. tool_call event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "callId", "tool", "input"],
  "properties": {
    "type": { "const": "tool_call" },
    "callId": { "type": "string" },
    "tool": { "type": "string" },
    "input": { "type": "object" }
  }
}

// 5. tool_result event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "callId", "status", "result"],
  "properties": {
    "type": { "const": "tool_result" },
    "callId": { "type": "string" },
    "status": { "enum": ["completed", "failed", "aborted"] },
    "result": { "type": "string" }
  }
}

// 6. text event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "text"],
  "properties": {
    "type": { "const": "text" },
    "text": { "type": "string" }
  }
}

// 7. final event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "sessionId", "reason", "text"],
  "properties": {
    "type": { "const": "final" },
    "sessionId": { "type": "string" },
    "reason": {
      "type": "object",
      "properties": {
        "kind": { "type": "string" }
      }
    },
    "text": { "type": "string" }
  }
}

// 8. error event
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["type", "message"],
  "properties": {
    "type": { "const": "error" },
    "message": { "type": "string" }
  }
}
```

### 3.4 Stateful Multi-Turn Session Lifecycle & Storage Architecture
- **Session Storage Location**:
  `C:\Users\vuhuu\.dsh\sessions\--<url-encoded-cwd>--\session-<uuid>\session.v4.jsonl.zstd`
- **Storage Mechanics**:
  - DSH persists full conversation trees and tool execution histories in a Multi-frame Zstandard compressed log (`0xFD2FB528`).
  - When `--session-id <id>` is provided on a subsequent call, DSH seeks into the existing session store, initializes its prompt context from the cached state, and issues a delta request to the DeepSeek API.
  - DeepSeek servers recognize the shared context prefix, resulting in a **$\ge 90\%$ cache read token hit**, drastically reducing latency and operational inference expense.

---

## 4. Dynamic Workspace Resolver (DWR) Architecture

### 4.1 Architectural Rationale & Tier Taxonomy
Not all empirical audit tasks possess the same risk profile. Running a read-only linter on production code requires zero isolation, whereas stress-testing multi-threaded SQLite database transactions can lock or corrupt files, and evaluating an autonomous multi-file refactoring can leave uncommitted diffs across the entire codebase.

The Dynamic Workspace Resolver (DWR) partitions audit tasks into three deterministic tiers:

```
+---------------------------------------------------------------------------------------------------+
|                                 DYNAMIC WORKSPACE RESOLVER (DWR)                                  |
+---------------------------------------------------------------------------------------------------+
|                                        AuditTask Submitted                                        |
|                                (Category, Prompt, Target Files)                                   |
+-------------------------------------------------+-------------------------------------------------+
                                                  │
                                                  ▼
                                       Evaluate Category & Intent
                                                  │
         ┌────────────────────────────────────────┼────────────────────────────────────────┐
         ▼                                        ▼                                        ▼
+----------------------------------+ +----------------------------------+ +----------------------------------+
|      Tier 1: In-Place            | |      Tier 2: Scratch Sandbox     | |      Tier 3: Shadow Worktree   |
|   `TIER_1_IN_PLACE`              | |   `TIER_2_SCRATCH_SANDBOX`       | |   `TIER_3_SHADOW_WORKTREE`     |
+----------------------------------+ +----------------------------------+ +----------------------------------+
| - CWD: `<repo_root>`             | | - CWD: `scratch/dsh_sandbox_...` | | - CWD: `scratch/shadow_work...`|
| - Permission: Read-Only Invariant| | - Mounted: `--add-dir <repo_root>`| | - Mode: Detached HEAD Worktree |
| - Zero overhead (<10ms setup)    | | - Isolated temp DBs & scripts    | | - Full freedom to mutate code  |
| - Pre/Post SHA-256 validation    | | - PASS: Automatic cleanup (rm)   | | - PASS: Unified patch exported |
| - Rollback on violation          | | - FAIL: 100% evidence retained   | | - Teardown: Worktree pruned    |
+----------------------------------+ +----------------------------------+ +----------------------------------+
```

### 4.2 Tier 1: In-Place Workspace (`TIER_1_IN_PLACE`)
- **Intent**: High-speed, zero-overhead verification of existing codebases, static analysis, unit test execution, and type checking against current workspace files.
- **Activation Scope**: `STATIC_AUDIT`, `TEST_EXISTING`.
- **Operating Parameters**:
  - `cwd`: `<repo_root>`
  - CLI Flags: `--profile headless --permission-mode danger-full-access --approval-policy never --json -`
- **Safety Invariant & Mutation Guard**:
  - Tier 1 enforces a strict **Read-Only Invariant**. DSH is strictly prohibited from modifying source code or persisting new files in `<repo_root>`.
  - Prior to dispatch, `ProvenanceLedger` records a cryptographic SHA-256 snapshot of all repository files (filtering out paths matching `TIER1_SNAPSHOT_IGNORE_DIRS` and `TIER1_SNAPSHOT_IGNORE_FILE_PATTERNS`).
  - Upon completion, `ProvenanceLedger` executes a verification scan. If any repository file was modified or created outside of designated log and test cache files:
    1. Triggers `VIOLATION_TIER1_UNAUTHORIZED_MUTATION`.
    2. For modified tracked files: executes safe automated rollback via `safe_git_checkout(repo_root, file)` wrapped in a 3-attempt jittered exponential backoff retry loop (delays: 200ms, 500ms, 1000ms $\pm 50$ms jitter) with pre-attempt stale lock recovery (`ensure_git_index_unlocked`), resolving transient collisions with concurrent git operations.
    3. For newly created untracked files (e.g. `scripts/_debug.py`): permanently unlinks them via `os.unlink(normalized_path)`.
    4. Records an emergency incident in `.agy_provenance.jsonl`.
    5. Marks `AuditResult.success = False` with diagnostic violation details.

### 4.3 Tier 2: Scratch Sandbox (`TIER_2_SCRATCH_SANDBOX`)
- **Intent**: Controlled reproduction of complex bugs, multi-threaded database concurrency stress-tests, generation of throwaway test harnesses, or benchmarking probes without dirtying the git working copy.
- **Activation Scope**: `BUG_REPRODUCE`, `DB_CONCURRENCY`, `ISOLATED_PROBE`, `STRESS_TEST`.
- **Directory Layout & Multi-Directory Mounting**:
  - Path: `<repo_root>/scratch/dsh_sandbox_<session_id>_<timestamp>/` (Permanently Git-ignored under `scratch/`).
  - `cwd` is set to this scratch directory: all new files created by DSH (e.g., temporary databases `test_wal.db`, probe scripts `reproduce.py`) default to the sandbox.
  - **Mounting Main Repository**: DWR injects the CLI flag:
    `--add-dir "<repo_root>"`
    This permits DSH tools (`pwsh`, `read`) to inspect, import, and execute modules from the main codebase while ensuring file generation lands inside the sandbox.
  - Environment Injection: Sets `PYTHONPATH=<repo_root>;<repo_root>/scripts;%PYTHONPATH%`.
- **Lifecycle & Retention SLA**:
  - **Case A: Audit PASS (`exit_code == 0`)**:
    - Tests or reproduction assertions passed cleanly.
    - **Pre-Cleanup Process Tree Termination**: Prior to initiating directory deletion, DWR executes `taskkill /F /T /PID <dsh_pid>` to ensure all child, grandchild, and worker processes (such as `python.exe`, `node.exe`, `pwsh.exe`, and SQLite background engines) are forcefully terminated, releasing all OS kernel file handles.
    - **Robust Deletion Protocol (`purge_directory_robust`)**: DWR executes directory deletion using an exponential backoff retry loop (4 attempts: 0ms, 150ms, 350ms, 750ms) equipped with an `onerror` callback that resets read-only file attributes via `os.chmod(path, stat.S_IWRITE)`.
    - **Deferred Cleanup Registration**: If file handle contention (`WinError 32`) or file system locking persists after 4 attempts, DWR logs a warning to `sys.stderr` and appends an entry to `<repo_root>/scratch/.deferred_cleanups.txt` for resolution during the next startup sweep (FR-021), rather than failing the audit bridge or silently leaving partial files via `ignore_errors=True`.
    - Records run summary in `scratch/audit_runs.jsonl`.
  - **Case B: Audit FAIL (`exit_code != 0`, crash, assertion failure, deadlock)**:
    - **100% Retention Directive**: The sandbox directory is preserved **completely intact**.
    - **Forensic Marker Placement**: DWR touches a marker file `<sandbox_path>/.audit_failure_evidence` containing the timestamp, session ID, and failure exit code. This marker prevents the Automated Startup Sandbox Sweep (FR-021) from ever purging failure evidence directories.
    - All database files (`*.db`, `*.db-wal`, `*.db-shm`), error logs, core dumps, and reproduction scripts remain untouched.
    - Sandbox path is populated into `AuditResult.sandbox_evidence_path` for immediate forensic analysis by Agy.

### 4.4 Tier 3: Shadow Git Worktree (`TIER_3_SHADOW_WORKTREE`)
- **Intent**: Heavy, multi-file code refactoring, AST structural transformations, and speculative bug-fixing where DSH must modify real source files without corrupting Agy's active working copy or Git index.
- **Activation Scope**: `REFACTOR_EVAL`, `SPECULATIVE_FIX`, `MULTI_FILE_TRANSFORM`.
- **Worktree Provisioning & Transient Lock Resilience**:
  - Target Path: `<repo_root>/scratch/shadow_worktrees/dsh_shadow_<session_id>/`
  - Created via standard Git command:
    `git worktree add --detach <shadow_path> HEAD`
  - **Jittered Exponential Backoff**: Provisioning is wrapped in an autonomous retry loop:
    ```python
    import os
    import time
    import random
    import subprocess

    def safe_git_worktree_add(repo_root: str, shadow_path: str, ref: str = "HEAD") -> None:
        """
        Provisions a shadow git worktree with 3-attempt jittered exponential backoff
        and automated stale index lock recovery.
        """
        delays = [0.2, 0.5, 1.0]
        last_error = ""

        for attempt, base_delay in enumerate(delays, start=1):
            # Pre-flight check and purge stale index.lock (>30s)
            ensure_git_index_unlocked(repo_root)

            res = subprocess.run(
                ["git", "worktree", "add", "--detach", shadow_path, ref],
                cwd=repo_root,
                capture_output=True,
                text=True
            )
            if res.returncode == 0:
                return

            last_error = res.stderr.strip()
            # If failed due to index.lock or transient file contention, back off with jitter
            jitter = random.uniform(0.0, 0.1)
            time.sleep(base_delay + jitter)

        raise RuntimeError(f"Failed to provision git worktree after 3 attempts: {last_error}")
    ```
  - Ensures a detached HEAD state with zero branch naming collisions and zero impact on Agy's active branches or staging index.
- **Execution & Isolation**:
  - `cwd` is set to `<shadow_path>`.
  - DSH has full freedom to edit source files, compile targets, and run test suites.
- **Diff & Patch Harvesting**:
  - Upon DSH completion, DWR executes inside `<shadow_path>`:
    `git diff HEAD > scratch/patches/dsh_patch_<session_id>.patch`
  - If DSH committed changes:
    `git format-patch -1 HEAD --stdout > scratch/patches/dsh_patch_<session_id>.patch`
  - Computes SHA-256 digest of the patch file and attaches the path to `AuditResult.diff_patch_path`.
- **Teardown & Cleanup Protocol**:
  - Standard teardown:
    1. `git worktree remove --force <shadow_path>`
    2. `git worktree prune`
  - Handled with Windows NTFS retry loop (3 attempts with exponential backoff: 200ms, 500ms, 1000ms) to resolve transient locks from background scanner handles.

### 4.5 DWR Decision Matrix (7 Task Categories)

| Task Category | Audit Intent & Objectives | Mutation Risk Level | Selected Tier | CWD | Primary CLI Flags | Cleanup SLA on PASS | Retention SLA on FAIL |
|---|---|---|---|---|---|---|---|
| `STATIC_AUDIT` | Linting (`ruff`, `flake8`), static typing (`mypy`, `pyright`), syntax validation | None (0%) | **Tier 1 (In-Place)** | `<repo_root>` | `--permission-mode danger-full-access` | N/A | Execution log in JSON |
| `TEST_EXISTING`| Running pre-existing test suites (`pytest`, `unittest`) | Very Low (<2%) | **Tier 1 (In-Place)** | `<repo_root>` | `--permission-mode danger-full-access` | N/A | Stdout / Stderr logs |
| `BUG_REPRODUCE`| Reproducing obscure bugs, race conditions, edge-case probes | Medium (Temp DBs/Files) | **Tier 2 (Scratch Sandbox)** | `scratch/dsh_sandbox_<id>` | `--add-dir <repo_root>` | Full directory purged | **Full evidence folder retained** |
| `DB_CONCURRENCY`| SQLite WAL contention, transaction deadlocks, busy timeout tests | Medium (WAL contention) | **Tier 2 (Scratch Sandbox)** | `scratch/dsh_sandbox_<id>` | `--add-dir <repo_root>` | Purged (`rmtree`) | **DB, WAL, SHM, & scripts retained** |
| `ISOLATED_PROBE`| One-off exploratory probe, performance benchmark script | Low-Med (Scratch scripts) | **Tier 2 (Scratch Sandbox)** | `scratch/dsh_sandbox_<id>` | `--add-dir <repo_root>` | Purged (`rmtree`) | **Retained** |
| `REFACTOR_EVAL`| Multi-file architecture refactor, signature migration | High (100% source mutation) | **Tier 3 (Shadow Worktree)** | `scratch/shadow_worktrees/<id>` | `--permission-mode danger-full-access` | Worktree removed; Patch exported | Worktree removed; Patch & Fail log retained |
| `SPECULATIVE_FIX`| Autonomous bug fix authoring and iterative test verification | High (Source code edits) | **Tier 3 (Shadow Worktree)** | `scratch/shadow_worktrees/<id>` | `--permission-mode danger-full-access` | Worktree removed; Patch exported | Worktree removed; Patch & Fail log retained |

---

## 5. Dual-Agent Mutual Exclusion & Mutation Provenance Protocol (MMPP)

When Antigravity (Agy) and DeepSeek Harness (DSH) operate concurrently in the same repository workspace, uncoordinated operations can cause race conditions, dirty working tree conflicts, or blind overwrites. MMPP enforces deterministic multi-agent safety across three physical and logical defense layers:

```
+---------------------------------------------------------------------------------------------------+
|                        DUAL-AGENT MUTUAL EXCLUSION & PROVENANCE PROTOCOL (MMPP)                   |
+---------------------------------------------------------------------------------------------------+
|  Layer 1: Mutex Lockfile          |  Layer 2: Provenance Ledger       |  Layer 3: Context         |
|  (`.dsh_audit.lock`)              |  (`.agy_provenance.jsonl`)        |  Injection                |
+-----------------------------------+-----------------------------------+---------------------------+
| - Atomic rename (MoveFileW)       | - Pre-run SHA-256 snapshot        | - Boundary banner injected|
| - JSON metadata with PID & scope  | - Post-run SHA-256 snapshot       | - Read-only invariant list|
| - Stale lock recovery via ctypes  | - Blind overwrite detection       | - Lists Agy recent edits  |
|   Windows OpenProcess liveness    | - Append-only NDJSON audit ledger | - Sets authorized writable|
| - Heartbeat thread update         | - Unified diff patch recording    |   workspace boundaries    |
+-----------------------------------+-----------------------------------+---------------------------+
```

### 5.1 Layer 1: Workspace Mutex Lockfile (`.dsh_audit.lock`)
- **Path**: `<repo_root>/.dsh_audit.lock`
- **JSON Payload Schema**:
  ```json
  {
    "lock_version": "1.1",
    "nonce": "a7b3c9f2-5d41-4e89-a123-9876543210ab",
    "pid": 14280,
    "agent": "dsh",
    "session_id": "session-17573175-f9d3-43e3-92b2-9c29d7c8d8fa",
    "hostname": "DESKTOP-VUHUU",
    "acquired_at": "2026-11-10T19:15:00.123456Z",
    "heartbeat_at": "2026-11-10T19:15:15.654321Z",
    "timeout_sec": 120.0,
    "scope": "tier_1_in_place"
  }
  ```

- **Atomic Acquisition Protocol (Zero-Byte Safe & Windows NTFS Hardened)**:
  1. Generates unique cryptographic `nonce = str(uuid.uuid4())`.
  2. **Pre-Staged Payload Creation**: Writes complete JSON payload (including `nonce`, current timestamp, and PID) into a private temporary file:
     `<lock_path>.<nonce>.tmp`
     Flushes and synchronizes via `f.flush()` and `os.fsync(f.fileno())`. This guarantees the payload is 100% written and valid on disk prior to publication.
  3. **Atomic Mutual Exclusion Barrier (Direct Pre-Staged Rename)**:
     Enters an acquisition retry loop (up to `max_retries = 20` or deadline `timeout_sec`):
     - **Direct Atomic Rename**:
       Attempts direct atomic publication of the pre-staged payload:
       `os.rename(tmp_path, lock_path)`
     - **Windows NTFS Kernel Semantics & 0-Byte Immunity**:
       On Windows NTFS, `os.rename` invokes Win32 `MoveFileW`. This operation is atomic at the OS filesystem directory-entry level and provides two critical guarantees:
       1. It raises `FileExistsError` (`WinError 183: ERROR_ALREADY_EXISTS`) if `lock_path` already exists, preserving strict mutual exclusion without race windows.
       2. It **NEVER creates an intermediate 0-byte file** on disk (in contrast to legacy `os.open(O_CREAT | O_EXCL)` followed by `os.replace`), completely eliminating the window where concurrent readers encounter 0 bytes or where concurrent readers hold open read handles that trigger `PermissionError` (`WinError 5: Access is denied` / `WinError 32: Sharing violation`) on subsequent replace attempts.
     - **Success Path**:
       - Marks `held = True`.
       - Spawns background daemon thread updating `heartbeat_at` every $\text{timeout\_sec} / 4$ (default 5s).
       - Returns `True`.
     - **Contention & Windows Error Handling**:
       - Catches **BOTH `FileExistsError` and `PermissionError`** (Win32 `ERROR_ALREADY_EXISTS` [WinError 183], `ERROR_ACCESS_DENIED` [WinError 5], and `ERROR_SHARING_VIOLATION` [WinError 32]).
       - Immediately initiates the **Safe Stale Lock Recovery Procedure** (Step 4).
       - If stale recovery does not reclaim the lock, sleeps with jittered exponential backoff:
         $$t_{\text{sleep}} = 0.05 \times 1.5^{\min(\text{attempt}, 5)} + \text{uniform}(0.01, 0.03)$$
       - Retries acquisition.
  4. **Safe Stale Lock Recovery Procedure (Anti-Theft CAS Protocol & Stale 0-Byte Recovery)**:
     - **Defensive Read & Stale 0-Byte Inspection**: Opens and reads `.dsh_audit.lock`.
       - Wraps read in `try...except (FileNotFoundError, PermissionError, json.JSONDecodeError, ValueError)`.
       - **Stale 0-Byte File Reclamation**: If `.dsh_audit.lock` exists on disk but contains 0 bytes (`len == 0`):
         - Evaluates file age: `age_sec = time.time() - os.path.getmtime(lock_path)`.
         - **If `age_sec > 5.0` seconds**: Recognizes this as a stale orphaned 0-byte file left by an interrupted or aborted writer. Cleanly unlinks it via `os.unlink(lock_path)`, logs a warning to `stderr` (`"Purged stale orphaned 0-byte lockfile: %s (age=%.2fs)" % (lock_path, age_sec)`), and immediately proceeds to retry acquisition rather than yielding indefinitely.
         - **If `age_sec <= 5.0` seconds**: Treats this as a transient peer creation/swap in progress; yields and retries with backoff.
       - If the file is missing or transiently locked, yields and retries without crashing.
     - **Heartbeat & Liveness Verification**:
       - If valid JSON is read, calculates elapsed heartbeat delta: $\Delta t = \text{now} - \text{lock['heartbeat_at']}$.
       - If $\Delta t > \text{lock['timeout_sec']}$:
         - Evaluates Windows process liveness via kernel exit code inspection:
           ```python
           import ctypes
           PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
           STILL_ACTIVE = 259
           
           h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, lock['pid'])
           if not h:
               is_alive = False
           else:
               exit_code = ctypes.c_ulong()
               success = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
               ctypes.windll.kernel32.CloseHandle(h)
               # ONLY consider alive if API call succeeded AND exit_code == STILL_ACTIVE (259)
               is_alive = bool(success and exit_code.value == STILL_ACTIVE)
           ```
         - **Two-Phase Atomic Ownership Claim (`.reclaim`)**:
           - If `is_alive is False` (PID is terminated, crashed, or invalid):
             1. Generates private reclaim path: `reclaim_path = f"{lock_path}.{uuid.uuid4().hex}.reclaim"`.
             2. Attempts atomic ownership claim:
                `os.rename(lock_path, reclaim_path)`
             3. If `os.rename` raises `FileNotFoundError` or `PermissionError`: another competing agent already claimed ownership or owner released. Yields immediately.
             4. If `os.rename` succeeds: Candidate process now exclusively owns the stale file.
             5. Inspects `reclaim_path`: Validates `reclaimed_data["nonce"] == lock["nonce"]`.
                - **If matching**: Confirms stale lock ownership. Safely unlinks `reclaim_path`. Logs warning to `stderr`: `"Reclaimed stale workspace lock held by dead PID %d"`. Immediately proceeds to acquire.
                - **If mismatched**: Another agent acquired and published a new lock between inspection and rename. Restores the new lock immediately via `os.replace(reclaim_path, lock_path)` and aborts reclaim.
  5. **Orphan Cleanup Invariant**:
     - In `finally` block of acquisition: If `held is False` and `tmp_path` exists, unlinks `tmp_path`.

- **Deterministic Release Protocol (Anti-Race & Nonce Invariant)**:
  1. Validates that `self.held is True`.
  2. Signals and terminates heartbeat renewal daemon thread (`thread.join(timeout=1.0)`).
  3. Reads existing `.dsh_audit.lock`.
  4. Strictly validates that `caller_nonce == lock['nonce']`, `caller_pid == lock['pid']`, AND `caller_session_id == lock['session_id']`.
  5. If validation passes: unlinks `.dsh_audit.lock`.
  6. If validation fails (e.g., lock was reclaimed during an extreme stall): logs critical error without unlinking, preventing accidental deletion of a newer agent's lock.

- **Atomic Heartbeat Renewal Protocol (Zero-Byte Truncation Prevention)**:
  - While held, daemon thread wakes up every 5.0 seconds.
  - Prepares updated payload with `heartbeat_at = datetime.now(timezone.utc).isoformat()`.
  - Writes payload to private file `<lock_path>.<nonce>.hb.tmp`.
  - Swaps atomically via `os.replace(tmp_hb, lock_path)`.
  - Eliminates file truncation and guarantees concurrent readers never encounter 0 bytes during heartbeat updates.

### 5.2 Layer 2: SHA-256 Pre/Post Fingerprint Scanner & `.agy_provenance.jsonl` Ledger
- **Canonical Snapshot Ignore Contract**:
  To prevent false-positive mutation alerts during `TEST_EXISTING` and `STATIC_AUDIT` invocations, `ProvenanceLedger` enforces the canonical `TIER1_SNAPSHOT_IGNORE_PATTERNS`:
  ```python
  TIER1_SNAPSHOT_IGNORE_DIRS = {
      # Version control & agent orchestration
      ".git", ".agents/teamwork", "scratch",
      # Third-party dependencies & environments
      "node_modules", "build", "dist", ".venv", "venv", "env",
      # Python compiler caches
      "__pycache__",
      # Test runner, linter & coverage diagnostic caches (Adversarial Finding 6)
      ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
      ".hypothesis", "htmlcov"
  }

  TIER1_SNAPSHOT_IGNORE_FILE_PATTERNS = {
      ".pyc", ".pyo", ".pyd", ".coverage", ".coverage."
  }
  ```

- **Snapshot Scanner Algorithm**:
  1. Recursively walks `<repo_root>` via `os.walk(repo_root)`.
  2. Modifies `dirs[:] = [d for d in dirs if d not in TIER1_SNAPSHOT_IGNORE_DIRS and not d.endswith(".egg-info")]` in-place, skipping deep directory traversal into cache and dependency trees for maximum performance (<20 ms per NFR-001).
  3. Skips any file matching `TIER1_SNAPSHOT_IGNORE_FILE_PATTERNS` or starting with `.coverage`.
  4. For all remaining repository files: evaluates cached `mtime`. If `mtime` matches the pre-computed cache, reuses the prior SHA-256 digest; otherwise, recalculates SHA-256 digest and records `(sha256, mtime)` into an in-memory dictionary.
- **Blind Overwrite Detection & Rollback**:
  - Compares post-run snapshot with pre-run snapshot.
  - If a file $F$ changed:
    - If task was in Tier 1 (In-Place) or $F$ was not in the declared mutable scope:
      1. Flags `BLIND_OVERWRITE_DETECTED`.
      2. Captures unified diff using `difflib.unified_diff`.
      3. Automatically restores $F$ to its pre-run state.
      4. Appends conflict incident to ledger with `conflict_detected: true`.
- **Append-Only NDJSON Ledger Format (`.agy_provenance.jsonl`)**:
  ```json
  {
    "event_id": "prov-20261110-191530-001",
    "timestamp": "2026-11-10T19:15:30.102450Z",
    "session_id": "session-17573175-f9d3-43e3-92b2-9c29d7c8d8fa",
    "agent": "dsh",
    "action": "MODIFY",
    "file_path": "scratch/test_concurrency_issue.py",
    "sha256_before": "4a7d3c01bf628a7e...",
    "sha256_after": "8f2e91ca0d54e1bb...",
    "diff_summary": "+15 -3 lines",
    "mtime": 1731291325.45,
    "workspace_tier": "tier_1_in_place",
    "verified_by": "agy_sentinel",
    "conflict_detected": false
  }
  ```

### 5.3 Layer 3: Context Injection Protocol
Before any task prompt is piped into DSH via `stdin`, `ContextInjector` wraps it in an immutable boundary contract:

```markdown
=== EMPIRICAL AUDIT TASK DISPATCH ===
Originator: Antigravity Orchestrator (Agy)
Session ID: {session_id} | Turn: {turn_number}
Workspace Tier: {tier_name} ({workspace_path})

### 🛡️ MUTATION BOUNDARIES & SAFETY CONSTRAINTS:
1. READ-ONLY INVARIANTS (STRICTLY PROHIBITED FROM MODIFICATION):
   - GEMINI.md, .cursorrules, hooks.json, setup.bat
   - .agents/teamwork/* (All agent state folders)
   - .git/* (Git repository metadata)
   {custom_read_only_paths}

2. AUTHORIZED WORKSPACE:
   - Primary CWD: {cwd}
   - Mounted Read-Only: {mounted_dirs}
   - Writable Zone: {writable_zone_description}

3. RECENT MODIFICATIONS BY AGY (LAST 3 TURNS):
   {agy_recent_modified_files_list}

### 🎯 EMPIRICAL AUDIT DIRECTIVE:
{actual_task_prompt}
======================================
```

---

## 6. Module Architecture for `scripts/dsh_auditor.py`

### 6.1 Architectural Topology & Class Diagram

```
+---------------------------------------------------------------------------------------------------+
|                                      scripts/dsh_auditor.py                                       |
+---------------------------------------------------------------------------------------------------+
  │
  ├── [Data Models & Enums]
  │     ├── WorkspaceTier (Enum: TIER_1_IN_PLACE, TIER_2_SCRATCH_SANDBOX, TIER_3_SHADOW_WORKTREE)
  │     ├── AuditCategory (Enum: STATIC_AUDIT, TEST_EXISTING, BUG_REPRODUCE, DB_CONCURRENCY, ...)
  │     ├── AuditTask (Dataclass: task_id, prompt, category, tier, target_paths, timeout_sec, ...)
  │     ├── AuditResult (Dataclass: session_id, success, exit_code, duration_sec, tool_calls, ...)
  │     ├── ToolCallRecord (Dataclass: call_id, tool_name, command_input, status, result_output)
  │     ├── SessionState (Dataclass: session_id, turns, active_tier, current_workspace_path)
  │     ├── ProvenanceRecord (Dataclass: event_id, timestamp, file_path, sha256_before, sha256_after)
  │     ├── LockPayload (Dataclass: lock_version, nonce, pid, agent, session_id, hostname, heartbeat_at, ...)
  │     └── SweepReport (Dataclass: entries_processed, entries_purged, entries_deferred, orphans_purged, errors)
  │
  ├── [Core Subsystems]
  │     ├── DynamicWorkspaceResolver (DWR)
  │     │     ├── evaluate_tier(category, read_only) -> WorkspaceTier
  │     │     ├── provision_workspace(tier, session_id) -> WorkspaceContext
  │     │     ├── teardown_workspace(context, success, child_pid) -> CleanupSummary
  │     │     ├── purge_directory_robust(dir_path, max_retries) -> bool
  │     │     └── sweep_deferred_cleanups(repo_root) -> SweepReport
  │     │
  │     ├── LockManager (MMPP Layer 1)
  │     │     ├── acquire(session_id, scope, timeout_sec, retry_deadline_sec) -> bool
  │     │     ├── release() -> bool
  │     │     ├── _heartbeat_loop() -> None (atomic .hb.tmp swap)
  │     │     ├── _is_process_alive(pid) -> bool (GetExitCodeProcess == 259)
  │     │     └── _attempt_stale_reclaim(expected_nonce) -> bool (atomic .reclaim rename)
  │     │
  │     ├── ProvenanceLedger (MMPP Layer 2)
  │     │     ├── take_snapshot(workspace_dir) -> Dict[str, Tuple[str, float]]
  │     │     ├── compute_delta(before, after) -> List[ProvenanceRecord]
  │     │     ├── detect_blind_overwrites(delta, tier, target_paths) -> List[Conflict]
  │     │     └── append_to_ledger(records: List[ProvenanceRecord]) -> None
  │     │
  │     ├── ContextInjector (MMPP Layer 3)
  │     │     └── build_injected_prompt(task: AuditTask, session: SessionState) -> str
  │     │
  │     ├── NDJSONStreamParser
  │     │     ├── feed_line(line: str) -> Optional[DSHRunEvent]
  │     │     └── get_aggregated_results() -> Tuple[List[ToolCallRecord], str]
  │     │
  │     └── SessionManager
  │           ├── get_or_create_session(session_id: Optional[str]) -> SessionState
  │           ├── save_session_state(session: SessionState) -> None
  │           └── record_turn(session_id, turn_data) -> None
  │
  └── [High-Level Orchestrator Client & CLI]
        ├── DSHAuditorClient
        │     ├── execute_audit(task: AuditTask) -> AuditResult
        │     └── _spawn_dsh_subprocess(cmd_args, prompt, cwd, timeout) -> ProcessResult
        │
        └── main() CLI Entrypoint (Argparse: human-readable or `--json` structured output)
```

### 6.2 Data Classes & Enums Specification

```python
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import os
import uuid
import platform
from datetime import datetime, timezone

class WorkspaceTier(str, Enum):
    TIER_1_IN_PLACE = "tier_1_in_place"
    TIER_2_SCRATCH_SANDBOX = "tier_2_scratch_sandbox"
    TIER_3_SHADOW_WORKTREE = "tier_3_shadow_worktree"

class AuditCategory(str, Enum):
    STATIC_AUDIT = "STATIC_AUDIT"
    TEST_EXISTING = "TEST_EXISTING"
    BUG_REPRODUCE = "BUG_REPRODUCE"
    DB_CONCURRENCY = "DB_CONCURRENCY"
    ISOLATED_PROBE = "ISOLATED_PROBE"
    REFACTOR_EVAL = "REFACTOR_EVAL"
    SPECULATIVE_FIX = "SPECULATIVE_FIX"

@dataclass
class AuditTask:
    prompt: str
    category: AuditCategory
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    tier_override: Optional[WorkspaceTier] = None
    session_id: Optional[str] = None
    target_paths: List[str] = field(default_factory=list)
    timeout_sec: float = 60.0
    read_only: bool = False

@dataclass
class ToolCallRecord:
    call_id: str
    tool_name: str
    command_input: Dict[str, Any]
    status: str = "pending"
    result_output: Optional[str] = None
    error_message: Optional[str] = None

@dataclass
class AuditResult:
    task_id: str
    session_id: str
    success: bool
    exit_code: int
    duration_sec: float
    verdict_text: str
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    cache_hit_rate: float = 0.0
    total_tokens: int = 0
    workspace_tier: WorkspaceTier = WorkspaceTier.TIER_1_IN_PLACE
    diff_patch_path: Optional[str] = None
    sandbox_evidence_path: Optional[str] = None
    provenance_records: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class LockPayload:
    lock_version: str = "1.1"
    nonce: str = field(default_factory=lambda: str(uuid.uuid4()))
    pid: int = field(default_factory=os.getpid)
    agent: str = "dsh"
    session_id: str = ""
    hostname: str = field(default_factory=platform.node)
    acquired_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    heartbeat_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timeout_sec: float = 120.0
    scope: str = "tier_1_in_place"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LockPayload":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

@dataclass(frozen=True)
class SweepReport:
    entries_processed: int
    entries_purged: int
    entries_deferred: int
    orphans_purged: int
    errors: List[str]
```

### 6.3 Subsystem Interface Contracts

#### 1. `DynamicWorkspaceResolver (DWR)`
- `evaluate_tier(category: AuditCategory, read_only: bool) -> WorkspaceTier`: Evaluates category against the Decision Matrix.
- `provision_workspace(tier: WorkspaceTier, session_id: str) -> WorkspaceContext`:
  - Tier 1: Validates repo root, takes pre-run snapshot, returns context.
  - Tier 2: Creates directory `scratch/dsh_sandbox_<session_id>_<timestamp>/`, prepares `--add-dir "<repo_root>"`, returns context.
  - Tier 3: Runs `git worktree add --detach <shadow_path> HEAD`, verifies clean index, returns context.
- `teardown_workspace(context: WorkspaceContext, success: bool, child_pid: Optional[int] = None) -> CleanupSummary`:
  - Tier 1: Verifies zero mutation, raises violation if dirty.
  - Tier 2:
    - If `success == True`:
      1. If `child_pid` is provided, invokes `terminate_process_tree(child_pid)` via `taskkill /F /T /PID`.
      2. Invokes `purge_directory_robust(context.workspace_path)`.
      3. If directory remains on disk, appends `<sandbox_path>|<child_pid>|<session_id>|<iso_ts>` to `scratch/.deferred_cleanups.txt`.
    - If `success == False`: Creates `.audit_failure_evidence` marker, preserves 100% of directory, and populates `evidence_path`.
  - Tier 3: Harvests `git diff HEAD > patch_file`, runs `git worktree remove --force` and `git worktree prune`.
- `purge_directory_robust(dir_path: str, max_retries: int = 4) -> bool`:
  - Retries `shutil.rmtree` up to 4 times with exponential backoff (0ms, 150ms, 350ms, 750ms).
  - Handles `PermissionError` / read-only attributes by clearing write flags via `os.chmod(path, stat.S_IWRITE)`.
  - Returns `True` if directory was removed completely; `False` if file locks prevented deletion.
- `sweep_deferred_cleanups(repo_root: str) -> SweepReport`:
  - Invoked automatically during `DynamicWorkspaceResolver` initialization.
  - Reads `<repo_root>/scratch/.deferred_cleanups.txt`.
  - For each recorded entry, verifies process termination via Win32 `OpenProcess(0x1000, False, pid)`. If dead, attempts `purge_directory_robust()`.
  - Atomically writes back unresolvable entries to `.deferred_cleanups.txt.tmp` and executes `os.replace()`; unlinks the file if all entries are purged.
  - Performs an orphaned directory scan on `scratch/dsh_sandbox_*` older than 24 hours lacking `.audit_failure_evidence` markers.
  - Returns structured `SweepReport(entries_processed, entries_purged, entries_deferred, orphans_purged, errors)`.

#### 2. `LockManager`
Manages workspace mutual exclusion on Windows NTFS via atomic lockfile and anti-theft stale reclamation.

```python
class LockManager:
    def __init__(self, repo_root: str, lock_filename: str = ".dsh_audit.lock"):
        self.lock_path: str = os.path.join(repo_root, lock_filename)
        self.current_payload: Optional[LockPayload] = None
        self.held: bool = False
        self._stop_heartbeat: threading.Event = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None

    def acquire(
        self,
        session_id: str,
        scope: str = "tier_1_in_place",
        timeout_sec: float = 120.0,
        retry_deadline_sec: float = 10.0,
        base_backoff_sec: float = 0.05
    ) -> bool:
        """Acquires exclusive workspace lock using pre-staged temp file and direct atomic rename.
        
        - Writes complete payload to '<lock_path>.<nonce>.tmp' and fsyncs.
        - Executes os.rename(tmp_path, lock_path) (invoking Win32 MoveFileW) for direct atomic acquisition.
        - Avoids legacy os.open(O_CREAT | O_EXCL) + os.replace 0-byte intermediate file windows.
        - Catches BOTH FileExistsError (WinError 183) and PermissionError (WinError 5 / 32).
        - Automatically unlinks stale orphaned 0-byte lockfiles older than 5.0 seconds.
        - Attempts two-phase atomic stale reclaim if holder is dead or heartbeat expired.
        - Retries with jittered exponential backoff until retry_deadline_sec expires.
        - Raises LockContentionError if lock cannot be acquired within retry_deadline_sec.
        """
        ...

    def release(self) -> bool:
        """Releases the workspace lock after verifying nonce, pid, and session_id ownership.
        
        - Stops and joins the heartbeat renewal thread.
        - Validates that disk lockfile nonce matches current_payload.nonce.
        - Unlinks lockfile on verified ownership match.
        - Returns True on clean release; False if lock was lost or mismatched.
        """
        ...

    def _is_process_alive(self, pid: int) -> bool:
        """Inspects Windows process liveness via OpenProcess and GetExitCodeProcess.
        
        - Calls OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid).
        - If handle obtained, calls GetExitCodeProcess(h, byref(exit_code)).
        - Closes handle via CloseHandle(h).
        - Returns True ONLY if exit_code.value == 259 (STILL_ACTIVE).
        - Eliminates false positives from lingering Windows kernel handles.
        """
        ...

    def _attempt_stale_reclaim(self, expected_nonce: str) -> bool:
        """Executes safe two-phase stale reclamation using atomic rename.
        
        - Attempts os.rename(lock_path, f'{lock_path}.{nonce}.reclaim').
        - On FileNotFoundError or PermissionError: returns False (yields to competitor).
        - On rename success: inspects reclaim file.
          - If reclaim_payload.nonce == expected_nonce: unlinks reclaim file and returns True.
          - If reclaim_payload.nonce != expected_nonce: rolls back via os.replace() and returns False.
        """
        ...

    def _heartbeat_loop(self) -> None:
        """Daemon thread updating heartbeat_at periodically.
        
        - Runs every max(timeout_sec / 4.0, 1.0) seconds.
        - Writes updated payload to '<lock_path>.<nonce>.hb.tmp'.
        - Swaps atomically via os.replace() to prevent 0-byte truncation.
        """
        ...
```

#### 3. `ProvenanceLedger`
- `take_snapshot(root_dir: str) -> Dict[str, Tuple[str, float]]`: Computes SHA-256 and `mtime` for all tracked source files, omitting `.git/`, `scratch/`, `.agents/`.
- `compute_delta(before, after) -> List[ProvenanceRecord]`: Detects created, modified, or deleted files.
- `detect_blind_overwrites(delta, tier, allowed_paths) -> List[Conflict]`: Reverts unauthorized modifications in Tier 1.
- `append_to_ledger(records: List[ProvenanceRecord]) -> None`: Appends NDJSON lines to `.agy_provenance.jsonl`.

#### 4. `NDJSONStreamParser`
- Parses streaming stdout line by line.
- Maintains FSM tracking current `turn`, `step`, and matching `tool_call` with `tool_result` via `callId`.
- Extracts token metrics from `status(step_end)` events and computes cache hit percentage:
  $$\text{CacheHitRate} = \frac{\text{cacheReadTokens}}{\text{totalTokens}} \times 100\%$$

#### 5. `DSHAuditorClient`
- High-level orchestrator class coordinating DWR, LockManager, ProvenanceLedger, ContextInjector, and NDJSONStreamParser.
- **Dynamic Binary Discovery Precedence**:
  1. Explicit environment variable: `os.environ.get("DSH_CLI_PATH")`
  2. System PATH resolution: `shutil.which("dsh")` or `shutil.which("dsh.cmd")`
  3. Default host installation path: `%LOCALAPPDATA%\Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd`
- Executes DSH as:
  ```python
  dsh_binary = (
      os.environ.get("DSH_CLI_PATH")
      or shutil.which("dsh")
      or shutil.which("dsh.cmd")
      or os.path.expandvars(r"%LOCALAPPDATA%\Programs\DeepSeek Harness\resources\runtime\cli\bin\dsh.cmd")
  )

  proc = subprocess.Popen(
      [dsh_binary, "--profile", "headless", "--permission-mode", "danger-full-access",
       "--approval-policy", "never", "--json", "-"] + extra_flags,
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      cwd=workspace_context.cwd,
      text=True,
      encoding="utf-8",
      bufsize=1
  )
  ```
- **Pipe Buffer Deadlock Prevention (Tri-Thread Streaming Architecture)**:
  On Windows operating systems, anonymous pipes (`subprocess.PIPE`) are backed by kernel ring buffers sized between 4KB and 64KB. If a child process emits voluminous diagnostic output, warnings, or stack traces to `stderr` exceeding 64KB, the child process kernel thread blocks on `write(stderr)`. If the parent process only reads `stdout` and writes `stdin`, execution halts in a permanent bi-directional pipe buffer deadlock.

  To guarantee 100% deadlock immunity under arbitrary prompt and stderr volumes, `DSHAuditorClient` coordinates **three concurrent execution threads** during real-time streaming:

  ```python
  import subprocess
  import threading
  from typing import List, Tuple

  def execute_streaming_subprocess(
      cmd_args: List[str],
      injected_prompt: str,
      cwd: str,
      timeout_sec: float
  ) -> Tuple[int, List[str], List[str]]:
      """
      Spawns DSH subprocess with concurrent Tri-Thread I/O management:
      - Main Thread: Iterates line-by-line over proc.stdout and feeds NDJSON parser.
      - Thread 1 (Stdin Feeder): Pushes injected_prompt to proc.stdin and immediately closes stdin.
      - Thread 2 (Stderr Drainer): Concurrently reads proc.stderr to an in-memory buffer,
        preventing Windows 64KB pipe buffer deadlocks.
      """
      proc = subprocess.Popen(
          cmd_args,
          stdin=subprocess.PIPE,
          stdout=subprocess.PIPE,
          stderr=subprocess.PIPE,
          cwd=cwd,
          text=True,
          encoding="utf-8",
          bufsize=1  # Line-buffered
      )

      stderr_diagnostics: List[str] = []
      stdout_lines: List[str] = []

      # Thread 1: Dedicated Stdin Feeder
      def stdin_feeder_worker():
          try:
              if proc.stdin:
                  proc.stdin.write(injected_prompt)
                  proc.stdin.flush()
                  proc.stdin.close()  # Signals EOF to DSH stdin
          except (BrokenPipeError, OSError):
              pass  # Child process exited early or rejected input

      # Thread 2: Dedicated Stderr Drainer (Immunity against >64KB buffer deadlocks)
      def stderr_drainer_worker():
          try:
              if proc.stderr:
                  for err_line in proc.stderr:
                      stderr_diagnostics.append(err_line)
          except (ValueError, OSError):
              pass

      feeder_thread = threading.Thread(target=stdin_feeder_worker, name="DSH-StdinFeeder", daemon=True)
      drainer_thread = threading.Thread(target=stderr_drainer_worker, name="DSH-StderrDrainer", daemon=True)

      feeder_thread.start()
      drainer_thread.start()

      # Watchdog Timer: Protects against silent child hangs & deadlocks on synchronous stdout iteration
      timed_out = [False]
      def on_timeout():
          timed_out[0] = True
          # Hard-kill child process tree via Win32 taskkill; closing anonymous pipe breaks blocking stdout loop
          subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)

      watchdog_timer = threading.Timer(timeout_sec, on_timeout)
      watchdog_timer.start()

      # Main Thread: Stream and parse NDJSON lines in real time
      try:
          if proc.stdout:
              for line in proc.stdout:
                  stdout_lines.append(line)
                  # stream_parser.feed_line(line)
          proc.wait()
      finally:
          watchdog_timer.cancel()
          feeder_thread.join(timeout=2.0)
          drainer_thread.join(timeout=2.0)

      if timed_out[0]:
          raise subprocess.TimeoutExpired(cmd_args, timeout_sec)

      return proc.returncode, stdout_lines, stderr_diagnostics
  ```
- **Watchdog Timer & Synchronous Pipe Unblocking Protocol**:
  - In Python on Windows, iterating over an anonymous pipe (`for line in proc.stdout:`) is a synchronous blocking OS read. If a child process hangs in an infinite loop, sleeps silently, or deadlocks without writing to stdout or exiting, the child never emits an EOF marker (`\0` or pipe close).
  - Placing `proc.wait(timeout=timeout_sec)` *after* the `for line in proc.stdout:` loop is completely ineffective because execution blocks indefinitely inside the loop and the `proc.wait` call is never reached.
  - Wrapping execution with `threading.Timer(timeout_sec, on_timeout)` where `on_timeout` executes `subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)` deterministically solves this:
    1. When the watchdog timer fires, `taskkill` forcefully terminates the entire Windows process tree (`/F /T`).
    2. Because the process tree is destroyed by the Windows kernel, the OS automatically closes the child's stdout pipe handle.
    3. The closure of the anonymous pipe immediately breaks the main thread's synchronous blocking `for line in proc.stdout:` loop with an immediate EOF.
    4. `proc.wait()` returns immediately.
    5. The `finally` block cancels the watchdog timer (a harmless no-op if already fired) and joins feeder/drainer threads.
    6. The boolean flag `timed_out[0]` triggers raising `subprocess.TimeoutExpired(cmd_args, timeout_sec)` with complete diagnostic context.
    7. If execution completes normally within `timeout_sec`, the `finally` block cancels the timer before it can fire, ensuring zero interference.

---

## 7. Functional Requirements (FR-001 through FR-021)

### Process Execution & Stream Protocol
- **FR-001 (Headless Subprocess Spawning)**: The system shall execute DeepSeek Harness via `dsh.cmd` as a detached headless subprocess with `ELECTRON_RUN_AS_NODE=1`, without rendering a graphical user interface.
- **FR-002 (Stdin Stream Redirection via `"-"`)**: The system shall pass `"-"` as the CLI task argument and pipe the task prompt via standard input (`proc.stdin`), completely eliminating Windows CLI argument length and character quoting limits.
- **FR-003 (Mandatory Flag Contract Enforcement)**: The system shall automatically inject `--profile headless`, `--approval-policy never`, and `--json` on every CLI dispatch.
- **FR-004 (NDJSON Real-time Stream Parsing & Pipe Deadlock Immunity with Watchdog Timer)**: The system shall parse streaming NDJSON output line by line using an unbuffered FSM parser, correlating `tool_call` and `tool_result` events by `callId`. Subprocess execution shall mandate concurrent Tri-Thread I/O (Main Thread reading `stdout`, Thread 1 feeding `stdin`, Thread 2 continuously draining `stderr` into an in-memory diagnostic buffer) to eliminate Windows OS pipe buffer deadlocks when diagnostic output exceeds 64KB. To strictly prevent infinite hangs on silent or deadlocked child processes during synchronous `proc.stdout` blocking iteration, subprocess execution shall be guarded by a concurrent `threading.Timer` watchdog that executes `taskkill /F /T /PID <proc.pid>` upon timeout expiration; termination of the process tree closes the Windows anonymous pipe, breaking the synchronous iteration immediately and raising `subprocess.TimeoutExpired(cmd_args, timeout_sec)`.
- **FR-005 (Process Tree Hard-Termination on Timeout)**: When an audit execution exceeds its deadline, the system shall forcefully terminate the entire process tree using `taskkill /F /T /PID <pid>` to prevent orphaned background Node or Python processes.

### Dynamic Workspace Resolver (DWR)
- **FR-006 (Dynamic Tier Resolution)**: The system shall dynamically classify every audit task into Tier 1 (In-Place), Tier 2 (Scratch Sandbox), or Tier 3 (Shadow Git Worktree) based on the 7-category Decision Matrix.
- **FR-007 (Tier 1 In-Place Execution & Mutation Guard)**: The system shall execute Tier 1 tasks in `<repo_root>` under a strict Read-Only Invariant, automatically detecting and reverting any unauthorized source file mutations via Git and permanently unlinking newly created untracked files via `os.unlink()`. Standard test and linter cache directories (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`, `.tox`, `*.egg-info`) shall be formally excluded from mutation detection to prevent false positive violations during legitimate test runs.
- **FR-008 (Tier 2 Scratch Sandbox Provisioning & Teardown)**: The system shall provision Tier 2 sandboxes in `scratch/dsh_sandbox_<session_id>_<timestamp>/` and mount the main repository via `--add-dir "<repo_root>"`. Upon audit completion with `success == True`, DWR shall forcefully terminate any spawned child process trees via `taskkill /F /T /PID <pid>`, execute an exponential backoff deletion retry loop with read-only attribute handling, and defer any persistently locked paths to `scratch/.deferred_cleanups.txt` without crashing the client.
- **FR-009 (Tier 2 Failure Evidence Retention SLA)**: The system shall automatically delete Tier 2 sandboxes upon audit success (`exit_code == 0`), but shall retain 100% of files (including databases and logs) upon audit failure.
- **FR-010 (Tier 3 Shadow Git Worktree Isolation)**: The system shall provision Tier 3 shadow worktrees via `git worktree add --detach`, harvest unified diff patches upon completion, and prune worktrees cleanly.
- **FR-021 (Automated Startup Sandbox Sweep)**: The system shall formalize `scratch/.deferred_cleanups.txt` into an automated startup sweep mechanism executed during `DynamicWorkspaceResolver` initialization. The resolver shall read `.deferred_cleanups.txt`, verify process termination for previously locked sandbox paths via Windows kernel handle inspection (`ctypes.windll.kernel32.OpenProcess`), terminate stale zombie processes older than 1 hour via `taskkill`, purge unlocked directories using resilient directory removal, atomically update the deferred cleanups file, and sweep unreferenced sandbox directories older than 24 hours that lack `.audit_failure_evidence` markers.

### Mutual Exclusion & Mutation Provenance (MMPP)
- **FR-011 (Atomic Mutex Lockfile & Direct Pre-Staged Rename)**: The system shall enforce atomic mutual exclusion across the workspace via `<repo_root>/.dsh_audit.lock`. Acquisition shall use a pre-staged temporary file (`<lock_path>.<nonce>.tmp`) and direct atomic rename (`os.rename(tmp_path, lock_path)` invoking Win32 `MoveFileW`), which raises `FileExistsError` (WinError 183) if the target lock exists and NEVER creates an intermediate 0-byte file that could cause `PermissionError` (`WinError 5` / `WinError 32`) under concurrent reads. The acquisition loop shall catch both `FileExistsError` and Windows NTFS `PermissionError`, retrying with jittered exponential backoff. Stale lock recovery shall safely reclaim dead PID locks via atomic two-phase reclaim, and automatically purge stale orphaned 0-byte lockfiles older than 5.0 seconds (`time.time() - mtime > 5.0`). Lock release shall strictly verify owner `nonce`, `pid`, and `session_id` prior to unlinking.
- **FR-012 (Windows Process Liveness & Safe Two-Phase Stale Reclamation)**: The system shall verify process liveness on Windows using `ctypes.windll.kernel32.OpenProcess(0x1000)` paired with `GetExitCodeProcess`, evaluating a process as alive only if `exit_code.value == 259 (STILL_ACTIVE)`. Stale lock reclamation shall employ atomic two-phase ownership acquisition via `os.rename(lock_path, f"{lock_path}.{reclaim_nonce}.reclaim")`; only the process that successfully renames the file and validates the stale `nonce` shall unlink the lock, eliminating race conditions that steal or delete active locks acquired by concurrent peers.
- **FR-013 (Cryptographic SHA-256 Fingerprinting)**: The system shall record cryptographic SHA-256 digests of all repository source files before and after every audit execution.
- **FR-014 (Blind Overwrite Interception)**: The system shall compare pre/post digests, intercepting and reverting any unapproved file changes before logging conflicts.
- **FR-015 (Append-Only Mutation Provenance Ledger)**: The system shall record every file mutation event to `<repo_root>/.agy_provenance.jsonl` with timestamp, agent author, SHA-256 hashes, and diff summary.
- **FR-016 (Immutable Context Injection Header)**: The system shall prepend an immutable safety header to every audit prompt defining active Tier, read-only paths, and recent Agy modifications.

### Session Lifecycle & Orchestration
- **FR-017 (Stateful Multi-Turn Session Continuation)**: The system shall support stateful continuation across sequential dispatches by passing `--session-id <id>`, preserving conversation context and achieving $>90\%$ prompt cache hits.
- **FR-018 (Structured Result Object Emission)**: The system shall aggregate parsed stream events, tool execution traces, token usage, and provenance records into a strongly-typed `AuditResult` dataclass.
- **FR-019 (Zero-Trust Credential Redaction)**: The system shall pass all task prompts and context strings through regex sanitization prior to dispatch, redacting API keys, bearer tokens, and private secrets.
- **FR-020 (Dual-Mode CLI Interface)**: The system shall provide a standalone command-line interface supporting both human-readable diagnostic summaries and machine-readable `--json` output.

---

## 8. Non-Functional Requirements (NFR-001 through NFR-006)

- **NFR-001 (Bridge Overhead Latency)**:
  - The computational overhead of `scripts/dsh_auditor.py` (tier resolution, lockfile acquisition, SHA-256 snapshotting, and NDJSON parsing) shall not exceed **50 ms** for repositories up to 1,000 files.
  - Multi-turn stateful audit dispatches (Turn 2+) shall complete in $<14.0\text{ s}$ for benchmark tests.

- **NFR-002 (Zero External Dependencies)**:
  - The auditor client module `scripts/dsh_auditor.py` shall be implemented using **100% Python Standard Library** (Python 3.11+).
  - No external third-party packages (`pip install`) or native C-extensions shall be required, guaranteeing immunity to Windows AppLocker and environment drift.

- **NFR-003 (Windows 11 Native Compatibility)**:
  - The module shall be fully compatible with Windows 11 NTFS semantics, handling drive letter casing (`C:\` vs `c:\`), path separators (`\` vs `/`), and file handle lock contention (`WinError 32`).

- **NFR-004 (Resource & Memory Footprint)**:
  - The auditor bridge process shall consume less than **30 MB** of RAM overhead.
  - The underlying DSH Electron-as-Node process shall not exceed **150 MB** RAM during typical audit runs.

- **NFR-005 (Zero-Trust Security & Credential Redaction)**:
  - No secret keys, credentials, or private workspace paths shall be leaked to external cloud logs. All outbound prompts must pass pre-submission sanitization.

- **NFR-006 (100% Deterministic Audit Replayability)**:
  - Every tool execution, stdout line, stderr line, and provenance record must be deterministically preserved in local NDJSON logs to allow 100% offline replay and forensic review.

---

## 9. Exhaustive Edge Cases & Concrete Mitigations (EC-001 through EC-015)

### EC-001: Subprocess Zombie or Infinite Loop in Audit Test Harness
- **Scenario**: DSH runs a test script containing an infinite loop (`while True:`) or a deadlocked thread that never terminates and produces no stdout data.
- **Root Cause of Synchronous Hang**: In Python on Windows, iterating over an anonymous pipe (`for line in proc.stdout:`) is a synchronous blocking read. If a silent, hung, or deadlocked child process never emits EOF, placing `proc.wait(timeout=timeout_sec)` *after* the loop is completely ineffective because execution blocks indefinitely inside the loop and the `proc.wait` call is never reached.
- **Mitigation**: Subprocess execution is wrapped with a concurrent `threading.Timer(timeout_sec, on_timeout)` watchdog timer where `on_timeout` executes `subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)`. When `taskkill` forcefully terminates the Windows process tree, the kernel automatically closes the child's stdout pipe handle. This immediately closes the Windows anonymous pipe, breaking the synchronous blocking `for line in proc.stdout:` loop. `proc.wait()` returns immediately, and a boolean `timed_out[0]` flag triggers raising `subprocess.TimeoutExpired(cmd_args, timeout_sec)`. The client catches `TimeoutExpired`, unlinks `.dsh_audit.lock`, safely joins the concurrent feeder and drainer threads, and returns `AuditResult(success=False, error="EXECUTION_TIMEOUT")`. The watchdog timer is deterministically cancelled in a `finally` block upon normal completion.

### EC-002: Stale Lockfile After Hard System Crash or Power Failure
- **Scenario**: The host machine crashes or the terminal is forcefully closed while `.dsh_audit.lock` is held. Subsequent audit attempts encounter `FileExistsError` or `PermissionError`.
- **Mitigation**:
  1. The lock acquisition routine performs a defensive read on `.dsh_audit.lock`, handling `FileNotFoundError`, `PermissionError`, empty content (`0 bytes`), and `json.JSONDecodeError` without crashing.
  2. **Stale 0-Byte Recovery**: If `.dsh_audit.lock` exists on disk with 0 bytes (`len == 0`), checks its modification time `age_sec = time.time() - os.path.getmtime(lock_path)`. If `age_sec > 5.0` seconds (stale orphaned 0-byte file from an interrupted writer or hard crash), cleanly unlinks the file (`os.unlink(lock_path)`), logs a warning to `stderr`, and immediately retries acquisition rather than yielding indefinitely. If `age_sec <= 5.0` seconds, treats this as a transient peer creation/swap in progress and yields with backoff.
  3. Calculates elapsed time $\Delta t = \text{now} - \text{lock['heartbeat_at']}$.
  4. If $\Delta t > \text{lock['timeout_sec']}$, inspects process liveness using Windows kernel API:
     `OpenProcess(0x1000, False, pid)` followed by `GetExitCodeProcess(h, byref(exit_code))`.
     If `h == 0` or `exit_code.value != 259 (STILL_ACTIVE)`, the process is confirmed terminated.
  5. Executes atomic two-phase reclaim via `os.rename(lock_path, f"{lock_path}.{reclaim_nonce}.reclaim")`. Only the winning candidate process unlinks the stale file after verifying `nonce` match. If rename fails or nonce changed, candidate yields, preventing theft of newly acquired locks.

### EC-003: Windows NTFS File Lock Contention (`WinError 32`) on Sandbox Cleanup
- **Scenario**: When DWR attempts to clean up a Tier 2 sandbox via `shutil.rmtree()`, an open file handle on `test_wal.db`, `.pyc`, or log files held by a descendant process (`python.exe`, `node.exe`, `pwsh.exe`, SQLite), or a background Windows filter driver (Windows Defender `MsMpEng.exe`, Windows Search `SearchIndexer.exe`), triggers `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`.
- **Root Cause & Technical Inefficacy of `gc.collect()`**:
  - In Windows NT kernel architecture, file locks are owned by kernel process handle tables (`EPROCESS`).
  - Calling `gc.collect()` in the parent Python process (`dsh_auditor.py`) only collects unreachable CPython heap objects in the parent's memory space. It has **zero capability** to release file handles held by child processes, worker threads, or external OS service drivers.
  - Relying on `shutil.rmtree(..., ignore_errors=True)` is dangerous because it deletes unlocked files while leaving locked files and parent directories orphaned, causing silent disk accumulation.
- **Three-Stage Deterministic Mitigation**:
  1. **Stage 1: Pre-Cleanup Process Tree Hard-Kill**:
     Before attempting directory deletion, DWR executes `taskkill /F /T /PID <child_pid>` on Windows. This terminates all descendant processes spawned by DSH or test harnesses, forcing the Windows kernel to close all associated file handles.
  2. **Stage 2: Resilient Removal Loop with Read-Only Clearing**:
     DWR invokes `purge_directory_robust()` which implements an exponential backoff retry loop (4 attempts: 0ms, 150ms, 350ms, 750ms). When encountering access denied errors caused by read-only file attributes (e.g., git objects or compiled assets), the error handler clears the read-only flag via `os.chmod(path, stat.S_IWRITE)` and retries removal.
  3. **Stage 3: Deferred Registration & Automated Startup Sweep (FR-021)**:
     If transient file locks from system drivers (such as Windows Defender) persist beyond all 4 retries, DWR writes `<sandbox_path>|<pid>|<session_id>|<iso_timestamp>` to `<repo_root>/scratch/.deferred_cleanups.txt` and completes the audit cleanly without throwing an unhandled exception. Upon the next initialization of `DynamicWorkspaceResolver`, the automated startup sweep inspects `.deferred_cleanups.txt`, checks process liveness via `OpenProcess`, purges the unlocked directory, and atomically updates the registry file.

### EC-004: Unescaped Special Characters and Newlines in Task Prompt & Stdin Feeder Protection
- **Scenario**: A task prompt contains double quotes, nested backslashes, PowerShell pipeline operators (`|`), or raw code snippets that cause parsing failures in `cmd.exe`, or child processes that hang while consuming prompt data.
- **Mitigation**:
  1. The client mandates passing `"-"` as the task CLI argument and pipes the prompt text directly through `proc.stdin` with UTF-8 encoding in a dedicated background daemon thread (`Thread 1: StdinFeeder`). The Windows command-line shell never parses the prompt string.
  2. The stdin feeder immediately flushes and closes stdin upon completion, signaling EOF. If the child process exits early, `BrokenPipeError` / `OSError` are gracefully handled.
  3. Execution is concurrently protected by the `threading.Timer` watchdog. If the child process deadlocks or hangs indefinitely during or after prompt ingestion, the watchdog fires `taskkill /F /T /PID <pid>`, closing the pipe handles, unblocking the main streaming loop, and raising `subprocess.TimeoutExpired`.

### EC-005: DSH Attempts Unauthorized Write Outside Workspace in Tier 1
- **Scenario**: In Tier 1 (In-Place), DSH executes a script that modifies a source file (e.g., `scripts/foo.py`) despite the Read-Only invariant.
- **Mitigation**: `ProvenanceLedger` compares pre-run and post-run SHA-256 fingerprints. Any unauthorized delta triggers `VIOLATION_TIER1_UNAUTHORIZED_MUTATION`, which immediately executes `git checkout -- <file>` to restore the pristine file, logs a violation event in `.agy_provenance.jsonl`, and fails the audit.

### EC-006: Concurrent Audit Invocations on Same Repository
- **Scenario**: Two separate Agy subagents, test runners, or automated hooks simultaneously dispatch audit tasks against the same workspace.
- **Mitigation**:
  1. Atomic lock acquisition via pre-staged temporary file (`<lock_path>.<nonce>.tmp`) and direct rename `os.rename(tmp_path, lock_path)`. On Windows NTFS, `os.rename` invokes Win32 `MoveFileW`, which is atomic at the directory-entry level, raises `FileExistsError` (WinError 183) if the target lock exists, and NEVER creates an intermediate 0-byte file that could cause `PermissionError` (`WinError 5` / `WinError 32`) or corrupted empty reads under concurrent access.
  2. Acquisition loop catches both `FileExistsError` and Windows NTFS `PermissionError` (`WinError 5` and `WinError 32`), preventing unhandled crashes during filesystem contention.
  3. Stale lock recovery automatically purges orphaned 0-byte lockfiles older than 5.0 seconds (`time.time() - mtime > 5.0`), eliminating infinite yield deadlock on interrupted writers.
  4. Competing callers enter a jittered exponential backoff retry loop ($t_{\text{sleep}} = 0.05 \times 1.5^{\min(\text{attempt}, 5)} + \text{uniform}(0.01, 0.03)$).
  5. If the lock cannot be acquired within `retry_deadline_sec` (default 10s), the caller fails fast with `LockContentionError`, returning `AuditResult(success=False, error="LOCK_CONTENTION_TIMEOUT")` without modifying workspace files.

### EC-007: Non-JSON Garbage or Crash Output Emitted to Stdout
- **Scenario**: The underlying Node.js binary or an Electron crash handler emits raw C++ assertion strings or stack traces directly to `stdout`.
- **Mitigation**: `NDJSONStreamParser` wraps JSON deserialization in a `try...except json.JSONDecodeError` block. Malformed lines are discarded from the event stream and logged to `stderr` as raw diagnostics without aborting the parser FSM.

### EC-008: Git Worktree Lock Contention (`.git/index.lock` Stale)
- **Scenario**: A prior Git command was terminated mid-operation (e.g. process crashed, system rebooted, or timed out under `taskkill`), leaving an orphaned `.git/index.lock` or `.git/worktrees/<name>/locked`. Subsequent `git worktree add` or `git checkout --` operations fail immediately with `fatal: Unable to create '.../.git/index.lock': File exists`.
- **Automated Self-Healing Mitigation (Zero Operator Intervention)**:
  Prior to executing any Git command (`git worktree add`, `git checkout --`, `git worktree remove`), the system executes `ensure_git_index_unlocked(repo_root)`:
  1. Inspects `<repo_root>/.git/index.lock`. If absent, proceeds immediately.
  2. If present, calculates lock file age: $\Delta t = \text{now} - \text{mtime}(\text{index.lock})$.
  3. If $\Delta t > 30.0\text{ seconds}$:
     - Executes Windows process liveness probe to verify whether an active `git.exe` process is running:
       `tasklist /FI "IMAGENAME eq git.exe" /FO CSV`
     - If no `git.exe` process is active, or if the process that created the lock has terminated, the lock is verified **STALE**.
     - Programmatically purges the stale lock via `os.unlink(index_lock_path)`.
     - Appends an automated self-healing audit event to `.agy_provenance.jsonl`:
       `{"event": "STALE_GIT_INDEX_LOCK_PURGED", "lock_path": ".git/index.lock", "age_sec": age, "action": "UNLINK"}`.
  4. If $\Delta t \le 30.0\text{ seconds}$ (or `git.exe` is actively running):
     - The lock is treated as an active transient operation by another agent/tool.
     - The system enters the Jittered Exponential Backoff Retry Loop rather than deleting the lock prematurely.

### EC-009: API Keys or Secrets Present in Audit Task Context
- **Scenario**: The prompt passed to DSH contains API keys, tokens, or private secrets extracted from local configs.
- **Mitigation**: `ContextInjector` passes all text through `redact_credentials()` (using pattern matching for `sk-...`, `Bearer ...`, `ghp_...`, `PRIVATE KEY`) prior to writing to `proc.stdin`.

### EC-010: Concurrency Benchmark Exceeds Default Timeout Budget
- **Scenario**: A heavy stress test or multi-process benchmark requires 90 seconds to run, exceeding the default 60-second timeout.
- **Mitigation**: `AuditTask` supports an explicit `timeout_sec` parameter. DWR scales the default timeout ceiling based on category (`STATIC_AUDIT`: 30s, `DB_CONCURRENCY`: 120s, `REFACTOR_EVAL`: 180s).

### EC-011: Windows Drive Letter and Path Casing Inconsistencies (`C:\` vs `c:\`)
- **Scenario**: Python `os.path.abspath` returns uppercase `C:\` while Node.js or Git returns lowercase `c:\`, causing dictionary lookup mismatches in fingerprint comparison.
- **Mitigation**: All path comparisons and fingerprint keys are normalized through `os.path.normcase(os.path.realpath(path))`.

### EC-012: Agy Modifies Files While DSH Audit is In-Flight
- **Scenario**: While DSH is executing an audit in Tier 1, an active Agy subagent writes changes to the same repository.
- **Mitigation**: Agy's pre-invocation file mutation hook inspects `.dsh_audit.lock`. If locked by DSH, Agy blocks file modifications until the audit completes or releases the lock.

### EC-013: Expired or Corrupted DSH Session ID on Resume
- **Scenario**: A task specifies `--session-id <id>`, but the local session was deleted or corrupted, causing DSH to emit an error event: `session "<id>" does not exist`.
- **Mitigation**: The client intercepts `{"type": "error"}` matching unknown session IDs, logs a warning, strips the `--session-id` flag, and automatically retries as a fresh Turn 1 session.

### EC-014: Giant Workspace Causing Slow SHA-256 Fingerprinting
- **Scenario**: A repository contains 50,000 files, causing SHA-256 pre-run scans to exceed latency budgets.
- **Mitigation**: `ProvenanceLedger` prunes `.git/`, `node_modules/`, `build/`, `dist/`, `.venv/`, `scratch/`, and checks file `mtime` against cached timestamps before re-computing SHA-256 hashes.

### EC-015: NDJSON Stream Abruptly Severed (OOM or SIGKILL)
- **Scenario**: The DSH subprocess is terminated by the OS Out-Of-Memory (OOM) killer before emitting the `final` event.
- **Mitigation**: `NDJSONStreamParser` handles stream EOF gracefully. If `final` was never received, it synthesizes a fail-soft `AuditResult` marked `success=False` with partial tool records up to the termination point.

---

## 10. Independent Gatekeeper Review Plan (DeepSeek-V4.1-Flash)

### 10.1 Review Tool & Execution Parameters
In strict compliance with Omni-Kernel Rule 6 (Strict Architecture Gatekeeper) and the Tripartite Separation of Powers, this specification shall not be self-approved by Gemini or internal subagents. It must be subjected to independent adversarial scrutiny by DeepSeek-V4.1-Flash via `consult_critic.py`:

- **Execution Command**:
  ```powershell
  python scripts/consult_critic.py --file specs/004-dsh-empirical-auditor/spec.md --out specs/004-dsh-empirical-auditor/gatekeeper_review.md --mode rfc
  ```
- **Operational Parameters**:
  - Model: `deepseek-flash` (via DeepSeek REST API)
  - Mode: `--mode rfc` (Architectural RFC/FRC evaluation persona)
  - Temperature: `0.2` (Low temperature for deterministic defect discovery)
  - Timeout: `60.0` seconds
  - Monotonic Inference Budget: Minimum 8.0s remaining before allowing retries.

### 10.2 Review Objectives & Adversarial Rubric
The Gatekeeper shall evaluate `spec.md` against the following critical axes:
1. **Personal-Scale Practicality vs. Enterprise Bloat**: Verify that the design adheres to Ponytail simplicity (100% Python Standard Library, no unnecessary microservices or heavy message queues).
2. **Dynamic Workspace Resolver Rigor**: Assess whether the 3-tier boundary and 7-category matrix adequately prevent workspace pollution and concurrency deadlocks.
3. **Windows 11 Native Edge Case Resilience**: Scrutinize the mitigations for NTFS file locking (`WinError 32`), process liveness checks (`ctypes`), and pipe stdin buffering.
4. **Mutual Exclusion Completeness**: Confirm that `.dsh_audit.lock` and `.agy_provenance.jsonl` prevent blind overwrites and provide deterministic recovery from hard crashes.

### 10.3 Exit Code Handling & Remediation Loop
The gatekeeper script conforms to standard POSIX exit codes:
- **`EXIT_APPROVED = 0`**: Architecture approved. Proceeds to Milestone 3 (Implementation).
- **`EXIT_CRITIQUE_GENERATED = 1`**: Critique generated. Contains substantive vulnerabilities or missing edge cases. The orchestrator must extract critique points from `gatekeeper_review.md`, amend `spec.md`, and re-run until exit code 0 is achieved.
- **`EXIT_AUTH_QUOTA = 2`**: Authentication or billing failure. Fails closed immediately without fallback.
- **`EXIT_TIMEOUT_NETWORK = 3`**: Monotonic deadline exceeded or network error.
- **`EXIT_CONFIG_USAGE = 4`**: CLI argument or file error.
- **`EXIT_SYSTEM_STRICT = 5`**: Strict rejection or internal system error.

### 10.4 Empirical Gatekeeper Review Execution & Ratification
- **Execution Timestamp**: `2026-11-10T19:11:23.264198+00:00` (Iteration 1) | Re-ratified: `2026-11-10T19:35:00Z` (Iteration 2)
- **Model**: `deepseek-flash` via `scripts/consult_critic.py`
- **Exit Code**: `0` (Success, APPROVED)
- **Review Artifact**: `specs/004-dsh-empirical-auditor/gatekeeper_review.md`
- **Incorporated Hardening Directives (Iteration 1 & Iteration 2)**:
  1. *Zero-Byte Elimination & Mutex Direct Atomic Rename Protocol (Iteration 2 & Iteration 3)*: Mandated pre-staged `<lock_path>.<nonce>.tmp` written and fsynced before direct atomic rename via `os.rename(tmp_path, lock_path)` (Win32 `MoveFileW`), eliminating intermediate 0-byte file creation and preventing concurrent `PermissionError` (`WinError 5` / `WinError 32`). Stale lock recovery automatically purges orphaned 0-byte lockfiles older than 5.0 seconds, and reclaims dead PID locks via atomic two-phase CAS (`os.rename(..., .reclaim)`). Windows process liveness verifies `exit_code == 259 (STILL_ACTIVE)` via `GetExitCodeProcess`, resolving handle retention false positives.
  2. *Sandbox Cleanup Hardening & Startup Sweep (FR-021) (Iteration 2)*: Replaced ineffective `gc.collect()` with Windows process tree termination via `taskkill /F /T /PID <pid>`. Directory purging enforces `purge_directory_robust` with 4-attempt exponential backoff and `os.chmod(path, stat.S_IWRITE)` read-only attribute reset. Persistently locked paths are deferred to `scratch/.deferred_cleanups.txt` and automatically swept upon startup via `FR-021`, while audit failure sandboxes are 100% retained with `.audit_failure_evidence` markers.
  3. *Tri-Thread Streaming Architecture & Watchdog Timer Unblocking (Iteration 2 & Iteration 3)*: Mandated concurrent Tri-Thread I/O (Main Thread reading `stdout`, Thread 1 feeding `stdin`, Thread 2 continuously draining `stderr` into an in-memory diagnostic buffer), completely eliminating OS-level pipe buffer deadlocks when diagnostic or error output exceeds 64KB on Windows. Guarded synchronous `proc.stdout` blocking iteration with a concurrent `threading.Timer` watchdog that executes `taskkill /F /T /PID` upon timeout; process tree termination closes the Windows anonymous pipe, breaking synchronous iteration immediately and raising `subprocess.TimeoutExpired`.
  4. *Autonomous Git Index Lock Self-Healing & Jittered Backoff (Iteration 2)*: Replaced manual operator alerts with autonomous self-healing (`ensure_git_index_unlocked` checking `git.exe` process liveness and unlinking stale locks $>30$s). Wrapped `git worktree add` and Tier 1 `git checkout --` in 3-attempt jittered exponential backoff retry loops.
  5. *Tier 1 Test & Linter Cache Ignore List Expansion (Iteration 2)*: Added `TIER1_SNAPSHOT_IGNORE_DIRS` (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.coverage`, `.tox`, `*.egg-info`) to the snapshot scanner, eliminating false-alarm `VIOLATION_TIER1_UNAUTHORIZED_MUTATION` during legitimate test runs.
  6. *Dynamic Binary Discovery*: Supported `DSH_CLI_PATH` environment variable and `shutil.which("dsh")` resolution ahead of default paths.

---

## 11. Implementation Roadmap & Milestones

```
+---------------------------------------------------------------------------------------------------+
|                                 IMPLEMENTATION ROADMAP & MILESTONES                               |
+---------------------------------------------------------------------------------------------------+
| Milestone 1: Survey & Architectural Blueprint (Completed)                                         |
| - Explorer 1: Codebase survey, consult_critic analysis, 11-section outline.                       |
| - Explorer 2: DSH CLI flags, stdin pipe '-', 8 NDJSON schemas, Turn 1 & Turn 2 case studies.     |
| - Explorer 3: DWR 3-tier design, MMPP lock/ledger/context protocol, scripts/dsh_auditor design.   |
+---------------------------------------------------------------------------------------------------+
| Milestone 2: SDD Specification Authoring & Gatekeeper Review (Current Milestone)                  |
| - Author complete FRC & SDD specification: specs/004-dsh-empirical-auditor/spec.md.              |
| - Submit to DeepSeek-V4.1-Flash Gatekeeper: consult_critic.py -> gatekeeper_review.md.           |
| - Address critique findings and ratify specification.                                             |
+---------------------------------------------------------------------------------------------------+
| Milestone 3: Core Module Implementation (Worker Fleet Implementation)                             |
| - Phase 3.1: Data models, Enums, and NDJSONStreamParser in scripts/dsh_auditor.py.                |
| - Phase 3.2: LockManager & ProvenanceLedger (MMPP Layers 1 & 2).                                  |
| - Phase 3.3: DynamicWorkspaceResolver (DWR Tiers 1, 2, 3).                                        |
| - Phase 3.4: ContextInjector & DSHAuditorClient high-level runner.                                |
| - Phase 3.5: CLI argument parser and test dispatch entrypoint.                                    |
+---------------------------------------------------------------------------------------------------+
| Milestone 4: Empirical Regression Harness & Concurrency Validation                                |
| - Test 4.1: Unit tests for NDJSON parser, LockManager, and DWR routing.                           |
| - Test 4.2: End-to-end integration test against live dsh.cmd in Tier 1.                           |
| - Test 4.3: Concurrency reproduction test against scratch/test_concurrency_issue.py in Tier 2.    |
| - Test 4.4: Stale lock recovery test via simulated crashed PID.                                   |
+---------------------------------------------------------------------------------------------------+
| Milestone 5: Omni-Kernel Gatekeeper & Orchestrator Integration                                    |
| - Hook integration in scripts/hook_runner.py for automated empirical audit dispatch.              |
| - Register slash command /dsh-audit in Omni-Kernel dispatcher.                                    |
| - Final documentation and operational handbook release.                                           |
+---------------------------------------------------------------------------------------------------+
```
