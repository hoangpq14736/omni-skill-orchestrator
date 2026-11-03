# Implementation Plan: Omni-Auditor Strict Architecture Gatekeeper (DeepSeek-V4.1-Flash)

**Branch**: `002-deepseek-v41-auditor` | **Date**: 2026-11-03 | **Spec**: [specs/002-deepseek-v41-auditor/spec.md](spec.md)  
**Input Documents**:
- `specs/002-deepseek-v41-auditor/spec.md` (Feature Specification)
- `PROJECT_DEEPSEEK_V41_AUDITOR.md` (Strict Architecture Gatekeeper Blueprint)
- `.specify/constitution.md` (Omni-Kernel v4.1 Constitution, Ratified 2026-11-02)
- `d:\Antigravity\Skill management\.agents\teamwork\orchestrator_1\PROJECT.md`
- `d:\Antigravity\Skill management\.agents\teamwork\explorer_m1_2\blueprint.md`
- Reference SDD: `specs/001-omni-memory-v4/plan.md`

---

## 1. Executive Summary & Problem Statement

### 1.1 Context & Tripartite Governance
In the Omni-Kernel v4.1 ecosystem, multi-agent orchestration is governed by an inviolable tripartite hierarchy:
1. **Executive & Lead Planner (Google Antigravity / Gemini 2.5/3.x Pro & Flash)**: Drives task decomposition, high-level milestone planning, user interaction, and agent dispatching.
2. **Worker Fleet**:
   - `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 GPU): Executes in-place source code editing, local SQLite WAL transactions, and AST mutations in an offline, zero-leakage sandbox.
   - `groq_worker_cloud` (Groq LPU Cloud 120B): Executes sub-second boilerplate synthesis, regex pipelines, and massive unit test suite authoring at 300–800+ tok/s.
3. **Supreme Architectural Gatekeeper (DeepSeek-V4.1-Flash MoE 552B with `-1017` Agentic Patch)**: Operates as an independent adversarial auditor tasked with challenging architectural assumptions, catching latent concurrency or hardware bugs, and preventing unvetted specifications from reaching the worker fleet.

### 1.2 Breakdown of Legacy Argon Bridge
The legacy gatekeeper mechanism (`scripts/consult_argon.py`) routed architectural critique requests to Gemini 4 Argon via a local bridge (`http://127.0.0.1:7890`) backed by a Tampermonkey userscript (`gemini_argon_bridge.user.js`) running inside a browser tab at `https://gemini.google.com`.

Forensic investigation revealed critical points of failure:
- **Process & Session Fragility**: The bridge requires an active, unminimized, unthrottled browser window. Operating system background tab sleep timers, navigation away from the tab, or Cloudflare/Google CAPTCHAs immediately severed the WebSocket connection.
- **Excessive Latency Ceiling**: The script enforced a default 240-second timeout ceiling, stalling agent workflows for minutes whenever the web interface suffered queue congestion.
- **DOM & UI Instability**: Because the Tampermonkey script relied on DOM scraping and simulated keyboard events, minor UI changes by Google broke the bridge silently.
- **Model Homogeneity**: The bridge routed to a Gemini-family model (Gemini 4 Argon), perpetuating cognitive self-review.

### 1.3 The Cognitive "Echo Chamber" Dilemma
During multi-agent planning sessions (such as `/teamwork` invocations), Antigravity systematically bypassed the Argon Bridge due to latency or connection errors. To fulfill the review requirement, Antigravity spawned internal Gemini subagents (e.g., Reviewer, Challenger, Forensic Auditor). 

Because these subagents shared identical model architectures, pre-training corpora, and inductive biases:
- **Shared Blind Spots**: Subtle hardware bottlenecks (such as Windows WDDM 60-second TDR Event 4101 timeouts on AMD Vega 20, or SQLite `remove_diacritics 2` tonal destruction on Vietnamese text) were approved without scrutiny.
- **Sycophancy & False Consensus**: Subagents politely complimented each other's proposals rather than mounting aggressive red-teaming assaults.
- **Soft Prompting Breakdown**: Placing rules solely in `rules/AGENTS.md` failed because large language models inherently follow the path of least resistance when facing external tool friction.

### 1.4 The Triad Separation of Powers (Tam Quyền Phân Lập)
To solve these systemic failures permanently, the architecture transitions to an inviolable tripartite separation of powers:

```
┌────────────────────────────────────────────────────────────────────────┐
│               EXECUTIVE / PLANNER: Google Antigravity                  │
│       (Gemini 2.5/3.x Pro & Flash — Task decomposition & UI)          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│           DETERMINISTIC HARD GATEKEEPER: scripts/hook_runner.py        │
│   (Subprocess interceptor: verifies audit artifact before merge/run)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Requires External Audit
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│        SUPREME AUDITOR & RED-TEAMING GATEKEEPER: DeepSeek-V4.1-Flash   │
│   (Independent MoE 552B Model, 1M Context Window, Direct Cloud REST)   │
│    - Role: Devil's Advocate / Principal Architect / Forensic Auditor   │
│    - Strict Anti-Praise Policy: Must find >= 3 critical vulnerabilities│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼ [IF REJECTED / CRITIQUE FOUND]                  ▼ [IF APPROVED]
┌──────────────────────────────────────┐  ┌──────────────────────────────────────┐
│ Planner receives critique payload    │  │ Tasks dispatched to Dual Worker Fleet│
│ Mandatory architectural refinement   │  │  - local_worker_mi50 (In-place edit) │
│ Subagent echo chamber blocked        │  │  - groq_worker_cloud (Fast codegen)  │
└──────────────────────────────────────┘  └──────────────────────────────────────┘
```

Why **DeepSeek-V4.1-Flash** (MoE 552B with `-1017` patch):
1. **1,000,000-Token Native Context Window**: Ingests multi-file SDD bundles, complete repository diffs, architectural constitutions, and test logs in a single unchunked request.
2. **Native Agentic Tuning (`-1017`)**: Optimized specifically for Agent Harnesses (Claude Code, Antigravity, SWE-bench), understanding git diff grammar and SDD lifecycle states.
3. **MoE Cost & Latency Profile**: Activates only 8B/16B parameters per forward pass, delivering 1.5s–5.0s TTFT (Time-To-First-Token) and P99 latency $<30\text{s}$ at ~$0.30/1M input tokens.
4. **Cognitive Independence**: Radically different architecture and pre-training dataset from Gemini, guaranteeing genuine red-teaming friction.

---

## 2. Technical Context

- **Runtime & Language**: Python 3.11+ Standard Library (`urllib.request`, `urllib.error`, `json`, `ssl`, `os`, `sys`, `time`, `argparse`, `re`, `random`, `pathlib`).
- **Dependencies**: Zero external dependencies (100% Python Standard Library). `requests`, `httpx`, `aiohttp`, `pydantic`, `openai`, `deepseek` are strictly prohibited.
- **Transport**: HTTPS POST over TLS 1.3 to `https://api.deepseek.com/chat/completions`.
- **Target Platform**: Windows 11 x64 (PowerShell host environment, AppLocker-safe, standard non-elevated user token).
- **Constraints**:
  - Global execution turnaround ceiling: strictly $\le 30.0\text{ s}$ governed by a monotonic clock deadline (`deadline = time.monotonic() + timeout_budget`, default 30.0s).
  - Socket connect timeout: $\le 5.0\text{ s}$; socket timeout is dynamic: $T_{\text{socket}} = \min(30.0, \max(0.1, \Delta t_{\text{remaining}}))$. Response reading in chunks continuously verifies monotonic deadline. Under no circumstances may accumulated retries and timeouts exceed 30.0s.
  - Pre-flight conversational filler bypass in `hook_runner.py`: $<1.0\text{ ms}$.
  - Pre-flight non-architectural hook turnaround: $<25.0\text{ ms}$.
  - MI50 VRAM consumption: Strictly 0 MB (preserves 3,741 MB VRAM headroom on AMD Instinct MI50).
  - Stop-Point Invariant: Production runtime code remains unmodified during this specification authoring run.

---

## 3. Constitution Check

*GATE: All principles from `.specify/constitution.md` evaluated prior to implementation planning.*

| Constitutional Principle | Requirement Summary | Architectural Compliance Strategy | Gate Verdict |
|---|---|---|---|
| **Principle I: Sub-Millisecond L1 Reflex** | P99 latency $<0.30\text{ ms}$; 2,048-char head clamp; decoupled writes; $<25\text{ ms}$ subprocess turnaround. | Two-phase gatekeeper decoupling: `hook_runner.py` only performs $<0.30\text{ ms}$ mtime artifact checks on disk, never executing synchronous cloud REST requests during turn pre-flight. | **PASS** |
| **Principle II: Zero-Trust Security** | Parameterized inputs; credential redaction; local-only storage; transparent cloud fallback; canonical path hashing. | Automated regex credential scrubbing via `scripts/sanitizer.py` before payload dispatch; path normalization via `os.path.normcase(os.path.normpath(os.path.abspath()))`; zero plaintext secrets in logs. | **PASS** |
| **Principle III: Dual-Language Parity** | Vietnamese & English equal-fidelity; `đ/Đ` normalization; automated bilingual diagnostics. | Error diagnostics and system prompts provide first-class Vietnamese and English operational messages. | **PASS** |
| **Principle IV: Hardware Realism** | Protect AMD Instinct MI50 VRAM headroom (>3,741 MB); 16k context cap; `-ub 2048`. | Critic client runs 100% against cloud REST API, consuming 0 MB host GPU VRAM. Prompts strictly enforce MI50 constraints during architectural reviews. | **PASS** |
| **Principle V: Bounded Consolidation** | Mathematically bounded algorithms; RRF $k=20$; Ebbinghaus stability; permanent invariants. | Telemetry logged to `l1_staging_log` with bounded file rotation; exit codes deterministically structured (0 to 5). | **PASS** |
| **Stop-Point Invariant** | Pause for human approval; zero runtime code changes during SDD bundle phase. | SDD bundle confined exclusively to `specs/002-deepseek-v41-auditor/`; production scripts in `scripts/` and `rules/` untouched. | **PASS** |

---

## 4. Authoritative REST API Contracts & DeepSeek Schema

### 4.1 Transport Layer & Protocol Specifications
The client communicates directly with DeepSeek Cloud endpoints over TLS 1.3:
- **Primary Endpoint**: `https://api.deepseek.com/chat/completions`
- **Configurable Base URL**: Overrideable via `DEEPSEEK_API_BASE` (default: `https://api.deepseek.com`)
- **HTTP Method**: `POST`
- **Transport**: HTTPS via standard library `urllib.request` with SSL verification (`ssl.create_default_context()`)
- **Authentication**: Bearer Token via `DEEPSEEK_API_KEY`

### 4.2 Exact HTTP Headers
```http
POST /chat/completions HTTP/1.1
Host: api.deepseek.com
Authorization: Bearer <DEEPSEEK_API_KEY>
Content-Type: application/json; charset=utf-8
Accept: application/json
User-Agent: AntigravityOmniAuditor/4.1 (Windows 11 x64; Python 3.11+; Stdlib)
Connection: close
```

### 4.3 JSON Request Payload Schema
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DeepSeekChatCompletionRequest",
  "type": "object",
  "required": ["model", "messages", "temperature", "max_tokens", "stream"],
  "properties": {
    "model": {
      "type": "string",
      "default": "deepseek-v4.1-flash",
      "description": "Model identifier. Fallback to deepseek-chat if HTTP 400, 404, or 422 with model error occurs."
    },
    "messages": {
      "type": "array",
      "minItems": 2,
      "items": {
        "type": "object",
        "required": ["role", "content"],
        "properties": {
          "role": { "type": "string", "enum": ["system", "user", "assistant"] },
          "content": { "type": "string", "minLength": 1 }
        }
      }
    },
    "temperature": {
      "type": "number",
      "default": 0.2,
      "minimum": 0.0,
      "maximum": 2.0,
      "description": "Low temperature (0.2) enforced for deterministic architectural critique."
    },
    "max_tokens": {
      "type": "integer",
      "default": 4096,
      "minimum": 256,
      "maximum": 8192,
      "description": "Token cap for critique report generation."
    },
    "top_p": { "type": "number", "default": 0.95 },
    "frequency_penalty": { "type": "number", "default": 0.0 },
    "presence_penalty": { "type": "number", "default": 0.0 },
    "response_format": {
      "type": "object",
      "properties": {
        "type": { "type": "string", "enum": ["text", "json_object"] }
      }
    },
    "stream": {
      "type": "boolean",
      "enum": [false],
      "description": "Streaming is false to preserve atomic output delivery and deterministic verification."
    }
  }
}
```

### 4.4 Structured JSON Response Format (when `--json` is active)
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

## 5. Zero-Dependency Client Architecture

### 5.1 Strict Standard Library Baseline
In conformance with Principle II (Zero-Trust Security) and the Zero-Dependency Architectural Baseline of the Omni-Kernel Constitution:
- **Strictly Prohibited Packages**: `requests`, `httpx`, `aiohttp`, `urllib3`, `pydantic`, `openai`, `deepseek`.
- **Approved 100% Python 3.11+ Standard Library Modules**:
  - `urllib.request`: `Request`, `urlopen`
  - `urllib.error`: `HTTPError`, `URLError`
  - `json`: `dumps`, `loads`, `JSONDecodeError`
  - `ssl`: `create_default_context`, `SSLContext`
  - `os`: `environ`, `path`, `walk`
  - `sys`: `argv`, `exit`, `stdin`, `stdout`, `stderr`
  - `time`: `time`, `sleep`
  - `random`: `uniform` (for jitter calculation)
  - `argparse`: `ArgumentParser`, `RawDescriptionHelpFormatter`
  - `pathlib`: `Path`
  - `re`: `compile`, `sub`, `search`

### 5.2 Platform & Security Guardrails
1. **Windows 11 AppLocker Safety**: Zero compiled C extensions or untrusted binary wheels. The entire client executes cleanly within standard Python 3.11+ interpreters without triggering Windows Software Restriction Policies.
2. **Path Normalization & Traversal Defense Invariant**: All input and output file paths must be normalized and boundary-checked using:
   ```python
   canonical_path = os.path.normcase(os.path.normpath(os.path.realpath(raw_path)))
   if os.path.commonpath([allowed_root, canonical_path]) != allowed_root:
       raise ValueError(f"Path traversal detected: {raw_path} escapes workspace root {allowed_root}")
   ```
   This prevents directory traversal vulnerabilities (`..` navigation), Windows symlink/junction escapes, and drive letter casing collisions (`d:\` vs `D:\`).
3. **UTF-8 Clean Stream Separation**:
   - `sys.stdout`: Reserved exclusively for audit report content (or valid JSON). Piped streams can be redirected directly to files (`python scripts/consult_critic.py -f plan.md > CRITIC_REVIEW.md`) without corrupting headers.
   - `sys.stderr`: Reserved exclusively for diagnostics, progress indicators, retry warnings, and latency telemetry.

---

## 6. Resilience, Backoff & Error Classification Matrix

### 6.1 Jittered Exponential Backoff Mathematics
To prevent thundering herds and cloud-side congestion while adhering to strict time budgets:

$$T_{\text{wait}}(i) = \min\left(T_{\max}, T_0 \cdot 2^{i}\right) + \mathcal{U}(J_{\min}, J_{\max})$$

Where:
- $T_0 = 1.0\text{ s}$ (Base initial backoff)
- $T_{\max} = 10.0\text{ s}$ (Backoff ceiling)
- $i \in \{0, 1, 2\}$ (Zero-indexed retry attempt count)
- $\mathcal{U}(J_{\min}, J_{\max}) \sim \text{Uniform}(0.1, 0.5)\text{ s}$ (Random additive uniform jitter)

**Worst-Case Retry Accumulation & Global Monotonic Deadline Contract**:
- Attempt 0 (failure): wait $1.0\text{s} + \sim 0.3\text{s} = 1.3\text{s}$
- Attempt 1 (failure): wait $2.0\text{s} + \sim 0.3\text{s} = 2.3\text{s}$
- Attempt 2 (failure): wait $4.0\text{s} + \sim 0.3\text{s} = 4.3\text{s}$
- **Total Backoff Wait Budget**: $\approx 7.9\text{ seconds}$ (empirical range: $[7.317\text{s}, 8.478\text{s}]$), leaving $\ge 21.5\text{s}$ of socket I/O budget.

### 6.1.1 Monotonic Deadline Clamping Algorithm
To guarantee that `consult_critic.py` never hangs or breaches the 30.0s SLA under any failure mode:
1. **Clock Monotonicity**: At entry, the client establishes:
   $$\text{deadline} = \text{time.monotonic()} + \text{timeout\_budget}$$
   (where $\text{timeout\_budget}$ is initialized from the `--timeout` CLI flag, default $30.0\text{s}$, bounded between $5.0\text{s}$ and $120.0\text{s}$).
2. **Remaining Time Evaluation**: Prior to each HTTP request and prior to each backoff sleep:
   $$\Delta t_{\text{remaining}} = \text{deadline} - \text{time.monotonic()}$$
   - If $\Delta t_{\text{remaining}} \le 0.5\text{s}$: The retry loop terminates immediately without further attempts, exiting with code 3 (`EXIT_TIMEOUT_NETWORK`).
3. **Dynamic Socket Timeout Clamping**: The socket timeout for `urllib.request.urlopen` is strictly dynamic:
   $$T_{\text{socket}} = \min\left(30.0, \max\left(0.1, \Delta t_{\text{remaining}}\right)\right)$$
4. **Socket Timeout & 8.0s Minimum Inference Budget Clamping**:
   If an HTTP attempt encounters a socket connect or read timeout (`urllib.error.URLError` wrapping `socket.timeout` or `TimeoutError`):
   - Evaluate remaining monotonic deadline budget: $\Delta t_{\text{remaining}} = \text{deadline} - \text{time.monotonic()}$.
   - If $\Delta t_{\text{remaining}} < 8.0\text{s}$ (Minimum Viable Inference Window): No viable model generation can complete within the remaining time (DeepSeek MoE requires 4.0s–10.0s TTFT + generation for 4k tokens). The client MUST Fail-Fast immediately (0 retries) and exit with code 3 (`EXIT_TIMEOUT_NETWORK`) to prevent wasted partial token generation.
   - If $\Delta t_{\text{remaining}} \ge 8.0\text{s}$: The client permits retry within the remaining budget (up to max 3 total retries across all transient errors), using dynamically clamped socket timeout $T_{\text{socket}} = \min(30.0, \Delta t_{\text{remaining}})$. Response reading in chunks continuously verifies monotonic deadline.

### 6.1.2 Safe `Retry-After` Header Parsing & Monotonic Budget Clamping
When DeepSeek Cloud emits an HTTP 429 (Rate Limit) response with a `Retry-After` header:
1. **Safe Numeric Parsing**: The header string must be safely converted to a numeric duration within a `try / except (ValueError, TypeError)` guard. If the header represents an HTTP-date (RFC 7231) or malformed token, the client logs a warning to `sys.stderr` and falls back immediately to the standard jittered exponential backoff formula:
   $$T_{\text{wait}}(i) = \min\left(10.0, 1.0 \cdot 2^i\right) + \mathcal{U}(0.1, 0.5)$$
2. **Monotonic Budget Clamping (with 8.0s Inference Floor)**:
   If a valid numeric `delay` is extracted, it MUST be clamped against the remaining monotonic deadline:
   $$\Delta t_{\text{remaining}} = \text{deadline} - \text{time.monotonic()}$$
   - If $\text{delay} \ge \Delta t_{\text{remaining}} - 8.0\text{s}$: Sleeping the requested duration would leave less than the Minimum Viable Inference Window ($8.0\text{s}$) to execute the retry request before the 30.0s SLA expires. The client **aborts the retry loop immediately**, emits a diagnostic message to `sys.stderr` (`[!] HTTP 429: Retry-After delay (Xs) exhausts remaining viable inference budget (<8.0s).`), and exits with code 2 (`EXIT_AUTH_QUOTA_ERROR`).
   - Otherwise, the sleep duration is set to:
     $$T_{\text{sleep}} = \min\left(\text{delay}, \max\left(0.0, \Delta t_{\text{remaining}} - 8.0\right)\right)$$

```python
def calculate_sleep_duration(
    retry_after_header: str | None, 
    attempt: int, 
    deadline: float, 
    min_infer_window: float = 8.0
) -> float | None:
    """Calculates backoff sleep duration with safe parsing and monotonic deadline clamping.
    Returns None when remaining budget after sleep is below min_infer_window (8.0s) to signal immediate Fail-Fast abort."""
    remaining = deadline - time.monotonic()
    if remaining <= min_infer_window:
        return None  # Viable inference budget exhausted, abort retry loop
        
    delay: float | None = None
    if retry_after_header:
        try:
            delay = float(retry_after_header.strip())
        except (ValueError, TypeError):
            # Fall back to exponential jitter on non-numeric or HTTP-date formats
            delay = None
            
    if delay is None:
        delay = min(10.0, 1.0 * (2 ** attempt)) + random.uniform(0.1, 0.5)
        
    if delay >= remaining - min_infer_window:
        # Sleep would leave remaining time below Minimum Viable Inference Window (8.0s); return None to abort immediately
        return None
        
    return min(delay, remaining - min_infer_window)
```

### 6.2 Error Classification & Recovery Matrix

| HTTP Status / Exception | Error Category | Retryable? | Max Retries | Backoff Strategy | Exit Code | Diagnostic Action & Message |
|---|---|---|---|---|---|---|
| **HTTP 400 Bad Request** | Client / Model | Conditional | 1 Fallback | None | `4` | If response body indicates `"model"` and any of `("not exist", "not found", "invalid", "unsupported")`, fall back once to `model = "deepseek-chat"`. Otherwise fail fast and print API error to `stderr`. |
| **HTTP 401 Unauthorized** | Authentication | No | 0 | None | `2` | Fail fast. Print: `[!] LỖI XÁC THỰC: DEEPSEEK_API_KEY không hợp lệ hoặc chưa được thiết lập trong biến môi trường hoặc .env!`. |
| **HTTP 402 Payment Required** | Quota / Billing | No | 0 | None | `2` | Fail fast. Print: `[!] LỖI TÀI KHOẢN: Tài khoản DeepSeek hết số dư (HTTP 402). Vui lòng nạp tiền tại https://platform.deepseek.com`. |
| **HTTP 404 Not Found** | Model Routing | Conditional | 1 Fallback | None | `4` | Catch 404; if response body indicates model routing error, attempt automatic transparent fallback to `deepseek-chat`; otherwise exit code 4. |
| **HTTP 422 Unprocessable** | Input / Model | Conditional | 1 Fallback | None | `4` | If response body indicates model routing error, fall back once to `deepseek-chat`. Otherwise fail fast with API validation error. |
| **HTTP 429 Rate Limit** | Cloud Throttling | **Yes** | 3 | Exponential Jitter with Safe `Retry-After` Clamping | `2` | If `Retry-After` header present, safely parse (falling back to jitter on `ValueError` / HTTP-date). Clamp sleep to $\min(\text{delay}, \Delta t_{\text{remaining}} - 8.0\text{s})$. If delay exhausts remaining inference budget ($<8.0\text{s}$), fail fast and exit code 2. |
| **HTTP 500 Internal Error** | Upstream Crash | **Yes** | 3 | Exponential Jitter | `3` | DeepSeek server-side crash. Retries up to 3 times within monotonic budget. |
| **HTTP 502 / 503 / 504** | Cloud Gateway | **Yes** | 3 | Exponential Jitter | `3` | Cloud gateway / load balancer timeout. Retries up to 3 times within monotonic budget. |
| `urllib.error.URLError` (Timeout) | Network Socket | **Conditional** | Up to 3 | Dynamic $T_{\text{socket}}$ Clamped | `3` | Evaluate $\Delta t_{\text{remaining}} = \text{deadline} - \text{time.monotonic()}$. If $< 8.0\text{s}$ (Minimum Viable Inference Window), abort immediately (Fail-Fast, 0 retries, exit code 3). If $\ge 8.0\text{s}$, allow retry up to 3 times within budget using dynamic socket timeout $T_{\text{socket}} = \min(30.0, \Delta t_{\text{remaining}})$. |
| `urllib.error.URLError` (DNS/Refused) | Local Network | **Yes** | 2 | Fixed delay: 2.0s | `3` | DNS resolution failure or network interface down. Retries twice. |

---

## 7. Devil's Advocate Red-Teaming System Prompts

### 7.1 Mode 1: Architectural Specification Review (`--mode rfc`)
```text
You are the Omni-Kernel Architecture Gatekeeper & Devil's Advocate, powered by DeepSeek-V4.1-Flash.
Your mandate is strictly RED-TEAMING. You are tasked with rigorously evaluating the provided technical specification, architecture RFC, or SDD bundle.

OPERATIONAL INVARIANTS:
1. ZERO SYCOPHANCY: Praise, flattery, compliments, or polite fillers are STRICTLY PROHIBITED. Do not say "Great job" or "Looks solid".
2. MANDATORY VULNERABILITY FLOOR & CONDITIONAL CRITIQUE CONTRACT:
   - DeepSeek JSON mode (`response_format: {"type": "json_object"}`) does not perform server-side Draft-07 schema validation. You MUST strictly adhere to this semantic contract:
   - If audit findings identify architectural defects, missing error bounds, or invariant violations, you MUST issue verdict REJECTED or CONDITIONAL_PASS, and you MUST populate AT LEAST 3 distinct critical vulnerabilities in `critical_vulnerabilities` (minItems: 3).
   - You are strictly FORBIDDEN from issuing verdict APPROVED with 0 critical vulnerabilities unless the architecture is verified 100% sound AND you document AT LEAST 3 rigorous defensive failure scenarios with concrete mitigations in `edge_cases` (minItems: 3). Issuing APPROVED with fewer than 3 edge cases is strictly invalid and will trigger automated gate rejection.
3. CONSTITUTIONAL VERIFICATION: Audit strictly against the Omni-Kernel v4.1 Constitution (.specify/constitution.md):
   - Principle I: Sub-millisecond L1 reflex (<0.30ms, <25ms subprocess turnaround, 2,048-char head clamping, two-process boundary).
   - Principle II: Zero-Trust Security (parameterized SQL ? only, automated regex credential redaction, local-only storage).
   - Principle III: Dual-language parity (Vietnamese & English, đ/Đ consonant stroke normalization, intfloat/multilingual-e5-small model mandate).
   - Principle IV: Physical hardware bounds (AMD Instinct MI50 VRAM Headroom strictly >3,741 MB, prompt cap <=16k tokens, -ub 2048, llama_autostart.lock with 30s stale recovery).
   - Principle V: Mathematically bounded consolidation (RRF k=20, Ebbinghaus decay S(t) in [0, 1], soft-archiving, permanent invariants).
4. OUTPUT FORMATTING:
   Your output must strictly follow this structure:
   # 🛡️ Architectural Red-Teaming Audit: [Document Title]
   ## 1. Constitutional & Ring 0 Invariants Verification (PASS / FAIL / WARN)
   ## 2. Top Critical Architectural Vulnerabilities & Failure Modes (Minimum 3 items)
   ## 3. Concurrency, Race Condition & Data Corruption Hazards
   ## 4. Hardware Realism & Resource Budget Evaluation
   ## 5. Prescriptive Remediation Directives (Concrete instructions before approval)
   ## 6. Council Gate Verdict: [APPROVED | CONDITIONAL_PASS | REJECTED]
```

### 7.2 Mode 2: Forensic Code Diff Review (`--mode code`)
```text
You are the Omni-Kernel Code Security & Reliability Auditor, powered by DeepSeek-V4.1-Flash.
Your mandate is to inspect code diffs and implementations generated by the worker fleet (local_worker_mi50 or groq_worker_cloud) before merging into the main codebase.

EVALUATION CRITERIA:
1. Zero-Trust Security: Check for SQL injection, unparameterized string formatting on DB cursors, unredacted API keys or secrets, and unvalidated user inputs.
2. Concurrency & Mutex Safety: Check for SQLite WAL locking conflicts, unhandled file lock stale states, deadlocks, and thread safety.
3. Ponytail Simplicity: Ensure minimal complete working diff. Flag any unrequested abstractions, extra wrappers, speculative config, or code bloat.
4. Error Handling & Fail-Loud: Ensure no silently swallowed exceptions (except: pass or bare except without diagnostics).
5. Environment Compatibility: Check Windows 11 compatibility (PowerShell syntax with semicolons, WDDM TdrDelay bounds, AppLocker safety).

OUTPUT FORMATTING:
# 🔍 Forensic Code & Diff Reliability Audit
## 1. Security & Trust Boundary Assessment
## 2. Concurrency & Resource Leak Analysis (Sockets, files, DB cursors)
## 3. Ponytail Minimalism Check (Over-engineering / Bloat)
## 4. Required Code Modifications (Exact minimal diff snippets)
## 5. Merge Verdict: [APPROVED | CONDITIONAL_PASS | REJECTED]
```

---

## 8. CLI Parity Interface & Exit Codes Specification

### 8.1 CLI Argument Parity with `scripts/consult_argon.py`
`scripts/consult_critic.py` maintains full backward-compatible flag parity with the legacy script while introducing structured auditing capabilities:

| CLI Flag | Short | Type | Default | Description |
|---|---|---|---|---|
| `--file` | `-f` | `str` | `None` | Path to target document (RFC, SDD bundle, plan.md, or git diff). |
| `--prompt` | `-p` | `str` | `None` | Raw text prompt or direct architectural query. |
| `--out` | `-o` | `str` | `None` | Output file path to write the markdown critique report. |
| `--mode` | `-m` | `choice` | `rfc` | Audit mode: `rfc` (architectural spec review) or `code` (diff review). |
| `--timeout` | `-t` | `int` | `30` | Maximum network timeout in seconds (bounded: 5 to 120). |
| `--model` | - | `str` | `deepseek-v4.1-flash`| Target model identifier. Overridable via `DEEPSEEK_MODEL`. |
| `--temperature` | - | `float` | `0.2` | Generation temperature (low temperature for strict analysis). |
| `--strict` | - | `flag` | `False` | When set, exits deterministically with code `5` (`EXIT_SYSTEM_INTERNAL`) if the council gate verdict is `REJECTED`. (When omitted, `REJECTED` exits with code `1` `EXIT_CRITIQUE_GENERATED` to allow programmatic inspection without halting shell pipelines). |
| `--json` | - | `flag` | `False` | Emits structured JSON to `stdout` instead of markdown. |

### 8.1.1 Custom ArgumentParser Implementation (Exit Code 4 Parity)
By default, Python's standard library `argparse.ArgumentParser.error()` prints usage to `sys.stderr` and calls `sys.exit(2)`. In the Omni-Auditor specification, exit code 2 is strictly reserved for `EXIT_AUTH_QUOTA_ERROR` (API key missing or balance exhausted).

To prevent contract collisions, `scripts/consult_critic.py` MUST subclass `argparse.ArgumentParser` and override `.error(message)` to exit deterministically with code 4 (`EXIT_CONFIG_INPUT_ERROR`):

```python
class StrictArgumentParser(argparse.ArgumentParser):
    """Custom CLI parser enforcing exit code 4 on parameter and usage errors."""
    
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"consult_critic.py: error: {message}\n")
        sys.exit(4)  # EXIT_CONFIG_INPUT_ERROR (preserves code 2 for auth/quota)
```

### 8.2 Authoritative Exit Code Specification
The exit codes are strictly partitioned to enable deterministic programmatic handling:

| Exit Code | Identifier | Trigger Conditions | Downstream Action |
|---|---|---|---|
| `0` | `EXIT_APPROVED` | Audit completed successfully with `APPROVED` verdict, or critique emitted without blocking execution. | Pipeline proceeds immediately. |
| `1` | `EXIT_CRITIQUE_GENERATED` | Audit completed successfully, but critic issued `CONDITIONAL_PASS` or `REJECTED` findings requiring mandatory remediation. | Planner must ingest critique and refine specification. |
| `2` | `EXIT_AUTH_QUOTA_ERROR` | `DEEPSEEK_API_KEY` missing/invalid (HTTP 401) or account balance depleted (HTTP 402 / 429 quota exhausted). Strictly isolated from CLI syntax errors. | Halts pipeline; prompts user to configure key or replenish credits. |
| `3` | `EXIT_TIMEOUT_NETWORK` | Global monotonic timeout (>30s SLA), socket read timeout, or upstream gateway error (HTTP 502/503/504) after retry exhaustion. | Triggers fallback protocol or alerts operator to cloud outage. |
| `4` | `EXIT_CONFIG_INPUT_ERROR`| Target input file not found, unreadable, 0 bytes, payload exceeds size clamp, or invalid CLI parameters / syntax errors intercepted by `StrictArgumentParser.error()`. | Fails fast with argument usage diagnostics. |
| `5` | `EXIT_SYSTEM_INTERNAL` | Unhandled internal exception, JSON parse error without fallback, or strict gate rejection (`--strict` and `REJECTED`). | Emits full stack trace to `stderr`. |

### 8.2.1 Verdict vs. `--strict` Flag Exit Code Truth Table

| Critic Verdict | `--strict` Flag | Exit Code | Symbolic Constant | Description & Downstream Handling |
|---|---|---|---|---|
| `APPROVED` | `False` (Omitted) | `0` | `EXIT_APPROVED` | Specification verified; pipeline proceeds to worker fleet. |
| `APPROVED` | `True` (Set) | `0` | `EXIT_APPROVED` | Specification verified; pipeline proceeds to worker fleet. |
| `CONDITIONAL_PASS` | `False` (Omitted) | `1` | `EXIT_CRITIQUE_GENERATED` | Non-blocking critique emitted; planner inspects and addresses caveats. |
| `CONDITIONAL_PASS` | `True` (Set) | `1` | `EXIT_CRITIQUE_GENERATED` | Warnings present; planner inspects caveats. |
| `REJECTED` | `False` (Omitted) | `1` | `EXIT_CRITIQUE_GENERATED` | Critique emitted; planner ingests findings for mandatory refinement. |
| `REJECTED` | `True` (Set) | `5` | `EXIT_SYSTEM_INTERNAL` | **Hard Gatekeeper Rejection**: Aborts automated build / agent loop immediately. |

---

## 9. Decoupled Two-Phase Gatekeeper Architecture

### 9.1 The Constitutional Latency Boundary
- **Principle I Invariant**: `scripts/hook_runner.py` must complete internal reflex processing in **$<0.30\text{ ms}$** and total CLI subprocess turnaround in **$<25.0\text{ ms}$**.
- **Network Latency Reality**: DeepSeek REST API roundtrip ranges between 1.5s and 15s.
- **Architectural Violation Prevention**: Synchronous execution of `consult_critic.py` inside `hook_runner.py` during normal turns is **strictly prohibited**.

### 9.2 Two-Phase Enforcement Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: PRE-INVOCATION REFLEX GATE (scripts/hook_runner.py)           │
│ - Execution Budget: <0.30 ms reflex / <25 ms subprocess               │
│ - 100% Python Standard Library, Zero Network I/O                       │
│ - Detects RFC / SDD / /teamwork intent in user prompt                  │
│ - Verifies filesystem mtime of spec vs CRITIC_REVIEW.md artifact       │
│ - Injects Deterministic Mandate if un-audited or stale                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼ [Prompt Guidance Injected]
┌────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: COUNCIL GATE EXECUTION (Phase 5 / CLI / MCP Server)           │
│ - Invocation: Dedicated subprocess or deepseek_worker_mcp tool call    │
│ - Execution Budget: Bounded <30.0s cloud REST call                     │
│ - Executes DeepSeek-V4.1-Flash Red-Teaming Critique                    │
│ - Persists CRITIC_REVIEW.md with cryptographic / mtime metadata       │
│ - Blocks Task Dispatch until APPROVED or CONDITIONAL_PASS resolved    │
└────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Phase 1 Implementation Detail (`hook_runner.py`)
1. **Slash Command & Intent Sequencing**:
   - In `scripts/hook_runner.py`, line 136 handles slash commands (`if raw_user_input.startswith("/"): ...`). Rather than a blanket bypass returning `{"injectSteps": []}`, selective routing evaluates `/teamwork`, `/speckit`, and `/plan`.
   - Gatekeeper intent evaluation MUST execute immediately following slash command processing (line 136) and BEFORE the empty-resolver early return (lines 155–156). This eliminates the vulnerability where prompts without matching skills bypassed architectural auditing.
2. **Deterministic Artifact Verification (`verify_critic_artifact`)**:
   When intent matches specification drafting (`spec.md`, `plan.md`, `RFC`, `architecture`):
   ```python
   def verify_critic_artifact(workspace_dir: str, target_file: str) -> tuple[bool, str]:
       review_file = os.path.join(workspace_dir, "CRITIC_REVIEW.md")
       if not os.path.exists(review_file):
           return False, "REVIEW_MISSING"
       # Verify review is fresher than the target file
       if os.path.getmtime(review_file) < os.path.getmtime(target_file):
           return False, "REVIEW_STALE"
       # Read first line / 512 bytes for machine-verifiable metadata
       try:
           with open(review_file, "r", encoding="utf-8", errors="replace") as f:
               first_line = f.readline().strip()
           m = re.match(r"^<!--\s*OMNI_AUDIT_META:\s*({.*?})\s*-->$", first_line)
           if not m:
               return False, "METADATA_HEADER_MISSING"
           meta = json.loads(m.group(1))
           # Prevent cross-file collision: verify target_file matches
           rec_target = os.path.normcase(os.path.normpath(meta.get("target_file", "")))
           exp_target = os.path.normcase(os.path.normpath(target_file))
           if rec_target and rec_target != exp_target and os.path.basename(rec_target) != os.path.basename(exp_target):
               return False, f"TARGET_FILE_MISMATCH: Review generated for '{rec_target}', not '{exp_target}'"
           verdict = meta.get("verdict", "")
           if verdict not in ("APPROVED", "CONDITIONAL_PASS"):
               return False, f"REJECTED_BY_CRITIC: {meta.get('summary', verdict)}"
           return True, verdict
       except Exception as e:
           return False, f"VERIFICATION_ERROR: {str(e)}"
   ```
3. **Two-State Injection Formatting**:
   - **State 1 (Unaudited / Stale / Rejected)**:
     ```markdown
     [CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE]
     Status: UNAUDITED OR REJECTED SPECIFICATION DETECTED.
     MANDATORY: You MUST run `python "scripts/consult_critic.py" --file "<path>" --out "<path_to_review>"`
     and incorporate DeepSeek-V4.1-Flash red-teaming mitigations BEFORE dispatching tasks to worker fleet.
     Strictly PROHIBITED: Spawning duplicate Gemini subagents for internal self-review.
     ```
   - **State 2 (Audited & Approved)**:
     ```markdown
     [CRITICAL REVIEW FROM DEEPSEEK-V4.1-FLASH]
     Status: APPROVED BY SUPREME ARCHITECTURAL AUDITOR.
     Mitigation Contracts: Verified. Task dispatch to worker fleet is authorized.
     ```
4. **Telemetry Mapping to Existing `l1_staging_log` (Schema Invariant)**:
   - Preserves the exact 7-column schema: `(session_id, timestamp, user_input, workspace_hash, top_skill, tier_used, recalled_traces)`.
   - Gatekeeper activation is recorded by setting `top_skill = "gatekeeper:UNAUDITED"` or `"gatekeeper:APPROVED"` and appending the audit event metadata into the `recalled_traces` JSON array without altering SQLite table definitions.

---

## 10. Architectural Risk Matrix (RSK-001 to RSK-010)

| Risk ID | Vulnerability / Hazard Description | Severity | Likelihood | Concrete Mitigation Strategy | Verification / Invalidation Criteria |
|---|---|---|---|---|---|
| **RSK-001** | Synchronous REST invocation inside `hook_runner.py` causes catastrophic violation of Principle I (<25ms SLA). | CRITICAL | HIGH | **Two-Phase Enforcement Contract**: Decouple hook check (mtime artifact check $<0.3\text{ms}$) from execution (CLI / MCP Phase 5 $<30\text{s}$). | Benchmark test verifying `hook_runner.py` exits in $<25\text{ms}$ even when spec is unaudited. |
| **RSK-002** | Gemini ignores `rules/AGENTS.md` and spawns internal subagents (Reviewer, Challenger) for self-review echo chamber. | HIGH | HIGH | **Programmatic Gatekeeper Mandate**: `hook_runner.py` deterministically injects explicit prohibition, and SDD Phase 5 gate rejects progress without external `CRITIC_REVIEW.md`. | Simulated SDD run verifies that subagent self-review is rejected by council gate. |
| **RSK-003** | DeepSeek API key leakage via environment dump, exception stack traces, or persistent markdown logs. | CRITICAL | LOW | **Hardened Regex Sanitization**: Integrate DeepSeek key pattern `sk-[A-Za-z0-9_-]{20,}`, Bearer tokens, GitHub PATs, and unquoted/quoted `.env` assignments into `scripts/sanitizer.py`. Mask raw keys as `[REDACTED_*]` / `[REDACTED_SECRET]` from `stderr` and logs. | Automated unit test asserting key string is replaced with `[REDACTED_SECRET]` across all outputs. |
| **RSK-004** | API rate limiting (HTTP 429) or transient cloud outages (HTTP 502/503) stall agent coordination indefinitely. | HIGH | MEDIUM | **Jittered Exponential Backoff**: Implement $T_{\text{wait}} = \min(10.0, 1.0 \times 2^i) + \mathcal{U}(0.1, 0.5)$ bounded to 3 retries. Total wait $\le 7.9\text{s}$. | Mock HTTP 429 test verifying client retries 3 times with backoff and fails loudly on 4th attempt. |
| **RSK-005** | DeepSeek returns complacent praise or flattery (e.g., "Looks good!"), failing the red-teaming mandate. | HIGH | MEDIUM | **Anti-Sycophancy Prompt & Conditional Floor**: System prompt strictly forbids compliments and mandates $\ge 3$ critical vulnerabilities for flawed inputs. For sound designs (`APPROVED`), allows 0 critical flaws provided $\ge 3$ edge cases evaluated. | Automated test verifying responses with $<3$ flaws on flawed inputs trigger regeneration or `REJECTED` gate status. |
| **RSK-006** | Windows file path casing differences (`d:\` vs `D:\`) or backslashes cause false stale-artifact detections. | MEDIUM | HIGH | **Canonical Path Normalization & Traversal Defense**: Mandate `os.path.normcase(os.path.normpath(os.path.realpath(path)))` and `os.path.commonpath([allowed_root, canonical_path]) == allowed_root` across all file loaders and checkers. | Unit test verifying identical canonical hash and match on uppercase/lowercase path variants. |
| **RSK-007** | DeepSeek API model identifier drift (`deepseek-v4.1-flash` renamed or tier-restricted). | MEDIUM | MEDIUM | **Automatic Transparent Fallback on HTTP 400/404/422**: Client catches HTTP 400, 404, or 422 with model error and falls back to `deepseek-chat` while emitting transparency notice to `stderr`. | Mock 400/404 test verifying automatic second request dispatched with `model: deepseek-chat`. |
| **RSK-008** | Cloud-based critic suggests architectures violating physical local hardware constraints (MI50 VRAM or 16k context). | HIGH | HIGH | **Hardware-Grounded System Prompt**: Prompt explicitly enumerates MI50 constraints (VRAM $>3,741\text{ MB}$, context $\le 16\text{k}$, `-ub 2048`, Host CPU ONNX). | Verification audit asserting DeepSeek flags any proposal attempting GPU-based embeddings or 32k MI50 prompts. |
| **RSK-009** | Empty or truncated input file passed to critic, wasting tokens and emitting nonsensical reviews. | LOW | MEDIUM | **Pre-flight Payload Validation**: Client checks `len(content.strip()) == 0`. Immediately aborts with exit code 4: `[!] Nội dung kiểm tra trống (Empty input).`. | Unit test passing 0-byte file verifying instant exit with code 4 without invoking network request. |
| **RSK-010** | Infinite recursion: `consult_critic.py` invocation triggers `hook_runner.py` which re-invokes `consult_critic.py`. | HIGH | LOW | **Process Recursion Guard**: Client exports `OMNI_GATEKEEPER_ACTIVE=1` into subprocess environment. `hook_runner.py` short-circuits instantly if variable is detected. | Subprocess nesting test verifying child processes terminate cleanly with zero circular triggers. |

---

## 11. Project Structure & Code Layout

```
d:\Antigravity\Skill management\
├── specs\
│   ├── 001-omni-memory-v4\              # Reference SDD Bundle
│   └── 002-deepseek-v41-auditor\        # TARGET SDD BUNDLE (Milestone 1)
│       ├── spec.md                      # Functional specs, user stories P1-P3, entities
│       ├── plan.md                      # Technical architecture RFC, REST API, hook integration
│       ├── tasks.md                     # Spec Kit task breakdown, worker fleet allocation
│       ├── checklist.md                 # Security, latency, token efficiency gates
│       └── research.md                  # Comparative model analysis, parameter tuning
├── scripts\
│   ├── consult_critic.py                # Standalone stdlib client (deferred to M1 implementation)
│   ├── consult_argon.py                 # Deprecated legacy bridge (fail-closed, no fallback)
│   ├── hook_runner.py                   # PreInvocation hook (deferred to M3 implementation)
│   └── sanitizer.py                     # Credential redaction (deferred to M1 implementation)
├── rules\
│   └── AGENTS.md                        # Council Protocol Rule 6 (deferred to M3 implementation)
└── d:\Antigravity\DeepSeek Worker\
    └── deepseek_worker_mcp.py           # Virtual MCP Server: registered as "deepseek_worker_cloud",
                                         # imports scripts via sys.path.insert, serialized stdio locking
```

---

## 12. Phased Implementation Roadmap & Dependency Graph

```
Phase 1: Setup & Scaffolding (T001-T004)
   │
   ▼
Phase 2: Foundational Prerequisites (T005-T009)
   │ (BLOCKS all user stories)
   ├──────────────────────────────┬──────────────────────────────┐
   ▼                              ▼                              ▼
Phase 3 (Milestone M1):       Phase 4 (Milestone M2):       Phase 5 (Milestone M3):
User Story 1                  User Story 3                  User Story 2
Core CLI Client               Virtual MCP Server            Gatekeeper Hook & Rule 6
`consult_critic.py`           `deepseek_worker_mcp.py`      `hook_runner.py` & AGENTS.md
(T010 - T017)                 (T018 - T026)                 (T027 - T033)
   │                              │                              │
   └──────────────────────────────┼──────────────────────────────┘
                                  ▼
Phase 6 (Milestone M4): Verification, Hardening & E2E Integration (T034-T040)
```

### Sequencing Rules:
1. **Prerequisites Gate**: Phase 2 foundational security, sanitization, and backoff must pass tests before any user story coding.
2. **M1 MVP Priority**: User Story 1 (`consult_critic.py`) delivers the core CLI and must be verified first.
3. **Parallel Tooling & Gatekeeping**: Milestones M2 (MCP Server) and M3 (Hook Runner) can be implemented in parallel once M1 core engine is verified.
4. **Final Convergence**: Phase 6 integration tests, adversarial simulations, and Spec Kit `analyze` audits confirm 100% convergence across all artifacts.

---

## 13. Complexity Tracking & Design Rationales

1. **Why 100% Python Standard Library?**
   - Eliminates `pip install` friction across heterogeneous agent environments.
   - Eliminates version conflicts between `urllib3`, `requests`, and Google GenAI SDK dependencies.
   - Ensures 100% compliance with Windows AppLocker and WDAC policies.

2. **Why Two-Phase Gatekeeper Decoupling?**
   - Principle I of the Omni-Kernel Constitution strictly mandates $<0.30\text{ ms}$ reflex latency and $<25\text{ ms}$ pre-flight turnaround.
   - Executing a multi-second cloud API call synchronously inside `hook_runner.py` on every prompt turn would destroy system responsiveness.
   - Decoupling fast filesystem mtime verification (<0.30ms) from dedicated out-of-band audit execution (<30s) satisfies both constraints simultaneously.

3. **Why Full Jitter Backoff over Fixed Retries?**
   - Prevents synchronized re-submission waves (thundering herds) when DeepSeek experiences transient rate limits or cloud gateway restarts.
