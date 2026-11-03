# Feature Specification: Omni-Memory v4.0 Production Upgrade

**Feature Branch**: `001-omni-memory-v4`  
**Created**: 2026-11-02  
**Status**: Draft (Ratified Architecture)  
**Input**: ORIGINAL_REQUEST.md, RFC-004-omni-memory-v4.md, survey_report.md  

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Sub-Millisecond L1 Reflex Grounding & Active Trace Cache (Priority: P1) 🎯 MVP

As an autonomous agent interacting with the Omni-Kernel orchestrator, I want my pre-flight invocation hook to instantly ground me with active local hardware capabilities and recalled verified fixes in strictly under 0.3ms, so that I never suffer from cross-session amnesia or waste expensive cloud tokens on problems already solved.

**Why this priority**: L1 reflex is the critical front-line defense. It executes synchronously before every LLM generation turn. If L1 is fast (<0.3ms) and accurate, it eliminates repetitive cognitive overhead and establishes immediate situational awareness with zero perceptible delay.

**Independent Test**: Can be verified independently by feeding known problem signatures and massive context payloads into `hook_runner.process_hook()`; verify that verified solutions and active hardware fleet directives (`local_worker_mi50`, `groq_worker_cloud`) are formatted into `injectSteps` in strictly $<0.30\text{ ms}$ (P99).

**Acceptance Scenarios**:

1. **Scenario 1.1 (Exact Procedural Match Recall)**:
   - **Given** an in-memory procedural cache indexed with trace `"Docker port already in use"`,
   - **When** user input arrives stating `"Port 8080 is already allocated: bind address in use"`,
   - **Then** the L1 reflex returns `injectSteps` containing the verified fix (`fuser -k 8080/tcp`) and hardware fleet directives in $<0.30\text{ ms}$.

2. **Scenario 1.2 (2,048-Character Head Clamping on Massive Context)**:
   - **Given** a developer prompt containing a 100 KB compiler stack trace and git diff,
   - **When** `hook_runner.py` evaluates the input,
   - **Then** input tokenization clamps to the first 2,048 characters, preventing regex blowup and keeping execution latency $<0.30\text{ ms}$.

3. **Scenario 1.3 (Conversational Filler Suppression)**:
   - **Given** a user input consisting only of conversational filler (e.g., `"ok"`, `"okay"`, `"tiếp tục"`, `"done"`, `"thanks"`, `"cảm ơn"`, `"yes"`, `"no"`, `"got it"`, `"sure"`),
   - **When** `hook_runner.py` evaluates the input against full-sentence pattern `r"^(ok|okay|tiếp tục|thanks|cảm ơn|yes|no|got it|sure)[.!\s]*$"`,
   - **Then** full injection is suppressed and an empty `{"injectSteps": []}` payload is emitted in $<1.0\text{ ms}$ to avoid context bloat; conversely, substantive developer prompts starting with filler words (e.g. `"ok, please fix this docker error"`) are NOT suppressed.

4. **Scenario 1.4 (Worker Fleet Directive Formatting)**:
   - **Given** an incoming technical coding prompt,
   - **When** the pre-flight hook executes,
   - **Then** the injected markdown context explicitly specifies `local_worker_mi50` for tactical implementation (`execute_code_task`, `fast_edit`, `generate_tests`) with micro-batch limit `-ub 2048` and single-prompt context cap of 16,000 tokens.

---

### User Story 2 - Local Hybrid Semantic & Episodic Memory (Priority: P2)

As a developer or autonomous agent working across multiple sessions, I want rich architectural decisions, workspace invariants, and past debugging solutions indexed in an embedded SQLite database with hybrid BM25 and vector retrieval, so that complex semantic and bilingual queries accurately recall relevant context in $<15\text{ ms}$.

**Why this priority**: Beyond exact keyword traces, agents need to discover conceptual workspace invariants (e.g. "Windows PowerShell requires semicolon chaining, not `&&`") and bilingual Vietnamese/English notes even when exact wording differs.

**Independent Test**: Can be verified independently by inserting episodic records into SQLite (`omni_memory.db`), generating dense vectors via host CPU ONNX (`fastembed`), and executing hybrid queries combining FTS5 BM25 with vector cosine similarity; verify that reciprocal rank fusion ($k=20$) retrieves top-1 relevant records in $<15\text{ ms}$ and unaccented Vietnamese queries match accented records with 100% precision.

**Acceptance Scenarios**:

1. **Scenario 2.1 (Bilingual FTS5 Search with Consonant Normalization)**:
   - **Given** a workspace episodic record stored with title `"Kiến trúc bộ nhớ đa tầng"` containing the stroked consonant `đ`,
   - **When** an unaccented query `"kien truc bo nho da tang"` is submitted to FTS5,
   - **Then** `fold_vietnamese()` maps `đ/Đ` to `d/D` and strips combining diacritics via Unicode NFD, producing a rank-1 lexical match with BM25 score.

2. **Scenario 2.2 (FTS5 Query Sanitization & Syntax Resilience)**:
   - **Given** a complex technical query containing reserved punctuation and operators (e.g. `http://127.0.0.1:8080 OR NOT NULL AND syntax error:`),
   - **When** `sanitize_fts5_query()` sanitizes the input prior to `MATCH` evaluation,
   - **Then** all reserved operators and punctuation are safely sanitized, executing without throwing `sqlite3.OperationalError`.

3. **Scenario 2.3 (Dense Vector Cosine Similarity & Partition Filtering)**:
   - **Given** 1,000 dense embedding records in `dense_embeddings` partitioned by `workspace_hash`,
   - **When** a 384-dimensional query vector is compared against workspace candidates,
   - **Then** partitioned cosine similarity evaluates in $<0.50\text{ ms}$ using precomputed vector norms and IEEE-754 float32 dot products.

4. **Scenario 2.4 (Reciprocal Rank Fusion k=20 Rank-Inversion Elimination)**:
   - **Given** Candidate A ranked #1 in Lexical BM25 (absent from Vector top-50) and Candidate B ranked #50 in both Lexical and Vector channels,
   - **When** RRF score fusion is calculated using $k=20$:
     $$\text{Score}(A) = \frac{0.5}{20 + 1} \approx 0.02381, \quad \text{Score}(B) = \frac{0.5}{70} + \frac{0.5}{70} \approx 0.01429$$
   - **Then** Candidate A strictly outranks Candidate B, eliminating the rank-inversion anomaly present when $k=60$.

5. **Scenario 2.5 (Offline Vector Fallback Graceful Degradation)**:
   - **Given** the local ONNX embedding engine is unavailable or disabled,
   - **When** a hybrid search is initiated,
   - **Then** the engine degrades gracefully to pure FTS5 BM25 lexical search in $<1.0\text{ ms}$ using partitioned SQL join `WHERE e.workspace_hash = ?` without throwing unhandled exceptions.

6. **Scenario 2.6 (FTS5 Cross-Workspace Partition Isolation)**:
   - **Given** episodic memories stored across multiple workspaces in `workspace_episodic_memory` and indexed in `episodic_fts`,
   - **When** an agent in Workspace B executes an FTS5 BM25 query,
   - **Then** the query strictly executes a partitioned JOIN `workspace_episodic_memory e ON f.rowid = e.rowid WHERE e.workspace_hash = ?`, returning only Workspace B's records and eliminating cross-workspace data leakage.

---

### User Story 3 - Asynchronous Background Consolidation & Memory Telemetry (Priority: P3)

As a maintainer of the Omni-Kernel runtime, I want an autonomous background consolidation daemon (`consolidator.py`) that periodically clusters session activation events, promotes frequent solutions to durable traces with bilingual tags, reinforces skill affinities, and decays obsolete memories using a bounded Ebbinghaus model, so that memory stays lean, relevant, and free of cognitive clutter without blocking active agents.

**Why this priority**: Without consolidation and pruning, episodic memory accumulates obsolete traces, leading to database bloat and decreased retrieval precision. Consolidation operates asynchronously to maintain long-term memory health.

**Independent Test**: Can be verified independently by populating `activation_events` with staged session histories, running `consolidator.py`, and asserting that multi-hit solutions ($\ge 2$ successes) are promoted to `workspace_episodic_memory` and `proven_traces.json`, skill affinities are reinforced, and records past 7 days with stability $<0.20$ are pruned while invariants ($\lambda_0=0$) are permanently preserved.

**Acceptance Scenarios**:

1. **Scenario 3.1 (Batch Ingestion & Idempotent Processing)**:
   - **Given** 150 pending records in `activation_events` with `is_consolidated = 0`,
   - **When** `consolidator.py` executes a batch consolidation cycle,
   - **Then** 100 records are ingested, consolidated, and marked `is_consolidated = 1` using parameterized SQL; running a second time processes remaining pending records without duplicating promotions.

2. **Scenario 3.2 (Pattern Promotion with Automated Bilingual Tags)**:
   - **Given** an intent cluster with $\ge 2$ successful executions for `"Docker port bind address conflict"`,
   - **When** Tier 3 consolidation promotes the cluster,
   - **Then** a new record is created in `workspace_episodic_memory` with `memory_type = 'proven_trace'`, automated bilingual tags (`"port conflict, xung dot cong, loi cong dang dung"`), and synchronized to `proven_traces.json`.

3. **Scenario 3.3 (Mathematically Bounded Ebbinghaus Stability Decay)**:
   - **Given** non-invariant memories with varying activation counts $N_{\text{hits}}$ and base confidences $S_0 \in [0.0, 1.0]$,
   - **When** stability $S(t) = S_0 \cdot \exp\left(-\frac{\lambda_0 \Delta t}{1 + 1.5\ln(1 + N_{\text{hits}})}\right)$ is evaluated,
   - **Then** $S(t)$ strictly remains within $[0.0, 1.0]$ for all parameter values, never blowing up above 1.0.

4. **Scenario 3.4 (7-Day Grace Period Protection & Invariant Permanence)**:
   - **Given** a new episodic memory with initial confidence $S_0 = 0.15$ created 3 days ago ($\Delta t = 3.0$) and an invariant record with $\lambda_0 = 0.0$ created 300 days ago,
   - **When** the pruning evaluation executes,
   - **Then** the 3-day-old record is protected by the 7-day grace period ($\Delta t < 7.0$), the invariant record remains at $S(t) = 1.0$ permanently, and only non-invariant records with $S(t) < 0.20$ AND $\Delta t \ge 7.0$ are pruned.

---

### Edge Cases & Failure Modes

- **EC-001 (Empty or Whitespace-Only Prompts)**: `hook_runner.py` receives `""` or `"\n\t  "`. Output: Returns `{"injectSteps": []}` with exit code 0; zero exceptions raised.
- **EC-002 (Corrupted JSON or Non-UTF8 Stdin)**: Stdin provides malformed JSON or invalid byte sequences. Output: Caught in top-level handler, logs error to stderr, returns valid fallback JSON `{"injectSteps": []}`.
- **EC-003 (SQLite Concurrency Collision / WAL Lock)**: Consolidator writes to SQLite while agent reads. Output: WAL mode enables simultaneous reader/writer access; `busy_timeout = 5000` eliminates `SQLITE_BUSY` errors.
- **EC-004 (FTS5 Syntax Bombs)**: Query contains unmatched quotes, single punctuation, or boolean strings like `NOT`, `AND`, `*`. Output: `sanitize_fts5_query()` scrubs punctuation, eliminates boolean operators, and wraps tokens in quotes (`"token"`), ensuring zero syntax crashes.
- **EC-005 (Clock Skew / Future Timestamps)**: System clock is set back, causing $t_{\text{now}} < t_{\text{last\_accessed}}$. Output: $\Delta t$ calculation clamps negative values: $\Delta t = \max(0.0, t_{\text{now}} - t_{\text{last\_accessed}})$.
- **EC-006 (Secret Leaks in Prompts)**: User prompt contains raw AWS secrets, GitHub PATs, or RSA private keys. Output: Regex pipeline redacts secrets to `[REDACTED_SECRET]` before persistence or trace storage.
- **EC-007 (Local MI50 Server Unresponsive)**: `127.0.0.1:8080` times out on socket probe. Output: Transparent fallback to `groq_worker_cloud` emitting `fallback_active = true` and `model_used = "openai/gpt-oss-120b (Groq Fallback)"`.
- **EC-008 (Inter-Process Mutex Stale Lock on llama_autostart.lock)**: A prior crashed process leaves `llama_autostart.lock` on disk. Output: `acquire_lock_with_stale_recovery()` checks `time.time() - os.path.getmtime(lock_path) > 30.0`. If file age exceeds 30.0s, the stale lock is automatically cleared and re-acquired atomically, preventing permanent daemon deadlock.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST implement Tier 1 pre-flight reflex hook in `scripts/hook_runner.py` executing in $<0.30\text{ ms}$ for in-memory procedural cache hits.
- **FR-002**: The system MUST enforce the 2,048-character head clamping invariant ($\text{prompt}[:2048]$) before evaluating tokenization or regex patterns in Tier 1.
- **FR-003**: The system MUST suppress pre-flight injection on conversational filler phrases matching full-sentence pattern `r"^(ok|okay|tiếp tục|thanks|cảm ơn|yes|no|got it|sure)[.!\s]*$"`, returning empty injection in $<1.0\text{ ms}$, while guaranteeing prompts with substantive instructions following a filler prefix (e.g. `"ok, please fix this docker error"`) are NOT suppressed.
- **FR-004**: The system MUST dynamically inject active hardware grounding into agent context, specifying `local_worker_mi50` (AMD Instinct MI50, `-ub 2048`, 16k context cap) and `groq_worker_cloud`.
- **FR-005**: The system MUST instantiate SQLite database `omni_memory.db` with WAL journal mode (`PRAGMA journal_mode = WAL`), memory-mapped I/O (`PRAGMA mmap_size = 268435456`), and foreign key enforcement.
- **FR-006**: The system MUST normalize Vietnamese diacritics via `fold_vietnamese()` mapping `đ/Đ` to `d/D` and decomposing combining marks via Unicode NFD before indexing and querying SQLite FTS5 table `episodic_fts`.
- **FR-007**: The system MUST sanitize all user queries via `sanitize_fts5_query()` before FTS5 `MATCH` execution, removing reserved punctuation and boolean keywords.
- **FR-008**: The system MUST generate dense vector embeddings using host CPU ONNX Runtime (Topology A: `fastembed`), strictly consuming 0 MB of GPU VRAM. Topology B on GPU is prohibited.
- **FR-009**: The system MUST combine lexical BM25 and dense vector cosine similarity using Reciprocal Rank Fusion with smoothing constant $k = 20$.
- **FR-010**: The system MUST provide an asynchronous background consolidation daemon (`scripts/consolidator.py`) that processes `activation_events` in batches of up to 100 records.
- **FR-011**: The system MUST automatically extract bilingual EN/VI keyword tags and promote multi-hit problem-fix patterns ($\ge 2$ successes) to `workspace_episodic_memory` and `proven_traces.json`.
- **FR-012**: The system MUST compute Ebbinghaus stability retention $S(t) \in [0.0, 1.0]$, enforce a 7-day grace period ($\Delta t \ge 7.0\text{ days}$) before pruning, and guarantee permanent retention ($S(t) \equiv 1.0$) for records with `memory_type = 'invariant'`.
- **FR-013**: The system MUST mandate that all FTS5 BM25 search queries explicitly JOIN `workspace_episodic_memory e ON f.rowid = e.rowid WHERE e.workspace_hash = ?` to strictly isolate memories by workspace partition and eliminate cross-workspace data leakage.
- **FR-014**: The system MUST derive `workspace_hash` by canonicalizing the workspace path via `os.path.normcase(os.path.normpath(os.path.abspath(path)))` prior to MD5 hashing, ensuring case-insensitive Windows drive letters (`d:\` vs `D:\`) and mixed slashes generate identical partition hashes.

---

### Non-Functional Requirements

- **NFR-001 (L1 Algorithmic Latency)**: P99 execution latency of `hook_runner.process_hook()` MUST remain $<0.30\text{ ms}$ on standard x86_64 host hardware.
- **NFR-002 (L2 Hybrid Retrieval Latency)**: End-to-end hybrid search latency (CPU embedding + FTS5 + vector dot product + RRF) MUST remain $<15.0\text{ ms}$ across 10,000 indexed records; pure lexical search MUST remain $<1.0\text{ ms}$.
- **NFR-003 (Zero-Trust Security & SQL Injection Immunity)**: All database interactions MUST strictly utilize parameterized SQL queries (`?` placeholders). String interpolation on cursors is strictly prohibited. Secrets MUST be sanitized prior to persistence.
- **NFR-004 (Zero-Dependency Standard Library Baseline)**: Core memory engine MUST execute using only Python 3.11+ Standard Library (`sqlite3`, `json`, `re`, `hashlib`, `urllib`, `time`, `os`, `sys`). External packages are strictly optional with automatic fallback.
- **NFR-005 (Physical VRAM Headroom Protection)**: The memory subsystem MUST NOT allocate GPU VRAM, leaving all 3,741 MB of available VRAM headroom on the AMD Instinct MI50 GPU for prompt prefill batches and desktop compositing.
- **NFR-006 (Zero Cloud Data Leakage)**: Episodic memories, workspace paths, and user source code MUST remain 100% on local disk; cloud storage sync is prohibited.

---

### Data Model & SQLite DDL Specification

```sql
-- ============================================================================
-- OMNI-MEMORY v4.0 PRODUCTION DDL SCHEMA
-- Embedded Storage: omni_memory.db
-- Pragmas: WAL mode, Normal Synchronous, 64MB Cache, 256MB MMAP
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Table 1: system_capabilities
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_capabilities (
    capability_id       TEXT PRIMARY KEY,            -- e.g. 'skill:spec-driven-development'
    name                TEXT NOT NULL,               -- Canonical name
    version             TEXT NOT NULL DEFAULT '1.0.0',
    capability_type     TEXT NOT NULL,               -- 'skill', 'mcp_server', 'mcp_tool', 'rule'
    source_type         TEXT NOT NULL,               -- 'builtin', 'plugin', 'workspace', 'synthesized'
    file_path           TEXT NOT NULL,               -- Absolute path to definition
    description         TEXT NOT NULL,
    trigger_tokens      TEXT NOT NULL,               -- JSON array of keyword strings
    bilingual_tags      TEXT NOT NULL,               -- JSON array of EN/VI tags
    affinity_score      REAL NOT NULL DEFAULT 1.0,   -- Dynamic learned weight (0.1 - 5.0)
    total_activations   INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL,               -- ISO-8601 UTC
    updated_at          TEXT NOT NULL                -- ISO-8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_cap_type_source ON system_capabilities(capability_type, source_type);
CREATE INDEX IF NOT EXISTS idx_cap_affinity ON system_capabilities(affinity_score DESC);

-- ----------------------------------------------------------------------------
-- Table 2: workspace_episodic_memory
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_episodic_memory (
    memory_id           TEXT PRIMARY KEY,            -- UUID v4 or SHA-256
    workspace_hash      TEXT NOT NULL,               -- MD5 hash of canonical workspace path: os.path.normcase(os.path.normpath(os.path.abspath(path)))
    workspace_path      TEXT NOT NULL,               -- Canonical workspace root path
    memory_type         TEXT NOT NULL,               -- 'invariant', 'architecture_decision', 'proven_trace', 'user_preference'
    title               TEXT NOT NULL,               -- Compact summary headline
    problem_signature   TEXT,                        -- Problem statement, regex, or error string
    solution_payload    TEXT NOT NULL,               -- Code snippet, shell command, or architectural rule
    context_metadata    TEXT,                        -- JSON: tool used, language, exit code, parameters
    bilingual_tags      TEXT,                        -- Comma-separated EN/VI tags
    content_folded      TEXT NOT NULL,               -- App-level fold_vietnamese(title + ' ' + problem_signature + ' ' + solution_payload + ' ' + tags)
    status              TEXT NOT NULL DEFAULT 'Active', -- 'Active', 'Archived', 'Superseded'
    superseded_by       TEXT,                        -- memory_id of newer replacement rule (for invariant versioning)
    activation_count    INTEGER NOT NULL DEFAULT 1,  -- Access reinforcement count
    confidence_score    REAL NOT NULL DEFAULT 1.0,   -- Initial quality metric (0.0 - 1.0)
    decay_rate          REAL NOT NULL DEFAULT 0.08,  -- Ebbinghaus lambda in day^-1 (0.0 = permanent invariant)
    last_accessed_at    TEXT NOT NULL,               -- ISO-8601 UTC timestamp
    created_at          TEXT NOT NULL                -- ISO-8601 UTC timestamp
);

CREATE INDEX IF NOT EXISTS idx_mem_workspace_type ON workspace_episodic_memory(workspace_hash, memory_type);
CREATE INDEX IF NOT EXISTS idx_mem_status ON workspace_episodic_memory(status);
CREATE INDEX IF NOT EXISTS idx_mem_last_accessed ON workspace_episodic_memory(last_accessed_at DESC);
CREATE INDEX IF NOT EXISTS idx_mem_confidence ON workspace_episodic_memory(confidence_score DESC);

-- ----------------------------------------------------------------------------
-- Table 3: dense_embeddings
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dense_embeddings (
    memory_id           TEXT PRIMARY KEY,            -- FK -> workspace_episodic_memory(memory_id)
    workspace_hash      TEXT NOT NULL,               -- Partition key for isolated workspace filtering
    model_name          TEXT NOT NULL,               -- e.g. 'intfloat/multilingual-e5-small' (INT8 quantized, 384 dim)
    dimensions          INTEGER NOT NULL DEFAULT 384,-- Dimension count: 384
    vector_blob         BLOB NOT NULL,               -- IEEE-754 float32 binary buffer (384 * 4 = 1536 bytes)
    norm                REAL NOT NULL,               -- Precomputed L2 Euclidean norm
    updated_at          TEXT NOT NULL,               -- ISO-8601 UTC timestamp
    FOREIGN KEY(memory_id) REFERENCES workspace_episodic_memory(memory_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_emb_workspace ON dense_embeddings(workspace_hash, model_name);
CREATE INDEX IF NOT EXISTS idx_emb_model ON dense_embeddings(model_name);

-- ----------------------------------------------------------------------------
-- Table 4: episodic_fts (FTS5 Dual-Column Virtual Table)
-- ----------------------------------------------------------------------------
-- SQLite FTS5 requires table-level tokenization. To preserve Vietnamese precision
-- without losing unaccented matches, we employ application-level diacritic folding
-- into content_folded while preserving 100% exact diacritics in content_exact.
CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(
    content_exact,
    content_folded,
    tokenize = 'unicode61 remove_diacritics 0'
);

-- Triggers for Automatic Synchronous FTS5 Maintenance with rowid Alignment
CREATE TRIGGER IF NOT EXISTS trg_episodic_after_insert AFTER INSERT ON workspace_episodic_memory
BEGIN
    INSERT INTO episodic_fts(rowid, content_exact, content_folded)
    VALUES (
        new.rowid,
        new.title || ' ' || coalesce(new.problem_signature, '') || ' ' || new.solution_payload || ' ' || coalesce(new.bilingual_tags, ''),
        new.content_folded
    );
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_delete AFTER DELETE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS trg_episodic_after_update AFTER UPDATE ON workspace_episodic_memory
BEGIN
    DELETE FROM episodic_fts WHERE rowid = old.rowid;
    INSERT INTO episodic_fts(rowid, content_exact, content_folded)
    VALUES (
        new.rowid,
        new.title || ' ' || coalesce(new.problem_signature, '') || ' ' || new.solution_payload || ' ' || coalesce(new.bilingual_tags, ''),
        new.content_folded
    );
END;

-- ----------------------------------------------------------------------------
-- Table 5: l1_staging_log (Lightweight Staging Buffer for L1 Reflex Ephemeral Logging)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS l1_staging_log (
    staging_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,               -- ISO-8601 UTC
    user_input          TEXT NOT NULL,
    workspace_hash      TEXT NOT NULL,
    top_skill           TEXT,
    tier_used           INTEGER NOT NULL DEFAULT 1,
    recalled_traces     TEXT,                        -- JSON array of recalled memory IDs
    is_drained          INTEGER NOT NULL DEFAULT 0   -- 0 = pending, 1 = processed by Memory Daemon Single-Writer
);

CREATE INDEX IF NOT EXISTS idx_staging_pending ON l1_staging_log(is_drained, timestamp);

-- ----------------------------------------------------------------------------
-- Table 5: activation_events (Staging Buffer for Tier 3 Consolidation)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activation_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT NOT NULL,
    timestamp           TEXT NOT NULL,               -- ISO-8601 UTC
    user_input          TEXT NOT NULL,
    workspace_dir       TEXT NOT NULL,
    top_skill           TEXT,
    tier_used           INTEGER NOT NULL DEFAULT 1,
    recalled_traces     TEXT,                        -- JSON array of recalled memory IDs
    feedback_score      REAL DEFAULT 0.0,            -- +1.0 (success), 0.0 (neutral), -1.0 (failure)
    is_consolidated     INTEGER NOT NULL DEFAULT 0   -- 0 = pending, 1 = consolidated
);

CREATE INDEX IF NOT EXISTS idx_event_pending ON activation_events(is_consolidated, timestamp);
```

---

### Defensive Boundaries & Algorithmic Specifications

#### 1. Vietnamese Diacritic Folding Pipeline (`fold_vietnamese`)
```python
import unicodedata

def fold_vietnamese(text: str) -> str:
    """
    Application-level diacritic removal preserving dual-column FTS5 precision.
    Pre-converts stroked consonants (đ/Đ -> d/D) before NFD decomposition
    because Unicode NFD does not separate the horizontal bar from 'đ'.
    """
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()
```

#### 2. Dual-Column FTS5 Hybrid Query Contract & BM25 Ordering
```sql
-- L2 Hybrid Lexical Search Query Contract
-- CRITICAL: SQLite FTS5 bm25() returns negative values (lower/more negative = higher relevance).
-- MUST order by rank_score ASC. Exact column has 10x weight over folded column.
SELECT rowid, bm25(episodic_fts, 10.0, 1.0) AS rank_score
FROM episodic_fts
WHERE episodic_fts MATCH 'content_exact : (' || :raw_q || ') OR content_folded : (' || :folded_q || ')'
ORDER BY rank_score ASC
LIMIT 30;
```

#### 3. Process Boundary Separation: Ephemeral CLI Subprocess vs. Persistent Daemon
- **Process 1: `hook_runner.py` (Ephemeral CLI Subprocess, <25ms SLA, 100% Python Stdlib)**:
  * Exclusively performs Tier 1 Reflex token/Jaccard matching (<0.3ms execution time).
  * Strict Invariant: MUST NOT import `onnxruntime`, `fastembed`, or C++ native libraries.
  * Strict Invariant: MUST NOT open multi-statement transactions or execute FTS5 writes.
  * Logging: Appends telemetry to unindexed staging table `l1_staging_log` with `PRAGMA synchronous = NORMAL;` or pushes non-blocking payload via loopback socket to Memory Daemon in <1.0ms.
- **Process 2: Memory Daemon / MCP Worker (Long-Lived Persistent Process)**:
  * Houses `intfloat/multilingual-e5-small` (INT8 quantized, 384 dim) permanently resident in ~120MB System RAM (0ms cold-start, 5–10ms inference for L2).
  * Sole owner of the Single-Writer Queue (`queue.Queue`) and dedicated writer thread. Exclusively handles all database writes across `l1_staging_log` draining, L2 episodic memory insertion, and L3 consolidation batches using `BEGIN IMMEDIATE`.
  * Enforces `PRAGMA busy_timeout = 5000;`, `PRAGMA wal_autocheckpoint = 1000;`, `PRAGMA journal_mode = WAL;`.

#### 4. Dense Vector Model Mandate & Asymmetric Prefixes
- **Model Mandate**: Strictly locked to `intfloat/multilingual-e5-small` (Quantized INT8 ONNX, 384 dimensions).
- **Prohibition**: `bge-small-en-v1.5` is STRICTLY PROHIBITED (English-only tokenizer destroys Vietnamese subword representations).
- **Asymmetric Prefix Invariant**:
  * Document/Passage Ingestion: MUST prefix with `"passage: " + text`.
  * Query Embedding: MUST prefix with `"query: " + user_prompt`.
  * Failure to attach prefixes causes 20%–30% drop in Recall@K due to vector manifold divergence.

#### 5. Bounded Ebbinghaus Stability Decay & Soft-Archiving
$$S(t) = S_0 \cdot \exp\left(-\frac{\lambda_0 \cdot \Delta t}{1 + \alpha \ln(1 + N_{\text{hits}})}\right)$$
- **Elapsed Time Metric ($\Delta t$)**:
  $$\Delta t = \frac{t_{\text{now}} - t_{\text{last\_accessed}}}{86400.0} \quad (\text{Days as float})$$
  * Strict Invariant: $\Delta t$ MUST be calculated from `last_accessed_at`, NEVER from `created_at`.
  * Strict Invariant: Units MUST be in Days. Passing seconds or milliseconds will trigger mathematical underflow to 0.0.
- **Canonical Constants**: $S_0 = 1.0$, $\lambda_0 = 0.08\text{ day}^{-1}$ (base half-life $\approx 8.66\text{ days}$ for new memory $N_{\text{hits}} = 0$), reinforcement scaling $\alpha = 1.5$.
- **Soft-Archiving (No Hard Deletes)**:
  * Memory is pruned if and only if $S(t) < 0.20$ AND $\Delta t \ge 7.0\text{ days}$ AND $\text{memory\_type} \ne \text{'invariant'}$.
  * Pruning action: UPDATE `status = 'Archived'`. Hard `DELETE` is prohibited.
  * Dense vector scanning loads embeddings only `WHERE status = 'Active'`.
  * If an `'Archived'` memory is recalled via FTS5 or `deep_recall`, resurrect it: set `status = 'Active'`, `last_accessed_at = now()`, and increment `activation_count`.
- **Invariant Rule Versioning ($\lambda_0 = 0.0$)**:
  * For permanent invariants ($\lambda_0 = 0.0$), $S(t) \equiv 1.0$.
  * When an invariant is superseded by an updated rule, update old record `status = 'Superseded'`, `superseded_by = new_memory_id` to eliminate Context Schizophrenia.

#### 6. Reciprocal Rank Fusion ($k=20$)
$$\text{RRF\_Score}(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{w_m}{20 + \text{rank}_m(d)}$$

#### 7. Conversational Filler Full-Sentence Boundary Regex (`FILLER_PATTERN`)
```python
import re

# Full-sentence boundary matching pattern: r"^(ok|okay|tiếp tục|thanks|cảm ơn|yes|no|got it|sure)[.!\s]*$"
# Prevents false-positive suppression on prompts with filler prefixes like "ok, please fix this docker error"
FILLER_PATTERN = re.compile(
    r"^((ok|okay|tiếp tục|tiep tuc|done|thanks|cảm ơn|cam on|chạy đi|chay di|yes|no|got it|sure)[.!\s,]*)+$",
    re.IGNORECASE
)
```
Enforces full-sentence boundary matching `^...[.!\s]*$` to ensure substantive developer instructions starting with conversational filler words (e.g., `'ok, please fix this docker error'`, `'yes, implement the function'`) are NOT suppressed and receive full reflex injection.

#### 6. FTS5 Cross-Workspace Partition Isolation Query Contract
```sql
-- Mandated partitioned SQL join: MUST join on rowid, filter by e.workspace_hash = :ws_hash, and exclude Superseded records
-- CRITICAL: SQLite FTS5 bm25() returns negative values (lower/more negative = higher relevance); MUST order by rank_score ASC.
SELECT e.memory_id, e.title, e.solution_payload, bm25(episodic_fts, 10.0, 1.0) AS rank_score
FROM episodic_fts
JOIN workspace_episodic_memory e ON episodic_fts.rowid = e.rowid
WHERE episodic_fts MATCH 'content_exact : (' || :raw_q || ') OR content_folded : (' || :folded_q || ')'
  AND e.workspace_hash = :ws_hash
  AND e.status != 'Superseded'
ORDER BY rank_score ASC
LIMIT 30;
```
Direct unpartitioned queries (`SELECT ... FROM episodic_fts WHERE MATCH ?`) are strictly prohibited to prevent cross-workspace memory and confidential code leakage.

#### 7. Canonical Workspace Path Hashing (`canonical_workspace_hash`)
```python
import os
import hashlib

def canonical_workspace_hash(path: str) -> str:
    """
    Generate deterministic MD5 hash for workspace partition isolation.
    Mandates os.path.normcase(os.path.normpath(os.path.abspath(path))) prior to hashing
    so case-insensitive Windows drive letters (d:\ vs D:\) and mixed slashes
    generate identical partition keys.
    """
    canonical = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()
```

#### 8. Inter-Process Mutex with 30s Stale-Lock Recovery (`acquire_lock_with_stale_recovery`)
```python
import os
import time

def acquire_lock_with_stale_recovery(lock_path: str, stale_timeout_sec: float = 30.0) -> bool:
    """Acquire inter-process file mutex with automatic 30s stale-lock recovery."""
    if os.path.exists(lock_path):
        file_age = time.time() - os.path.getmtime(lock_path)
        if file_age > stale_timeout_sec:
            try:
                os.remove(lock_path)
            except OSError:
                pass
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, f"pid={os.getpid()};time={time.time()}".encode("utf-8"))
        os.close(fd)
        return True
    except FileExistsError:
        return False
```

---

### Key Entities

- **SystemCapability**: Represents an installed or synthesized capability (skill, MCP server, tool, rule) with learned affinity score and activation counts.
- **WorkspaceEpisodicMemory**: Durable knowledge unit tied to a specific workspace (or global fallback), carrying a solution payload, problem signature, decay parameters, and bilingual tags.
- **DenseEmbedding**: Partitioned vector representation of an episodic memory record, serialized as IEEE-754 float32 bytes with precomputed L2 norm.
- **ActivationEvent**: Ephemeral telemetry record logging an agent interaction turn, recalled traces, user feedback, and consolidation status.
- **ProceduralTrace**: High-confidence in-memory cached fix for instantaneous L1 reflex injection.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Tier 1 pre-flight hook algorithmic response latency is $<0.30\text{ ms}$ (P99) for all in-memory procedural cache hits.
- **SC-002**: Tier 1 latency on massive prompts (up to 200 KB) remains strictly $<0.30\text{ ms}$ due to the 2,048-character clamping invariant.
- **SC-003**: End-to-end Tier 2 hybrid retrieval latency is $<15.0\text{ ms}$ (P99) across 10,000 indexed records; pure lexical search is $<1.0\text{ ms}$.
- **SC-004**: Bilingual retrieval recall achieves 100% parity between unaccented and accented Vietnamese queries (`đ/Đ` normalized).
- **SC-005**: All technical developer queries containing reserved characters execute with zero `sqlite3.OperationalError` exceptions.
- **SC-006**: Background consolidation executes with zero unhandled exceptions, maintains $S(t) \in [0.0, 1.0]$, and enforces the 7-day grace period.

---

## Assumptions

- **A-001**: Python 3.11+ is the host runtime environment with standard library `sqlite3` enabled with FTS5 support.
- **A-002**: Host CPU possesses AVX2 or similar SIMD instruction sets, allowing `onnxruntime` or `struct.unpack` dot product calculations in $<1.0\text{ ms}$.
- **A-003**: The primary LLM inference server `llama-server.exe` on AMD Instinct MI50 is operated on port 8080 with `-ub 2048` and `--cache-reuse 256`.
- **A-004**: Local filesystem supports atomic replacement via `os.replace` (standard Windows NTFS / POSIX behavior).
