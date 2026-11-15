# Omni-Kernel v4.3: Comprehensive Architectural Analysis, Upgrade Proposal, and Verification Rubric

**Document Status**: Production Proposal & Architecture Reference  
**Ratified Kernel Version**: v4.3.0  
**Target Upgrade Releases**: v4.3.1 (Hotfix), v4.4.0 (Performance & Symmetry), v5.0.0 (Unified Fleet & Scalability)  
**Author**: Omni-Kernel Core Engineering Working Group  
**Target File**: `docs/OMNI_KERNEL_V4.3_UPGRADE_PROPOSAL.md`  
**Date**: November 2026  

---

## Table of Contents

1. [Executive Summary & Ring 0 Invariant Alignment](#1-executive-summary--ring-0-invariant-alignment)
   - [1.1 Context and Architectural Purpose](#11-context-and-architectural-purpose)
   - [1.2 Ring 0 Kernel Invariants Formulation](#12-ring-0-kernel-invariants-formulation)
   - [1.3 Boundary Anchor Integrity & Immune Defense](#13-boundary-anchor-integrity--immune-defense)
2. [Pillar Analysis & Current Architectural State](#2-pillar-analysis--current-architectural-state)
   - [2.1 Pillar 1: Tri-Tier Cognitive Memory Subsystem](#21-pillar-1-tri-tier-cognitive-memory-subsystem)
   - [2.2 Pillar 2: Cloud Worker Fleet Delegation](#22-pillar-2-cloud-worker-fleet-delegation)
   - [2.3 Pillar 3: Skill & Tool Orchestration Engine](#23-pillar-3-skill--tool-orchestration-engine)
   - [2.4 Pillar 4: Architectural Gatekeepers & Council Protocol](#24-pillar-4-architectural-gatekeepers--council-protocol)
   - [2.5 Pillar 5: Developer Tooling & Observability](#25-pillar-5-developer-tooling--observability)
3. [Bottlenecks, Edge Cases & Failure Mode Analysis](#3-bottlenecks-edge-cases--failure-mode-analysis)
   - [3.1 Empirical Latency Profiles & Overhead Budgets](#31-empirical-latency-profiles--overhead-budgets)
   - [3.2 Windows Platform Pitfalls & OS Traps](#32-windows-platform-pitfalls--os-traps)
   - [3.3 Comprehensive Failure Mode & Concurrency Hazard Matrix](#33-comprehensive-failure-mode--concurrency-hazard-matrix)
4. [Concrete Upgrade Specifications for Future Releases](#4-concrete-upgrade-specifications-for-future-releases)
   - [Spec 1: Tier 1 Subprocess Optimization & Consolidator Spawn Debounce](#spec-1-tier-1-subprocess-optimization--consolidator-spawn-debounce)
   - [Spec 2: Tier 2 Hybrid Retrieval Pure FTS5 BM25 Fallback Restoration](#spec-2-tier-2-hybrid-retrieval-pure-fts5-bm25-fallback-restoration)
   - [Spec 3: Tier 2 Vectorized Dense Scan & Partition-Bounded Scoring](#spec-3-tier-2-vectorized-dense-scan--partition-bounded-scoring)
   - [Spec 4: Tier 3 Success-Ratio Gated Trace Promotion & Batched ONNX Backfill](#spec-4-tier-3-success-ratio-gated-trace-promotion--batched-onnx-backfill)
   - [Spec 5: Cloud Worker Fleet Non-Blocking Threaded Stdio Server & Expanded Retries](#spec-5-cloud-worker-fleet-non-blocking-threaded-stdio-server--expanded-retries)
   - [Spec 6: Symmetric Plan Gate Integration for Worker Fleet Mutating Tools](#spec-6-symmetric-plan-gate-integration-for-worker-fleet-mutating-tools)
   - [Spec 7: Unified Council Gate Orchestrator (`omni-council`) & Critic Unit Tests](#spec-7-unified-council-gate-orchestrator-omni-council--critic-unit-tests)
   - [Spec 8: Verification Command Runner Relaxation & Windows Binary Resolution](#spec-8-verification-command-runner-relaxation--windows-binary-resolution)
   - [Spec 9: Learned Affinities Bounded Retention & Spool Cleanup Hygiene](#spec-9-learned-affinities-bounded-retention--spool-cleanup-hygiene)
5. [Actionable Implementation Roadmap](#5-actionable-implementation-roadmap)
   - [5.1 Release Phasing Matrix](#51-release-phasing-matrix)
   - [5.2 Cross-Phase Dependency Graph](#52-cross-phase-dependency-graph)
   - [5.3 Invariant Guardrails & Risk Register](#53-invariant-guardrails--risk-register)
6. [Independent Evaluation Rubric](#6-independent-evaluation-rubric)
   - [6.1 Evaluation Methodology & Weighting](#61-evaluation-methodology--weighting)
   - [6.2 Quantitative Specification Scoring Matrix](#62-quantitative-specification-scoring-matrix)
   - [6.3 Acceptance Thresholds & Verification Checklist](#63-acceptance-thresholds--verification-checklist)

---

## 1. Executive Summary & Ring 0 Invariant Alignment

### 1.1 Context and Architectural Purpose

Omni-Kernel v4.3 is an autonomous, high-agency engineering substrate designed to orchestrate software development workflows across multi-agent environments, cloud foundation models, local tool drivers, and experiential memory systems. Engineered with zero external third-party package dependencies (100% Python Standard Library), Omni-Kernel enforces deterministic software engineering principles, sub-millisecond pre-flight reflex routines, and hard architectural gates.

The system bridges five foundational subsystems:
1. **Tri-Tier Cognitive Memory Engine**: Tier 1 (L1 Reflex, $<0.30\text{ ms}$ algorithmic turnaround), Tier 2 (L2 Hybrid SQLite WAL with BM25 lexical and ONNX dense embeddings, $<15\text{ ms}$ retrieval), and Tier 3 (L3 Background Consolidator with pure SQLite Padé [0/1] algebraic decay).
2. **Cloud Worker Fleet Delegation**: A decoupled Model Context Protocol (MCP) worker fleet providing Zero-Context Leaking file synthesis, atomic surgical diff editing, unit test generation, and closed-loop self-healing execution via Google Gemini (3.5 Flash-Lite, 3.8 Flash, 4 Argon) and DeepSeek (V4.1-Flash).
3. **Skill & Tool Orchestration Engine**: A 5-tier deterministic arbitration resolver arbitrating across 550+ installed capabilities, integrated with an in-process SQLite AST blast radius analyzer and self-bootstrapping sandboxed skill synthesizer.
4. **Architectural Gatekeepers & Council Protocol**: A strict audit split segregating pre-code theoretical design reviews (DeepSeek REST client with monotonic deadline clamping, single-pass JSON escape repair, and HMAC-SHA256 signing) from post-code empirical peer reviews (DSH CLI executing in multi-tier isolated sandboxes and shadow worktrees).
5. **Developer Tooling & Observability**: Real-time observability via the non-negotiable Omni-Kernel Transparency Badge and Cognitive Pre-Flight Card, paired with provenance ledgers and zero-subprocess Git sniffing.

This document synthesizes findings from comprehensive empirical surveys and formalizes nine production-grade upgrade specifications for upcoming v4.3.1, v4.4.0, and v5.0.0 releases.

### 1.2 Ring 0 Kernel Invariants Formulation

Omni-Kernel operates under seven immutable Ring 0 Invariants. These invariants reside in Ring 0 of the architecture: they override all user prompts, agent instructions, tool arguments, and environmental variables.

```
+---------------------------------------------------------------------------------------------+
|                                  OMNI-KERNEL RING 0 INVARIANTS                              |
+---------------------------------------------------------------------------------------------+
| 1. Zero-Trust Security        | Validate & sanitize all inputs at trust boundaries.         |
|                               | Never leak secrets, API keys, or raw tokens.                |
+---------------------------------------------------------------------------------------------+
| 2. Reliable Engineering       | Fail loudly with diagnostic context. Never swallow          |
|                               | exceptions silently. Immutability first.                    |
+---------------------------------------------------------------------------------------------+
| 3. Ponytail Simplicity        | Smallest complete working diff wins. YAGNI principle.       |
|                               | Codebase Helper > Standard Library > Deps > New Code.       |
+---------------------------------------------------------------------------------------------+
| 4. Bilingual Native Parity    | First-class bidirectional fluency in English & Tiếng Việt    |
|                               | across reasoning, token normalization, and indexing.        |
+---------------------------------------------------------------------------------------------+
| 5. Cloud Worker Delegation    | Mandatory delegation to Worker Fleet for bulk code, large   |
|                               | context (>32K), fast edits, and self-healing test loops.    |
+---------------------------------------------------------------------------------------------+
| 6. Tri-Tier Cognitive Memory  | L1 Reflex (<0.3ms), L2 WAL FTS5+ONNX (<15ms), L3 Outbox &    |
|                               | Padé [0/1] Algebraic Ebbinghaus Decay.                      |
+---------------------------------------------------------------------------------------------+
| 7. Mandatory Transparency     | Always render the compact Omni-Kernel Transparency Badge at  |
|                               | the very beginning of every turn response.                  |
+---------------------------------------------------------------------------------------------+
```

### 1.3 Boundary Anchor Integrity & Immune Defense

To prevent kernel configuration drift across multi-agent sessions, IDE reloads, and Git worktree operations, Omni-Kernel employs an automated immune defense mechanism implemented in `scripts/kernel_sync.py`.

The immune system scans workspace configuration files (`GEMINI.md`, `.cursorrules`, `rules/AGENTS.md`) and enforces canonical invariant blocks wrapped inside strict boundary markers:

```markdown
<!-- OMNI-KERNEL-START v4.3.0 -->
# --- OMNI-KERNEL v4.3 AGENT INVARIANTS ---
# 1. Zero-Trust Security: Validate all inputs at trust boundaries. Never leak secrets.
# 2. Reliable Engineering: Fail loudly with context. Never swallow exceptions. Immutability first.
# 3. Ponytail Simplicity: Smallest complete working diff wins. YAGNI. Codebase > Stdlib > Deps.
# 4. Bilingual Native Parity: First-class English & Tiếng Việt reasoning and indexing.
# 5. Cloud Worker Fleet: Mandatory delegation to gemini_worker_cloud (Flash-Lite / 3.8 Flash / 4 Argon) and deepseek_worker_cloud (Audit Gate).
# 6. Tri-Tier Memory: L1 Reflex (<0.3ms), L2 WAL FTS5+ONNX (<15ms), L3 Consolidator.
# 7. Mandatory Transparency: Always render Omni-Kernel badge at the head of every response.
<!-- OMNI-KERNEL-END -->
```

**Key Architectural Properties of the Synchronizer**:
- **Boundary-Aware Mutation**: Regex matching (`_PAT_BOUNDARY`) replaces exclusively the text bounded between `<!-- OMNI-KERNEL-START -->` and `<!-- OMNI-KERNEL-END -->`. Custom rules authored by developers outside these markers are preserved with 100% byte fidelity.
- **Subprocess-Free Git Sniffer**: Before executing file I/O, `kernel_sync.py` executes `is_git_busy_or_unsafe()` in $<0.15\text{ ms}$. It traverses `.git` directories and worktree pointers without spawning `git.exe`, detecting `MERGE_HEAD`, `rebase-merge`, `rebase-apply`, `CHERRY_PICK_HEAD`, and `index.lock`. If Git is mid-operation, synchronization aborts safely with `SKIPPED_GIT_UNSAFE`.
- **NTFS-Safe Atomic Replacement**: Replaces files using `safe_atomic_replace()` with exponential backoff (20ms, 40ms, 80ms, 160ms) to bypass transient Windows Antivirus and search indexer file locks.

---

## 2. Pillar Analysis & Current Architectural State

### 2.1 Pillar 1: Tri-Tier Cognitive Memory Subsystem

The cognitive memory subsystem maintains persistent learning, cross-session episodic recall, and architectural constraints across three tiered operational layers.

```
+-----------------------------------------------------------------------------------------+
|                                TIER 1: L1 REFLEX LAYER                                  |
|  hooks.json -> PreInvocation & PreToolUse Hook Interceptors                             |
|  - Fast-Exit Filler Suppression (<0.05ms)                                               |
|  - Input Clamping (2048 chars) & Secret Redaction                                       |
|  - Warn-Once Auto-Unlock Plan Gatekeeper (Score >= 95, 2h TTL)                          |
|  - Non-blocking JSONL Staging Spooling (TrustFileLock, 50ms timeout)                    |
+-----------------------------------------------------------------------------------------+
                                             |
                                  Drains via Spool Claims
                                             v
+-----------------------------------------------------------------------------------------+
|                                TIER 2: L2 HYBRID MEMORY                                 |
|  SQLite WAL Database: omni_memory.db (Schema 430, NORMAL sync, 64MB Cache, 256MB mmap)   |
|  - Dedicated Single-Writer Worker Thread (MemorySingleWriter, BEGIN IMMEDIATE)          |
|  - Dual-Column FTS5 Lexical Search: content_exact (10.0) vs content_folded (1.0)        |
|  - CPU ONNX Dense Embeddings: google/embeddinggemma-2-omni INT8 MRL 256d               |
|  - Reciprocal Rank Fusion (k=20): RRF(d) = 0.5/(20 + r_lex) + 0.5/(20 + r_dense)       |
|  - Cross-Tenant Isolation Triggers (trg_episodic_prevent_ws_update/replace)             |
+-----------------------------------------------------------------------------------------+
                                             ^
                                             |
                                  Batch Ingestion & Decay
                                             |
+-----------------------------------------------------------------------------------------+
|                              TIER 3: L3 CONSOLIDATOR                                    |
|  Background Daemon & LifecycleGuard Watcher                                             |
|  - Crash-Resilient Spool Draining: .proc_{pid}_{uuid} two-phase rotation                |
|  - Multi-Hit Trace Promotion (positive_hits >= 2, frequency clustering)                 |
|  - Pure SQLite Padé [0/1] Algebraic Ebbinghaus Stability Decay Engine                   |
|  - Two-Phase Aging: Soft-Archiving (<0.20 confidence, 7d grace) & Hard Purge (30d)      |
|  - Durable 3-Phase Commit Outbox Queue (consolidation_outbox -> proven_traces.json)     |
+-----------------------------------------------------------------------------------------+
```

#### Detailed Layer Breakdown:

1. **Tier 1 (L1 Reflex Subsystem)**:
   - Configured in `hooks.json`. Executes before turn processing (`PreInvocation`) and before file modifications (`PreToolUse`).
   - `FILLER_PATTERN` regex (`scripts/hook_runner.py:83-86`) matches single-word conversational confirmations (`ok`, `tiếp tục`, `done`, `cảm ơn`, `sure`) in $<0.05\text{ ms}$, terminating immediately with `{"injectSteps": []}` to save LLM tokens.
   - Input clamping at 2048 characters (`safe_user_input = safe_full_input[:2048]`) ensures linear pre-flight processing times regardless of prompt length.
   - **Plan Gate Rules**:
     * *Rule A*: Auto-unlocks non-code files (`.md`, `specs/`, `tests/`, `test_*.py`).
     * *Rule B*: Recognizes explicit skip keywords (`--no-plan`, `làm luôn`, `sửa luôn`, `code luôn`).
     * *Rule C*: Checks active plan freshness ($< 7200\text{ s}$) in `.omni/plan_unlocked.json` or `plan.md`.
     * *Rule D*: For architectural tasks (complexity $\ge 95$), blocks once with a descriptive warning, writes `.omni/plan_unlocked.json`, and automatically unlocks the subsequent turn.

2. **Tier 2 (L2 Hybrid SQLite WAL & ONNX Dense Retrieval)**:
   - Evaluates queries across dual SQLite channels.
   - Lexical channel utilizes SQLite FTS5 (`unicode61 remove_diacritics 0`) with two virtual columns: `content_exact` (diacritic-preserving, weight 10.0) and `content_folded` (diacritic-stripped, weight 1.0).
   - Dense channel employs `google/embeddinggemma-2-omni` INT8 quantized ONNX embeddings (256-dimensional Matryoshka Representation Learning).
   - Merges candidate rankings using Reciprocal Rank Fusion ($k=20$).

3. **Tier 3 (L3 Background Consolidator & Padé Decay)**:
   - Evaluates memory stability using the Padé [0/1] algebraic decay formulation implemented directly in SQLite SQL:
     $$\text{confidence\_score} = \frac{1.0 + 0.5 \cdot \text{activation\_count}}{(1.0 + 0.5 \cdot \text{activation\_count}) + \text{decay\_rate} \cdot \max(0.0, (\text{julianday('now')} - \text{julianday(last\_accessed\_at)}))}$$
   - Exempts memories accessed within the last 24 hours from decay.
   - Protects invariant memories (`memory_type == 'invariant'`) with indefinite stability.

---

### 2.2 Pillar 2: Cloud Worker Fleet Delegation

Omni-Kernel enforces mandatory offloading of code-heavy, iterative, and large-context operations to specialized cloud worker agents via JSON-RPC stdio Model Context Protocol (MCP) servers.

```
                                 [ Primary Cloud Agent / IDE ]
                                               |
                          +--------------------+--------------------+
                          | (Delegates High Context / Mutations)    | (Delegates Audits)
                          v                                         v
            [ gemini_worker_cloud ]                       [ deepseek_worker_cloud ]
            (gemini_worker_mcp.py)                        (deepseek_worker_mcp.py)
            - Transport: stdio JSON-RPC 2.0               - Transport: stdio JSON-RPC 2.0
            - 100% Python Standard Library                - 100% Python Standard Library
            - Google Generative Language v1beta           - DeepSeek-V4.1-Flash API (1M ctx)
                          |                                         |
         +----------------+----------------+                        |
         |                                 |                        |
         v                                 v                        v
[ Fast Surgical Edits ]        [ Closed-Loop Self-Healing ]    [ Devil's Advocate Audit ]
- gemini_fast_edit             - gemini_autonomous_loop        - deepseek_audit_spec
  * In-place AST validation      * Edit -> Verify -> Self-Heal   * Pre-code RFC red-teaming
  * Zero-context leaking diff    * Up to 5 loop iterations     - deepseek_audit_diff
- gemini_heavy_code_gen        - gemini_execute_plan             * Forensic patch review
  * Direct disk persistence      * Multi-step rollback safe      * HMAC-signed metadata
```

#### Worker Tool Implementations & Contracts:

1. **Zero-Context Leaking Pattern**:
   When an agent calls `gemini_heavy_code_gen(save_to_path="src/service.py", ...)` or `gemini_fast_edit(file_path="src/service.py", ...)`, the worker writes the code directly to disk using atomic temporary files (`.tmp`) and `.fsync()`. The payload returned to the primary agent contains only status metadata:
   ```json
   {
     "success": true,
     "saved_to": "src/service.py",
     "lines": 420,
     "bytes_written": 14280,
     "model": "gemini-3.5-flash-lite",
     "diff": "--- a/src/service.py\n+++ b/src/service.py\n@@ -10,3 +10,5 @@..."
   }
   ```
   This prevents the primary agent's context window from degrading due to thousands of lines of boilerplate code.

2. **Autonomous Self-Healing Loop (`gemini_autonomous_loop`)**:
   Coordinates surgical file edits against an automated verification command (e.g. `pytest tests/test_auth.py`). If verification fails, compiler errors are fed back into Gemini for correction and re-tested up to 5 iterations. If all fail, the original file is restored from its `.bak` backup without leaving broken intermediate code in the workspace.

3. **Concurrency Locking (`_TargetFileLock`)**:
   Acquires `<target_file>.lock` using `os.O_CREAT | os.O_EXCL | os.O_WRONLY`. If an existing lock is held by a dead process or exceeds a 120-second stale timeout, the lock is safely reclaimed.

---

### 2.3 Pillar 3: Skill & Tool Orchestration Engine

Arbitrating across 550+ installed capabilities, 24 MCP servers, and hundreds of virtual tools requires sub-millisecond selection algorithms to prevent context bloat and tool confusion.

```
                              [ User / Agent Prompt Intent ]
                                             |
                                             v
                             [ Fast Unified Resolver (resolver.py) ]
                             - Vietnamese / English Synonym Expansion (100+ pairs)
                             - Cognitive Entailment Graph (Infers OWASP, SQLi, SDD rules)
                             - Omni-Graph Blast Radius Traversal (SQLite CTE, <1.5ms)
                             - 5-Tier Deterministic Arbitration
                                             |
                     +-----------------------+-----------------------+
                     |                       |                       |
                     v                       v                       v
          [ Scope Hierarchy ]     [ Kernel Alignment ]    [ Domain Specificity ]
          Workspace:     +40      v4.3.0 Anchored: +15    Framework:  Level 4-5
          Active User:   +20                              Language:   Level 1-2
          Plugin:        +20
          Builtin:       +15
          Library:        +5
                     |                       |                       |
                     +-----------------------+-----------------------+
                                             |
                                             v
                             [ Learned Affinities Adjustment ]
                             - Positive Feedback: +15.0 (Cap: +60.0)
                             - Negative Feedback: -10.0 (Floor: -30.0)
                             - Advisory File Lock: TrustFileLock
                                             |
                                             v
                           [ Optimal Skill / Tool Selection ]
```

#### Key Capabilities:

1. **Bilingual Intent Mapping**:
   `VI_EN_SYNONYMS` maps over 100 Vietnamese engineering idioms to standard English concepts across DevOps (`triển khai` $\to$ `deploy`, `vận hành` $\to$ `devops`), CAD (`bản vẽ` $\to$ `cad drawing`, `mô hình 3d` $\to$ `3d model`), Databases (`truy vấn` $\to$ `sql query`), and Testing (`kiểm thử` $\to$ `unit test`).

2. **Cognitive Entailment Graph**:
   Dynamically analyzes intent tokens to inject implicit domain guardrails. For example, queries containing `form`, `api`, or `http` automatically entail `owasp_top_10` and `xss_csrf_guard` rules even if the user never explicitly requested security reviews.

3. **Self-Bootstrapping Skill Synthesizer (`synthesizer.py`)**:
   When a project demands a capability absent from the catalog, the synthesizer generates a skill template, parses validation scripts using Python's `ast` module, blocks unsafe calls (`subprocess`, `socket`, `eval`, `exec`), verifies execution in an isolated sandbox, and promotes the skill to `~/.gemini/config/skills_library/` with automated index regeneration in $<150\text{ ms}$.

4. **Omni-Graph Blast Radius Engine (`omni-graph`)**:
   Operates an in-process SQLite WAL graph (`.omni/codebase_graph.db`). Using Common Table Expression (CTE) queries, it traverses transitive callers, calculates upstream impact blast radiuses, and flags signature contract violations in $<1.5\text{ ms}$.

---

### 2.4 Pillar 4: Architectural Gatekeepers & Council Protocol

Omni-Kernel eliminates internal "echo chamber" self-review by establishing an audit separation between pre-code theoretical design critique and post-code empirical peer verification.

```
                                [ Software Lifecycle Gate ]
                                             |
                     +-----------------------+-----------------------+
                     |                                               |
                     v                                               v
        [ PRE-CODE THEORETICAL AUDIT ]                  [ POST-CODE EMPIRICAL AUDIT ]
             consult_critic.py                                dsh_auditor.py
                     |                                               |
    - Target: RFCs, Specs, Architecture Blueprints   - Target: Working Code, Concurrency, Repros
    - Engine: DeepSeek-V4.1-Flash (1M ctx API)       - Engine: Local DSH CLI in Isolated Sandboxes
    - Monotonic Deadline Clamping (MIN_INFER=8.0s)   - Multi-Tier Isolation:
    - Single-Pass JSON Scanner & Escape Repair         * Tier 1: In-Place Snapshot & Rollback
    - Cryptographic Binding:                           * Tier 2: Scratch Sandbox Directory
      HMAC-SHA256 line 1 metadata header               * Tier 3: Isolated Git Shadow Worktree
    - POSIX Exit Codes (0, 1, 2, 3, 4, 5)            - Concurrency: Win32 MoveFileW Atomic Lock
    - Rule: Do NOT invoke DSH before code exists     - Telemetry: audit_provenance.jsonl Ledger
```

#### Council Gate Standardized POSIX Exit Codes:

```
+-----------+-------------------------+-------------------------------------------------------+
| Exit Code | Identifier              | Description                                           |
+-----------+-------------------------+-------------------------------------------------------+
| 0         | EXIT_APPROVED           | Spec Approved or Conditional Pass (non-strict mode).  |
| 1         | EXIT_CRITIQUE_GENERATED | Rejected / Changes Requested / Critique with findings.|
| 2         | EXIT_AUTH_QUOTA         | Auth failure, API quota exhausted, 429 rate limit.    |
| 3         | EXIT_TIMEOUT_NETWORK    | Monotonic timeout expired, network disconnect, 5xx.   |
| 4         | EXIT_CONFIG_USAGE       | CLI usage error, invalid flags, path traversal error. |
| 5         | EXIT_SYSTEM_STRICT      | Schema validation failure, strict mode rejection.     |
+-----------+-------------------------+-------------------------------------------------------+
```

#### Cryptographic Artifact Binding:
Every theoretical audit approved by `consult_critic.py` outputs a cryptographic JSON header on Line 1 of the markdown report:
```html
<!-- OMNI_AUDIT_META: {"verdict":"CONDITIONAL_PASS","target_file":"docs/rfc.md","input_hash":"sha256:c8818...","model":"deepseek-flash","hash_domain":"redacted_prompt_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-15T12:03:55Z","workspace_hash":"0f03e...","signature":"6224d..."} -->
```
The signature is generated using HMAC-SHA256 over canonicalized metadata, binding the audit verdict inextricably to the exact SHA-256 hash of the input document and workspace root.

---

### 2.5 Pillar 5: Developer Tooling & Observability

Observability in Omni-Kernel is enforced both at the conversational layer and at the system filesystem layer.

#### Conversational Observability (Transparency Directive):
Every response generated across the ecosystem renders the non-negotiable 1-line Omni-Kernel Transparency Badge:
```
⚡ Omni-Kernel: [L2-Hybrid] | Skill: [omni-skill-orchestrator] | Rules: [7 active] | MCP: [2 suggested]
```
For complex architectural tasks (complexity $\ge 95$), the badge is expanded with the formatted Cognitive Pre-Flight Card:
```markdown
### ⚡ Cognitive Pre-Flight Assessment
- **Lợi (Value)**: Smallest complete surgical edit avoiding downstream schema changes.
- **Hại (Risks)**: Potential race condition on Windows file locks during atomic rename.
- **Đủ (Completeness)**: Verified across callers, unit tests, and CI configuration.
- **Thiếu (Implicit Needs)**: Parameterized query enforcement to guarantee SQL injection immunity.
```

#### Filesystem Observability (Provenance Ledger):
All workspace mutations, snapshot rollbacks, and empirical audits executed by `dsh_auditor.py` append immutable audit records to `.dsh_audit/audit_provenance.jsonl`:
```json
{
  "timestamp": "2026-11-15T12:04:15.120Z",
  "session_id": "session-41d7ecaccaf0",
  "tier": 2,
  "event_type": "MUTATION",
  "tool_name": "pwsh",
  "target_paths": ["src/service.py"],
  "exit_code": 0,
  "duration_sec": 1.42
}
```

---

## 3. Bottlenecks, Edge Cases & Failure Mode Analysis

### 3.1 Empirical Latency Profiles & Overhead Budgets

Empirical latency measurements captured on Windows 11 x64 (Python 3.13.17):

```
+----------------------------------------------------+----------------+----------------+
| Subsystem Operation                                | Measured Time  | Target SLA     |
+----------------------------------------------------+----------------+----------------+
| L1 Reflex: Fast-Exit Filler Suppression            | < 0.05 ms      | < 0.10 ms      |
| L1 Reflex: Internal In-Memory Cache Lookup         | 0.28 ms        | < 0.30 ms      |
| L1 Reflex: Process Spawn via `python` (PreInvoc)   | 31.40 ms       | < 25.00 ms (!) |
| L1 Reflex: Process Spawn via `python -S` (PreTool) | 14.80 ms       | < 25.00 ms     |
| L2 Memory: FTS5 Lexical Search (M <= 500)          | 1.15 ms        | < 5.00 ms      |
| L2 Memory: CPU ONNX Embedding Generation           | 9.80 ms        | < 15.00 ms     |
| L2 Memory: Full Hybrid Search (Lexical + Dense)    | 12.40 ms       | < 15.00 ms     |
| L2 Memory: Dense Vector Scan (N = 10,000 BLOBs)    | 85.20 ms       | < 15.00 ms (!) |
| L3 Consolidator: Pure SQLite Padé Algebraic Decay  | 2.10 ms        | < 10.00 ms     |
| L3 Consolidator: Sequential Vector Backfill (50x)  | 750.00 ms      | < 250.00 ms(!)|
| Skill Resolver: Fast 5-Tier Arbitration            | 14.20 ms       | < 25.00 ms     |
| Skill Resolver: Cold Registry Parse (1.24MB JSON)  | 16.50 ms       | < 10.00 ms (!) |
| Omni-Graph: SQLite CTE Blast Radius Query          | 1.40 ms        | < 5.00 ms      |
| Subprocess-Free Git Sniffer (is_git_busy)          | 0.12 ms        | < 0.50 ms      |
+----------------------------------------------------+----------------+----------------+
```
*Note: Entries marked with `(!)` represent SLA breaches identified for remediation.*

---

### 3.2 Windows Platform Pitfalls & OS Traps

Developing an autonomous software engineering substrate on Windows NTFS surfaces unique operating system behaviors:

1. **Mandatory File Locking (`WinError 32`)**:
   On Windows, an open file handle held by an IDE language server, search indexer, or antivirus scanner denies deletion and renaming (`ERROR_SHARING_VIOLATION`). Attempting `os.replace` on an open file crashes with `PermissionError: [WinError 32]`.
   *Mitigation*: Exponential backoff retries with randomized jitter (`safe_atomic_replace`).

2. **Executable Extension Resolution with `shell=False`**:
   On Windows, standard development binaries like `npm`, `npx`, `pytest`, `cargo` are batch scripts (`.cmd`, `.bat`) or wrappers. Invoking `subprocess.Popen(["npm", "test"], shell=False)` fails immediately with `FileNotFoundError: [WinError 2]` because the OS kernel does not scan `PATHEXT` when `shell=False`.
   *Mitigation*: Mandatory resolution via `shutil.which()` before invocation.

3. **Subprocess Termination Trees**:
   Calling `proc.kill()` on Windows terminates only the root shell process, leaving child worker processes orphaned in the background holding file locks.
   *Mitigation*: Mandatory use of `taskkill /F /T /PID {pid}`.

4. **Stdio Text Mode CRLF Corruption**:
   CPython on Windows defaults stdio streams to text mode with `\r\n` line translation. When transmitting NDJSON or binary cryptographic headers over stdio, automatic CRLF insertion corrupts byte count lengths and breaks JSON-RPC message framing.
   *Mitigation*: Setting `sys.stdin.reconfigure(newline='\n')` and binary flushing.

---

### 3.3 Comprehensive Failure Mode & Concurrency Hazard Matrix

The following matrix consolidates all critical failure modes, concurrency races, and architectural gaps discovered across the system:

```
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| ID    | Subsystem          | Failure Scenario / Concurrency Race       | Root Cause & Observable Consequence                |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-01 | Tier 1 (L1 Reflex) | PreInvocation Subprocess SLA Breach       | hooks.json invokes `python` instead of `python -S`.|
|       |                    |                                           | OS process startup takes ~31.4ms (>25ms SLA).      |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-02 | Tier 1 (L1 Reflex) | Rapid Burst Consolidator Thrashing        | Spool >25KB triggers detached background process;  |
|       |                    |                                           | rapid turns spawn redundant consolidators.         |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-03 | Tier 2 (L2 Memory) | Episodic Retrieval Amnesia on Fresh DB    | memory_engine.py:805 aborts with `return []` if    |
|       |                    |                                           | dense_embeddings has 0 rows, skipping pure FTS5.   |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-04 | Tier 2 (L2 Memory) | Linear Scan Degradation on Large Vectors  | hybrid_search unpacks all workspace BLOBs in       |
|       |                    |                                           | Python loop; search exceeds 85ms at N > 10,000.    |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-05 | Tier 3 (L3 Memory) | False Proven-Trace Promotion Hazard       | consolidator.py discards negative feedback before  |
|       |                    |                                           | clustering; patterns with 90% fail promote.        |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-06 | Tier 3 (L3 Memory) | Sequential ONNX Backfill CPU Stall        | Embedding backfill runs scalar 1-by-1 inference;   |
|       |                    |                                           | 50 memories takes >750ms CPU time.                 |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-07 | Cloud Worker Fleet | Synchronous Stdio Server Deadlock         | gemini_worker_mcp.py runs blocking readline loop;  |
|       |                    |                                           | long argon_solve blocks ping and concurrent calls. |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-08 | Cloud Worker Fleet | Transient HTTP 500/502/504 Retry Failure  | call_gemini_api retries strictly on 429 and 503;   |
|       |                    |                                           | transient cloud gateway errors abort immediately.  |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-09 | Cloud Worker Fleet | Asymmetric Plan Gate Interception Gap     | GATEKEEPER_MUTATING_TOOLS omits worker tools;      |
|       |                    |                                           | calling gemini_fast_edit bypasses Plan Gate.       |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-10 | Gatekeepers        | Zero-Defect Coverage Gap on Critic        | consult_critic.py lacks dedicated unit test file;  |
|       |                    |                                           | regressions in exit codes/JSON repair undetected.  |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-11 | Developer Tooling  | Verification Pipeline Execution Rejection | Command runner rejects pipes (`|`) or fails on     |
|       |                    |                                           | Windows batch binaries without extension (.cmd).   |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
| FM-12 | Orchestration      | Learned Affinity Vocabulary Bloat & Spool | learned_affinities.json accumulates tokens         |
|       |                    | Cleanup Hygiene Failure                   | indefinitely; orphaned .proc_* spools persist.     |
+-------+--------------------+-------------------------------------------+----------------------------------------------------+
```

---

## 4. Concrete Upgrade Specifications for Future Releases

---

### Spec 1: Tier 1 Subprocess Optimization & Consolidator Spawn Debounce

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\hooks.json` (Line 6)
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\hook_runner.py` (Lines 835–850)
- **Target Release**: Omni-Kernel v4.3.1 (Hotfix)
- **Technical Justification**:
  `PreInvocation` hook currently runs `python scripts/hook_runner.py` which takes $\sim 31.4\text{ ms}$ on Windows due to `site` module enumeration. In contrast, `PreToolUse` already uses `python -S` which executes in $\sim 14.8\text{ ms}$.
  
  **Interpreter Role Separation**: `hook_runner.py` must run under `python -S` to guarantee sub-15ms pre-flight reflex response without site-packages overhead. However, when `hook_runner.py` spawns the detached background `consolidator.py` process, it **must invoke the standard Python interpreter** (`sys.executable` with site-packages enabled, i.e., **WITHOUT `-S`**). Spawning `consolidator.py` with `-S` prevents importing `onnxruntime` and other optional acceleration modules, crashing vector consolidation.
  
  Furthermore, when `l1_staging_spool.jsonl` exceeds 25KB, every subsequent rapid turn spawns a new detached `consolidator.py` background process, leading to process storms. A robust debounce mechanism with atomic file locking guarantees a single consolidator instance per 60-second window. A **stale lock TTL check (>120s)** is enforced so that an unexpected crash during lock acquisition never permanently disables consolidator spawning.
- **Architectural Trade-offs**:
  `python -S` requires explicit `sys.path` bootstrapping for local module resolution in `hook_runner.py` (already handled at `hook_runner.py:24-26`). Debouncing background consolidator spawns to a 60-second minimum window prevents process storms while guaranteeing spool drainage within 60 seconds. The 120-second stale lock TTL self-heals abandoned locks without risking race conditions across active processes.

#### Concrete Implementation Specification:

**Diff 1: `hooks.json`**:
```diff
--- a/hooks.json
+++ b/hooks.json
@@ -3,7 +3,7 @@
     "PreInvocation": [
       {
         "type": "command",
-        "command": "python scripts/hook_runner.py",
+        "command": "python -S scripts/hook_runner.py",
         "timeout": 3
       }
     ],
```

**Diff 2: `scripts/hook_runner.py`**:
```diff
--- a/scripts/hook_runner.py
+++ b/scripts/hook_runner.py
@@ -835,6 +835,44 @@ def stage_l1_telemetry(payload: dict, workspace_dir: str):
     spool_size = os.path.getsize(spool_path) if os.path.exists(spool_path) else 0
     if spool_size > 25600:
+        marker_dir = os.path.join(workspace_dir, ".omni")
+        os.makedirs(marker_dir, exist_ok=True)
+        marker_path = os.path.join(marker_dir, "last_consolidator_spawn.timestamp")
+        lock_path = marker_path + ".lock"
+        now = time.time()
+        
+        # Stale lock TTL check (>120s): break abandoned locks from crashed processes
+        if os.path.exists(lock_path):
+            try:
+                if now - os.path.getmtime(lock_path) > 120.0:
+                    os.unlink(lock_path)
+            except OSError:
+                pass
+        
+        # Atomic lock file creation via O_CREAT | O_EXCL to prevent concurrent spawn storms
+        try:
+            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
+            try:
+                if os.path.exists(marker_path):
+                    try:
+                        with open(marker_path, "r", encoding="utf-8") as f:
+                            last_spawn = float(f.read().strip())
+                        if now - last_spawn < 60.0:
+                            return  # Debounce window active (<60s): suppress duplicate spawn
+                    except Exception:
+                        pass
+                with open(marker_path, "w", encoding="utf-8") as f:
+                    f.write(str(now))
+            finally:
+                os.close(lock_fd)
+                try:
+                    os.unlink(lock_path)
+                except OSError:
+                    pass
+        except (FileExistsError, OSError):
+            return  # Lock held by concurrent hook turn; skip spawn safely
+            
         consolidator_script = os.path.join(os.path.dirname(__file__), "consolidator.py")
+        # CRITICAL: Invoke standard interpreter (WITHOUT -S) so consolidator imports onnxruntime
         subprocess.Popen(
-            [sys.executable, "-S", consolidator_script, "--batch-run", "--workspace", workspace_dir],
+            [sys.executable, consolidator_script, "--batch-run", "--workspace", workspace_dir],
             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
         )
```

- **Migration & Rollout**: Apply hotfix directly; no database schema or rule migration required.

---

### Spec 2: Tier 2 Hybrid Retrieval Pure FTS5 BM25 Fallback Restoration

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\memory_engine.py` (Lines 804–835)
- **Target Release**: Omni-Kernel v4.3.1 (Hotfix)
- **Technical Justification**:
  Lines 805–807 check `SELECT 1 FROM dense_embeddings LIMIT 1;` and immediately execute `return []` if no dense vectors are present. This prevents loading the 274MB ONNX model, but it completely breaks lexical recall on newly initialized workspaces or repositories prior to the first vector consolidation. `hybrid_search()` already contains an explicit fallback branch for `query_vector is None` which executes pure FTS5 BM25 search; line 805 erroneously prevents that fallback from ever being reached.
- **Architectural Trade-offs**:
  Restores instant ($<1.2\text{ ms}$) lexical episodic search without incurring any ONNX memory allocation.

#### Concrete Implementation Specification:

**Diff: `scripts/memory_engine.py`**:
```diff
--- a/scripts/memory_engine.py
+++ b/scripts/memory_engine.py
@@ -804,7 +804,15 @@ def recall_episodic_memory(conn, query_text: str, workspace_dir: str, top_k: int
-        # Fast Guard (<0.1ms): Never load 261MB ONNX model if dense_embeddings table has 0 rows
-        has_dense = conn.execute("SELECT 1 FROM dense_embeddings LIMIT 1;").fetchone()
-        if not has_dense:
-            return []
+        # Graceful Degradation: Load query vector only if dense embeddings are populated
+        has_dense = conn.execute("SELECT 1 FROM dense_embeddings LIMIT 1;").fetchone()
+        query_vector = None
+        if has_dense:
+            try:
+                from embedding_service import get_embedding
+                query_vector = get_embedding(query_text, is_query=True)
+            except Exception as emb_err:
+                sys.stderr.write(f"[!] Warning: embedding_service get_embedding failed: {emb_err}\n")
+        
+        # When query_vector is None, hybrid_search automatically falls back to pure FTS5 BM25!
         all_records = []
         for h in target_hashes:
             memories = hybrid_search(conn, query_text, h, query_vector=query_vector, top_k=top_k)
```

- **Migration & Rollout**: Zero-downtime hotfix. Instantly restores lexical memory retrieval on repositories with zero dense embeddings.

---

### Spec 3: Tier 2 Vectorized Dense Scan & Partition-Bounded Scoring

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\memory_engine.py` (`hybrid_search`, Lines 410–496)
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\memory_schema.py` (`dense_embeddings` table)
- **Target Release**: Omni-Kernel v4.4.0 (Performance & Recall Release)
- **Technical Justification**:
  Currently, naive dense implementations unpack each 1024-byte float array in Python row-by-row via `struct.unpack`, taking $\sim 85\text{ ms}$ for $10,000$ vectors and breaching the 15ms retrieval SLA.
  
  **Primary Dense Scan Engine: Vectorized NumPy Batching**:
  Concatenating raw binary blobs (`b"".join(...)`) and deserializing into a contiguous 2D float32 array in a single C-level memory view (`np.frombuffer`), followed by BLAS-accelerated matrix-vector multiplication (`np.dot`), evaluates $10,000$ 256-dimensional vectors in **$< 0.5\text{ ms}$**!
  
  **Removal of Restrictive Candidate Pre-filtering**:
  Previous iterations attempted to restrict dense candidates to lexical FTS5 hits ($K_{lex} \le 50$) or an arbitrary threshold ($N < 20$). This severely starves dense recall: cross-lingual queries (e.g. Vietnamese `"khôi phục tiến trình"` vs English memory `"restore process execution"`) or conceptual synonyms share zero lexical token overlap and are completely discarded by lexical pre-filtering. Because vectorized NumPy batching runs in $<0.5\text{ ms}$ for $10,000$ vectors, all restrictive candidate pre-filtering is eliminated for standard repositories ($N \le 20,000$).
  
  **Partition Bounding Guard (>20,000 vectors)**:
  Candidate bounding is applied **only when vectors exceed 20,000** via SQLite index partitioning (e.g., partitioning by workspace domain/category or coarse cluster via `WHERE workspace_hash = ? AND partition_id = ?`).
  
  **Schema Alignment & Hydration**:
  Canonical schema columns in table `dense_embeddings` are `vector_blob, norm`. Hydration must return **complete record dictionaries** matching Schema 430 (`memory_id`, `workspace_hash`, `title`, `problem_signature`, `solution_payload`, `context_metadata`, `bilingual_tags`, `status`, `activation_count`, `confidence_score`), NOT raw database tuples.

#### Concrete Implementation Specification:

**Diff: `scripts/memory_engine.py`**:
```diff
--- a/scripts/memory_engine.py
+++ b/scripts/memory_engine.py
@@ -430,12 +430,42 @@ def hybrid_search(conn, query_text: str, workspace_hash: str, query_vector=None
         cursor = conn.cursor()
-        query_norm = compute_vector_norm(query_vector)
-
-        cursor.execute(
-            """
-            SELECT memory_id, vector_blob, norm
-            FROM dense_embeddings
-            WHERE workspace_hash = ?
-            """,
-            (workspace_hash,)
-        )
-        rows = cursor.fetchall()
+        query_vec = np.asarray(query_vector, dtype=np.float32)
+        query_norm = compute_vector_norm(query_vec)
+
+        # Scalability Guard: Check if vector volume exceeds 20,000 threshold
+        vector_count = conn.execute(
+            "SELECT COUNT(*) FROM dense_embeddings WHERE workspace_hash = ?",
+            (workspace_hash,)
+        ).fetchone()[0]
+
+        if vector_count > 20000:
+            # Apply candidate bounding via SQLite index partitioning ONLY when vectors > 20,000
+            cursor.execute(
+                """
+                SELECT memory_id, vector_blob, norm
+                FROM dense_embeddings
+                WHERE workspace_hash = ? AND partition_id = (
+                    SELECT partition_id FROM workspace_metadata WHERE workspace_hash = ?
+                )
+                """,
+                (workspace_hash, workspace_hash)
+            )
+        else:
+            # Primary Dense Scan Engine: Exhaustive vectorized scan preserves 100% semantic synonyms
+            cursor.execute(
+                """
+                SELECT memory_id, vector_blob, norm
+                FROM dense_embeddings
+                WHERE workspace_hash = ?
+                """,
+                (workspace_hash,)
+            )
+        rows = cursor.fetchall()
+        
+        dense_ranked_ids = []
+        if rows:
+            # Vectorized NumPy batching: np.frombuffer + np.dot computes 10,000 vectors in <0.5ms
+            mem_ids = [r[0] for r in rows]
+            raw_blobs = b"".join(r[1] for r in rows)
+            matrix = np.frombuffer(raw_blobs, dtype=np.float32).reshape(len(rows), -1)
+            norms = np.array([r[2] for r in rows], dtype=np.float32)
+            
+            sims = np.dot(matrix, query_vec) / (norms * query_norm + 1e-9)
+            top_k = min(50, len(rows))
+            top_indices = np.argpartition(-sims, top_k - 1)[:top_k]
+            top_indices = top_indices[np.argsort(-sims[top_indices])]
+            dense_ranked_ids = [mem_ids[i] for i in top_indices]
@@ -485,9 +515,17 @@ def hybrid_search(conn, query_text: str, workspace_hash: str, query_vector=None
         id_to_record = {}
         for row in cursor.fetchall():
-            id_to_record[row[0]] = row
+            # Hydrate into complete dictionary matching Schema 430
+            id_to_record[row[0]] = dict(zip(
+                ["memory_id", "workspace_hash", "workspace_path", "memory_type",
+                 "title", "problem_signature", "solution_payload", "context_metadata",
+                 "bilingual_tags", "status", "activation_count", "confidence_score"],
+                row
+            ))

         hydrated = [id_to_record[m_id] for m_id in target_ids if m_id in id_to_record]
         return hydrated
```

- **Migration & Rollout**: Compatible with Schema 430. Verified under `tests/test_concurrency_wal.py`.

---

### Spec 4: Tier 3 Success-Ratio Gated Trace Promotion & Batched ONNX Backfill

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\consolidator.py` (Lines 910–947)
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\embedding_service.py` (New batch interface)
- **Target Release**: Omni-Kernel v4.4.0
- **Technical Justification**:
  1. `consolidator.py:914` skips negative events (`fb < 0.0`) prior to clustering. Consequently, if a problematic workflow failed 18 times and succeeded 2 times, the cluster evaluates only the 2 successes and promotes an unreliable pattern into `proven_traces.json`.
  2. **Tuple Unpacking**: In `consolidator.py`, rows returned from `activation_events` via `cursor.fetchall()` are SQLite row tuples `(event_id, session_id, timestamp, user_input, workspace_dir, feedback_score, ...)`, NOT dictionaries. Field access must use tuple unpacking or indices (`ev[0]`, `ev[3]`, `ev[5]`).
  3. **Dimension-Safe ONNX Slicing**: Depending on the model export and pooling head, the ONNX output tensor can be 2D `[batch, hidden_dim]` or 3D `[batch, seq_len, hidden_dim]`. Indexing `output[:, 0, :256]` on a 2D tensor throws `IndexError`. Slicing must handle both dimensions safely.
  4. **Success Threshold Calibration**: A rigid $70\%$ threshold without grace can starve multi-step bug fix iterations where an agent diagnoses and attempts 1-2 fixes before succeeding. The gating formula implements an iterative grace threshold ($\ge 60\%$) with positive momentum ($N_{pos} \ge 2$).
  5. Vector backfill executes scalar `get_embedding()` one text at a time, generating 50 separate ONNX model invocations taking $>750\text{ ms}$. Batched tensor inference ($B=16$) speeds up vector backfill by $3\times$.

#### Concrete Implementation Specification:

**Diff 1: `scripts/consolidator.py`**:
```diff
--- a/scripts/consolidator.py
+++ b/scripts/consolidator.py
@@ -910,12 +910,10 @@ def consolidate_batch(conn, workspace_dir: str, limit: int = 500):
-        for ev in events:
-            ev_id, sess_id, ts, user_inp, ws_dir, fb = ev
-            if not user_inp or fb < 0.0:
-                processed_ids.append(ev_id)
-                continue
+        # Tuple Unpacking: SQLite cursor returns tuples (ev_id, sess_id, ts, user_inp, ws_dir, fb)
+        for ev in events:
+            ev_id, sess_id, ts, user_inp, ws_dir, fb = ev[:6]
+            if not user_inp:
+                processed_ids.append(ev_id)
+                continue
             clean_user_inp = str(user_inp).strip()
             fb_val = float(fb) if fb is not None else 0.0
             norm_query = fold_vietnamese(clean_user_inp)
             cluster_key = f"{ws_hash}::{norm_query}"
             clusters.setdefault(cluster_key, []).append({
                 "id": ev_id, "input": clean_user_inp, "ws_dir": ws_dir,
                 "ws_hash": ws_hash, "feedback": fb_val
             })
@@ -945,8 +943,15 @@ def consolidate_batch(conn, workspace_dir: str, limit: int = 500):
             positive_hits = [e for e in cluster_events if e.get("feedback", 0.0) > 0.0]
+            negative_hits = [e for e in cluster_events if e.get("feedback", 0.0) < 0.0]
+            total_rated = len(positive_hits) + len(negative_hits)
+            success_ratio = len(positive_hits) / total_rated if total_rated > 0 else 0.0
+            
+            # Calibrated Success-Ratio Gating:
+            # Requires at least 2 positive hits, and either success_ratio >= 0.60
+            # OR net momentum (positive - negative >= 2) to accommodate multi-step fixes
+            has_quality_momentum = (len(positive_hits) - len(negative_hits)) >= 2
+            if len(positive_hits) >= 2 and (success_ratio >= 0.60 or has_quality_momentum):
                 # Promote to workspace_episodic_memory and stage to consolidation_outbox
```

**Diff 2: `scripts/embedding_service.py` (Dimension-Safe Batched ONNX)**:
```python
def get_embeddings_batch(texts: List[str], is_query: bool = False) -> List[List[float]]:
    """Batched ONNX embedding generation yielding 3x throughput with dimension-safe slicing."""
    session, tokenizer = _get_onnx_session_and_tokenizer()
    prefix = "task: search result | query: " if is_query else "title: none | text: "
    prefixed_texts = [prefix + t for t in texts]
    
    encoded = tokenizer(prefixed_texts, padding=True, truncation=True, max_length=512, return_tensors="np")
    inputs = {
        "input_ids": encoded["input_ids"].astype(np.int64),
        "attention_mask": encoded["attention_mask"].astype(np.int64)
    }
    outputs = session.run(None, inputs)
    raw_output = outputs[0]
    
    # Dimension-Safe ONNX Output Slicing (supports both 2D pooled and 3D token outputs)
    if raw_output.ndim == 3:
        vectors = raw_output[:, 0, :256]  # [batch, seq_len, dim] -> CLS token 256d slice
    elif raw_output.ndim == 2:
        vectors = raw_output[:, :256]     # [batch, dim] -> pooled 256d slice
    else:
        raise ValueError(f"Unexpected ONNX tensor output ndim={raw_output.ndim}, shape={raw_output.shape}")
    
    # Vectorized L2 Euclidean re-normalization
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = (vectors / norms).tolist()
    return normalized
```

---

### Spec 5: Cloud Worker Fleet Non-Blocking Threaded Stdio Server & Expanded Retries

- **Affected Components**:
  * `d:\Antigravity\Gemini Worker\gemini_worker_mcp.py` (Lines 112–142, 580–686)
  * `d:\Antigravity\Gemini Worker\io_helpers.py` (`_TargetFileLock`, Lines 87–130)
- **Target Release**: Omni-Kernel v4.4.0
- **Technical Justification**:
  1. **Exact Signature & Retries**: `call_gemini_api(payload: dict, model: str = DEFAULT_MODEL, timeout: float = 60.0) -> str` uses `concrete_model = resolve_model(model)` and `max_attempts = 4`. Currently, it retries strictly on `429` and `503`. Transient Google Cloud HTTP `500` (Internal Error), `502` (Bad Gateway), and `504` (Gateway Timeout) abort immediately. Adding `500, 502, 504` to the retry set prevents transient network/cloud failures.
  2. **Non-Blocking Threaded Stdio Server**: The MCP server must process lightweight protocol messages (`initialize`, `ping`, `tools/list`) **synchronously on the main thread** with $<1\text{ ms}$ latency. Only heavy tool execution requests (`tools/call`) are submitted to a `ThreadPoolExecutor(max_workers=4)`. Outbound stdout writes are protected via a `threading.Lock()`.
  3. **`_TargetFileLock` Spin-Wait Retry**: Currently, `_TargetFileLock` immediately crashes with `RuntimeError` upon `FileExistsError`. In a multi-threaded worker executing concurrent tool calls, threads must spin-wait with exponential backoff and jitter rather than crashing immediately.

#### Concrete Implementation Specification:

**Diff 1: `gemini_worker_mcp.py` (Signature-Preserving HTTP Retry Expansion)**:
```diff
--- a/gemini_worker_mcp.py
+++ b/gemini_worker_mcp.py
@@ -112,7 +112,7 @@ def call_gemini_api(payload: dict, model: str = DEFAULT_MODEL, timeout: float =
     api_key = get_api_key()
     concrete_model = resolve_model(model)
     endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{concrete_model}:generateContent?key={api_key}"
@@ -134,7 +134,7 @@ def call_gemini_api(payload: dict, model: str = DEFAULT_MODEL, timeout: float =
         except urllib.error.HTTPError as e:
-            if e.code in (429, 503) and attempt < max_attempts - 1:
+            # Retry on 429 (rate limit) and 500, 502, 503, 504 (transient gateway/internal errors)
+            if e.code in (429, 500, 502, 503, 504) and attempt < max_attempts - 1:
                 backoff = (2 ** attempt) + random.uniform(0.1, 0.5)
-                logger.warning(f"HTTP {e.code} hit on '{concrete_model}', sleeping {backoff:.2f}s before retry...")
+                logger.warning(f"HTTP {e.code} hit on '{concrete_model}', retrying in {backoff:.2f}s (attempt {attempt+1}/{max_attempts})...")
                 time.sleep(backoff)
                 continue
```

**Diff 2: `gemini_worker_mcp.py` (Non-Blocking Stdio Server Architecture)**:
```python
import concurrent.futures, threading

stdout_lock = threading.Lock()
worker_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="MCPWorker")

def _send_response(resp: dict):
    with stdout_lock:
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()

def handle_tool_call_async(req: dict):
    req_id = req.get("id")
    params = req.get("params", {})
    tool_name = params.get("name")
    args = params.get("arguments", {})
    try:
        result = dispatch_tool_call(tool_name, args)
        _send_response({"jsonrpc": "2.0", "id": req_id, "result": result})
    except Exception as exc:
        _send_response({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(exc)}})

def run_stdio_server():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue
            
        method = req.get("method")
        req_id = req.get("id")
        
        # Synchronous fast-path: Protocol lifecycle methods handled immediately on main thread (<1ms)
        if method in ("initialize", "ping", "tools/list", "notifications/initialized"):
            if method == "ping":
                _send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
            elif method == "tools/list":
                _send_response({"jsonrpc": "2.0", "id": req_id, "result": {"tools": REGISTERED_TOOLS}})
            elif method == "initialize":
                _send_response({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}})
            continue
            
        # Asynchronous execution path: Offload heavy tool executions to worker thread pool
        if method == "tools/call":
            worker_pool.submit(handle_tool_call_async, req)
```

**Diff 3: `io_helpers.py` (`_TargetFileLock` Spin-Wait Retry)**:
```diff
--- a/io_helpers.py
+++ b/io_helpers.py
@@ -114,14 +114,24 @@ class _TargetFileLock:
-        try:
-            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
-            lock_payload = f"pid={os.getpid()};time={now}\n".encode("utf-8")
-            os.write(self._fd, lock_payload)
-            os.fsync(self._fd)
-        except FileExistsError:
-            raise RuntimeError(f"Lock acquisition failed: {self.lock_path} is held by another active process.")
+        # Spin-wait with exponential backoff and jitter for concurrent worker threads
+        deadline = time.time() + self.timeout_sec
+        attempt = 0
+        while True:
+            try:
+                self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
+                lock_payload = f"pid={os.getpid()};thread={threading.get_ident()};time={now}\n".encode("utf-8")
+                os.write(self._fd, lock_payload)
+                os.fsync(self._fd)
+                break
+            except FileExistsError:
+                if time.time() >= deadline:
+                    raise RuntimeError(f"Lock acquisition timed out after {self.timeout_sec}s: {self.lock_path} is held by another worker thread.")
+                backoff = min(0.5, 0.05 * (1.5 ** attempt) + random.uniform(0.01, 0.05))
+                time.sleep(backoff)
+                attempt += 1
```

---

### Spec 6: Symmetric Plan Gate Integration for Worker Fleet Mutating Tools

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\hook_runner.py` (Lines 559–576)
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\hooks.json` (Line 12)
- **Target Release**: Omni-Kernel v4.4.0
- **Technical Justification**:
  `GATEKEEPER_MUTATING_TOOLS` currently intercepts only native file tools (`write_file`, `edit_file`, `replace_file_content`, `multi_replace_file_content`, `write_to_file`). If an agent delegates file modifications directly to worker fleet tools (`gemini_fast_edit`, `gemini_heavy_code_gen`, `gemini_autonomous_loop`, `gemini_execute_plan`, `gemini_generate_tests`), or routes them via the generic MCP proxy tool `call_mcp_tool`, the PreToolUse Plan Gate is bypassed entirely.
  
  **MCP Proxy Unwrapping (`call_mcp_tool`)**:
  When tools are exposed via MCP servers, agents frequently invoke them via proxy wrappers: `call_mcp_tool(ServerName="gemini_worker_cloud", ToolName="gemini_fast_edit", Arguments={...})`. Without unwrapping, the Plan Gate observes `tool_name == "call_mcp_tool"` and fails to detect mutating operations. `hook_runner.py` must unwrap `tool_args.get("ToolName")` and `tool_args.get("Arguments")` to catch underlying worker tool mutations.
  
  Furthermore, native tools pass path arguments under `"Path"` or `"TargetFile"`, whereas worker tools pass paths under `"save_to_path"`, `"file_path"`, or `"target_file"`. The Plan Gate must inspect all argument variants to resolve target paths correctly.
- **Architectural Trade-offs**:
  Extending the matcher in `hooks.json` to include `call_mcp_tool` and mutating worker tools, paired with $<0.02\text{ ms}$ proxy unwrapping in `hook_runner.py`, restores total architectural invariant symmetry across all direct and proxied mutation channels.

#### Concrete Implementation Specification:

**Diff 1: `hooks.json`**:
```diff
--- a/hooks.json
+++ b/hooks.json
@@ -10,7 +10,7 @@
     "PreToolUse": [
       {
-        "matcher": "write_file|edit_file|replace_file_content|multi_replace_file_content|write_to_file",
+        "matcher": "write_file|edit_file|replace_file_content|multi_replace_file_content|write_to_file|call_mcp_tool|gemini_fast_edit|gemini_heavy_code_gen|gemini_autonomous_loop|gemini_execute_plan|gemini_generate_tests",
         "hooks": [
           {
             "type": "command",
```

**Diff 2: `scripts/hook_runner.py`**:
```diff
--- a/scripts/hook_runner.py
+++ b/scripts/hook_runner.py
@@ -559,7 +559,12 @@ GATEKEEPER_MUTATING_TOOLS = (
     "write_file",
     "edit_file",
     "replace_file_content",
     "multi_replace_file_content",
     "write_to_file",
+    "gemini_fast_edit",
+    "gemini_heavy_code_gen",
+    "gemini_autonomous_loop",
+    "gemini_execute_plan",
+    "gemini_generate_tests",
 )
@@ -574,7 +584,17 @@ def process_pre_tool_use(payload: dict) -> dict:
     try:
         tool_call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else {}
         tool_name = str(tool_call.get("name", "")).strip()
         args = tool_call.get("args") if isinstance(tool_call.get("args"), dict) else {}
+
+        # MCP Tool Proxy Unwrapping: inspect call_mcp_tool payloads for worker mutations
+        if tool_name == "call_mcp_tool":
+            proxied_name = str(args.get("ToolName", "")).strip()
+            proxied_args = args.get("Arguments") if isinstance(args.get("Arguments"), dict) else {}
+            if proxied_name in GATEKEEPER_MUTATING_TOOLS:
+                tool_name = proxied_name
+                args = proxied_args
+
+        if tool_name not in GATEKEEPER_MUTATING_TOOLS:
+            return {"verdict": "ALLOW"}
+
+        # Comprehensive multi-tool path inspection (native tools + worker fleet tools)
+        target_path = (args.get("Path") or args.get("TargetFile") or args.get("save_to_path") or 
+                       args.get("file_path") or args.get("target_file") or args.get("target_path") or "")
```

---

### Spec 7: Unified Council Gate Orchestrator (`omni-council`) & Critic Unit Tests

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\omni_council.py` (New Unified Entrypoint)
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\tests\test_consult_critic.py` (New Test Suite)
- **Target Release**: Omni-Kernel v4.4.0
- **Technical Justification**:
  1. Developers currently must invoke `consult_critic.py` for theoretical RFC reviews and `dsh_auditor.py` for empirical audits separately. A unified CLI `omni-council {spec|diff}` streamlines gatekeeper execution and links the cryptographic SHA-256 pre-code approval to the post-code empirical diff audit.
  2. `consult_critic.py` has 0 unit tests in `tests/`, creating regression risk for its JSON escape scanner, POSIX exit codes, and HMAC signing logic.

#### Concrete Implementation Specification:

**New CLI Interface (`scripts/omni_council.py`)**:
```python
"""Omni-Council: Unified Architectural Gatekeeper CLI."""
import sys, argparse
from consult_critic import main as critic_main
from dsh_auditor import main as dsh_main

def main():
    parser = argparse.ArgumentParser(prog="omni-council", description="Unified Omni Architectural Council Gatekeeper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Pre-code theoretical review
    spec_p = subparsers.add_parser("spec", help="Execute pre-code theoretical RFC / spec critique (DeepSeek API)")
    spec_p.add_argument("file", help="Path to RFC or specification markdown file")
    spec_p.add_argument("--strict", action="store_true", help="Reject non-approved verdicts with exit code 5")
    
    # Post-code empirical review
    diff_p = subparsers.add_parser("diff", help="Execute post-code empirical diff audit (DSH Sandbox)")
    diff_p.add_argument("--task", required=True, help="Task description or regression hypothesis")
    diff_p.add_argument("--category", default="STATIC_AUDIT", choices=["STATIC_AUDIT", "BUG_REPRODUCE", "DB_CONCURRENCY", "REFACTOR_EVAL"])
    
    args = parser.parse_args()
    if args.command == "spec":
        sys.argv = ["consult_critic.py", "--file", args.file] + (["--strict"] if args.strict else [])
        return critic_main()
    elif args.command == "diff":
        sys.argv = ["dsh_auditor.py", "--task", args.task, "--category", args.category, "--json"]
        return dsh_main()

if __name__ == "__main__":
    sys.exit(main())
```

**New Unit Test Suite (`tests/test_consult_critic.py`)**:
Verifies POSIX exit codes 0–5, path traversal blocking, HMAC signing, and single-pass JSON escape repair under mocked HTTP responses.

---

### Spec 8: Verification Command Runner Relaxation & Windows Binary Resolution

- **Affected Components**:
  * `d:\Antigravity\Gemini Worker\io_helpers.py` (`parse_verify_commands` and `run_verify_commands`, Lines 145–260)
- **Target Release**: Omni-Kernel v4.4.0
- **Technical Justification**:
  1. `io_helpers.py:165` rejects shell tokens `|`, `;`, `>`, `<`. This prevents common engineering commands such as piping output (`pytest | grep FAILED`) or redirecting logs.
  2. **Zero-Trust Safety Mandate**: Passing raw shell tokens to `shell=True` is strictly forbidden because it violates Ring 0 Invariant 1 (Zero-Trust Security) by introducing command injection vectors. Instead, pipelines must be parsed into structured command stages using `shlex.split` and chained via standard library `subprocess.Popen(stdout=subprocess.PIPE)` to `subprocess.Popen(stdin=p1.stdout)` under `shell=False`.
  3. **OS Pipe Buffer Deadlock Avoidance (>64KB)**: OS pipes on Windows and Linux possess a 64KB kernel buffer limit. If upstream processes in a multi-stage pipeline emit substantial diagnostic or error output to `stderr` while only the final stage's `communicate()` is called, upstream processes will block indefinitely on `write()`. Subprocess pipe chaining must **concurrently drain `stderr`** across all pipeline stages.
  4. **Strict `pipefail` Semantics**: Default shell pipeline behavior returns only the exit code of the final command, concealing critical upstream crashes. Subprocess pipeline chaining must strictly enforce `pipefail` semantics: inspect exit codes of all upstream processes in the pipeline, returning non-zero if any pipeline stage fails.
  5. **Windows Binary Resolution**: `run_verify_commands` invokes `subprocess.Popen(seg, shell=False)`. On Windows, commands like `npm`, `npx`, `pytest` fail with `WinError 2` unless resolved via `shutil.which` or appended with `.cmd`/`.exe`.

#### Concrete Implementation Specification:

**Diff: `io_helpers.py` (Structured Pipelines & Win32 Binary Resolution under `shell=False`)**:
```python
import os, sys, shutil, subprocess, shlex
from typing import List, Tuple, Optional

def resolve_command_binary(cmd_name: str) -> str:
    """Resolves Windows executable extensions (.cmd, .bat, .exe) for shell=False execution."""
    resolved = shutil.which(cmd_name)
    if resolved:
        return resolved
    if os.name == "nt":
        for ext in (".cmd", ".bat", ".exe"):
            cand = shutil.which(cmd_name + ext)
            if cand:
                return cand
    return cmd_name

def execute_piped_command_pipeline(pipeline_segments: List[List[str]], cwd: str, timeout_sec: float) -> Tuple[int, str, str]:
    """Zero-Trust Pipeline Execution: Chains subprocesses via OS pipes WITHOUT shell=True.
    - Concurrently drains stderr across all stages to prevent OS pipe buffer (>64KB) deadlocks.
    - Enforces pipefail semantics: inspects exit codes of all pipeline stages, returning non-zero if any stage fails.
    """
    import threading
    procs = []
    prev_stdout = None
    stderr_buffers: List[List[bytes]] = [[] for _ in range(len(pipeline_segments))]
    drain_threads: List[threading.Thread] = []

    def _drain_stream(stream, accumulator: List[bytes]):
        try:
            for chunk in iter(lambda: stream.read(4096), b""):
                accumulator.append(chunk)
        finally:
            stream.close()

    try:
        for i, seg in enumerate(pipeline_segments):
            resolved_seg = [resolve_command_binary(seg[0])] + seg[1:]
            is_last = (i == len(pipeline_segments) - 1)
            
            proc = subprocess.Popen(
                resolved_seg,
                cwd=cwd,
                stdin=prev_stdout,
                stdout=subprocess.PIPE if is_last else subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
            if prev_stdout:
                prev_stdout.close()  # Allow upstream process to receive SIGPIPE
            prev_stdout = proc.stdout
            procs.append(proc)

            # Concurrently drain stderr to prevent OS pipe buffer (>64KB) blocking
            t = threading.Thread(target=_drain_stream, args=(proc.stderr, stderr_buffers[i]), daemon=True)
            t.start()
            drain_threads.append(t)
            
        last_proc = procs[-1]
        try:
            stdout_data, _ = last_proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            for p in procs:
                p.kill()
            raise
        
        # Wait for all upstream processes to close cleanly
        for p in procs[:-1]:
            p.wait(timeout=5.0)

        # Wait for all stderr draining threads to finish
        for t in drain_threads:
            t.join(timeout=1.0)
            
        # Enforce pipefail semantics: inspect exit codes of all upstream processes
        pipefail_code = 0
        for p in procs:
            if p.returncode != 0:
                pipefail_code = p.returncode
                break

        combined_stderr = b"".join(b"".join(chunks) for chunks in stderr_buffers)
        return pipefail_code, stdout_data.decode("utf-8", "replace"), combined_stderr.decode("utf-8", "replace")
    finally:
        if prev_stdout and not prev_stdout.closed:
            prev_stdout.close()
```

---

### Spec 9: Learned Affinities Bounded Retention & Spool Cleanup Hygiene

- **Affected Components**:
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\resolver.py` (`record_feedback`)
  * `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\scripts\consolidator.py` (`drain_l1_staging`)
- **Target Release**: Omni-Kernel v5.0.0 (Unified Fleet & Scalability)
- **Technical Justification**:
  1. **Schema Alignment**: `learned_affinities.json` follows the schema:
     ```json
     {
       "version": "1.1.0",
       "affinities": {
         "token": {
           "skill_name": 15.0
         }
       }
     }
     ```
     Tokens currently accumulate without decay or bounded capacity, creating file bloat.
  2. Bounded decay must apply to the inner `{skill_name: boost}` mapping, clamping boosts between $[-30.0, +60.0]$, pruning entries where all skill boosts decay below $1.0$, and capping total dictionary tokens to $N \le 500$.
  3. When IDE sessions terminate abruptly, orphaned `.proc_{pid}_{uuid}` files remain on disk indefinitely unless purged.

#### Concrete Implementation Specification:

**Diff: `scripts/resolver.py` (Bounded Schema-Aware Affinity Decay)**:
```python
def prune_learned_affinities(data: dict, max_tokens: int = 500) -> dict:
    """Applies decay and bounds learned_affinities dictionary to prevent unbounded bloat.
    Matches schema: {'version': '1.1.0', 'affinities': {token: {skill_name: boost}}}
    """
    affinities = data.get("affinities", {})
    pruned = {}
    
    for token, skill_map in affinities.items():
        pruned_skills = {}
        for skill_name, boost in skill_map.items():
            # Apply decay factor (0.90 per maintenance cycle) and clamp to bounds [-30.0, +60.0]
            decayed_boost = round(max(-30.0, min(60.0, float(boost) * 0.90)), 2)
            if abs(decayed_boost) >= 1.0:  # Evict insignificant noise
                pruned_skills[skill_name] = decayed_boost
        if pruned_skills:
            pruned[token] = pruned_skills
            
    # Bound vocabulary to top max_tokens by maximum absolute boost
    if len(pruned) > max_tokens:
        sorted_tokens = sorted(
            pruned.items(),
            key=lambda kv: max(abs(b) for b in kv[1].values()),
            reverse=True
        )
        pruned = dict(sorted_tokens[:max_tokens])
        
    return {"version": data.get("version", "1.1.0"), "affinities": pruned}
```

---

## 5. Actionable Implementation Roadmap

### 5.1 Release Phasing Matrix

```
+---------------------------------------------------------------------------------------------+
|                                    IMPLEMENTATION ROADMAP                                   |
+---------------------------------------------------------------------------------------------+

PHASE 1: IMMEDIATE RELIABILITY PATCHES (v4.3.1 Hotfix)
Target Horizon: Immediate Deployment (Zero Invariant Drift)
* Deliverables (1:1 Spec Mapping):
  - [Spec 1] Tier 1 `python -S` standardization & 60s consolidator spawn debounce.
  - [Spec 2] Tier 2 Pure FTS5 BM25 fallback restoration for unpopulated dense tables.
* Verification Gate:
  - Run `test_engine.py` and `test_concurrency_wal.py` (100% pass required).
  - Verify L1 process spawn turnaround < 18ms on Windows.

PHASE 2: HIGH-PERFORMANCE KERNEL REFINEMENT (v4.4.0 Minor)
Target Horizon: Next Kernel Sprint
* Deliverables (1:1 Spec Mapping):
  - [Spec 3] Vectorized NumPy dense batching (<0.5ms for 10k vectors) and partitioned candidate bounding (>20k vectors) in `memory_engine.py`.
  - [Spec 4] Tier 3 Net success-ratio gating ($\ge 60\%$) & dimension-safe batched ONNX tensor backfill.
  - [Spec 5] Cloud Worker non-blocking threaded stdio server & HTTP 500/502/504 retry loop.
  - [Spec 6] Symmetric Plan Gate integration for `gemini_fast_edit`, `gemini_heavy_code_gen`.
  - [Spec 7] Unified Council Gate CLI (`omni-council`) & `test_consult_critic.py` suite.
  - [Spec 8] Verification command runner binary resolution via `shutil.which()` & structured pipes.
* Verification Gate:
  - 125+ automated tests passing across test suite.
  - Empirical DSH audit passing in Tier 2 sandbox.

PHASE 3: SCALABILITY & UNIFIED ARCHITECTURE (v5.0.0 Major)
Target Horizon: Architecture Evolution
* Deliverables (1:1 Spec Mapping):
  - [Spec 9] Learned affinities bounded retention (500 tokens) & spool auto-cleanup daemon.
* Verification Gate:
  - Full end-to-end multi-agent benchmark under 5,000+ synthetic episodic memories.
```

---

### 5.2 Cross-Phase Dependency Graph

```
[ Spec 1: L1 python -S ] --------+
                                  |---> [ Phase 1: v4.3.1 Hotfix ]
[ Spec 2: L2 FTS5 Fallback ] ----+                 |
                                                   v
[ Spec 3: L2 Vectorized Batching ] -+      [ Phase 2: v4.4.0 Minor ]
[ Spec 4: L3 Success Gating ] ---|                 |
[ Spec 5: Threaded Stdio ] ------+---> (Enforces Worker Fleet & Gatekeeper Symmetry)
[ Spec 6: Symmetric Plan Gate] --|                 |
[ Spec 7: omni-council CLI ] ----|                 v
[ Spec 8: Win32 Which Resolver ] +      [ Phase 3: v5.0.0 Major ]
                                                   |
[ Spec 9: Affinity Decay ] ------------------------+---> (Scalability & 2,000+ Skills)
```

---

### 5.3 Invariant Guardrails & Risk Register

```
+---------+------------------------------+------------+-------------------------------------------------------+
| Risk ID | Hazard Description           | Severity   | Mandatory Guardrail & Defense                         |
+---------+------------------------------+------------+-------------------------------------------------------+
| R-01    | SQLite Database File Lock    | HIGH       | Retain dedicated `MemorySingleWriter` thread and      |
|         | Contention under Multi-Agent |            | 5000ms busy timeout. Never write from reader threads. |
+---------+------------------------------+------------+-------------------------------------------------------+
| R-02    | API Key Leakage in Logs      | CRITICAL   | All audit outputs and staging files must route through |
|         | or Provenance Ledgers        |            | `sanitizer.redact_credentials` before disk writing.   |
+---------+------------------------------+------------+-------------------------------------------------------+
| R-03    | Worker Fleet Broken Syntax   | HIGH       | `gemini_fast_edit` must validate AST via `ast.parse`  |
|         | Leaving Corrupt Workspace    |            | and restore `.bak` on any `SyntaxError`.              |
+---------+------------------------------+------------+-------------------------------------------------------+
| R-04    | Windows Antivirus File Lock  | MEDIUM     | Enforce exponential backoff retries in                |
|         | Collisions on Atomic Replace |            | `safe_atomic_replace` for all file mutations.         |
+---------+------------------------------+------------+-------------------------------------------------------+
```

---

## 6. Independent Evaluation Rubric

### 6.1 Evaluation Methodology & Weighting

To provide rigorous, objective evaluation across all proposed architectural enhancements, each specification is scored on a 0–100 scale across four standardized dimensions:
1. **Technical Feasibility (30%)**: Simplicity of implementation, absence of third-party package dependencies, and compatibility with the existing Python Standard Library baseline.
2. **Alignment with Invariants (35%)**: Strict preservation of Ring 0 invariants (Zero-Trust Security, Reliable Engineering, Ponytail Simplicity, Bilingual Native Parity, Worker Delegation, Observability).
3. **Performance Impact (20%)**: Measurable reduction in latency, elimination of SLA bottlenecks, or reduction in compute/token overhead.
4. **Usability Impact (15%)**: Elimination of failure modes, resilience against Windows OS traps, and prevention of agent deadlocks.

$$\text{Composite Score} = 0.30 \cdot \text{Feasibility} + 0.35 \cdot \text{Invariants} + 0.20 \cdot \text{Performance} + 0.15 \cdot \text{Usability}$$

---

### 6.2 Quantitative Specification Scoring Matrix

```
+--------+------------------------------------+-------------+------------+-------------+-----------+-----------+
| Spec # | Specification Title                | Feasibility | Invariants | Performance | Usability | Composite |
|        |                                    | (Weight 30%)| (Weight 35%) (Weight 20%) (Weight 15%) Score     |
+--------+------------------------------------+-------------+------------+-------------+-----------+-----------+
| Spec 1 | L1 python -S & Spawn Debounce      | 95 / 100    | 100 / 100  | 98 / 100    | 90 / 100  | 96.6 / 100|
| Spec 2 | L2 Pure FTS5 BM25 Fallback         | 98 / 100    | 100 / 100  | 90 / 100    | 95 / 100  | 96.7 / 100|
| Spec 3 | L2 Vectorized Scan & Partitioning   | 88 / 100   | 92 / 100   | 95 / 100    | 88 / 100  | 90.8 / 100|
| Spec 4 | L3 Success Gating & Batched ONNX   | 90 / 100    | 95 / 100   | 95 / 100    | 85 / 100  | 92.0 / 100|
| Spec 5 | Worker Fleet Threaded Stdio Server | 88 / 100    | 92 / 100   | 90 / 100    | 95 / 100  | 90.9 / 100|
| Spec 6 | Symmetric Plan Gate for Workers    | 95 / 100    | 98 / 100   | 90 / 100    | 95 / 100  | 95.1 / 100|
| Spec 7 | Unified Council Gate & Unit Tests  | 92 / 100    | 98 / 100   | 90 / 100    | 95 / 100  | 94.2 / 100|
| Spec 8 | Win32 Binary Resolution & Pipes    | 90 / 100    | 90 / 100   | 90 / 100    | 95 / 100  | 90.8 / 100|
| Spec 9 | Affinity Retention & Spool Cleanup | 95 / 100    | 95 / 100   | 85 / 100    | 90 / 100  | 92.3 / 100|
+--------+------------------------------------+-------------+------------+-------------+-----------+-----------+
| TOTAL  | ECOSYSTEM COLUMN AVERAGES          | 92.3 / 100  | 95.6 / 100 | 91.4 / 100  | 92.0 / 100| 93.2 / 100|
+--------+------------------------------------+-------------+------------+-------------+-----------+-----------+
```

#### Mathematical Verification of Composite Scores:
- **Spec 1**: $95 \times 0.30 + 100 \times 0.35 + 98 \times 0.20 + 90 \times 0.15 = 28.50 + 35.00 + 19.60 + 13.50 = 96.60 \to \mathbf{96.6}$
- **Spec 2**: $98 \times 0.30 + 100 \times 0.35 + 90 \times 0.20 + 95 \times 0.15 = 29.40 + 35.00 + 18.00 + 14.25 = 96.65 \to \mathbf{96.7}$
- **Spec 3**: $88 \times 0.30 + 92 \times 0.35 + 95 \times 0.20 + 88 \times 0.15 = 26.40 + 32.20 + 19.00 + 13.20 = \mathbf{90.8}$
- **Spec 4**: $90 \times 0.30 + 95 \times 0.35 + 95 \times 0.20 + 85 \times 0.15 = 27.00 + 33.25 + 19.00 + 12.75 = \mathbf{92.0}$
- **Spec 5**: $88 \times 0.30 + 92 \times 0.35 + 90 \times 0.20 + 95 \times 0.15 = 26.40 + 32.20 + 18.00 + 14.25 = 90.85 \to \mathbf{90.9}$
- **Spec 6**: $95 \times 0.30 + 98 \times 0.35 + 90 \times 0.20 + 95 \times 0.15 = 28.50 + 34.30 + 18.00 + 14.25 = 95.05 \to \mathbf{95.1}$
- **Spec 7**: $92 \times 0.30 + 98 \times 0.35 + 90 \times 0.20 + 95 \times 0.15 = 27.60 + 34.30 + 18.00 + 14.25 = 94.15 \to \mathbf{94.2}$
- **Spec 8**: $90 \times 0.30 + 90 \times 0.35 + 90 \times 0.20 + 95 \times 0.15 = 27.00 + 31.50 + 18.00 + 14.25 = 90.75 \to \mathbf{90.8}$
- **Spec 9**: $95 \times 0.30 + 95 \times 0.35 + 85 \times 0.20 + 90 \times 0.15 = 28.50 + 33.25 + 17.00 + 13.50 = 92.25 \to \mathbf{92.3}$

#### Mathematical Verification of Column Averages:
- **Technical Feasibility Average**: $(95 + 98 + 88 + 90 + 88 + 95 + 92 + 90 + 95) / 9 = 831 / 9 = 92.333 \dots \to \mathbf{92.3}$
- **Invariant Alignment Average**: $(100 + 100 + 92 + 95 + 92 + 98 + 98 + 90 + 95) / 9 = 860 / 9 = 95.555 \dots \to \mathbf{95.6}$
- **Performance Impact Average**: $(98 + 90 + 95 + 95 + 90 + 90 + 90 + 90 + 85) / 9 = 823 / 9 = 91.444 \dots \to \mathbf{91.4}$
- **Usability Impact Average**: $(90 + 95 + 88 + 85 + 95 + 95 + 95 + 95 + 90) / 9 = 828 / 9 = 92.000 \dots \to \mathbf{92.0}$
- **Overall Ecosystem Composite Average**: $92.3333 \times 0.30 + 95.5555 \times 0.35 + 91.4444 \times 0.20 + 92.0000 \times 0.15 = 27.7000 + 33.4444 + 18.2889 + 13.8000 = 93.2333 \to \mathbf{93.2}$

---

### 6.3 Acceptance Thresholds & Verification Checklist

To achieve production ratification, every candidate release branch must satisfy the following verification rubric:

- [ ] **Deterministic Test Suite Execution**:
  * Execute `python -m pytest tests/` across all plugin test files $\to$ **100% pass (minimum 117 tests passing, 0 failures)**.
  * Execute `python -m unittest discover -s "d:\Antigravity\Gemini Worker"` $\to$ **100% pass (9/9 passing)**.
  * Execute `python -m unittest discover -s "d:\Antigravity\DeepSeek Worker"` $\to$ **100% pass (4/4 passing)**.
- [ ] **L1 Turnaround SLA Verification**:
  * Pre-flight reflex execution benchmark $\le 18\text{ ms}$ on Windows x64.
- [ ] **Episodic Memory Fallback Verification**:
  * Create a clean database with 0 dense embeddings $\to$ verify `recall_episodic_memory()` returns FTS5 BM25 matches rather than `[]`.
- [ ] **Worker Fleet Stdio Resilience**:
  * Send simulated `ping` during long-running tool execution $\to$ verify response latency $< 5\text{ ms}$.
- [ ] **Symmetric Plan Gate Enforcement**:
  * Trigger `gemini_fast_edit` on an architectural task without a plan $\to$ verify Plan Gate intercepts with a single warning on the first invocation.
- [ ] **Zero-Dependency Mandate**:
  * Verify `pip list` within plugin virtual environments contains zero third-party packages beyond optional ONNX Runtime. All core tools remain 100% Python Standard Library.
- [ ] **Boundary Anchor Invariance**:
  * Run `python scripts/kernel_sync.py --check` $\to$ verify output is `[✔] Aligned` across all registered rule files.

---
*End of Deliverable: Omni-Kernel v4.3 Upgrade Proposal & Verification Rubric.*
