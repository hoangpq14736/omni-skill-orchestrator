---
name: skill-arbiter
description: >-
  Arbitrates and resolves conflicts when multiple skills or plugins offer overlapping capabilities within Omni-Kernel v4.1. Ranks candidates by Kernel Alignment, SemVer freshness, domain specificity, scope priority, and quality score to select the single best skill and suppress obsolete duplicates.
metadata:
  version: 4.1.0
---

# Skill Arbiter Protocol v4.1

When managing hundreds or thousands of skills across plugins and libraries in **Omni-Kernel v4.1**, multiple skills will inevitably cover similar domains (e.g. general Python vs FastAPI; React 18 vs React 19; generic Git vs GitHub Ops).

The **Skill Arbiter** applies a strict 5-tier decision matrix to select the superior skill:

```
                        +----------------------------+
                        |   Overlapping Candidates   |
                        +----------------------------+
                                      |
                                      v
        Tier 1: Scope Override (Workspace Custom > Active > Plugin > Library)
                                      |
                                      v
        Tier 2: Kernel Alignment (Aligned with Omni-Kernel v4.1 Invariants)
                                      |
                                      v
        Tier 3: Domain Specificity (Specific Framework > Generic Language)
                                      |
                                      v
        Tier 4: Version Freshness (SemVer 4.x/2.x > Obsolete 1.x / Modern Standard)
                                      |
                                      v
        Tier 5: Quality & Completeness (Actionable Guide > Empty Stubs)
                                      |
                                      v
                        +----------------------------+
                        |      Selected Winner       |
                        +----------------------------+
```

## Arbitration Rules

1. **Scope Priority**:
   - `workspace` (.agents/skills or .gemini/skills in project): +40 points (user project-specific overrides always win).
   - `user_active` (~/.gemini/config/skills): +20 points.
   - `plugin` (~/.gemini/config/plugins): +20 points.
   - `builtin` (Antigravity core): +15 points.
   - `library` (Offline fallback library): +5 points.

2. **Kernel Version & Architectural Alignment**:
   - Skills specifically aligned with the current **Omni-Kernel v4.1** and **Tri-Tier Omni-Memory** receive an additional **+15 points** over unaligned or legacy v2.0/v3.0 skills.
   - Prohibits selecting skills that violate Kernel Ring 0 Invariants (Zero-Trust Security, Reliable Error Handling, Ponytail Simplicity).

3. **Domain Specificity**:
   - Framework beats generic language:
     - `fastapi-patterns` beats `python-patterns` for FastAPI endpoints.
     - `nextjs-patterns` beats `react-patterns` for Next.js app router.
     - `flutter-dart-code-review` beats general `code-reviewer` for Flutter widgets.
     - `bigquery-sql` beats general `database-patterns` for BigQuery queries.
   - *Constraint*: Specificity bonus is ONLY granted if the framework is present in the workspace stack or explicitly requested by the user.

4. **Version & Freshness**:
   - SemVer comparison: higher numerical version wins when candidates belong to the same tool/framework.
   - Explicit tech versioning: e.g. `swift-concurrency-6-2` is chosen for Swift 6.2 projects over older concurrency guides.

5. **Deduplication & Context Hygiene**:
   - The arbiter selects at most 1 primary specialized skill + 1 complementary workflow skill (e.g., framework skill + `spec-driven-development` or `ponytail`).
   - Suppresses duplicate or obsolete versions to prevent prompt dilution and conflicting rules.
