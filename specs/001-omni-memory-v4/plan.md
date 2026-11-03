# Implementation Plan: Omni-Memory v4.0 Production Upgrade

**Branch**: `001-omni-memory-v4` | **Date**: 2026-11-02 | **Spec**: [specs/001-omni-memory-v4/spec.md](spec.md)  
**Input**: Feature specification from `specs/001-omni-memory-v4/spec.md` and ratified `docs/rfcs/RFC-004-omni-memory-v4.md`  

---

## Summary

Omni-Memory v4.0 establishes a hierarchical Tri-Tier Cognitive Architecture for Omni-Kernel to eliminate cross-session contextual amnesia while preserving zero cloud data leakage, deterministic reproducibility, and strict sub-millisecond reflex latency. The architecture integrates:
1. **Tier 1 (L1 Reflex & Grounding)**: Pre-flight hook (`scripts/hook_runner.py`) executing in $<0.30\text{ ms}$ with 2,048-char head clamping, in-memory inverted index caching of `proven_traces.json`, and dynamic worker fleet directive injection.
2. **Tier 2 (L2 Local Hybrid Memory)**: Embedded ACID SQLite 3 database (`omni_memory.db`) with WAL mode, FTS5 BM25 with Python-level `đ/Đ` normalization, safe query sanitization (`sanitize_fts5_query`), IEEE-754 float32 vector BLOBs via host CPU ONNX Runtime (Topology A: `fastembed`), and Reciprocal Rank Fusion ($k=20$).
3. **Tier 3 (L3 Background Consolidation)**: Asynchronous daemon (`scripts/consolidator.py`) clustering session activation telemetry, promoting multi-hit solutions with automated bilingual EN/VI tags, and decaying stale memories via a bounded Ebbinghaus model ($S(t) \in [0.0, 1.0]$, 7-day grace period, permanent invariants).

---

## Technical Context

- **Runtime & Language**: Python 3.11+ (Standard Library: `sqlite3`, `json`, `re`, `hashlib`, `urllib.request`, `struct`, `math`, `time`, `os`, `sys`).
- **Primary Dependencies**:
  - *Core*: Zero external dependencies (100% Python Standard Library).
  - *Optional Acceleration*: `onnxruntime` or `fastembed` for Host CPU embeddings; automatic fallback to FTS5 BM25 lexical search when absent.
- **Storage**:
  - Embedded SQLite 3 database (`omni_memory.db`) with `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, `PRAGMA mmap_size = 268435456;`.
  - In-memory inverted index backed by `proven_traces.json` snapshot.
- **Hardware Acceleration Subsystem**:
  - *Dedicated Local AI Worker*: AMD Instinct MI50 16GB HBM2 GPU (`gfx906`) running `llama-server.exe` on `http://127.0.0.1:8080/v1` via MCP server `local_worker_mi50`.
  - *Host CPU*: Multi-core x86_64 host CPU handling Tier 2 ONNX dense embeddings (Topology A, 0 MB GPU VRAM overhead).
  - *Cloud LPU Worker*: Groq LPU cluster running `openai/gpt-oss-120b` via MCP server `groq_worker_cloud` for high-throughput cloud failover.
- **Testing Framework**: `pytest` and `unittest` with parameterized test matrices and latency benchmarks.
- **Target Platform**: Windows 11 x64 (PowerShell host environment, AppLocker-safe, ROCm Vega 20 WDDM compatibility).
- **Project Type**: Embedded Cognitive Subsystem & Agent Lifecycle Middleware.
- **Performance Goals**:
  - Tier 1 Pre-Flight Latency: $<0.30\text{ ms}$ (P99).
  - Tier 2 Lexical Search Latency: $<1.00\text{ ms}$ (P99).
  - Tier 2 End-to-End Hybrid Latency: $<15.00\text{ ms}$ (P99).
  - Tier 3 Background Consolidation: $<2,000.00\text{ ms}$ async batch.
- **Constraints**:
  - 100% Zero-Trust security: parameterized SQL queries only (`?`), automated regex credential redaction.
  - AMD Instinct MI50 VRAM headroom protection: strictly 0 MB GPU VRAM allocated to embeddings, preserving 3,741 MB headroom.
  - Stop-point requirement: no modification to production runtime files (`scripts/hook_runner.py`, `rules/AGENTS.md`) prior to human approval.

---

## Constitution Check

*GATE: All principles from `.specify/constitution.md` evaluated prior to implementation planning.*

| Constitutional Principle | Requirement Summary | Architectural Compliance Strategy | Gate Verdict |
|---|---|---|---|
| **Principle I: Sub-Millisecond L1 Reflex** | P99 latency $<0.30\text{ ms}$; 2,048-char head clamp; decoupled writes; in-memory inverted index. | Enforce $\text{prompt}[:2048]$ clamp; load `proven_traces.json` into RAM with `st_mtime` caching; buffer writes to async queue. | **PASS** |
| **Principle II: Zero-Trust Security** | Parameterized SQL (`?`); credential redaction; local-only storage; transparent cloud fallback; canonical path hashing (`os.path.normcase`). | Mandatory `sqlite3` parameter substitution; regex redaction pipeline; zero network DB sync; emit `fallback_active = true`; partition isolation via `canonical_workspace_hash()`. | **PASS** |
| **Principle III: Dual-Language Parity** | Vietnamese & English equal-fidelity; `đ/Đ` normalization; automated bilingual tags. | Python-level `fold_vietnamese()`; FTS5 diacritic stripping; consolidator dual-language tag extraction. | **PASS** |
| **Principle IV: Hardware Realism** | Topology A CPU/ONNX only; protect 3,741 MB VRAM headroom; 16k context cap; `-ub 2048`; autostart lock with 30s stale recovery. | Prohibit GPU embedding server; enforce 16k prompt cap; specify `-ub 2048`; implement `llama_autostart.lock` with 30s stale-lock recovery and 25s timeout. | **PASS** |
| **Principle V: Bounded Consolidation** | RRF $k=20$; Ebbinghaus stability $S(t) \in [0.0, 1.0]$; 7-day grace period; permanent invariants. | Implement RRF formula with $k=20$; stability decay in exponent; protect $\Delta t < 7.0\text{ days}$; enforce $\lambda_0 = 0.0$ for invariants. | **PASS** |
| **Stop-Point Invariant** | Pause for human approval; zero runtime code changes during SDD bundle phase. | SDD bundle confined exclusively to `.specify/`, `specs/`, and tests; runtime scripts untouched. | **PASS** |

---

## Performance Budgets & SLA Matrix

```
+=====================================================================================================+
|                                  OMNI-MEMORY v4.1 SLA MATRIX                                        |
+=====================================================================================================+
| Operation Tier                 | P50 Latency | P99 Latency | Max SLA  | Fallback Action             |
+--------------------------------+-------------+-------------+----------+-----------------------------+
| L1 Hook: OS Process Spawn      | 15.000 ms   | 22.000 ms   | 25.00 ms | Stdlib-only fast launch     |
| L1 Hook: Filler Suppression    | 0.005 ms    | 0.015 ms    | 1.00 ms  | Emit empty injectSteps      |
| L1 Hook: In-Memory Reflex Hit  | 0.045 ms    | 0.120 ms    | 0.30 ms  | Emit static system grounding|
| L1 Hook: Clamped 200KB Input   | 0.048 ms    | 0.135 ms    | 0.30 ms  | Truncate head to 2048 chars |
| L2 Search: Dual-Col FTS5 BM25  | 0.180 ms    | 0.400 ms    | 1.00 ms  | Title keyword fallback      |
| L2 Search: Vector Cosine Only  | 0.350 ms    | 0.750 ms    | 2.00 ms  | Omit vector; rely on BM25   |
| L2 Search: Hybrid (CPU + RRF)  | 5.200 ms    | 8.500 ms    | 12.00 ms | Fallback to FTS5 BM25       |
| L3 Consolidator: Batch Run     | 25.000 ms   | 120.000 ms  | 2000 ms  | Defer batch to next cycle   |
| MI50 Socket Ping Probe         | 1.500 ms    | 4.500 ms    | 250 ms   | Fallback to Groq LPU Cloud  |
| MI50 Cold Autostart Polling    | 12.000 s    | 18.000 s    | 25.00 s  | Fail-closed / Cloud fallback|
+=====================================================================================================+
```

---

## Architectural Risk Matrix & Mitigations

| Risk ID | Risk Description | Severity | Likelihood | Mitigation Strategy |
|---|---|---|---|---|
| **RSK-001** | Prompt size blowup causes regex evaluation in Tier 1 to exceed $<0.30\text{ ms}$ budget. | HIGH | HIGH | **Immutable 2,048-Char Clamping**: Enforce $\text{prompt}[:2048]$ at entry of `hook_runner.py`. Benchmark proves latency remains $<0.05\text{ ms}$ even on 1 MB inputs. |
| **RSK-002** | RRF $k=60$ causes rank-inversion where low-relevance dual-channel results outrank top-1 single matches. | HIGH | MEDIUM | **RRF Parameter Tuning ($k=20$)**: Mathematically proven that under $k=20$, Rank 1 ($0.02381$) strictly outranks Dual Rank 50 ($0.01429$). |
| **RSK-003** | Auxiliary GPU embedding server exhausts MI50 VRAM, triggering PCIe paging and WDDM TDR Event 4101 crashes. | CRITICAL | HIGH | **Topology A Mandate**: Prohibit GPU embedding servers. Enforce Host CPU ONNX (`intfloat/multilingual-e5-small` INT8), using 0 MB GPU VRAM and preserving 3,741 MB headroom. |
| **RSK-004** | Table-level `remove_diacritics 2` collapses distinct Vietnamese tones (`ma, má, mà, mả...`), destroying BM25 precision. | HIGH | HIGH | **Dual-Column FTS5 Architecture**: Table-level `remove_diacritics 0` with app-level `fold_vietnamese()`. Exact column weighted 10x (`bm25(fts, 10.0, 1.0) ORDER BY rank_score ASC`). |
| **RSK-005** | Technical queries containing colons, dots, hyphens, and boolean operators trigger SQLite FTS5 syntax errors. | HIGH | HIGH | **Defensive FTS5 Sanitization Pipeline**: Implement `sanitize_fts5_query()`, replacing reserved punctuation with spaces and wrapping alphanumeric tokens in quotes. |
| **RSK-006** | Ebbinghaus decay formula blows up retention strength above 1.0 or prunes newly created memories prematurely. | HIGH | MEDIUM | **Bounded Stability Formulation**: Scale memory half-life in denominator exponent $S(t) \in [0.0, 1.0]$; enforce 7-day grace period ($\Delta t \ge 7.0\text{ days}$) and $\lambda_0 = 0.0$ for invariants. |
| **RSK-007** | Concurrent subagents attempt to launch `llama-server.exe` simultaneously, or process crash leaves stale lock file causing permanent deadlock. | HIGH | MEDIUM | **Inter-Process Mutex with 30s Stale-Lock Recovery**: Guard autostart logic with `llama_autostart.lock`, 30-second stale file recovery check (auto-clears if file age > 30s), and 25-second socket polling timeout. |
| **RSK-008** | Secret credentials or private keys leaked into persistent SQLite memory or trace files. | CRITICAL | LOW | **Hardened Regex Redaction**: Automated sanitization pipeline redacting Bearer tokens, GitHub PATs, AI keys, and private keys before storage. |
| **RSK-009** | Windows path variations (differing drive case `d:\` vs `D:\`, forward vs backward slashes, trailing slashes) generate divergent MD5 hashes, fragmenting workspace partitions. | HIGH | HIGH | **Canonical Path Normalization Mandate**: Mandate `os.path.normcase(os.path.normpath(os.path.abspath(path)))` prior to MD5 hashing, guaranteeing identical `workspace_hash` values across all path representations. |
| **RSK-010** | Direct unpartitioned FTS5 queries allow memory records from one workspace to leak into another workspace during full-text search. | HIGH | MEDIUM | **Mandated Partitioned SQL Join**: Mandate that all FTS5 queries explicitly JOIN `workspace_episodic_memory e ON f.rowid = e.rowid WHERE e.workspace_hash = ?`, strictly isolating search results by workspace. |
| **RSK-011** | Multi-session write concurrency triggers `SQLITE_BUSY: database is locked` during batch consolidation or logging. | HIGH | HIGH | **Single-Writer Queue Pattern**: Memory Daemon owns exclusive dedicated writing thread draining `queue.Queue`. Commits via `BEGIN IMMEDIATE` with `PRAGMA busy_timeout = 5000;` and `PRAGMA wal_autocheckpoint = 1000;`. |
| **RSK-012** | CLI subprocess ephemeral lifecycle kills background writer threads and cold-starts ONNX (500–1200ms). | CRITICAL | HIGH | **Process Boundary Decoupling**: Process 1 (`hook_runner.py`) is ephemeral CLI (<25ms, stdlib only, stages logs to `l1_staging_log`); Process 2 (Memory Daemon) is persistent, holds ONNX resident in 120MB RAM, and owns the writer queue. |
| **RSK-013** | Omission of E5 asymmetric prefixes causes 20–30% drop in Recall@K, and English-only models destroy Vietnamese semantics. | HIGH | HIGH | **Strict Model & Prefix Invariant**: Lock `intfloat/multilingual-e5-small`. Forbid English-only models. Strictly prepend `"passage: "` on ingest and `"query: "` on search. |
| **RSK-014** | Exponential decay dominates reinforcement, causing active engineering memories to be purged during temporary developer absence. | HIGH | HIGH | **Soft-Archiving & Denominator Scaling**: Reinforcement in exponent denominator $\lambda_0 \Delta t / (1 + \alpha \ln(1+N_{\text{hits}}))$ with $\Delta t$ in days from `last_accessed_at`. When $S(t) < 0.20$, update `status = 'Archived'`, never hard-delete. Invariants versioned via `superseded_by`. |

---

## Project Structure & Layout

```text
d:\Antigravity\Skill management/
├── .specify/
│   └── constitution.md                            # SDD Constitution & Architectural Invariants
├── docs/
│   └── rfcs/
│       └── RFC-004-omni-memory-v4.md              # Ratified RFC Architectural Proposal
├── specs/
│   └── 001-omni-memory-v4/
│       ├── spec.md                                # Functional & Technical Specification
│       ├── plan.md                                # This Implementation Plan & Risk Matrix
│       ├── tasks.md                               # Granular Executable Task Checklist
│       ├── checklist.md                           # Quality & Verification Checklist
│       └── tests/
│           ├── test_tier1_reflex.py               # Tier 1 Executable Test Suite
│           ├── test_tier2_hybrid_memory.py        # Tier 2 Executable Test Suite
│           └── test_tier3_consolidation.py        # Tier 3 Executable Test Suite
└── [Target Runtime Files - Modification PAUSED pending human approval]:
    ├── rules/
    │   └── AGENTS.md                              # Rule 6 Worker Fleet Enshrinement (Future Phase)
    └── scripts/
        ├── hook_runner.py                         # Tier 1 Reflex Lifecycle Hook (Future Phase)
        ├── memory_engine.py                       # Tier 2 SQLite Hybrid Search Engine (Future Phase)
        ├── consolidator.py                        # Tier 3 Background Consolidator (Future Phase)
        └── migrate_v3_to_v4.py                    # Legacy Migration Utility (Future Phase)
```

---

## Phased Implementation Roadmap & Dependency Graph

```
+=========================================================================================+
|                             SDD IMPLEMENTATION ROADMAP                                  |
+=========================================================================================+
|                                                                                         |
|  [Phase 1: Setup & Scaffolding]                                                         |
|  ├── T001: Initialize SDD directories and config                                        |
|  ├── T002: Create shared test fixtures & helpers (conftest)                             |
|  └── T003: Verify AppLocker compliance and Python stdlib baseline                       |
|         │                                                                               |
|         ▼                                                                               |
|  [Phase 2: Foundational (Blocking Prerequisites)]                                       |
|  ├── T004: Implement DDL schemas & WAL pragma configuration                             |
|  ├── T005: Implement fold_vietnamese() utility                                       |
|  ├── T006: Implement sanitize_fts5_query() defensive pipeline                           |
|  ├── T007: Implement Zero-Trust secret redaction regex filter                           |
|  └── T008: Implement autostart file mutex (llama_autostart.lock)                        |
|         │                                                                               |
|         ├───────────────────────────────┬───────────────────────────────┐               |
|         ▼                               ▼                               ▼               |
|  [Phase 3: User Story 1 (P1)]    [Phase 4: User Story 2 (P2)]    [Phase 5: User Story 3 (P3)]
|  Tier 1 Reflex & Grounding      Tier 2 Hybrid Memory (SQLite)   Tier 3 Background Consolidator
|  ├── T009: P1 Pytest Suite      ├── T016: P2 Pytest Suite       ├── T023: P3 Pytest Suite
|  ├── T010: 2,048-char clamp     ├── T017: FTS5 BM25 Engine      ├── T024: Batch Event Ingest
|  ├── T011: Filler suppression   ├── T018: Topology A CPU Embed  ├── T025: Pattern Promotion
|  ├── T012: In-memory cache      ├── T019: Vector Dot Product    ├── T026: Bilingual Tag Gen
|  ├── T013: Worker fleet inject  ├── T020: RRF k=20 Score Fusion ├── T027: Bounded Decay S(t)
|  ├── T014: Decouple disk I/O    ├── T021: Workspace Partition   ├── T028: 7-day Grace Prune
|  └── T015: P1 Benchmark Check   └── T022: P2 Benchmark Check    └── T029: WAL Vacuum Compact
|         │                               │                               │               |
|         └───────────────────────────────┴───────────────────────────────┘               |
|                                         │                                               |
|                                         ▼                                               |
|  [Phase 6: Polish, Integration & Convergence]                                           |
|  ├── T030: Execute Full Cross-Tier Pytest Suite                                         |
|  ├── T031: Author Migration Script (scripts/migrate_v3_to_v4.py)                        |
|  ├── T032: Verify Zero Cloud Leakage & Zero-Trust Invariants                            |
|  ├── T033: Update rules/AGENTS.md with Rule 6 Fleet Directives                          |
|  └── T034: Perform Spec-Code Convergence Verification                                   |
+=========================================================================================+
```

---

## Complexity Tracking

| Potential Deviation / Complexity | Justification | Simpler Alternative Rejected Because |
|---|---|---|
| Host CPU ONNX Runtime (`fastembed`) | Required for dense semantic similarity when lexical keywords differ. | Dedicated GPU server (`llama-server`) rejected because 2,500 MB VRAM footprint triggers WDDM TDR Event 4101 crashes. |
| Python-level `đ/Đ` normalization | SQLite `unicode61 remove_diacritics 2` classifies `đ` as Latin consonant with stroke, not diacritic. | Custom C SQLite tokenizer extension rejected because it violates zero-dependency AppLocker-safe standard. |
| Reciprocal Rank Fusion ($k=20$) | Eliminates rank inversion where bottom dual-channel results beat top-1 single matches. | Min-Max score normalization rejected because BM25 and cosine scores have non-comparable unbounded distributions. |
| Two-tier in-memory cache index | Required to meet $<0.30\text{ ms}$ L1 pre-flight latency budget. | Direct SQLite querying rejected because SQLite process invocation overhead exceeds 1.5ms. |
