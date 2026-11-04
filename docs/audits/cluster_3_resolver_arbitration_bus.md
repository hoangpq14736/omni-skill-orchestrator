<!-- OMNI_AUDIT_META: {"verdict":"REJECTED","target_file":"Cluster 3: Resolver, Arbitration, Dynamic Bus & Indexer","input_hash":"sha256:bacd8f3b1af8356b0f17060d8a95474c7bcb74b26a25a90a2c8224e6d28a5aa1","model":"deepseek-flash","timestamp_utc":"2026-11-03T20:33:09.772546+00:00"} -->

# 🛡️ Architectural Red-Teaming Audit: Cluster 3: Resolver, Arbitration, Dynamic Bus & Indexer
**Audit Status**: `REJECTED` | **Model**: `deepseek-flash` | **Confidence**: `0.94` | **Timestamp**: `2026-11-03T20:33:09.772546+00:00`

## Executive Summary
Cluster 3 is not merge-safe. The synthesizer's 'sandbox' is arbitrary code execution, index/tokenization has no memory bounds, MCP schema validation is type-confused and crash-prone, and arbitration is non-deterministic and can discard the arbitrated winner when top_k truncates. Registry and affinity writes are non-atomic and race-prone. No parameterized SQL usage was found in this cluster.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `REJECTED` with 9 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (9 identified)
### 1. [CRITICAL] VULN-001: Synthesizer 'sandbox' executes arbitrary code without isolation
**Description**: synthesizer.run_sandbox_validation() writes caller/model-supplied test_code to a temp file and executes it with sys.executable. It inherits environment variables, filesystem access, network access, and user privileges. The only control is a timeout. This is not a sandbox and turns any influence over test_code into remote/local code execution. The function is also reachable through synthesize_and_promote_skill().
**Remediation**: `Remove automatic execution of synthesized test code. Require explicit human approval and a signed test artifact. If execution is required, run inside a real OS sandbox: container/nsjail/bubblewrap, dedicated low-privilege UID, no network, read-only bind mounts, seccomp, rlimits, clean environment, and a hard timeout. Never describe subprocess.run(timeout=...) as a sandbox.`

### 2. [HIGH] VULN-002: YAML frontmatter injection via synthesized description
**Description**: generate_skill_template() interpolates description into a YAML folded scalar using only two leading spaces on the first line. A description containing newline plus 'name: attacker-skill' or 'version: 999.0.0' breaks out of the scalar and injects arbitrary frontmatter keys. parse_frontmatter() then trusts those keys, enabling skill impersonation, registry poisoning, and prompt-injection payloads inside SKILL.md.
**Remediation**: `Do not hand-build YAML. Serialize frontmatter with a safe encoder or validate description by rejecting newlines, '---', control characters, and leading/trailing unindented keys. Enforce max description length. Re-parse the generated file and assert that only expected keys/values exist before promotion.`

### 3. [CRITICAL] VULN-003: Unbounded inverted-index and tokenization memory amplification
**Description**: indexer.extract_tokens() indexes every word and hyphenated compound from skill name, description, and plugin name with no caps. build_index() materializes token_index lists and dumps the full registry as JSON. resolver.load_registry() loads the entire JSON into RAM. mcp_gateway.index_mcp_tools() similarly stores every token from tool descriptions and parameter names. A malicious or malformed SKILL.md/MCP schema with a multi-megabyte description can force OOM or extreme memory pressure in the resolver process.
**Remediation**: `Enforce hard byte limits on SKILL.md, plugin.json, MCP schema JSON, package.json, and requirements files. Cap description length, token count per skill/tool, token length, and registry size. Reject binary/control-character content. Stream or mmap large JSON. Add explicit OOM guards and tests for oversized inputs.`

### 4. [CRITICAL] VULN-004: MCP validator is bypassable and malformed schemas crash dynamic dispatch
**Description**: validate_tool_arguments() does not require arguments to be a dict, does not reject additionalProperties, ignores enum/format/min/max/nested schemas, and treats bool as valid int/number because bool is a subclass of int. index_mcp_tools() assumes name/description are strings and parameters/properties are dicts; a schema with description: [] or properties: {x: 'string'} crashes tokenize() or route_mcp_tool() when v.get('type') is called. This can cause a dynamic MCP bus crash or allow invalid arguments to reach destructive tools.
**Remediation**: `Treat MCP schemas as untrusted input. Validate schema root and field types before indexing. Reject non-dict parameters/properties and non-string name/description. Implement recursive JSON-schema subset validation: required, type, enum, additionalProperties=false, array items, nested objects, and bool-before-int type checks. Return structured validation errors instead of raising. Never route a tool whose schema failed validation.`

### 5. [HIGH] VULN-005: Arbitration tie-breaking is non-deterministic and can drop the arbitrated winner
**Description**: candidates.sort(key=lambda c: c['raw_score'], reverse=True) has no deterministic tie-breaker. Candidate insertion depends on set iteration over all_target_tokens, so equal-score candidates can order differently across processes. _arbitrate_candidates() removes an existing candidate and appends the replacement to the end of selected. resolve_skill() then slices arbitrated[:top_k], so a replacement arbitration decision can be excluded entirely while the candidate it replaced is also gone. Domain grouping by first SPECIFICITY_MAP substring and version-string comparison makes selection brittle and manipulable.
**Remediation**: `Define a total deterministic ordering: raw_score, specificity, quality_score, scope priority, parsed version tuple, source type, then skill name. Re-sort selected after every replacement. Do not use substring-first domain grouping; compute explicit domain keys. Make version comparison return a tuple and never treat inconclusive versions as equal winners by accident.`

### 6. [HIGH] VULN-006: Registry and learned-affinity writes are non-atomic and silently lossy
**Description**: build_index() writes registry.json directly with open(..., 'w') and json.dump(), so a crash or concurrent read can observe a truncated or partially written registry. save_learned_affinities() falls back to direct write on failure and uses a temp path containing only os.getpid(), so two threads in the same process collide on the same temp file. load_learned_affinities() and load_registry() catch broad exceptions and silently return defaults or rebuild, masking corruption and enabling repeated rebuild loops.
**Remediation**: `Write registry and affinity files with a unique temp file, flush, fsync, and atomic os.replace(). Add advisory file locking or a single-writer queue. Add thread locks around same-process save operations. On corruption, emit a diagnostic and fail or quarantine the file instead of silently resetting. Add stale-lock recovery if file locks are introduced.`

### 7. [HIGH] VULN-007: Symlink traversal in workspace stack and assimilator scans
**Description**: detect_workspace_stack() uses os.scandir() and entry.is_dir() with default follow_symlinks=True, then scans subdirectories. assimilator.find_workspace_skills() and find_workspace_rules() use glob patterns that can follow symlinks. A malicious workspace can point a scanned directory or skill path at a large or sensitive location outside the workspace, causing out-of-workspace reads, information exposure through inferred tags/rules, and CPU/IO denial of service.
**Remediation**: `Use follow_symlinks=False for DirEntry checks. Resolve realpath() for every discovered path and verify it is contained under the workspace root before reading. Reject symlinked skill/rule directories. Add scan depth, entry count, and total byte limits.`

### 8. [MEDIUM] VULN-008: MCP discovery treats generic plugin JSON as tool schemas and trusts workspace configs
**Description**: discover_mcp_servers() scans plugin directories and accepts any JSON file except package.json, tsconfig.json, and codex_contract.json. plugin.json is not excluded, so normal plugin metadata can be indexed as an MCP tool. Workspace MCP configs under .cursor/mcp.json, mcp.json, .vscode/mcp.json, and .specify/mcp.json are ingested without sanitization or allowlisting, enabling routing pollution or malicious tool injection in untrusted workspaces.
**Remediation**: `Require an explicit MCP manifest or tool-schema marker. Exclude plugin.json and all known metadata files. Validate server definitions and tool schemas before indexing. For untrusted workspaces, require user approval or a signed allowlist before ingesting workspace MCP configs.`

### 9. [MEDIUM] VULN-009: Unbounded regex/tokenization input enables CPU and memory denial of service
**Description**: No classic catastrophic ReDoS pattern was found; the regexes are mostly linear. However extract_query_tokens(), extract_tokens(), mcp_gateway.tokenize(), and route_mcp_tool() run regexes and set operations over unbounded intent_text, SKILL.md descriptions, and MCP descriptions. A multi-megabyte prompt or schema creates very large token sets, high CPU, and memory amplification even without exponential backtracking.
**Remediation**: `Cap input bytes before regex/tokenization. Reject oversized prompts and schemas. Limit total tokens and token length. Precompile regexes. Add fuzz/benchmark tests with multi-MB inputs and many hyphenated compounds.`

## 3. Concurrency, Race Condition & Mutex Hazards (5 identified)
- **Resource**: `registry.json` | **Hazard**: Reader sees partially written JSON while build_index() writes directly; concurrent rebuilds overwrite each other; load_registry() silently rebuilds on parse failure. | **Mitigation**: Write to a unique temp file, fsync, and os.replace(). Serialize index builds with a lock file or single-writer queue. Fail loudly with diagnostic context on corruption instead of silently rebuilding in a loop.
- **Resource**: `learned_affinities.json` | **Hazard**: record_feedback() performs load-modify-save without locking; concurrent calls lose updates; temp path uses only os.getpid(), so same-process threads collide on the same temp file. | **Mitigation**: Add an in-process threading.Lock plus an inter-process advisory lock. Use uuid4 in temp file names. Use atomic replace and fsync. Detect and recover stale locks with an owner PID and timestamp.
- **Resource**: `mcp_gateway module globals _CACHED_MCP_INDEX, _CACHED_MCP_TIME, _LAST_STALE_CHECK` | **Hazard**: Concurrent route_mcp_tool() calls can trigger multiple stale checks and reindex operations against shared mutable globals without a lock, producing transient inconsistent indexes. | **Mitigation**: Guard cache reads/writes with threading.Lock. Use an immutable snapshot object swapped atomically. Avoid unbounded duplicate reindex work with a single-flight lock.
- **Resource**: `Skill promotion in synthesizer.py` | **Hazard**: synthesize_and_promote_skill() writes SKILL.md directly and then rebuilds the registry; concurrent promotions with the same clean_name can interleave writes and index stale or partial content. | **Mitigation**: Lock per target skill name. Write SKILL.md atomically. Rebuild or update the registry under the same registry lock. Return failure if indexing fails instead of swallowing the exception.
- **Resource**: `MCP cache freshness check` | **Hazard**: is_mcp_stale() checks directory mtime and files without a lock; concurrent file creation/deletion can be missed or cause repeated reindex storms. | **Mitigation**: Use a short TTL plus single-flight reindex. Record a generation/version token. Revalidate after reindex. Add lock-file stale recovery if inter-process coordination is added.

## 4. Defensive Failure Scenarios & Edge Cases (10 verified)
### 1. MCP tool schema contains description: [] or name: 123.
- **Consequence**: index_mcp_tools() calls tokenize() on a non-string, raising TypeError and breaking the entire MCP index build.
- **Mitigation**: Validate root schema field types before indexing. Skip invalid tools with a diagnostic and a counter instead of crashing the bus.

### 2. MCP tool properties contains {x: 'string'} instead of {x: {'type': 'string'}}.
- **Consequence**: route_mcp_tool() calls v.get('type'), raising AttributeError; validate_tool_arguments() also assumes dict property definitions.
- **Mitigation**: Reject non-dict property schemas. Normalize or drop invalid properties during indexing.

### 3. validate_tool_arguments() receives arguments = [] or null.
- **Consequence**: required membership tests or arguments.items() raise TypeError/AttributeError instead of returning invalid.
- **Mitigation**: Require isinstance(arguments, dict); return valid=false with a diagnostic if not.

### 4. A boolean argument is supplied for an integer/number field.
- **Consequence**: Because bool subclasses int, validation wrongly accepts it and may dispatch invalid MCP arguments.
- **Mitigation**: Check isinstance(val, bool) before int/number checks and reject bools for numeric fields.

### 5. Synthesized description contains a newline followed by 'name: evil-skill'.
- **Consequence**: Frontmatter injection changes the registered skill name/version/metadata and enables registry poisoning or prompt injection.
- **Mitigation**: Reject control/newline characters in description or use a safe YAML encoder; re-parse and assert allowed keys before promotion.

### 6. Skill name sanitizes to empty string, e.g., '..' or '///'.
- **Consequence**: target_dir becomes the library root and SKILL.md is written at library/SKILL.md, potentially overwriting an unrelated file.
- **Mitigation**: Reject empty clean_name and names outside [a-z0-9-], enforce max length, and verify the target path is exactly one directory under library_dir.

### 7. Two skills have equal raw_score and same specificity/version.
- **Consequence**: Set iteration and stable sort order determine the winner; selection is non-reproducible across runs and can choose the wrong skill.
- **Mitigation**: Add a total deterministic tie-breaker and re-sort after arbitration replacements.

### 8. A replacement candidate is appended after arbitration but top_k is small.
- **Consequence**: The arbitrated winner is sliced off and the resolver returns neither the original candidate nor the replacement.
- **Mitigation**: Sort selected by final ranking after every replacement before slicing to top_k.

### 9. Workspace contains a symlink to /etc or a huge external directory.
- **Consequence**: detect_workspace_stack() and assimilator scans can read outside the workspace, leak path/metadata information, or cause IO/CPU DoS.
- **Mitigation**: Disable symlink following, realpath-check containment, and cap scan depth/entries.

### 10. registry.json is truncated by a crash during build_index().
- **Consequence**: load_registry() catches the parse exception and rebuilds silently; if rebuild also fails due to permissions, the resolver crashes without clear context or loops in rebuild attempts.
- **Mitigation**: Use atomic replace. On corruption, emit a diagnostic, quarantine the bad file, and fail with an actionable error if rebuild cannot complete.

## 5. Prescriptive Remediation Directives (10 items)
- Remove automatic execution of synthesized test code or replace it with a real OS sandbox and explicit human approval.
- Serialize skill frontmatter with a safe encoder and reject newlines/control characters in description before writing SKILL.md.
- Add hard size, token-count, token-length, and registry-size limits across indexer.py, resolver.py, and mcp_gateway.py.
- Treat MCP JSON schemas as untrusted: validate root fields, property types, required lists, and reject malformed tools before indexing or routing.
- Implement recursive MCP argument validation with additionalProperties=false, enum/format checks, and bool-before-int type discrimination.
- Replace arbitration with a total deterministic ordering and re-sort selected candidates after every replacement before top_k slicing.
- Make registry.json and learned_affinities.json writes atomic with temp files, fsync, os.replace(), unique temp names, and advisory locks.
- Use follow_symlinks=False and realpath containment checks for every workspace scan; reject symlinked skill/rule paths.
- Require explicit MCP manifests and exclude plugin.json/metadata JSON from tool indexing; gate workspace MCP configs behind trust approval.
- Replace broad except Exception: pass blocks with fail-loud diagnostics that include path, operation, and exception class; add fuzz tests for malformed JSON, oversized inputs, tied scores, and concurrent writers.

## 6. Council Gate Final Verdict: `REJECTED`
