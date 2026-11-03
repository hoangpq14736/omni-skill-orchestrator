# Feature Specification: DeepSeek-V4.1-Flash Strict Architecture Gatekeeper (Omni-Auditor v4.1)

**Feature Branch**: `002-deepseek-v41-auditor`  
**Created**: 2026-11-03  
**Status**: Draft (Ratified Architecture)  
**Input Documents**:
- `ORIGINAL_REQUEST.md` (Requirements R1, R2, Acceptance Criteria)
- `PROJECT_DEEPSEEK_V41_AUDITOR.md` (Strict Architecture Gatekeeper Blueprint)
- `.specify/constitution.md` (Omni-Kernel v4.1 Constitution, Ratified 2026-11-02)
- `d:\Antigravity\Skill management\.agents\teamwork\orchestrator_1\PROJECT.md`
- `d:\Antigravity\Skill management\.agents\teamwork\explorer_m1_1\blueprint.md`
- Reference SDD: `specs/001-omni-memory-v4/spec.md`

---

## 1. Executive Summary & Problem Statement

### 1.1 Legacy Architectural Vulnerabilities & Failure Modes
In the legacy Omni-Kernel architecture, architectural oversight suffered from three systemic pathology failure modes:

1. **Argon Bridge Fragility & Flakiness**:
   - The legacy gatekeeper bridge (`scripts/consult_argon.py`) routed architectural critique requests to Gemini 4 Argon through a local Tampermonkey WebSocket bridge (`http://127.0.0.1:7890`) connected to a consumer browser chat tab at `https://gemini.google.com`.
   - This required an active, unminimized, and unthrottled browser window. Operating system background tab sleep policies, user navigation, or Google Cloudflare/reCAPTCHA challenges immediately severed the connection.
   - The script enforced an exorbitant default 240-second timeout ceiling, stalling multi-agent workflows for minutes.
   - Relying on DOM scraping and simulated keyboard events made the bridge inherently brittle against minor Google UI updates.

2. **The "Echo-Chamber" Self-Review Dilemma**:
   - During multi-agent planning sessions (such as `/teamwork` invocations and SDD bundle drafting), Antigravity routinely encountered Argon Bridge connection timeouts.
   - To bypass this friction, Antigravity defaulted to spawning duplicate internal Gemini subagents (e.g., Challenger, Reviewer, Forensic Auditor).
   - Because these subagents shared identical model weights, training corpora, and cognitive priors with the executive planner, they exhibited severe sycophancy. Subagents politely complimented flawed architectures rather than detecting critical race conditions, Windows WDDM 60s TDR Event 4101 hardware timeouts on AMD Vega 20, or tonal diacritic destruction in bilingual text.

3. **Soft-Prompting Governance Failure**:
   - Constitutional directives placed solely in `rules/AGENTS.md` and `.specify/constitution.md` operated as soft suggestions. Under latency pressure, agents consistently took the path of least resistance, skipping external scrutiny and self-approving unvetted code.

### 1.2 The Tripartite Separation of Powers (Tam Quyền Phân Lập)
PROJECT_DEEPSEEK_V41_AUDITOR formalizes a strict tripartite separation of powers within the Omni-Kernel v4.1 runtime:

- **Executive & Planner (Google Antigravity / Gemini 2.5/3.x)**: Coordinates high-level mission goals, prompt decomposition, interactive developer UX, and agent dispatching.
- **Deterministic Hard Gatekeeper (`scripts/hook_runner.py`)**: Intercepts prompts, tool calls, and lifecycle transitions at the OS subprocess boundary, deterministically blocking task dispatch until an external audit artifact is verified.
- **Supreme Architectural Auditor (DeepSeek-V4.1-Flash MoE 552B with `-1017` Agentic Patch)**: Operates as an independent, adversarial Devil's Advocate and Forensic Auditor via a direct, cloud-native REST API and stdio MCP server.
- **Dual Worker Fleet**:
  - `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 GPU @ 1024 GB/s): Dedicated to local source code mutations, AST transforms, and SQLite WAL operations in an offline, zero-leakage sandbox.
  - `groq_worker_cloud` (Groq LPU Cloud @ 300–800+ tok/s): Dedicated to sub-second boilerplate synthesis, regex compilation, and massive Pytest suite generation.

### 1.3 Scope and Objectives
The objective of this specification is to define the functional, operational, and non-functional requirements for the complete Omni-Auditor subsystem, encompassing:
1. `scripts/consult_critic.py`: 100% Python standard-library zero-dependency REST client for DeepSeek-V4.1-Flash.
2. `deepseek_worker_mcp.py`: Stdio JSON-RPC 2.0 MCP server exposing virtual auditing tools to agent harnesses.
3. Decoupled Pre-Flight Gatekeeper Hook in `scripts/hook_runner.py`: Preserving $<25\text{ ms}$ turnaround on interactive turns while strictly enforcing external audit gates on architectural proposals.
4. Council Protocol Governance: Updating Rule 6 in `rules/AGENTS.md` to permanently outlaw echo-chamber self-review.

---

## 2. User Scenarios & Acceptance Criteria (Given-When-Then)

### User Story 1 (P1 - Core CLI Client `scripts/consult_critic.py`) 🎯 MVP

As an autonomous orchestrator or senior software engineer,  
I want a standalone, zero-dependency command-line client (`scripts/consult_critic.py`) communicating directly with DeepSeek-V4.1-Flash via HTTPS,  
So that I can obtain objective, adversarial architectural and code-diff reviews in under 30 seconds without browser dependencies, DOM scraping, or internal Gemini self-review.

**Why this priority**: The CLI client forms the foundational execution primitive. The pre-flight hook runner, MCP server, and automated CI pipelines all rely on this core engine.

**Independent Test**: Invoke `python scripts/consult_critic.py --file <path> --out <review> --mode rfc` against synthetic architectural RFCs; verify response is returned in $<30.0\text{ s}$, exit code conforms to status, and report identifies $\ge 3$ critical risks.

#### Acceptance Scenarios:

1. **Scenario 1.1 (Standard RFC Architectural Review `--mode rfc`)**:
   - **Given** an RFC or SDD specification file (e.g., `RFC_DRAFT.md`),
   - **When** the operator executes `python scripts/consult_critic.py --file RFC_DRAFT.md --out REVIEW.md --mode rfc`,
   - **Then** `consult_critic.py` loads and sanitizes the file, submits it to `https://api.deepseek.com/chat/completions` using TLS 1.3 via `urllib.request`,
   - **And** the model generates an adversarial critique containing at least 3 critical vulnerabilities, missing edge cases, and concrete remediation directives,
   - **And** the output is saved to `REVIEW.md` with wall-clock latency logged to `stderr`, exiting with code 0 (if approved) or code 1 (if critique findings require remediation).

2. **Scenario 1.2 (Forensic Code Diff Review `--mode code`)**:
   - **Given** a git diff or code patch file (e.g., `patch.diff`),
   - **When** the operator executes `python scripts/consult_critic.py --file patch.diff --out AUDIT.md --mode code`,
   - **Then** the client applies the Forensic Auditor persona focusing on race conditions, memory leaks, trust boundary bypasses, and Ponytail simplicity,
   - **And** returns a line-specific mitigation patch adhering to minimalism, writing findings to `AUDIT.md` and exiting with code 0 or 1.

3. **Scenario 1.3 (Jittered Exponential Backoff on Upstream 429/5xx Failures & 8.0s Inference Budget Guardrail)**:
   - **Given** upstream DeepSeek API returns HTTP 429 (Rate Limit), HTTP 503 (Service Unavailable), or a socket timeout occurs,
   - **When** `consult_critic.py` executes the HTTP request,
   - **Then** it evaluates remaining monotonic deadline budget $\Delta t_{\text{remaining}} = \text{deadline} - \text{time.monotonic()}$,
   - **And** on socket timeout or retry evaluation, if $\Delta t_{\text{remaining}} < 8.0\text{s}$ (Minimum Viable Inference Window), aborts retry immediately (Fail-Fast, 0 retry, exit code 3 `EXIT_TIMEOUT_NETWORK`) to avoid wasting tokens on doomed partial requests,
   - **And** if $\Delta t_{\text{remaining}} \ge 8.0\text{s}$, allows retry up to 3 times within budget using dynamic socket timeout $T_{\text{socket}} = \min(30.0, \Delta t_{\text{remaining}})$,
   - **And** for retryable HTTP statuses (429, 500, 502, 503, 504), calculates full jitter backoff: $T = \min(10.0, 1.0 \times 2^{\text{attempt}}) + \text{uniform}(0.1, 0.5)$,
   - **And** retries up to 3 times within the monotonic deadline; if successful on retry, exits cleanly; if all 3 attempts fail or budget is exhausted, logs error diagnostic to `stderr` and exits with code 3.

4. **Scenario 1.4 (Fast-Fail on Missing Authentication or Zero Credits — Fail-Closed Invariant)**:
   - **Given** `DEEPSEEK_API_KEY` is missing from the environment, empty, or returns HTTP 401 Unauthorized or HTTP 402 Payment Required,
   - **When** `consult_critic.py` is invoked,
   - **Then** the client fails immediately on attempt 0 with ZERO network retries, fails closed, and strictly prohibits fallback to legacy `consult_argon.py` or internal Gemini subagent self-review,
   - **And** prints actionable diagnostic instructions to `stderr` (e.g., account recharge URL `https://platform.deepseek.com` or `.env` configuration), exiting with code 2 (`EXIT_AUTH_QUOTA_ERROR`).

5. **Scenario 1.5 (Zero-Trust Pre-Submission Credential Sanitization)**:
   - **Given** an input specification or prompt containing sensitive credentials (e.g., `sk-...`, `sk-ant-...`, `Bearer ...`, `ghp_...`, `github_pat_...`, `BEGIN PRIVATE KEY`, or unquoted/quoted `.env` assignments),
   - **When** `consult_critic.py` prepares the HTTP payload,
   - **Then** it passes content through `scripts/sanitizer.py:redact_credentials()`,
   - **And** transmits only sanitized text (`[REDACTED_*]` / `[REDACTED_SECRET]`), guaranteeing zero secret leakage to external cloud APIs.

6. **Scenario 1.6 (Machine-Parseable JSON Verdict Mode `--json`)**:
   - **Given** the `--json` flag is provided via CLI,
   - **When** `consult_critic.py` constructs the API request,
   - **Then** it sets `response_format: {"type": "json_object"}` in the payload,
   - **And** parses the returned response into a validated JSON object conforming to `DeepSeekArchitectureAuditVerdict`, emitting pure JSON to `stdout` or the output file.

---

### User Story 2 (P2 - Deterministic Pre-Flight Gatekeeper Hook `scripts/hook_runner.py`)

As an Omni-Kernel system governor,  
I want the pre-flight invocation lifecycle hook (`scripts/hook_runner.py`) to deterministically intercept architectural proposals, RFC drafts, and SDD bundle operations,  
So that unreviewed specifications are blocked before task dispatch to workers, and external DeepSeek critiques are injected into the agent context, eliminating the self-review echo chamber while preserving $<25\text{ ms}$ turnaround on conversational turns.

**Why this priority**: Deterministic software-level enforcement. Without a hard interceptor at the subprocess boundary, agents bypass the external critic and default to internal self-approval.

**Independent Test**: Feed simulated PreInvocation payloads into `hook_runner.process_hook()`; assert conversational fillers bypass gatekeeper in $<1.0\text{ ms}$, while prompts with RFC/architecture intent activate the Gatekeeper and format `[CRITICAL REVIEW FROM DEEPSEEK-V4.1-FLASH]` into `injectSteps`.

#### Acceptance Scenarios:

1. **Scenario 2.1 (Architectural RFC / SDD Invocation Interception & Multi-File Target Verification)**:
   - **Given** a developer prompt containing architectural intent (e.g., `"Author the RFC for authentication"`, `"Create SDD spec.md"`),
   - **When** `hook_runner.py` intercepts the PreInvocation event,
   - **Then** it evaluates gatekeeper triggers immediately following slash-command suppression (line 136) and before empty-resolver exit (lines 155–156),
   - **And** calls `verify_critic_artifact(workspace_dir, target_file)` which checks:
     - Review file existence (`CRITIC_REVIEW.md` or specified review path),
     - Modification time: `mtime(review) >= mtime(target_file)`,
     - Reads first 512 bytes / line 1 and parses the machine metadata header comment:
       `<!-- OMNI_AUDIT_META: {"verdict": "APPROVED", "target_file": "...", "input_hash": "sha256:...", "timestamp_utc": "..."} -->`,
     - Verifies `meta["target_file"]` matches `target_file` (matching normalized path or basename), preventing review artifacts for one file (e.g. `spec.md`) from acting as a false pass for another unvetted file (e.g. `plan.md`),
     - Verifies `verdict in ("APPROVED", "CONDITIONAL_PASS")`; if `verdict == "REJECTED"`, treats review as non-approving (`REJECTED_BY_CRITIC`),
   - **And** if unreviewed, stale, target-mismatched, or rejected, injects a high-priority gating directive into `injectSteps` instructing the agent to run `consult_critic.py` and remediate findings before task execution, with zero subprocess or network calls inside `hook_runner.py`.

2. **Scenario 2.2 (Sub-Millisecond Conversational Filler Bypass)**:
   - **Given** user prompt matching conversational filler (e.g., `"ok"`, `"thanks"`, `"tiếp tục"`, `"done"`),
   - **When** `hook_runner.py` evaluates the input,
   - **Then** full-sentence regex matching exits in $<1.0\text{ ms}$, returning empty `injectSteps` without calling the external DeepSeek API or incurring network overhead.

3. **Scenario 2.3 (Slash Command Bypass Elimination for `/teamwork`)**:
   - **Given** user input beginning with a slash command (e.g., `"/teamwork design the memory layout"`),
   - **When** `hook_runner.py` inspects the command,
   - **Then** rather than blindly returning `{"injectSteps": []}`, it checks if the command is `/teamwork` or `/spec-driven-development`,
   - **And** activates gatekeeper verification if architectural intent is present, closing the legacy bypass hole.

4. **Scenario 2.4 (Anti-Echo-Chamber Subagent Block)**:
   - **Given** Antigravity attempts to finalize an architectural milestone without a valid DeepSeek critique artifact,
   - **When** the gatekeeper evaluates workspace state,
   - **Then** it rejects approval, injecting `[GATEKEEPER REJECTION: Mandatory External DeepSeek-V4.1-Flash Review Missing]`, strictly prohibiting internal Gemini subagent self-approval.

---

### User Story 3 (P3 - DeepSeek Worker MCP Driver `deepseek_worker_mcp.py`)

As an AI agent interacting via the Model Context Protocol (MCP),  
I want native MCP tools `deepseek_audit_spec` and `deepseek_audit_diff` exposed by a standard-library JSON-RPC 2.0 server (`deepseek_worker_mcp.py`),  
So that I can trigger external red-teaming audits programmatically during tool-use phases without shell escaping, terminal multiplexing, or subprocess management.

**Why this priority**: Enables interactive mid-task auditing where subagents or worker fleets can validate code diffs or specifications before submitting pull requests or task handoffs.

**Independent Test**: Run `python deepseek_worker_mcp.py` over stdin/stdout; send `initialize`, `tools/list`, and `tools/call` for `deepseek_audit_spec`; assert valid JSON-RPC 2.0 response with formatted critique in `<content>`.

#### Acceptance Scenarios:

1. **Scenario 3.1 (Interactive SDD Bundle Audit via `deepseek_audit_spec`)**:
   - **Given** an agent provides `spec_content` or `spec_path` to `deepseek_audit_spec`,
   - **When** the MCP server receives the `tools/call` request,
   - **Then** it dispatches the payload to DeepSeek-V4.1-Flash using the Devil's Advocate persona,
   - **And** returns a structured text critique identifying top vulnerabilities within the 30-second budget.

2. **Scenario 3.2 (Automated Code Diff Forensic Audit via `deepseek_audit_diff`)**:
   - **Given** an agent or worker provides `diff_content` to `deepseek_audit_diff`,
   - **When** the MCP tool executes,
   - **Then** DeepSeek-V4.1-Flash performs forensic analysis (race conditions, memory leaks, boundary checks),
   - **And** returns a structured vulnerability report and line-specific patch recommendation.

3. **Scenario 3.3 (Zero-Crash Stdlib JSON-RPC 2.0 Stdio Loop)**:
   - **Given** malformed JSON, network disconnection, or unknown tool calls received on stdin,
   - **When** `deepseek_worker_mcp.py` processes the input,
   - **Then** all diagnostic logs are strictly written to `sys.stderr`,
   - **And** JSON-RPC error objects (`-32601` or `-32000`) are emitted to `sys.stdout` without terminating the daemon process.

---

## 3. Functional Requirements (FR-001 through FR-015)

- **FR-001 (Zero-Dependency Stdlib Client)**: The core client `scripts/consult_critic.py` MUST be implemented using 100% Python 3.11+ Standard Library (`urllib.request`, `urllib.error`, `json`, `argparse`, `time`, `ssl`, `re`, `os`, `sys`, `random`). Third-party HTTP packages (`requests`, `httpx`, `aiohttp`, `urllib3`) are strictly forbidden.
- **FR-002 (Dual Audit Modes)**: The system MUST support two distinct audit modes: `--mode rfc` (for PRD, RFC, and SDD bundles) and `--mode code` (for Git diffs, PR patches, and source code files).
- **FR-003 (Red-Teaming Anti-Praise Prompting & Conditional Vulnerability Floor)**: System prompts for both modes MUST enforce an aggressive Devil's Advocate persona, strictly forbidding praise, flattery, or superficial validation. Because DeepSeek JSON mode (`response_format: {"type": "json_object"}`) does not perform server-side Draft-07 schema validation, system prompts MUST explicitly instruct the model: If `verdict != "APPROVED"`, `critical_vulnerabilities >= 3` is mandatory; if `verdict == "APPROVED"`, `critical_vulnerabilities == 0` is allowed ONLY IF at least 3 concrete failure scenarios with mitigations are proven in `edge_cases` (`minItems: 3`).
- **FR-004 (Jittered Exponential Backoff & 8.0s Inference Budget Guardrail)**: The HTTP client MUST automatically retry transient failures (HTTP 429, 500, 502, 503, 504, and socket timeouts) up to 3 times using full jitter exponential backoff:
  $$T_{\text{wait}} = \min(10.0, 1.0 \times 2^{\text{attempt}}) + \text{uniform}(0.1, 0.5)$$
  Before any retry attempt (after calculating backoff sleep), if remaining monotonic deadline budget $\Delta t_{\text{remaining}} < 8.0\text{s}$ (Minimum Viable Inference Window), the client MUST Fail-Fast immediately (0 retries, exit code 3 `EXIT_TIMEOUT_NETWORK`) to prevent firing doomed partial requests that waste tokens. Response reading in chunks MUST continuously verify `time.monotonic() < deadline`.
- **FR-005 (Strict Deterministic Exit Codes)**: `consult_critic.py` MUST return standardized POSIX exit codes:
  - `0`: Success / Approved (No blocking vulnerabilities found).
  - `1`: Critique Generated (Adversarial findings require remediation).
  - `2`: Authentication / Quota Failure (`DEEPSEEK_API_KEY` missing, HTTP 401, 402, or 429 budget exhausted; fails closed, no fallback).
  - `3`: Network / Upstream Failure (5xx errors, socket timeout, monotonic deadline budget exhaustion).
  - `4`: Client Configuration / Input Error (File not found, invalid CLI syntax, path traversal outside workspace).
  - `5`: Internal System Error.
- **FR-006 (Structured JSON Mode)**: The client MUST support `--json` utilizing DeepSeek's `response_format: {"type": "json_object"}`, returning a machine-parseable JSON object conforming to `DeepSeekArchitectureAuditVerdict`.
- **FR-007 (Performance Telemetry)**: Every CLI invocation MUST measure wall-clock round-trip duration and log a badge to `stderr` (e.g., `[+] Audit completed in 4.8s (3820 tokens)`).
- **FR-008 (Pre-Submission Secret Redaction)**: The client MUST pass all user-provided files and prompts through `scripts/sanitizer.py:redact_credentials()` prior to HTTP payload assembly, scrubbing API keys (`sk-[A-Za-z0-9_-]{20,}`), Anthropic keys (`sk-ant-[A-Za-z0-9_-]{20,}`), Bearer tokens, GitHub PATs (`ghp_` and `github_pat_`), private keys, and `.env` assignments to `[REDACTED_*]` / `[REDACTED_SECRET]`.
- **FR-009 (Pre-Flight Intent Interception)**: `scripts/hook_runner.py` MUST evaluate gatekeeper triggers immediately following slash-command suppression (line 136) and BEFORE empty-resolver exit (lines 155–156). When triggered, it performs two-state local disk artifact checks (`verify_critic_artifact`) with zero network and zero subprocess calls inside `hook_runner.py`.
- **FR-010 (Slash Command Bypass Elimination)**: `scripts/hook_runner.py` MUST eliminate the legacy blanket bypass on slash commands at line 136 (`raw_user_input.startswith("/")`), specifically recognizing `/teamwork`, `/spec-driven-development`, and `/plan` for gatekeeper evaluation.
- **FR-011 (Two-State Context Injection Formatting)**: When triggered, the hook runner MUST format appropriate context into `injectSteps`:
  - **State 1 (Unaudited / Stale / Rejected)**: Injects `[CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE]` mandating `consult_critic.py` execution before task dispatch.
  - **State 2 (Audited & Approved)**: Injects `[CRITICAL REVIEW FROM DEEPSEEK-V4.1-FLASH]` with review metadata and mitigation contracts into agent prompt context.
- **FR-012 (Standard-Library MCP Server)**: The system MUST provide `deepseek_worker_mcp.py` in `d:\Antigravity\DeepSeek Worker\` implementing JSON-RPC 2.0 over stdio without external packages, registering under `deepseek_worker_cloud` in `mcp_config.json`.
- **FR-013 (MCP Tools Specification)**: The MCP server MUST expose `deepseek_audit_spec(spec_content, spec_path, mode)` and `deepseek_audit_diff(diff_content, target_file, language)`.
- **FR-014 (Council Protocol Enshrinement & Fail-Closed Gate)**: Rule 6 of `rules/AGENTS.md` and SDD Primitive 5 in `skills/spec-driven-development/SKILL.md` MUST be updated to formally mandate DeepSeek-V4.1-Flash as the sole ratified Council Gatekeeper, permanently deprecating Argon Bridge. Missing `DEEPSEEK_API_KEY` or quota depletion fails closed with exit code 2, blocking task dispatch and strictly forbidding echo-chamber fallback to `consult_argon.py` or Gemini subagents.
- **FR-015 (1M Context Processing)**: The client and MCP server MUST support ingestion of large documents up to 1,000,000 tokens without client-side arbitrary chunking, relying on DeepSeek-V4.1-Flash's native 1M context window.

---

## 4. Non-Functional Requirements (NFR-001 through NFR-006)

- **NFR-001 (Audit Latency SLA & 8.0s Minimum Inference Budget)**: End-to-end API roundtrip execution time for `consult_critic.py` MUST remain $<30.0\text{ s}$ for payloads up to 100,000 tokens. Socket timeout is dynamic: $T_{\text{socket}} = \min(30.0, \max(0.1, \Delta t_{\text{remaining}}))$. Socket connect timeout MUST be $\le 5.0\text{ s}$ (or clamped to $\Delta t_{\text{remaining}}$). If remaining budget is less than the Minimum Viable Inference Window ($T_{\text{infer\_min}} = 8.0\text{s}$), retries are aborted immediately (Fail-Fast). Response reading in chunks continuously checks monotonic deadline.
- **NFR-002 (Pre-Flight Hook SLA)**: Turnaround time of `scripts/hook_runner.py` for conversational filler inputs MUST remain $<1.0\text{ ms}$; internal algorithmic reflex for cached traces MUST remain $<0.30\text{ ms}$; total non-architectural preflight turnaround MUST remain $<25.0\text{ ms}$.
- **NFR-003 (Zero-Trust Security & AppLocker Compliance)**: All subprocess executions MUST pass arguments as lists (e.g., `[sys.executable, script_path, "--file", target]`), never using `shell=True` or raw shell string concatenation. The script MUST run cleanly under Windows AppLocker and WDAC.
- **NFR-004 (Zero External Dependencies Invariant)**: `scripts/consult_critic.py` MUST execute on Python 3.11+ without running `pip install`. Zero non-stdlib imports permitted.
- **NFR-005 (Physical VRAM Headroom Protection)**: The DeepSeek client and MCP server execute entirely against cloud REST endpoints, consuming 0 MB of GPU VRAM on the host machine. This preserves all 3,741 MB of VRAM headroom on the local AMD Instinct MI50 GPU for local coding workers and system tasks.
- **NFR-006 (Strict Echo-Chamber Elimination)**: Under no circumstances may an internal Gemini subagent (e.g., Gemini Challenger or Gemini Reviewer) provide the final architectural sign-off for an SDD bundle or major RFC. Approval requires an external model family (DeepSeek-V4.1-Flash).

---

## 5. Domain Entity Models & Schemas

### 5.1 Entity: `CriticRequest`
Represents the normalized payload submitted to the DeepSeek REST API.

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

@dataclass
class CriticRequest:
    model: str = "deepseek-v4.1-flash"
    mode: str = "rfc"                     # "rfc" | "code"
    system_prompt: str = ""
    user_content: str = ""
    temperature: float = 0.2
    max_tokens: int = 4096
    top_p: float = 0.95
    stream: bool = False
    response_format: Dict[str, str] = field(default_factory=lambda: {"type": "text"})
    timeout_sec: float = 30.0
    sanitized: bool = False
```

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CriticRequest",
  "type": "object",
  "required": ["model", "mode", "system_prompt", "user_content", "temperature", "max_tokens", "stream"],
  "properties": {
    "model": { "type": "string", "default": "deepseek-v4.1-flash" },
    "mode": { "type": "string", "enum": ["rfc", "code"] },
    "system_prompt": { "type": "string" },
    "user_content": { "type": "string" },
    "temperature": { "type": "number", "default": 0.2 },
    "max_tokens": { "type": "integer", "default": 4096 },
    "top_p": { "type": "number", "default": 0.95 },
    "stream": { "type": "boolean", "default": false },
    "response_format": {
      "type": "object",
      "properties": { "type": { "type": "string", "enum": ["text", "json_object"] } }
    },
    "timeout_sec": { "type": "number", "default": 30.0 },
    "sanitized": { "type": "boolean", "default": false }
  }
}
```

### 5.2 Entity: `CriticResponse`
Represents the structured response returned by DeepSeek-V4.1-Flash.

```python
@dataclass
class CriticResponse:
    id: str
    model: str
    content: str
    verdict: str                          # "APPROVED" | "CONDITIONAL_PASS" | "REJECTED"
    confidence_score: float               # 0.0 to 1.0
    critical_vulnerabilities: List[Dict[str, Any]]
    edge_cases: List[Dict[str, str]]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_sec: float
    raw_json: Optional[Dict[str, Any]] = None
```

### 5.3 Entity: `AuditSession`
Represents the audit execution metadata persisted for traceability and council gate checks.

```python
@dataclass
class AuditSession:
    session_id: str                       # UUID or timestamp hash
    timestamp_utc: str                    # ISO-8601 UTC
    target_file: Optional[str]
    input_hash: str                       # SHA-256 of sanitized input
    mode: str                             # "rfc" | "code"
    exit_code: int                        # 0, 1, 2, 3, 4, 5
    duration_sec: float
    model_version: str
    verdict: str
    retry_count: int
    error_message: Optional[str] = None
```

### 5.4 Entity: `GatekeeperTrigger`
Defines the pattern matching rules used by `hook_runner.py` to trigger external audits.

```python
@dataclass
class GatekeeperTrigger:
    trigger_id: str
    name: str
    regex_pattern: str                    # Regular expression for prompt detection
    intent_category: str                  # "RFC", "SDD", "TEAMWORK", "DIFF"
    is_active: bool = True
    bypass_allowed: bool = False
```

### 5.5 Entity: `DeepSeekArchitectureAuditVerdict` (JSON Mode Output)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DeepSeekArchitectureAuditVerdict",
  "type": "object",
  "required": [
    "verdict",
    "confidence_score",
    "summary",
    "critical_vulnerabilities",
    "edge_cases",
    "constitutional_alignment"
  ],
  "properties": {
    "verdict": {
      "type": "string",
      "enum": ["APPROVED", "CONDITIONAL_PASS", "REJECTED"]
    },
    "confidence_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 1.0
    },
    "summary": {
      "type": "string",
      "description": "Executive summary of critique."
    },
    "critical_vulnerabilities": {
      "type": "array",
      "minItems": 0,
      "description": "Critical vulnerabilities discovered (mandatory >=3 if REJECTED or CONDITIONAL_PASS).",
      "items": {
        "type": "object",
        "required": ["id", "severity", "category", "description", "impact", "recommendation"],
        "properties": {
          "id": { "type": "string", "pattern": "^(VULN|FLAW)-[0-9]{3}$" },
          "severity": { "type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"] },
          "category": { "type": "string", "enum": ["ARCHITECTURE", "SECURITY", "CONCURRENCY", "HARDWARE_LIMIT", "CONSTITUTION"] },
          "description": { "type": "string" },
          "impact": { "type": "string" },
          "recommendation": { "type": "string" }
        }
      }
    },
    "edge_cases": {
      "type": "array",
      "minItems": 3,
      "description": "Mandatory >=3 concrete edge cases evaluated with mitigation strategies.",
      "items": {
        "type": "object",
        "required": ["scenario", "expected_failure", "mitigation"],
        "properties": {
          "scenario": { "type": "string" },
          "expected_failure": { "type": "string" },
          "mitigation": { "type": "string" }
        }
      }
    },
    "constitutional_alignment": {
      "type": "object",
      "required": ["passed", "checked_principles", "violations"],
      "properties": {
        "passed": { "type": "boolean" },
        "checked_principles": { "type": "array", "items": { "type": "string" } },
        "violations": { "type": "array", "items": { "type": "string" } }
      }
    }
  },
  "if": {
    "properties": { "verdict": { "enum": ["REJECTED", "CONDITIONAL_PASS"] } }
  },
  "then": {
    "properties": { "critical_vulnerabilities": { "minItems": 3 } }
  }
}
```

---

## 6. Exhaustive Edge Cases & Concrete Mitigations (14 Distinct Scenarios)

| # | Edge Case / Scenario | Trigger Condition | System Behavior & Mitigation |
|---|----------------------|-------------------|------------------------------|
| **EC-001** | **Massive Document (Up to 1M Tokens)** | User passes entire codebase or monolithic multi-file SDD exceeding 200k tokens. | Stream payload directly without client-side chunking; DeepSeek-V4.1-Flash ingests up to 1,000,000 tokens. Socket read timeout defaults to 30s, overridable to 60s via `--timeout`. |
| **EC-002** | **Network Socket Timeout & 8.0s Inference Budget** | Cloud API queue congestion or slow connection causes socket read/connect timeout. | Caught via `urllib.error.URLError` wrapping `socket.timeout`. Evaluates remaining monotonic deadline budget $\Delta t_{\text{remaining}} = \text{deadline} - \text{time.monotonic()}$. If $\Delta t_{\text{remaining}} < 8.0\text{s}$ (Minimum Viable Inference Window), aborts retry immediately (Fail-Fast, 0 retry, exit code 3 `EXIT_TIMEOUT_NETWORK`) to prevent wasted partial token generation. If $\Delta t_{\text{remaining}} \ge 8.0\text{s}$, retries up to 3 times within budget using dynamic socket timeout $T_{\text{socket}} = \min(30.0, \Delta t_{\text{remaining}})$. Chunked reads verify monotonic deadline continuously. If budget exhausted, prints `[!] DeepSeek API Timeout after 30s. Consider checking status.deepseek.com` and exits with code 3. |
| **EC-003** | **HTTP 429 Rate Limit Throttling** | High-frequency invocations burst past DeepSeek TPM or RPM limits. | Parses `Retry-After` header if available; otherwise falls back to exponential backoff: $T = \min(10.0, 1.0 \times 2^i) + \text{uniform}(0.1, 0.5)$. Retries 3 times before failing loud with exit code 2. |
| **EC-004** | **HTTP 401 Authentication Failure** | `DEEPSEEK_API_KEY` is missing from environment, expired, or invalid. | Fails fast on attempt 0 with ZERO retries. Prints diagnostic: `[!] LỖI XÁC THỰC: DEEPSEEK_API_KEY không hợp lệ hoặc chưa được thiết lập!` and exits code 2. |
| **EC-005** | **HTTP 402 Payment Required** | DeepSeek account balance depleted (0 credits). | Fails fast on attempt 0 with ZERO retries. Prints account recharge instructions with URL `https://platform.deepseek.com` and exits code 2. |
| **EC-006** | **Malformed JSON in Structured Mode** | Model returns invalid JSON or embeds backticks inside `--json` output. | Catches `json.JSONDecodeError`; applies regex extraction for innermost `{...}` block. If parsing succeeds, returns object; if unrecoverable, wraps raw text into `{"verdict": "ERROR", "raw_output": text}` and exits with code 5 (`EXIT_SYSTEM_INTERNAL`). |
| **EC-007** | **HTTP 500/502/503 Upstream Outage** | DeepSeek platform experiences temporary downtime or gateway error. | Categorized as transient server error; retried 3 times with jittered backoff. If persistent, logs error diagnostic and exits code 3. |
| **EC-008** | **Empty File or Whitespace Input** | Target file is 0 bytes or prompt contains only spaces/newlines. | Checks `len(content.strip()) == 0`. Fails immediately without making HTTP call: `[!] Nội dung kiểm tra trống (Empty input). Không thể thực hiện phản biện!`. Exits code 4. |
| **EC-009** | **Non-Existent or Inaccessible File** | `--file` points to a missing path or inaccessible file. | Validates file existence via `os.path.exists()`. Exits immediately with code 4 and message: `[!] Không tìm thấy file: <path>`. |
| **EC-010** | **Complacent / Flattering LLM Output & Defect Floor** | Model outputs praise (e.g., "Looks great, approved!"). | System prompt strictly enforces Devil's Advocate persona forbidding praise. In `--json` mode, schema validator rejects response if verdict is `REJECTED`/`CONDITIONAL_PASS` and `critical_vulnerabilities` array has length $< 3$, or if `edge_cases` array has length $< 3$. When verdict is `APPROVED`, `critical_vulnerabilities` can have length 0 provided `edge_cases` has length $\ge 3$. |
| **EC-011** | **Recursive Gatekeeper Trigger Loop** | `consult_critic.py` execution triggers `hook_runner.py` which triggers `consult_critic.py`. | Prevented by setting process environment variable `OMNI_GATEKEEPER_ACTIVE=1` during subprocess execution; `hook_runner.py` checks this flag and exits immediately if set. |
| **EC-012** | **Windows Path with Spaces & Mixed Slashes** | Windows paths like `d:\Antigravity\Skill management\specs\...` passed via CLI. | Normalizes paths via `os.path.normcase(os.path.normpath(os.path.realpath(path)))`. Subprocess calls use argument lists, completely safe from Windows shell tokenization errors. |
| **EC-013** | **Pre-Flight Hook SLA vs Critic Call** | `hook_runner.py` PreInvocation SLA is $<25\text{ ms}$, but critic API takes several seconds. | Two-phase decoupled architecture: `hook_runner.py` only performs fast local disk checks (<0.30ms) to verify mtime and `OMNI_AUDIT_META` header of `CRITIC_REVIEW.md`, never executing synchronous cloud REST requests during interactive turn pre-flight. |
| **EC-014** | **Model Identifier Drift or Deprecation** | Endpoint returns HTTP 400, 404, or 422 with body indicating model does not exist or is unsupported. | Client catches HTTP 400, 404, or 422; if `err_body.lower()` contains `"model"` and any of `("not exist", "not found", "invalid", "unsupported")`, automatically falls back once to canonical alias `deepseek-chat` and emits transparency notice to `stderr`: `[!] Fallback to deepseek-chat active`. |

---

## 7. Security Trust Boundaries & Defensive Policies

1. **Zero-Trust Network Boundary**:
   - The client communicates solely with `https://api.deepseek.com/chat/completions` using TLS 1.3.
   - Arbitrary custom endpoints are disallowed unless explicitly passed via `DEEPSEEK_BASE_URL` by an administrator.

2. **Credential Redaction Invariant**:
   - Any text passed to `consult_critic.py` is scrubbed using `scripts/sanitizer.py`. Patterns scrubbed include:
     - DeepSeek/OpenAI keys: `sk-[A-Za-z0-9_-]{20,}`
     - Anthropic keys: `sk-ant-[A-Za-z0-9_-]{20,}`
     - Groq keys: `gsk_[A-Za-z0-9]{20,}`
     - GitHub classic PATs: `gh[pousr]_[A-Za-z0-9_]{36,}`
     - GitHub fine-grained PATs: `github_pat_[A-Za-z0-9_]{22,}`
     - Bearer tokens: `(?i)(Bearer\s+)[A-Za-z0-9._\-]{20,}`
     - Private keys: `-----BEGIN [A-Z ]*PRIVATE KEY-----`
     - Quoted and unquoted `.env` assignment statements: `(?i)(password|api_key|secret|token|deepseek_api_key)\s*=\s*(?:["'][A-Za-z0-9+/=_-]{16,}["']|[A-Za-z0-9+/=_-]{16,})`
     - Replacement tokens: `[REDACTED_*]` / `[REDACTED_SECRET]`.

3. **Path Traversal Prevention & Root Clamping**:
   - File reading and writing paths are canonicalized via `os.path.normcase(os.path.normpath(os.path.realpath(path)))` and verified with `os.path.commonpath([allowed_root, canonical_path]) == allowed_root` to ensure they reside within the workspace directory tree, preventing traversal attacks (`../../Windows/System32`) and symlink/junction escapes.

4. **AppLocker & WDAC Hardening**:
   - Zero non-stdlib binary dependencies, zero ctypes DLL loading, zero arbitrary string execution (`eval`, `exec`). All subprocess calls execute with clean argument lists without invoking `cmd.exe` or `powershell.exe` shell wrappers.

5. **Process Recursion Suppression**:
   - Subprocess executions set `OMNI_GATEKEEPER_ACTIVE=1` in `os.environ` to prevent infinite gatekeeper recursion.
