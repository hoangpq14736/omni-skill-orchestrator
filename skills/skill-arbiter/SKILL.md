---
name: skill-arbiter
description: >-
  Arbitrates and resolves conflicts when multiple skills or plugins offer overlapping capabilities. Ranks candidates by SemVer freshness, domain specificity, scope priority, and quality score to select the single best skill and suppress obsolete duplicates.
metadata:
  version: 1.0.0
---

# Skill Arbiter Protocol

When managing hundreds or thousands of skills across plugins and libraries, multiple skills will inevitably cover similar domains (e.g. general Python vs FastAPI; React 18 vs React 19; generic Git vs GitHub Ops).

The **Skill Arbiter** applies a strict 4-tier decision matrix to select the superior skill:

```
                        +----------------------------+
                        |   Overlapping Candidates   |
                        +----------------------------+
                                      |
                                      v
       Tier 1: Scope Override (Workspace Custom > Active > Plugin > Library)
                                      |
                                      v
       Tier 2: Domain Specificity (Specific Framework > Generic Language)
                                      |
                                      v
       Tier 3: Version Freshness (SemVer 2.x > 1.x / Modern Standard)
                                      |
                                      v
       Tier 4: Quality & Completeness (Actionable Guide > Empty Stubs)
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

2. **Domain Specificity**:
   - Framework beats generic language:
     - `fastapi-patterns` beats `python-patterns` for FastAPI endpoints.
     - `nextjs-patterns` beats `react-patterns` for Next.js app router.
     - `flutter-dart-code-review` beats general `code-reviewer` for Flutter widgets.
     - `bigquery-sql` beats general `database-patterns` for BigQuery queries.
   - *Constraint*: Specificity bonus is ONLY granted if the framework is present in the workspace stack or explicitly requested by the user.

3. **Version & Freshness**:
   - SemVer comparison: higher numerical version wins when candidates belong to the same tool/framework.
   - Explicit tech versioning: e.g. `swift-concurrency-6-2` is chosen for Swift 6.2 projects over older concurrency guides.

4. **Deduplication & Context Hygiene**:
   - The arbiter selects at most 1 primary specialized skill + 1 complementary workflow skill (e.g., framework skill + `tdd-workflow` or `ponytail`).
   - Suppresses duplicate or obsolete versions to prevent prompt dilution and conflicting rules.
