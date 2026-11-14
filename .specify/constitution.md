# Omni-Kernel & Omni-Memory v4.3 Constitution

<!--
  Sync Impact Report:
  - Version: 4.3.0 (Ratified Architectural Invariants)
  - Scope: Omni-Kernel Tri-Tier Cognitive Architecture, Hardware Fleet & Memory Management
  - Ratification Date: 2026-11-02
  - Principles Enshrined: Principles I through V, Governance & SemVer Policies
-->

## Core Principles

### Principle I: Sub-Millisecond Pre-Flight Reflex & Process Boundary Decoupling
1. **Algorithmic Latency Ceiling & Turn SLA**: The Tier 1 lifecycle hook (`scripts/hook_runner.py`) MUST complete internal prompt grounding and in-memory cache recall in strictly under **0.30 milliseconds (300 µs)**, and total CLI subprocess turnaround time MUST remain under **25.0 milliseconds**.
2. **Strict Two-Process Boundary Invariant**:
   - **Process 1 (`hook_runner.py` - Ephemeral CLI Subprocess, <25ms, 100% Python Stdlib)**: Executes token/Jaccard matching only. Strict prohibition against importing `onnxruntime`, `fastembed`, or native C++ libraries. Writes telemetry only to unindexed staging table `l1_staging_log` with `PRAGMA synchronous = NORMAL;` or pushes non-blocking payload via loopback socket to Memory Daemon.
   - **Process 2 (Memory Daemon / MCP Worker - Persistent Long-Lived Process)**: Holds `google/embeddinggemma-2-omni` (INT8 ONNX MRL 256d) resident in ~260MB System RAM (0ms cold start). Exclusively owns the Single-Writer Queue (`queue.Queue`) and dedicated writer thread, committing all database writes via `BEGIN IMMEDIATE` with `PRAGMA busy_timeout = 5000;` and `PRAGMA wal_autocheckpoint = 1000;`.
3. **2,048-Character Input Clamping Invariant**: To guarantee zero latency violations on massive prompts (build logs, git diffs, stack traces), Tier 1 tokenization and regex evaluation MUST clamp input to the first **2,048 characters**:
   $$\text{Input}_{\text{tokenized}} = \text{prompt}[:2048]$$
4. **Decoupled Asynchronous Telemetry**: The Tier 1 fast-path MUST NEVER perform synchronous blocking disk I/O or multi-statement FTS5 transactions.
5. **MTime-Validated In-Memory Caching**: `proven_traces.json` MUST be maintained in memory as an inverted index (`token -> trace_ids`) and reloaded only upon detected filesystem timestamp modification (`st_mtime`).

### Principle II: Local-First Confidentiality & Zero-Trust Security
1. **Mandatory Parameterized SQL Invariant**: All SQLite database queries, inserts, and updates across all tiers MUST use parameterized SQL (`?` placeholders in Python `sqlite3`). String formatting (`f"..."`, `format()`, `%s`) on database cursors is strictly prohibited.
2. **Hardened Credential Redaction**: All prompts, code snippets, stack traces, and metadata MUST pass through an automated regex sanitization filter prior to entering SQLite persistence (`omni_memory.db`) or procedural cache (`proven_traces.json`). Redaction targets include Bearer tokens, GitHub PATs (`ghp_`, `github_pat_`), AI provider keys (`gsk_`, `sk-proj-`, `sk-ant-`), private keys (RSA/EC/OPENSSH/PKCS#8), and unquoted `.env` secrets.
3. **Local-Only Storage Boundary**: Under no circumstances may episodic memory records, workspace decisions, or traces be transmitted to external cloud databases. All state remains strictly on local storage.
4. **Transparent Cloud Worker Telemetry**: When Cloud Worker Fleet members are invoked (`gemini_worker_cloud`, `deepseek_worker_cloud`), the response payload MUST transparently report `model_used` and execution metadata. Masking cloud model identities or silently failing is strictly prohibited.

### Principle III: Dual-Language Parity (Vietnamese & English) & Model Mandate
1. **Dual-Column FTS5 Architecture**: SQLite FTS5 table tokenization MUST use `tokenize = 'unicode61 remove_diacritics 0'` to preserve 100% Vietnamese tonal precision. Diacritic folding MUST occur at the application layer via `fold_vietnamese()`, storing unaccented text in `content_folded` and raw text in `content_exact`. BM25 queries MUST weight exact matches 10x over folded matches (`bm25(episodic_fts, 10.0, 1.0) ORDER BY rank_score ASC`).
2. **Vietnamese Consonant Stroke Normalization (`đ/Đ` $\rightarrow$ `d/D`)**: `fold_vietnamese()` MUST explicitly replace `đ/Đ` before Unicode NFD decomposition, ensuring 100% orthographic recall between unaccented and accented terms.
3. **Dense Model Mandate & Prohibition of English-Only Models**: Dense vector embeddings MUST use `google/embeddinggemma-2-omni` (Fine-Tuned Quantized INT8 ONNX, MRL 256 dimensions). English-only models (including `bge-small-en-v1.5`) are STRICTLY PROHIBITED due to severe subword fragmentation on Vietnamese text.
4. **Asymmetric Embedding Prefixes**: Embeddings MUST strictly enforce asymmetric prefixes: `"title: none | text: " + text` for stored memories and `"task: search result | query: " + prompt` for search queries. Omitting prefixes is an architectural violation.
5. **Automated Bilingual Tag Generation**: Tier 3 consolidation MUST automatically extract dual-language keyword pairs into `bilingual_tags` for all promoted traces.

### Principle IV: Cloud Worker Fleet & System Resource Invariants
1. **Serving Topology Mandate (Topology A CPU/ONNX)**: Dense vector generation for Tier 2 MUST execute on the host CPU using ONNX Runtime (`onnxruntime` + `tokenizers`), consuming 0 MB GPU VRAM.
2. **Cloud Worker Fleet Division of Labor**:
   - Fast edits, unit test synthesis, closed-loop self-healing verification, large-context codebase generation (1M context), multimodal vision, and deep reasoning: `gemini_worker_cloud` (Google Gemini 3.5 Flash-Lite / 3.8 Flash / 4 Argon).
   - Independent specification & diff verification gatekeeping: `deepseek_worker_cloud` (DeepSeek-V4.1-Flash).
   - Zero-Context Leaking: Always pass `save_to_path` / `file_path` for file generation and edits.
3. **Decommissioning of Legacy Local & Groq Workers**: Legacy local GPU workers (`local_worker_mi50`) and rate-limited `groq_worker_cloud` are permanently decommissioned. All code/test synthesis, edits, and autonomous verification loops run through `gemini_worker_cloud` + `deepseek_worker_cloud`.
4. **Process Mutex & AppLocker Compliance**: Background daemons and CLI workers MUST adhere to Windows AppLocker and Software Restriction Policies without spawning unmonitored external server processes.

### Principle V: Mathematically Bounded Memory Consolidation & Soft-Archiving
1. **Reciprocal Rank Fusion Smoothing ($k=20$)**: Multi-channel hybrid retrieval combining BM25 lexical rank and dense vector cosine similarity MUST use RRF with smoothing constant $k=20$:
   $$\text{RRF}(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{w_m}{20 + \text{rank}_m(d)}$$
   $k=60$ is strictly prohibited as it causes rank-inversion anomalies where rank #50 dual-channel noise outranks rank #1 single-channel matches.
2. **Bounded Ebbinghaus Memory Stability Decay**: Non-invariant episodic memories MUST decay according to the stability formulation:
   $$S(t) = S_0 \cdot \exp\left(-\frac{\lambda_0 \cdot \Delta t}{1 + \alpha \ln(1 + N_{\text{hits}})}\right)$$
   guaranteeing $S(t) \in [0.0, 1.0]$ across all parameters without amplitude blowup.
3. **Elapsed Time Metric ($\Delta t$)**: $\Delta t$ MUST be computed in Days as a floating point value from `last_accessed_at` ($\Delta t = (t_{\text{now}} - t_{\text{last\_accessed}})/86400.0$). Computing $\Delta t$ from `created_at` or in seconds/milliseconds is strictly prohibited. Constants are locked to $S_0 = 1.0$, $\lambda_0 = 0.08\text{ day}^{-1}$, $\alpha = 1.5$.
4. **Soft-Archiving Invariant (No Hard Deletes)**: A record is pruned when $S(t) < 0.20$ AND $\Delta t \ge 7.0\text{ days}$ AND `memory_type != 'invariant'`. Pruning MUST set `status = 'Archived'`. Hard SQL `DELETE` is prohibited. Active vector scans ONLY load `WHERE status = 'Active'`. Archived records are awakened upon FTS5/deep_recall access.
5. **Permanent Invariant Versioning**: Permanent invariants have $\lambda_0 = 0.0 \implies S(t) \equiv 1.0$. When an invariant is superseded by an updated rule, the old record MUST be updated to `status = 'Superseded'`, `superseded_by = new_memory_id` to eliminate Context Schizophrenia.

---

## Additional Constraints & Non-Negotiables

### Zero-Dependency Architectural Baseline
- Core runtime components (`hook_runner.py`, `consolidator.py`, SQLite engine) MUST operate using the Python 3.11+ Standard Library (`sqlite3`, `json`, `re`, `hashlib`, `urllib`, `time`, `os`, `sys`).
- Optional extensions (`onnxruntime`, `fastembed`) MUST degrade gracefully to FTS5 BM25 lexical search when absent.
- The system MUST remain 100% compliant with Windows AppLocker and Software Restriction Policies.

### Stop-Point & Human Approval Gate
- No implementation task or modification to production runtime code (`scripts/hook_runner.py`, `rules/AGENTS.md`) may be executed until the complete Spec Kit SDD bundle is reviewed and approved by stakeholders.

---

## Governance

1. **Precedence**: This Constitution supersedes all other documentation, specifications, implementation plans, and agent instructions. Any architectural plan or pull request that violates these principles MUST be rejected.
2. **Amendments**: Amending this Constitution requires:
   - A formal RFC submitted to the Omni-Kernel Architecture Council.
   - Comprehensive justification demonstrating why existing principles cannot accommodate the requirement.
   - 100% passing results on all regression and performance benchmark suites.
3. **Semantic Versioning Policy**:
   - **MAJOR (X.0.0)**: Incompatible principle removals or foundational governance shifts.
   - **MINOR (x.Y.0)**: Addition of new principles, sections, or materially expanded architectural guidance.
   - **PATCH (x.y.Z)**: Non-semantic clarifications, typographical fixes, and wording refinements.

---

**Version**: 4.3.0 | **Ratified**: 2026-11-02 | **Last Amended**: 2026-11-13
