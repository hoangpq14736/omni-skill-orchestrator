---
name: omni-graph
description: Deterministic Codebase Topology & Semantic Call-Graph Guard (Graphify Core Engine for Omni-Kernel v4.1). Provides AST-level Signature Contract Guard, Lifecycle Registration Guard, Blast Radius Traversal (<1ms via SQLite WAL CTE), and zero-dependency offline HTML5 canvas topology visualizer.
version: 4.1.0
domain: code-analysis
---

# Omni-Graph (Graphify Core Engine)

**Omni-Graph** is the deterministic codebase topology and syntactic graph intelligence engine of Omni-Kernel v4.1.

## Core Architectural Invariants
1. **Zero-Conflict Duality**: Physically separated from cognitive memory (`omni_memory.db`). Stored per-workspace in `<workspace>/.omni/codebase_graph.db` (SQLite WAL mode).
2. **Ponytail Zero-Dependency**: 100% Python Standard Library (`ast`, `sqlite3`, `pathlib`, `re`, `hashlib`) - zero external wheels, zero C-extensions, AppLocker safe.
3. **Sub-Millisecond Blast Radius**: SQLite Recursive CTEs resolve transitive callers and impact scopes in `< 1ms`.
4. **Signature Contract Guard**: Catches parameter mismatches (e.g. `allocated_ram` vs `ram`), missing required args, and positional-only violations before code changes are executed.
5. **Lifecycle Registration Guard**: Detects unregistered/unsynced handlers (e.g. Discord slash commands missing `bot.tree.sync()`, FastAPI endpoints missing `include_router`).
6. **Autonomous Zero-Config Bootstrapping**:
   - JIT cold start on first turn in any workspace (<100ms).
   - Incremental delta re-indexing (<8.5ms) via mtime & SHA-256 fingerprinting.
   - Post-edit micro-indexer hook on touched files.
   - Automatic Git hygiene: `.omni/` automatically added to `.gitignore`.

---

## CLI Usage

### 1. Workspace Indexing (Incremental or Full)
```bash
python scripts/omni_graph.py --workspace "<path>" --scan
python scripts/omni_graph.py --workspace "<path>" --rebuild
```

### 2. Transitive Blast Radius Query
```bash
python scripts/omni_graph.py --workspace "<path>" --blast-radius "<symbol_or_file>"
```

### 3. Signature Contract Verification
```bash
python scripts/omni_graph.py --workspace "<path>" --check-contract --symbol "<func_name>" --kwargs '{"param1": "val"}'
```

### 4. Lifecycle Registration Audit
```bash
python scripts/omni_graph.py --workspace "<path>" --check-lifecycle
```

### 5. Offline Interactive HTML Topology Visualizer
```bash
python scripts/omni_graph.py --workspace "<path>" --visualize
```
Generates `<workspace>/.omni/graph.html` (zero-CDN HTML5 Canvas force-directed graph).
