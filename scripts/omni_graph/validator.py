"""Signature Contract Guard and Validator for Omni-Graph (Graphify)."""

from __future__ import annotations

import ast
import difflib
import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from omni_graph.visitor import (
    _JS_ARROW_RE,
    _JS_CALL_RE,
    _JS_FUNC_RE,
    _JS_IMPORT_RE,
    _extract_js_call_args,
)

@dataclass(frozen=True)
class ValidationResult:
    """Result of a signature contract validation."""
    is_valid: bool
    error_code: Optional[str] = None
    message: Optional[str] = None
    suggested_fix: Optional[str] = None

class HardenedSignatureContractValidator:
    """
    Validates a call site against an extracted signature contract.
    Enforces method receiver binding, positional-only arguments (PEP 570),
    keyword validity, and required argument completeness.
    """

    @staticmethod
    def _slice_binding(
        node_type: str,
        posonly_args: List[str],
        args: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Remove implicit self / cls for bound methods."""
        if node_type not in ("method", "async_method"):
            return posonly_args, args

        if posonly_args and posonly_args[0] in ("self", "cls"):
            return posonly_args[1:], args

        if args and args[0] in ("self", "cls"):
            return posonly_args, args[1:]

        return posonly_args, args

    @staticmethod
    def validate(
        node_id: str,
        node_type: str,
        sig_data: Dict[str, Any],
        call_args_count: int,
        call_kwargs: List[str],
        has_splat_pos: bool = False,
        has_splat_kw: bool = False,
        renamed_params: Optional[Dict[str, str]] = None,
    ) -> ValidationResult:
        # 1. Unpack parameters and strip method receiver if bound method
        posonly_args: List[str] = list(sig_data.get("posonly_args", []))
        args: List[str] = list(sig_data.get("args", []))
        defaults_count: int = int(sig_data.get("defaults_count", 0))
        vararg: Optional[str] = sig_data.get("vararg")
        kwonly_args: List[str] = list(sig_data.get("kwonly_args", []))
        kw_defaults: List[bool] = list(sig_data.get("kw_defaults", []))
        kwarg: Optional[str] = sig_data.get("kwarg")

        posonly_args, args = HardenedSignatureContractValidator._slice_binding(
            node_type, posonly_args, args
        )

        # 2. Positional argument count check
        total_pos_slots = len(posonly_args) + len(args)
        if not has_splat_pos and call_args_count > total_pos_slots and not vararg:
            return ValidationResult(
                False,
                "TOO_MANY_POSITIONAL_ARGS",
                f"Received {call_args_count} positional args, expected at most {total_pos_slots}",
                None,
            )

        # 3. Keyword argument validity check
        allowed_kw = set(args) | set(kwonly_args)
        posonly_set = set(posonly_args)

        for kw in call_kwargs:
            if kw in posonly_set:
                return ValidationResult(
                    False,
                    "POSITIONAL_ONLY_AS_KEYWORD",
                    f"Parameter '{kw}' is positional-only and cannot be passed as keyword",
                    f"Pass '{kw}' as positional argument",
                )

            if not has_splat_kw and kw not in allowed_kw and not kwarg:
                suggestion: Optional[str] = None
                if renamed_params and kw in renamed_params:
                    suggestion = f"Did you mean '{renamed_params[kw]}'?"
                else:
                    close = difflib.get_close_matches(kw, list(allowed_kw), n=1, cutoff=0.5)
                    if close:
                        suggestion = f"Did you mean '{close[0]}'?"

                return ValidationResult(
                    False,
                    "UNEXPECTED_KEYWORD_ARG",
                    f"Unexpected keyword argument '{kw}'. Allowed parameters: {sorted(list(allowed_kw))}",
                    suggestion,
                )

        # 4. Required argument completeness check (when call sites don't use splats)
        if not has_splat_pos and not has_splat_kw:
            # a) Required keyword-only arguments
            for i, kw in enumerate(kwonly_args):
                has_def = kw_defaults[i] if i < len(kw_defaults) else False
                if not has_def and kw not in call_kwargs:
                    return ValidationResult(
                        False,
                        "MISSING_REQUIRED_KWONLY_ARG",
                        f"Missing required keyword-only argument '{kw}'",
                        f"Add {kw}=...",
                    )

            # b) Required positional arguments (posonly + regular args before defaults)
            num_required_pos = max(0, total_pos_slots - defaults_count)
            for idx in range(num_required_pos):
                if idx < len(posonly_args):
                    param_name = posonly_args[idx]
                    supplied = call_args_count > idx
                else:
                    arg_idx = idx - len(posonly_args)
                    param_name = args[arg_idx]
                    supplied = (call_args_count > idx) or (param_name in call_kwargs)

                if not supplied:
                    return ValidationResult(
                        False,
                        "MISSING_REQUIRED_ARG",
                        f"Missing required argument '{param_name}'",
                        f"Pass '{param_name}'",
                    )

        return ValidationResult(True, None, "Signature contract valid", None)

def validate_call_site(
    conn: sqlite3.Connection,
    target_symbol_or_id: str,
    call_args_count: int,
    call_kwargs: List[str],
    *,
    has_splat_pos: bool = False,
    has_splat_kw: bool = False,
    renamed_params: Optional[Dict[str, str]] = None,
) -> ValidationResult:
    """
    Retrieve signature contract from DB and validate call site.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count,
               s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg
        FROM signatures s
        JOIN nodes n ON s.node_id = n.id
        WHERE s.node_id = ? OR n.name = ? OR n.qualified_name = ?
        LIMIT 1
        """,
        (target_symbol_or_id, target_symbol_or_id, target_symbol_or_id),
    )
    row = cur.fetchone()
    if row is None:
        return ValidationResult(True, "UNKNOWN_TARGET", f"No signature found for '{target_symbol_or_id}'", None)

    (
        node_id,
        node_type,
        posonly_json,
        args_json,
        defaults_count,
        vararg,
        kwonly_json,
        kw_defaults_json,
        kwarg,
    ) = row

    def _load_json(val: Any) -> Any:
        if val is None:
            return []
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return val

    sig_data: Dict[str, Any] = {
        "posonly_args": _load_json(posonly_json),
        "args": _load_json(args_json),
        "defaults_count": defaults_count,
        "vararg": vararg,
        "kwonly_args": _load_json(kwonly_json),
        "kw_defaults": _load_json(kw_defaults_json),
        "kwarg": kwarg,
    }

    return HardenedSignatureContractValidator.validate(
        node_id=node_id,
        node_type=node_type,
        sig_data=sig_data,
        call_args_count=call_args_count,
        call_kwargs=call_kwargs,
        has_splat_pos=has_splat_pos,
        has_splat_kw=has_splat_kw,
        renamed_params=renamed_params,
    )


_SKIP_BUILTIN_CALLS = frozenset({
    "len", "print", "str", "int", "float", "bool", "dict", "list", "set", "tuple",
    "isinstance", "issubclass", "getattr", "setattr", "hasattr", "open", "range",
    "enumerate", "zip", "sorted", "reversed", "min", "max", "sum", "any", "all",
    "super", "type", "repr", "id", "hash", "abs", "round", "format", "next", "iter",
    "Exception", "ValueError", "TypeError", "RuntimeError", "KeyError", "OSError",
    "Path", "get", "items", "keys", "values", "append", "extend", "strip", "split",
    "join", "replace", "lower", "upper", "startswith", "endswith", "encode", "decode",
    "read_text", "write_text", "mkdir", "exists", "is_file", "is_dir", "close",
    "execute", "fetchall", "fetchone", "commit", "cursor", "format", "pop", "update",
})


def _row_to_sig_data(row: Any) -> Dict[str, Any]:
    def _load(val: Any) -> Any:
        if val is None:
            return []
        if isinstance(val, str):
            try:
                return json.loads(val)
            except Exception:
                return []
        return val

    return {
        "posonly_args": _load(row[2]),
        "args": _load(row[3]),
        "defaults_count": row[4],
        "vararg": row[5],
        "kwonly_args": _load(row[6]),
        "kw_defaults": _load(row[7]),
        "kwarg": row[8],
    }


def audit_python_calls(
    conn: sqlite3.Connection,
    source_code: str,
    target_lines: Optional[Tuple[int, int]] = None,
    exclude_file_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Statically validates Python AST calls in source_code against unambiguous workspace
    signatures in codebase_graph.db. Fails soft on syntax errors (zero false positives).
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    def _extract_py_import_map(tree: ast.AST) -> Dict[str, Tuple[str, ...]]:
        import_map: Dict[str, Tuple[str, ...]] = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    local_name = alias.asname or alias.name.split(".")[0]
                    mod_p = alias.name.replace(".", "/")
                    import_map[local_name] = (f"{mod_p}.py", f"{mod_p}/__init__.py", mod_p)
            elif isinstance(n, ast.ImportFrom):
                if n.module:
                    mod_path = n.module.replace(".", "/")
                    for alias in n.names:
                        local_name = alias.asname or alias.name
                        sub_path = f"{mod_path}/{alias.name}"
                        import_map[local_name] = (
                            f"{mod_path}.py",
                            f"{mod_path}/__init__.py",
                            f"{sub_path}.py",
                            f"{sub_path}/__init__.py",
                        )
        return import_map

    import_map = _extract_py_import_map(tree)
    violations: List[Dict[str, Any]] = []
    cur = conn.cursor()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        lineno = getattr(node, "lineno", 0)
        if target_lines and not (target_lines[0] <= lineno <= target_lines[1]):
            continue

        sym = None
        dotted = None
        if isinstance(node.func, ast.Name):
            sym = node.func.id
        elif isinstance(node.func, ast.Attribute):
            sym = node.func.attr
            if isinstance(node.func.value, ast.Name):
                dotted = f"{node.func.value.id}.{sym}"
        if not sym or sym.startswith("_") or sym in _SKIP_BUILTIN_CALLS:
            continue

        rows = []
        if dotted:
            cur.execute(
                "SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count, "
                "s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg, n.file_path "
                "FROM signatures s JOIN nodes n ON s.node_id = n.id "
                "WHERE n.qualified_name = ? LIMIT 10",
                (dotted,),
            )
            rows = cur.fetchall()
        if not rows:
            cur.execute(
                "SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count, "
                "s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg, n.file_path "
                "FROM signatures s JOIN nodes n ON s.node_id = n.id "
                "WHERE n.name = ? LIMIT 10",
                (sym,),
            )
            rows = cur.fetchall()

        if len(rows) > 1:
            base_sym = dotted.split(".")[0] if dotted else sym
            mod_hints = import_map.get(base_sym)
            if mod_hints:
                filtered = []
                for r in rows:
                    fpath = (r[9] or "").replace("\\", "/").lower()
                    if any(fpath == h.lower() or fpath.endswith("/" + h.lower()) for h in mod_hints):
                        filtered.append(r)
                if filtered:
                    rows = filtered

        if len(rows) > 1:
            first_sig = rows[0][1:9]
            if all(r[1:9] == first_sig for r in rows):
                rows = [rows[0]]

        if len(rows) != 1:
            continue
        row = rows[0]
        norm_excl = exclude_file_path.replace("\\", "/").lower() if exclude_file_path else None
        if norm_excl and (row[9] or "").replace("\\", "/").lower() == norm_excl:
            continue

        call_args_count = sum(1 for a in node.args if not isinstance(a, ast.Starred))
        has_splat_pos = any(isinstance(a, ast.Starred) for a in node.args)
        call_kwargs = [k.arg for k in node.keywords if k.arg is not None]
        has_splat_kw = any(k.arg is None for k in node.keywords)

        res = HardenedSignatureContractValidator.validate(
            node_id=row[0],
            node_type=row[1],
            sig_data=_row_to_sig_data(row),
            call_args_count=call_args_count,
            call_kwargs=call_kwargs,
            has_splat_pos=has_splat_pos,
            has_splat_kw=has_splat_kw,
        )
        if not res.is_valid:
            violations.append({
                "line": lineno,
                "symbol": dotted or sym,
                "defined_in": row[9],
                "error_code": res.error_code,
                "message": res.message,
                "suggested_fix": res.suggested_fix,
            })
    cur.close()
    return violations


def audit_callers_of_file(
    conn: sqlite3.Connection,
    canonical_file_path: str,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    """
    Checks external call sites in other workspace files against updated signatures
    defined inside canonical_file_path.
    """
    norm = canonical_file_path.replace("\\", "/").lower()
    stem = norm.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT file_path FROM edges WHERE relation_type = 'imports' "
        "AND (target_id = ? OR target_id LIKE ? OR target_id LIKE ? OR target_id LIKE ?)",
        (stem, f"%.{stem}", f"{stem}.%", f"%/{stem}"),
    )
    importing_files = {r[0].replace("\\", "/").lower() for r in cur.fetchall() if r[0]}

    cur.execute(
        "SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count, "
        "s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg, n.name, n.qualified_name "
        "FROM signatures s JOIN nodes n ON s.node_id = n.id WHERE n.file_path = ?",
        (norm,),
    )
    defs = cur.fetchall()
    violations: List[Dict[str, Any]] = []
    for row in defs:
        name, qname = row[9], row[10]
        if name.startswith("_"):
            continue
        cur.execute("SELECT COUNT(*) FROM nodes WHERE name = ?", (name,))
        is_unique = cur.fetchone()[0] == 1
        sig_data = _row_to_sig_data(row)
        cur.execute(
            "SELECT file_path, line_number, call_args_count, call_kwargs, has_splat_pos, has_splat_kw, target_id "
            "FROM edges WHERE relation_type = 'calls' AND file_path != ? "
            "AND (target_id = ? OR target_id = ? OR target_id LIKE ?)",
            (norm, name, qname, f"%.{name}"),
        )
        for edge in cur.fetchall():
            if edge[2] is None:
                continue
            f_path_edge = (edge[0] or "").replace("\\", "/").lower()
            target_id_str = (edge[6] or "").lower()
            if not is_unique and f_path_edge not in importing_files and not target_id_str.startswith(f"{stem}."):
                continue
            try:
                kw_list = json.loads(edge[3]) if edge[3] else []
            except Exception:
                kw_list = []
            res = HardenedSignatureContractValidator.validate(
                node_id=row[0],
                node_type=row[1],
                sig_data=sig_data,
                call_args_count=int(edge[2]),
                call_kwargs=kw_list,
                has_splat_pos=bool(edge[4]),
                has_splat_kw=bool(edge[5]),
            )
            if not res.is_valid:
                violations.append({
                    "file_path": edge[0],
                    "line": edge[1],
                    "symbol": name,
                    "error_code": res.error_code,
                    "message": res.message,
                    "suggested_fix": res.suggested_fix,
                })
                if len(violations) >= limit:
                    cur.close()
                    return violations
    cur.close()
    return violations


_JS_TS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

_JS_SKIP_KEYWORDS = frozenset({
    "if", "for", "while", "switch", "catch", "function", "return", "new", "typeof", "await", "import", "require", "super", "constructor",
    "log", "warn", "error", "push", "pop", "map", "filter", "reduce", "forEach", "find", "some", "every", "includes", "join", "split", "slice", "trim", "keys", "values", "entries", "stringify", "parse", "resolve", "reject", "all", "then"
})


def _extract_js_call_obj_keys(source: str, open_paren_idx: int) -> Tuple[List[str], bool]:
    """If a JS/TS call passes a single `{ k1, k2: v }` object literal, returns (keys, has_spread)."""
    from omni_graph.visitor import _split_js_args
    depth = 0
    end_idx = open_paren_idx
    for i in range(open_paren_idx, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                end_idx = i
                break
    inside = source[open_paren_idx + 1:end_idx].strip()
    args = _split_js_args(inside, track_generics=False)
    if len(args) != 1 or not args[0].startswith("{") or not args[0].endswith("}"):
        return [], False
    body = args[0][1:-1].strip()
    keys: List[str] = []
    has_spread = False
    for item in _split_js_args(body, track_generics=False):
        if item.startswith("..."):
            has_spread = True
            continue
        k = item.split(":", 1)[0].strip()
        if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", k):
            keys.append(k)
    return keys, has_spread


def _resolve_ts_interface_fields(
    conn: sqlite3.Connection,
    type_name: str,
    visited: Optional[set] = None,
    depth: int = 0,
) -> Tuple[List[str], List[bool]]:
    """Recursively resolves TS interface/type fields across `extends`, `Pick`, `Omit`, and `&`."""
    if depth > 4:
        return [], []
    seen = visited if visited is not None else set()
    if type_name in seen:
        return [], []
    seen.add(type_name)

    cur = conn.cursor()
    cur.execute(
        "SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count, "
        "s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg, n.file_path "
        "FROM signatures s JOIN nodes n ON s.node_id = n.id "
        "WHERE n.node_type = 'interface' AND n.name = ? LIMIT 2",
        (type_name,),
    )
    trows = cur.fetchall()
    if len(trows) != 1:
        cur.close()
        return [], []
    trow = trows[0]
    tsig = _row_to_sig_data(trow)
    tag = tsig.get("kwarg") or ""

    if isinstance(tag, str) and (tag.startswith("__ts_pick__:") or tag.startswith("__ts_omit__:")):
        cur.close()
        parts = tag.split(":", 2)
        if len(parts) == 3:
            op, base_name, keys_csv = parts
            target_keys = [k for k in keys_csv.split(",") if k]
            b_keys, b_opts = _resolve_ts_interface_fields(conn, base_name, seen, depth + 1)
            if op == "__ts_pick__":
                tset = set(target_keys)
                pairs = [(k, o) for k, o in zip(b_keys, b_opts) if k in tset]
                return [p[0] for p in pairs], [p[1] for p in pairs]
            else:
                oset = set(target_keys)
                pairs = [(k, o) for k, o in zip(b_keys, b_opts) if k not in oset]
                return [p[0] for p in pairs], [p[1] for p in pairs]
        return [], []

    cur.execute(
        "SELECT target_id FROM edges WHERE source_id = ? AND relation_type = 'inherits'",
        (trow[0],),
    )
    parent_names = [r[0] for r in cur.fetchall()]
    cur.close()

    merged: Dict[str, bool] = {}
    for pname in parent_names:
        p_keys, p_opts = _resolve_ts_interface_fields(conn, pname, seen, depth + 1)
        for k, o in zip(p_keys, p_opts):
            merged[k] = o

    direct_keys = tsig.get("kwonly_args") or []
    direct_opts = tsig.get("kw_defaults") or []
    for i, k in enumerate(direct_keys):
        merged[k] = direct_opts[i] if i < len(direct_opts) else False

    return list(merged.keys()), list(merged.values())


def audit_js_ts_calls(
    conn: sqlite3.Connection,
    source_code: str,
    target_lines: Optional[Tuple[int, int]] = None,
    exclude_file_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Statically validates JS/TS/JSX/TSX call arg counts and destructured option keys."""
    from omni_graph.visitor import (
        _JS_ARROW_RE,
        _JS_CALL_RE,
        _JS_FUNC_RE,
        _JS_IMPORT_RE,
        _JS_METHOD_RE,
        _extract_js_call_args,
        _strip_js_comments_and_strings,
    )

    clean_code = _strip_js_comments_and_strings(source_code, strip_strings=False)
    call_code = _strip_js_comments_and_strings(source_code, strip_strings=True)

    import_map: Dict[str, str] = {}
    for m_imp in _JS_IMPORT_RE.finditer(clean_code):
        mod = m_imp.group("mod") or m_imp.group("req_mod") or ""
        if not mod:
            continue
        mod_stem = mod.replace("\\", "/").split("/")[-1].rsplit(".", 1)[0]
        if m_imp.group("def"):
            import_map[m_imp.group("def")] = mod_stem
        named = m_imp.group("named") or ""
        for item in named.split(","):
            item_clean = item.strip().split(" as ")[-1].strip()
            if item_clean:
                import_map[item_clean] = mod_stem

    decl_lines: set[int] = set()
    for pat in (_JS_FUNC_RE, _JS_ARROW_RE, _JS_METHOD_RE):
        for dm in pat.finditer(clean_code):
            s_ln = clean_code[:dm.start()].count("\n") + 1
            e_ln = clean_code[:dm.end()].count("\n") + 1
            for ln in range(s_ln, e_ln + 1):
                decl_lines.add(ln)

    violations: List[Dict[str, Any]] = []
    cur = conn.cursor()
    for m_call in _JS_CALL_RE.finditer(call_code):
        callee = m_call.group("callee")
        sym = callee.split(".")[-1]
        if not sym or sym in _JS_SKIP_KEYWORDS or sym.startswith("_"):
            continue

        lineno = call_code[:m_call.start()].count("\n") + 1
        if lineno in decl_lines:
            continue
        if target_lines and not (target_lines[0] <= lineno <= target_lines[1]):
            continue

        call_args_count, has_splat = _extract_js_call_args(call_code, m_call.end() - 1)
        rows = []
        if "." in callee:
            cur.execute(
                "SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count, "
                "s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg, n.file_path "
                "FROM signatures s JOIN nodes n ON s.node_id = n.id "
                "WHERE n.qualified_name = ? LIMIT 10",
                (callee,),
            )
            rows = [r for r in cur.fetchall() if any((r[9] or "").lower().endswith(ext) for ext in _JS_TS_EXTS)]
        if not rows:
            cur.execute(
                "SELECT s.node_id, n.node_type, s.posonly_args, s.args, s.defaults_count, "
                "s.vararg, s.kwonly_args, s.kw_defaults, s.kwarg, n.file_path "
                "FROM signatures s JOIN nodes n ON s.node_id = n.id "
                "WHERE n.name = ? LIMIT 10",
                (sym,),
            )
            rows = [r for r in cur.fetchall() if any((r[9] or "").lower().endswith(ext) for ext in _JS_TS_EXTS)]
        if not rows:
            continue

        if len(rows) > 1:
            base_sym = callee.split(".")[0] if "." in callee else sym
            mod_hint = import_map.get(base_sym) or import_map.get(sym)
            if mod_hint:
                filtered = [r for r in rows if mod_hint.lower() in (r[9] or "").replace("\\", "/").lower()]
                if filtered:
                    rows = filtered

        if len(rows) > 1:
            first_sig = rows[0][1:9]
            if all(r[1:9] == first_sig for r in rows):
                rows = [rows[0]]

        if len(rows) != 1:
            continue
        row = rows[0]
        norm_excl = exclude_file_path.replace("\\", "/").lower() if exclude_file_path else None
        if norm_excl and (row[9] or "").replace("\\", "/").lower() == norm_excl:
            continue

        sig_data = _row_to_sig_data(row)
        kw_args_defined = sig_data.get("kwonly_args") or []
        kw_defs_defined = sig_data.get("kw_defaults") or []
        if not kw_args_defined and isinstance(sig_data.get("kwarg"), str) and sig_data["kwarg"].startswith("__ts_type__:"):
            tname = sig_data["kwarg"].split(":", 1)[1]
            kw_args_defined, kw_defs_defined = _resolve_ts_interface_fields(conn, tname)
        if kw_args_defined:
            obj_keys, obj_spread = _extract_js_call_obj_keys(call_code, m_call.end() - 1)
            if obj_keys or obj_spread:
                # Validate destructured/typed option object keys against kwonly_args
                res = HardenedSignatureContractValidator.validate(
                    node_id=row[0],
                    node_type="function",
                    sig_data={
                        "posonly_args": [],
                        "args": [],
                        "defaults_count": 0,
                        "vararg": None,
                        "kwonly_args": kw_args_defined,
                        "kw_defaults": kw_defs_defined or [True] * len(kw_args_defined),
                        "kwarg": None,
                    },
                    call_args_count=0,
                    call_kwargs=obj_keys,
                    has_splat_pos=False,
                    has_splat_kw=obj_spread,
                )
            else:
                res = HardenedSignatureContractValidator.validate(
                    node_id=row[0],
                    node_type="function",
                    sig_data={**sig_data, "kwonly_args": [], "kw_defaults": []},
                    call_args_count=call_args_count,
                    call_kwargs=[],
                    has_splat_pos=has_splat,
                    has_splat_kw=False,
                )
        else:
            res = HardenedSignatureContractValidator.validate(
                node_id=row[0],
                node_type="function",
                sig_data=sig_data,
                call_args_count=call_args_count,
                call_kwargs=[],
                has_splat_pos=has_splat,
                has_splat_kw=False,
            )
        if not res.is_valid:
            violations.append({
                "line": lineno,
                "symbol": callee,
                "defined_in": row[9],
                "error_code": res.error_code,
                "message": res.message,
                "suggested_fix": res.suggested_fix,
            })

    cur.close()
    return violations
