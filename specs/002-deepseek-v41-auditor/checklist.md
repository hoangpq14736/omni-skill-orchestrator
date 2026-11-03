# Operational Quality Gates: DeepSeek-V4.1-Flash Strict Architecture Gatekeeper (Omni-Auditor v4.1)

**Purpose**: Reviewer-owned operational quality checklist verifying security, performance, dependency invariants, red-teaming rigor, and fault-tolerance gates.  
**Created**: 2026-11-03  
**Feature**: `specs/002-deepseek-v41-auditor/` (`spec.md`, `plan.md`, `tasks.md`)  
**Review Ownership**: Reviewer-owned requirements-quality review artifact. Mark an item `[x]` only when the reviewer confirms the criterion is satisfied with passing verification evidence.  
**Marker Semantics**: `[x]` indicates that the criterion has been reviewed and verified against authoritative requirements. It does not mean implementation code has been written prior to implementation phase approval.  

---

## Category 1: Security & Zero-Trust Invariants

- [ ] **CHK001** [Security] Does `consult_critic.py` load `DEEPSEEK_API_KEY` exclusively from environment variables without default hardcoded fallbacks?
  - **Criterion**: Zero hardcoded API keys, tokens, or plaintext secrets in any script, config, or test fixture. Missing key must abort immediately without network connection attempts.
  - **Pass Threshold**: 100% compliance. Codebase grep `sk-[A-Za-z0-9_-]{20,}` returns zero matches. Script fails closed and exits with code 2 (`EXIT_AUTH_QUOTA_ERROR`) when `DEEPSEEK_API_KEY` is unset, strictly prohibiting echo-chamber fallback.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py -k "test_api_key_from_env_only" -v
    ```

- [ ] **CHK002** [Zero-Trust Redaction] Does `scripts/sanitizer.py` scrub sensitive credentials (API keys, bearer tokens, private keys, GitHub PATs, .env assignments) before payload transmission?
  - **Criterion**: Outbound HTTP payloads and local telemetry logs must have all credentials scrubbed (DeepSeek keys `sk-[A-Za-z0-9_-]{20,}`, Anthropic `sk-ant-[A-Za-z0-9_-]{20,}`, Bearer tokens, GitHub classic/fine-grained PATs `github_pat_`, private keys, and `.env` assignments) replaced with `[REDACTED_*]` / `[REDACTED_SECRET]`.
  - **Pass Threshold**: Zero unmasked secrets in outbound request body or `l1_staging_log`. Verified against test fixtures containing deliberate dummy secrets.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_credential_leakage.py -v
    ```

- [ ] **CHK003** [Path Traversal Defense] Are `--file` and `--out` parameters strictly validated against path traversal attacks (`..` escaping allowed directory boundaries)?
  - **Criterion**: Input file paths must be resolved via `os.path.normcase(os.path.normpath(os.path.realpath(path)))` and verified with `os.path.commonpath([allowed_root, canonical_path]) == allowed_root` to ensure they do not attempt symlink/junction escapes, unauthorized file reads, or overwrite system binaries.
  - **Pass Threshold**: CLI immediately aborts with exit code 4 on path traversal attempts outside project boundaries.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py -k "test_path_traversal_prevention" -v
    ```

---

## Category 2: Latency & Operational Performance (<30s)

- [ ] **CHK004** [Turnaround Ceiling & 8.0s Inference Budget Floor] Does `consult_critic.py` enforce a strict 30-second turnaround ceiling and dynamic socket timeout with an 8.0s inference budget floor?
  - **Criterion**: Global execution timeout must not exceed 30.0s under standard network conditions for inputs up to 100k tokens. Socket timeout dynamically clamped: $T_{\text{socket}} = \min(30.0, \Delta t_{\text{remaining}})$. If remaining monotonic budget is less than the Minimum Viable Inference Window ($<8.0\text{s}$), retries abort immediately (Fail-Fast, exit code 3).
  - **Pass Threshold**: Execution wall-clock time $\le 30.0\text{s}$. Hanging or budget-exhausted connections terminate with exit code 3.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py -k "test_turnaround_and_socket_timeout" -v
    ```

- [ ] **CHK005** [Jittered Exponential Backoff] Does the retry engine implement full jitter exponential backoff with a hard ceiling of 3 retries?
  - **Criterion**: Retries on HTTP 429, 500, 502, 503 must adhere to $T_{\text{wait}} = \min(10.0, 1.0 \times 2^{\text{attempt}}) + \text{uniform}(0.1, 0.5)$. Must fail loud after attempt 3.
  - **Pass Threshold**: Exactly 3 retry attempts executed; backoff sleep durations strictly within jitter bounds; exits code 2 (for 429) or code 3 (for 5xx).
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py -k "test_jittered_backoff_retry_limit" -v
    ```

- [ ] **CHK006** [Sub-Millisecond Pre-Flight SLA] Does `scripts/hook_runner.py` maintain $<25\text{ms}$ subprocess turnaround and bypass filler prompts in $<1.0\text{ms}$?
  - **Criterion**: Conversational filler prompts (`"ok"`, `"thanks"`, `"tiếp tục"`) must exit in $<1.0\text{ms}$ with `{"injectSteps": []}`. Standard pre-flight hook turnaround must complete within $<25\text{ms}$ OS budget ($<0.30\text{ms}$ internal reflex).
  - **Pass Threshold**: P99 filler exit $<1.0\text{ms}$; P99 overall hook turnaround $<25.0\text{ms}$. Zero regression on existing L1 reflex SLA.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_gatekeeper_hook.py -k "test_filler_bypass_and_hook_latency" -v
    ```

---

## Category 3: Zero-Dependency Architecture & AppLocker Compliance

- [ ] **CHK007** [100% Python Standard Library] Is `scripts/consult_critic.py` implemented strictly using the Python 3.11+ standard library?
  - **Criterion**: Zero third-party dependencies (`requests`, `httpx`, `aiohttp`, `urllib3` prohibited). Uses only `urllib.request`, `json`, `re`, `argparse`, `os`, `sys`, `time`, `ssl`, `hashlib`, `random`.
  - **Pass Threshold**: Static AST import scan verifies 100% standard library compliance. No `pip install` required for runtime execution.
  - **Verification Command**:
    ```powershell
    python -c "import ast, sys; tree = ast.parse(open('scripts/consult_critic.py', encoding='utf-8').read()); imports = [n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import)] + [n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module]; stdlib = sys.stdlib_module_names; non_std = set(imports) - stdlib - {'sanitizer', 'memory_utils'}; assert not non_std, f'Disallowed imports: {non_std}'; print('PASSED: 100% Stdlib')"
    ```

- [ ] **CHK008** [Windows AppLocker & WDAC Compliance] Does the entire critic toolchain execute under standard user privileges without DLL injection or C-extension compilation?
  - **Criterion**: Scripts must execute cleanly under Windows PowerShell without requiring administrator privileges, custom binary drivers, or unsigned DLL loads.
  - **Pass Threshold**: Clean execution under standard non-elevated user token. Exits 0 on environment audit.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_environment.py -k "test_applocker_wdac_compliance" -v
    ```

---

## Category 4: Red-Teaming Quality & Anti-Echo-Chamber Rigor

- [ ] **CHK009** [Devil's Advocate Persona Invariant] Does the system prompt strictly forbid agreeable, polite, or superficial praise?
  - **Criterion**: System prompts for `--mode rfc` and `--mode code` must mandate hostile architectural scrutiny and explicitly forbid flattering responses ("Looks great!", "No issues found").
  - **Pass Threshold**: Persona template includes explicit negative constraints against affirmations; output formatting mandates vulnerability listings.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py -k "test_devils_advocate_persona_invariants" -v
    ```

- [ ] **CHK010** [Quantitative Defect Threshold & Conditional Gate] Does the critic output identify $\ge 3$ distinct vulnerabilities for flawed inputs, and enforce conditional schema validation?
  - **Criterion**: When evaluated against a deliberately flawed RFC (`flawed_rfc.md`), the critic must extract at least 3 actionable, structured vulnerability findings (`minItems: 3`) with proposed remediation contracts, issuing `REJECTED` or `CONDITIONAL_PASS` (exit code 1). When evaluating a sound architecture, verdict is `APPROVED` with 0 critical vulnerabilities provided at least 3 concrete defensive edge cases and mitigations are evaluated.
  - **Pass Threshold**: Verified $\ge 3$ distinct defect findings parsed from markdown output on flawed inputs; conditional schema passes for both flawed inputs ($\ge 3$ vulns) and approved specs (0 vulns, $\ge 3$ edge cases).
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_deepseek_auditor_e2e.py -k "test_quantitative_defect_threshold" -v
    ```

- [ ] **CHK011** [Strict Separation of Powers] Is the critic confirmed to be an independent external model family (DeepSeek-V4.1-Flash), eliminating Gemini internal self-review?
  - **Criterion**: Review calls must route to external endpoint `api.deepseek.com`. Internal Gemini subagents (e.g., Gemini Challenger, Gemini Reviewer) are barred from satisfying Council Gate review requirements.
  - **Pass Threshold**: Request headers target DeepSeek endpoint; response metadata records `model: deepseek-v4.1-flash`; echo-chamber self-review blocked.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_gatekeeper_hook.py -k "test_separation_of_powers_enforcement" -v
    ```

---

## Category 5: Fallback & Resiliency Handling

- [ ] **CHK012** [Graceful Offline Degradation] Does the system fail closed with clear, actionable diagnostics on network partitions or upstream outages?
  - **Criterion**: If `api.deepseek.com` is unreachable or DNS fails, the system must not crash silently or hang indefinitely. It must output actionable guidance to stderr and exit with code 3.
  - **Pass Threshold**: Structured error diagnostic printed to stderr; zero uncaught Python stack traces exposed to user; exit code 3.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py -k "test_offline_network_failure_diagnostics" -v
    ```

- [ ] **CHK013** [MCP Server Lifecycle & Resource Cleanup] Does `deepseek_worker_mcp.py` terminate cleanly without orphaned background processes or file handle leaks?
  - **Criterion**: When the parent process terminates or closes stdin, the MCP server must catch EOF, close open descriptors, and exit 0 within $<500\text{ms}$.
  - **Pass Threshold**: Process terminates cleanly upon EOF; zero lingering python processes detected in tasklist.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/test_deepseek_mcp.py -k "test_mcp_clean_shutdown_on_eof" -v
    ```

---

## Operational Verification Matrix

| Checklist Item | Target Subsystem | Owner Fleet | Automated Command Exists? | Gate Type | Pass Criteria |
|---|---|---|:---:|---|---|
| **CHK001** | `consult_critic.py` | `local_worker_mi50` | Yes | Pre-Merge Blocking | Zero hardcoded keys, exits code 2 on missing key |
| **CHK002** | `sanitizer.py` | `local_worker_mi50` | Yes | Pre-Merge Blocking | All secrets masked as `[REDACTED_SECRET]` |
| **CHK003** | `consult_critic.py` | `local_worker_mi50` | Yes | Pre-Merge Blocking | Traversal attempts outside workspace exit code 4 |
| **CHK004** | `consult_critic.py` | `groq_worker_cloud` | Yes | Performance Gate | Total roundtrip $\le 30.0\text{s}$, socket timeout 30s |
| **CHK005** | `consult_critic.py` | `groq_worker_cloud` | Yes | Reliability Gate | Full jitter backoff formula, max 3 retries |
| **CHK006** | `hook_runner.py` | `local_worker_mi50` | Yes | SLA / Latency Gate | Filler bypass $<1.0\text{ms}$, pre-flight $<25\text{ms}$ |
| **CHK007** | `consult_critic.py` | `local_worker_mi50` | Yes | Invariant / Architecture Gate | 100% Python stdlib, zero third-party packages |
| **CHK008** | Environment / Host | `local_worker_mi50` | Yes | Security / Host Gate | AppLocker safe, non-elevated user execution |
| **CHK009** | System Prompts | `groq_worker_cloud` | Yes | Quality Gate | Zero praise, hostile red-teaming persona enforced |
| **CHK010** | `consult_critic.py` | `groq_worker_cloud` | Yes | Quality Gate | $\ge 3$ critical defects identified on flawed inputs |
| **CHK011** | `hook_runner.py` / Rules | `local_worker_mi50` | Yes | Constitution Ring 0 Gate | Independent model family verified, echo chamber banned |
| **CHK012** | `consult_critic.py` | `local_worker_mi50` | Yes | Reliability Gate | Structured stderr diagnostic, exit code 3 on failure |
| **CHK013** | `deepseek_worker_mcp.py` | `local_worker_mi50` | Yes | Lifecycle Gate | Clean EOF exit in $<500\text{ms}$, zero orphan processes |

---

## Worker Fleet Implementation Mapping

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       DUAL WORKER FLEET DIRECTIVES                          │
├──────────────────────────────────────┬──────────────────────────────────────┤
│ local_worker_mi50 (AMD Instinct MI50)│ groq_worker_cloud (Groq LPU Cloud)   │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • In-place file edits (fast_edit)    │ • Rapid boilerplate generation       │
│ • Local Python stdlib modules        │ • Large Pytest test suite generation │
│ • SQLite WAL staging log operations  │ • Mock JSON-RPC server harnesses     │
│ • AST parsing and import validation  │ • Synthetic flawed RFC test fixtures │
│ • Regex compilation & credential scrub│ • Cross-artifact Spec Kit audits    │
│ • Local execution benchmarks         │ • Sub-second test stub creation      │
│ • Zero token consumption             │ • 300-800+ tok/s generation speed    │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

### Detailed Mapping Table for Implementation Phase
1. **Scaffolding & Fixtures (T001 - T004)**: Delegated to `groq_worker_cloud` for high-throughput creation of `conftest.py`, `flawed_rfc.md`, and test stubs.
2. **Security & Foundational stdlib (T005 - T009)**: Delegated to `local_worker_mi50` for exact in-place AST and stdlib editing in `scripts/sanitizer.py` and `scripts/consult_critic.py`.
3. **Core Client US1 Test Suite (T010)**: Delegated to `groq_worker_cloud` for generating comprehensive unit test cases covering all edge cases.
4. **Core Client US1 Implementation (T011 - T017)**: Delegated to `local_worker_mi50` for surgical coding using pure standard library.
5. **MCP Server US3 (T018 - T026)**: Scaffolding, registration, and protocol verification (`T018, T025 - T026`) delegated to `groq_worker_cloud`; stdio loop and mutex implementation (`T019 - T024`) delegated to `local_worker_mi50`.
6. **Gatekeeper Hook US2 (T027 - T033)**: Intent regex, decoupled mtime check, and Council enshrinement (`T027 - T033`) implemented by `local_worker_mi50` in `scripts/hook_runner.py` and `rules/AGENTS.md`.
7. **End-to-End Validation & Convergence (T034 - T040)**: Integration tests and Spec Kit convergence (`T034 - T035, T038 - T040`) delegated to `groq_worker_cloud`; clean-room adversarial and fail-closed auth gate verification (`T036 - T037`) run locally by `local_worker_mi50`.
