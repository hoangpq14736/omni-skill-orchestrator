---
name: spec-driven-development
description: >-
  Specification-First Software Engineering (GitHub Spec Kit SDD engine): Autonomously orchestrates the 10 SDD phases (constitution, specify, clarify, plan, tasks, implement, converge, checklist, analyze, taskstoissues) within Omni-Kernel v4.1 with Tri-Tier Omni-Memory persistence, Hard Architecture Gatekeeper, zero external dependencies, and native AppLocker-safe execution.
metadata:
  version: 4.1.0
  author: GitHub & Omni-Kernel
  aliases: ["speckit", "sdd", "spec-kit"]
---

# Specification-Driven Development (SDD) Engine v4.1

The **Specification-Driven Development (SDD)** skill brings GitHub Spec Kit's structured engineering discipline directly into **Omni-Kernel v4.1**. It enforces the immutable principle: **Code is the consequence of clear intent. Never write code without an explicit specification, architectural plan, and dependency-ordered tasks.**

Integrated natively with **Omni-Memory v4.1 (Tri-Tier Cognitive Architecture)** and the **Omni-Auditor Council Gate (Strict Architecture Gatekeeper)**, SDD ensures zero cross-session amnesia, zero architectural blind spots, and zero drift between specification and codebase reality.

---

## 1. Operating Modes & Zero-Dependency Invariant

SDD operates under two execution tiers:
1. **Mode A: Native Zero-Dependency SDD (Default & AppLocker-Proof):**
   - Pure Markdown & Python architecture using 100% Python Standard Library.
   - Requires zero external binaries and zero npm/pip packages.
   - Immune to Windows AppLocker / WDAC enterprise blocks.
   - Omni-Kernel v4.1 autonomously creates, validates, and manages `.specify/` and `specs/` structures directly.
2. **Mode B: CLI & Virtual MCP Mode (Enhanced Tooling):**
   - Automatically activated when `specify-cli` is installed via `uv tool install specify-cli`.
   - Accessible via Virtual MCP Bus (`specify_mcp`) or `uv tool run specify`.

---

## 2. Directory & Artifact Structure

Every SDD-governed project organizes specifications under a clean, versioned layout:

```text
<project_root>/
├── .specify/
│   ├── constitution.md          # Immutable architectural invariants & core principles (Precedence Rule)
│   └── templates/               # Project-specific custom templates (optional)
└── specs/
    └── 001-<feature-name>/       # Numbered sequential feature branch/spec folder
        ├── spec.md              # Functional specification & prioritized user stories (FRC / Spec)
        ├── plan.md              # Technical design, stack choices, contracts, data models (RFC / Architecture)
        ├── tasks.md             # Dependency-ordered, checkable task breakdown
        ├── checklist.md         # Custom quality, a11y, performance, or security checks
        ├── research.md          # Technical research notes and discarded alternatives
        └── tests/               # Empirical regression & validation test harness
```

---

## 3. Omni-Memory v4.1 & Tri-Tier Cognitive Integration

SDD is deeply integrated with the **Omni-Memory v4.1 Tri-Tier Cognitive Hierarchy**:

1. **Tier 1 (L1 Reflex - Ephemeral Prompt Grounding, <0.3ms)**:
   - Active specs, current task state, and constitutional invariants are cached in procedural memory.
   - Guarantees sub-millisecond grounding on every user interaction without disk latency.
2. **Tier 2 (L2 Hybrid Memory - SQLite WAL + Dual-Column FTS5 BM25 + ONNX Embeddings, <15ms)**:
   - Historical specifications, architectural decision records (ADRs), and empirical test traces are indexed in `omni_memory.db`.
   - Cross-session queries retrieve architectural precedents with 100% Vietnamese diacritic folding and dense vector cosine similarity.
3. **Tier 3 (L3 Consolidator - Background Stabilization & Ebbinghaus Decay)**:
   - Successful SDD workflows and ratified architectural patterns are promoted with automated bilingual tags (`bilingual_tags`).
   - Outdated or superseded specs are soft-archived (`status = 'Archived'`) or marked `status = 'Superseded'`, eliminating Context Schizophrenia.

---

## 4. The 10 Core SDD Primitives

### 1. `constitution` (Architectural Invariants & Precedence)
- **Purpose**: Define non-negotiable project laws, architectural boundaries, hardware constraints, and security invariants before any features are designed.
- **Location**: `.specify/constitution.md`
- **Rule**: Every subsequent `spec.md` and `plan.md` must comply with the constitution. Any conflicting proposal is rejected.

### 2. `specify` (Feature Specification / FRC)
- **Purpose**: Transform raw human intent into a structured functional specification in `specs/<NNN>-<feature>/spec.md`.
- **Core Sections**:
  - **User Stories & Scenarios**: Prioritized journeys (P1, P2, P3) written in `Given-When-Then` format.
  - **Functional Requirements**: Explicit capabilities the system must have.
  - **Key Entities & Attributes**: Conceptual data model without premature SQL/ORM coupling.
  - **Edge Cases & Failure Modes**: Network dropouts, corrupted input, empty collections, auth failures.

### 3. `clarify` (Targeted Requirement Phỏng Vấn)
- **Purpose**: Uncover ambiguous or underspecified requirements *before* technical design begins.
- **Constraint**: Ask up to **5 highly targeted clarification questions**.
- **Action**: Once answered by the user, encode the answers directly back into `spec.md` and increment the spec revision.

### 4. `plan` (Technical Architecture Design / RFC)
- **Purpose**: Formulate the technical strategy to satisfy `spec.md` in `specs/<NNN>-<feature>/plan.md`.
- **Core Sections**:
  - **Tech Stack & Dependencies**: Evaluate standard library first before adding dependencies (Ponytail Simplicity).
  - **API Contracts / Schemas**: Endpoint definitions, parameter validation schemas, type definitions.
  - **Data Model & Migrations**: Schema alterations, index requirements, state transitions.
  - **Hardware & Resource Limits**: Memory boundaries, compute quotas (e.g. MI50 VRAM, Groq rate limits).
  - **Security & Trust Boundaries**: Zero-trust input sanitization, parameterized SQL.

### 5. `council_gate` (Strict Architecture Gatekeeper / Red-Teaming)
- **Purpose**: Subject the completed `spec.md` and `plan.md` to independent architectural review before task execution.
- **Mechanism**: Invokes the **Omni-Auditor Gatekeeper (DeepSeek-V4.1-Flash Council Gate)** via `consult_critic.py` or `deepseek_worker_mcp`.
- **Invariant**: Strict prohibition against internal self-review ("echo chamber"). Hard rejection if any Ring 0 invariant or constitutional rule is violated.

### 6. `tasks` (Actionable Task Decomposition)
- **Purpose**: Break down `plan.md` into dependency-ordered, checkable tasks in `specs/<NNN>-<feature>/tasks.md`.
- **Structure**:
  - **Phase 1: Setup & Scaffolding** (Directories, configuration, base types).
  - **Phase 2: Foundation & Data Layer** (Storage, models, migrations).
  - **Phase 3: Core Domain & Services** (Business logic, processors).
  - **Phase 4: Interface & Integration** (Endpoints, CLI, UI).
  - **Phase 5: Verification & Hardening** (Unit tests, benchmarks, edge case coverage).
- **Format**: Every task must be checkable (`- [ ] T001: Description`).

### 7. `implement` (Step-by-Step Task Execution & Worker Fleet)
- **Purpose**: Execute tasks sequentially following `tasks.md`.
- **Fleet Allocation**:
  - `groq_worker_cloud` (Groq LPU): Generates boilerplate, AST parsing, and rapid unit test suites.
  - `local_worker_mi50` (AMD Instinct MI50): In-place file edits (`fast_edit`), SQLite WAL transactions, 100% offline.
- **Rules**:
  - Complete tasks one at a time or in small atomic batches.
  - Mark finished tasks as `- [x] T001: Description`.
  - Run verification tests immediately after each task. Never skip ahead to Phase 4 before Phase 2 foundation passes.

### 8. `converge` (Convergence & Drift Detection)
- **Purpose**: Evaluate the codebase reality against `spec.md`, `plan.md`, and `tasks.md`.
- **Output**:
  - Identify drift or unbuilt requirements.
  - Automatically append remaining work as new tasks at the bottom of `tasks.md`.
  - Stop only when all acceptance criteria converge to 100%.

### 9. `checklist` (Unit Tests for English)
- **Purpose**: Generate domain-specific checklists verifying code against non-functional requirements (Security, Privacy, Accessibility, Reliability, Performance).
- **Location**: `specs/<NNN>-<feature>/checklist.md`.

### 10. `analyze` (Cross-Artifact Consistency Verification)
- **Purpose**: Non-destructive consistency scan between `spec.md`, `plan.md`, and `tasks.md`.
- **Checks**:
  - Are all P1 user stories covered by tasks in `tasks.md`?
  - Does `plan.md` introduce technologies or endpoints not mentioned in `spec.md`?
  - Are prerequisite tasks properly sequenced?

---

## 5. Omni-Kernel v4.1 Integration & Slash Commands

When activated in Omni-Kernel v4.1, the following slash commands or prompt intents are automatically recognized:

| Command / Intent | Equivalent SDD Primitive | Description |
|---|---|---|
| `/speckit-constitution`, `tao constitution` | `constitution` | Initialize or update project constitution |
| `/speckit-specify`, `tao spec`, `viet spec` | `specify` | Draft feature specification (FRC) in `specs/` |
| `/speckit-clarify`, `clarify spec` | `clarify` | Interactively clarify missing requirements |
| `/speckit-plan`, `len plan architecture` | `plan` | Create technical architecture plan (RFC) |
| `/speckit-council`, `kiem tra gatekeeper` | `council_gate` | Submit spec/plan to DeepSeek-V4.1-Flash Auditor Gate |
| `/speckit-tasks`, `chia task` | `tasks` | Generate dependency-ordered tasks |
| `/speckit-implement`, `trien khai task` | `implement` | Execute tasks in order with worker fleet |
| `/speckit-converge`, `kiem tra do lech` | `converge` | Check convergence and append missing tasks |
| `/speckit-analyze`, `phan tich nhat quan` | `analyze` | Cross-artifact validation |
| `/speckit-checklist`, `tao checklist` | `checklist` | Build non-functional quality checklists |

---

## 6. Pre-Flight Verification & Quality Invariant

Before completing any SDD task:
1. Verify that all referenced markdown files exist.
2. Confirm no undocumented requirements or unauthorized architectural shifts were made.
3. Confirm that the specification adheres to the ratified Constitution (`.specify/constitution.md`).
4. Conclude every SDD run with a concise summary stating current phase, completed tasks, and next recommended action.
