---
name: spec-driven-development
description: >-
  Specification-First Software Engineering (GitHub Spec Kit SDD engine): Autonomously orchestrates the 10 SDD phases (constitution, specify, clarify, plan, tasks, implement, converge, checklist, analyze, taskstoissues) with zero external dependency and native AppLocker-safe execution.
metadata:
  version: 3.0.0
  author: GitHub & Omni-Kernel
  aliases: ["speckit", "sdd", "spec-kit"]
---

# Specification-Driven Development (SDD) Engine

The **Specification-Driven Development (SDD)** skill brings GitHub Spec Kit's structured engineering discipline directly into Omni-Kernel v3.0. It enforces the immutable principle: **Code is the consequence of clear intent. Never write code without an explicit specification, architectural plan, and dependency-ordered tasks.**

---

## 1. Operating Modes & Zero-Dependency Invariant

SDD operates under two execution tiers:
1. **Mode A: Native Zero-Dependency SDD (Default & AppLocker-Proof):**
   - Pure Markdown & Python architecture.
   - Requires zero external binaries and zero npm/pip packages.
   - Immune to Windows AppLocker / WDAC blocks.
   - Omni-Kernel autonomously creates, validates, and manages `.specify/` and `specs/` structures directly.
2. **Mode B: CLI & Virtual MCP Mode (Enhanced Tooling):**
   - Automatically activated when `specify-cli` is installed via `uv tool install specify-cli`.
   - Accessible via Virtual MCP Bus (`specify_mcp`) or `uv tool run specify`.

---

## 2. Directory & Artifact Structure

Every SDD-governed project organizes specifications under a clean, versioned layout:

```text
<project_root>/
├── .specify/
│   ├── constitution.md          # Immutable architectural invariants & core principles
│   └── templates/               # Project-specific custom templates (optional)
└── specs/
    └── 001-<feature-name>/       # Numbered sequential feature branch/spec folder
        ├── spec.md              # Functional specification & prioritized user stories
        ├── plan.md              # Technical design, stack choices, contracts, data models
        ├── tasks.md             # Dependency-ordered, checkable task breakdown
        ├── checklist.md         # Custom quality, a11y, performance, or security checks
        └── research.md          # Technical research notes and discarded alternatives
```

---

## 3. The 10 Core SDD Primitives

### 1. `constitution` (Architectural Invariants)
- **Purpose**: Define non-negotiable project laws, architectural boundaries, code conventions, and testing requirements before any features are designed.
- **Location**: `.specify/constitution.md`
- **Rule**: Every subsequent `spec.md` and `plan.md` must comply with the constitution. Any conflicting proposal is rejected.

### 2. `specify` (Feature Specification)
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

### 4. `plan` (Technical Architecture Design)
- **Purpose**: Formulate the technical strategy to satisfy `spec.md` in `specs/<NNN>-<feature>/plan.md`.
- **Core Sections**:
  - **Tech Stack & Dependencies**: Evaluate standard library first before adding dependencies.
  - **API Contracts / Schemas**: Endpoint definitions, parameter validation schemas, type definitions.
  - **Data Model & Migrations**: Schema alterations, index requirements, state transitions.
  - **Security & Performance**: Trust boundaries, auth validation, caching, resource constraints.

### 5. `tasks` (Actionable Task Decomposition)
- **Purpose**: Break down `plan.md` into dependency-ordered, checkable tasks in `specs/<NNN>-<feature>/tasks.md`.
- **Structure**:
  - **Phase 1: Setup & Scaffolding** (Directories, configuration, base types).
  - **Phase 2: Foundation & Data Layer** (Storage, models, migrations).
  - **Phase 3: Core Domain & Services** (Business logic, processors).
  - **Phase 4: Interface & Integration** (Endpoints, CLI, UI).
  - **Phase 5: Verification & Hardening** (Unit tests, benchmarks, edge case coverage).
- **Format**: Every task must be checkable (`- [ ] T001: Description`).

### 6. `implement` (Step-by-Step Task Execution)
- **Purpose**: Execute tasks sequentially following `tasks.md`.
- **Rules**:
  - Complete tasks one at a time or in small atomic batches.
  - Mark finished tasks as `- [x] T001: Description`.
  - Run verification tests immediately after each task.
  - Never skip ahead to Phase 4 before Phase 2 foundation passes.

### 7. `converge` (Convergence & Drift Detection)
- **Purpose**: Evaluate the codebase reality against `spec.md`, `plan.md`, and `tasks.md`.
- **Output**:
  - Identify drift or unbuilt requirements.
  - Automatically append remaining work as new tasks at the bottom of `tasks.md`.
  - Stop only when all acceptance criteria converge to 100%.

### 8. `checklist` (Unit Tests for English)
- **Purpose**: Generate domain-specific checklists verifying code against non-functional requirements (Security, Privacy, Accessibility, Reliability, Performance).
- **Location**: `specs/<NNN>-<feature>/checklist.md`.

### 9. `analyze` (Cross-Artifact Consistency Verification)
- **Purpose**: Non-destructive consistency scan between `spec.md`, `plan.md`, and `tasks.md`.
- **Checks**:
  - Are all P1 user stories covered by tasks in `tasks.md`?
  - Does `plan.md` introduce technologies or endpoints not mentioned in `spec.md`?
  - Are prerequisite tasks properly sequenced?

### 10. `taskstoissues` (Issue Tracker Synchronization)
- **Purpose**: Map tasks in `tasks.md` into GitHub Issues or tracking tickets with labels, milestone assignments, and dependencies.

---

## 4. Omni-Kernel Integration & Slash Commands

When activated in Omni-Kernel, the following slash commands or prompt intents are automatically recognized:

| Command / Intent | Equivalent SDD Primitive | Description |
|---|---|---|
| `/speckit-constitution`, `tao constitution` | `constitution` | Initialize or update project constitution |
| `/speckit-specify`, `tao spec`, `viet spec` | `specify` | Draft feature specification in `specs/` |
| `/speckit-clarify`, `clarify spec` | `clarify` | Interactively clarify missing requirements |
| `/speckit-plan`, `len plan architecture` | `plan` | Create technical architecture plan |
| `/speckit-tasks`, `chia task` | `tasks` | Generate dependency-ordered tasks |
| `/speckit-implement`, `trien khai task` | `implement` | Execute tasks in order with verification |
| `/speckit-converge`, `kiem tra do lech` | `converge` | Check convergence and append missing tasks |
| `/speckit-analyze`, `phan tich nhat quan` | `analyze` | Cross-artifact validation |
| `/speckit-checklist`, `tao checklist` | `checklist` | Build non-functional quality checklists |

---

## 5. Pre-Flight Verification & Quality Invariant

Before completing any SDD task:
1. Verify that all referenced markdown files exist.
2. Confirm no undocumented requirements or unauthorized architectural shifts were made.
3. Conclude every SDD run with a concise summary stating current phase, completed tasks, and next recommended action.
