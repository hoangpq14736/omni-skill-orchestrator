"""Universal AST & Pattern Visitor for Omni-Graph (Graphify).

Supports polyglot codebase parsing for Python, JavaScript/TypeScript, Go, Rust, SQL, Shell, Markdown, and Configs.
100% Python standard library (zero native wheels required).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import List, Tuple, Optional, Any, Dict

# --------------------------------------------------------------------------- #
# 1. Python Native AST Visitor (Deep Precision)
# --------------------------------------------------------------------------- #

def _unparse_expr(node: ast.AST) -> str:
    """Return dotted string or unparsed representation for an AST expression."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        val = _unparse_expr(node.value)
        return f"{val}.{node.attr}" if val else node.attr
    elif isinstance(node, ast.Call):
        return _unparse_expr(node.func)
    try:
        return ast.unparse(node)
    except Exception:
        return ""

def _docstring(node: ast.AST) -> Optional[str]:
    return ast.get_docstring(node, clean=True)

class CodebaseASTVisitor(ast.NodeVisitor):
    def __init__(self, canonical_file_path: str, display_path: str, source_code: str):
        self.canonical_file_path = canonical_file_path
        self.display_path = display_path
        self.source_code = source_code

        self.nodes: List[Tuple] = []
        self.signatures: List[Tuple] = []
        self.edges: List[Tuple] = []
        self.lifecycle_hooks: List[Tuple] = []

        # Scope stack entries: (scope_id, scope_name, qualified_prefix, scope_type)
        self.scope_stack: List[Tuple[str, str, str, str]] = []

    def _current_source_id(self) -> str:
        if self.scope_stack:
            return self.scope_stack[-1][0]
        return f"{self.canonical_file_path}:module"

    def visit_Module(self, node: ast.Module) -> None:
        module_name = Path(self.canonical_file_path).stem
        module_id = f"{self.canonical_file_path}:module"
        self.nodes.append((
            module_id,
            module_name,
            module_name,
            self.canonical_file_path,
            self.display_path,
            1,
            getattr(node, "end_lineno", 1) or 1,
            "module",
            _docstring(node),
            1,
        ))
        self.scope_stack.append((module_id, module_name, "", "module"))
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent_prefix = self.scope_stack[-1][2] if self.scope_stack else ""
        qualified = f"{parent_prefix}.{node.name}" if parent_prefix else node.name
        class_id = f"{self.canonical_file_path}:{qualified}"
        exported = 0 if node.name.startswith("_") else 1

        self.nodes.append((
            class_id,
            node.name,
            qualified,
            self.canonical_file_path,
            self.display_path,
            node.lineno,
            getattr(node, "end_lineno", node.lineno) or node.lineno,
            "class",
            _docstring(node),
            exported,
        ))

        source_id = self._current_source_id()
        for base in node.bases:
            base_name = _unparse_expr(base)
            if base_name:
                self.edges.append((
                    class_id,
                    base_name,
                    "inherits",
                    self.canonical_file_path,
                    base.lineno,
                    getattr(base, "col_offset", 0) or 0,
                    None,
                    json.dumps([]),
                    0,
                    0,
                    0,
                ))

        self.scope_stack.append((class_id, node.name, qualified, "class"))
        self.generic_visit(node)
        self.scope_stack.pop()

    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        parent_prefix = self.scope_stack[-1][2] if self.scope_stack else ""
        parent_type = self.scope_stack[-1][3] if self.scope_stack else "module"
        qualified = f"{parent_prefix}.{node.name}" if parent_prefix else node.name
        func_id = f"{self.canonical_file_path}:{qualified}"
        node_type = "method" if parent_type == "class" else ("async_function" if is_async else "function")
        exported = 0 if (node.name.startswith("_") and not node.name.startswith("__")) else 1

        self.nodes.append((
            func_id,
            node.name,
            qualified,
            self.canonical_file_path,
            self.display_path,
            node.lineno,
            getattr(node, "end_lineno", node.lineno) or node.lineno,
            node_type,
            _docstring(node),
            exported,
        ))

        posonly = [a.arg for a in getattr(node.args, "posonlyargs", [])]
        args = [a.arg for a in node.args.args]
        defaults_count = len(node.args.defaults)
        vararg = node.args.vararg.arg if node.args.vararg else None
        kwonly = [a.arg for a in node.args.kwonlyargs]
        kw_defaults = [1 if d is not None else 0 for d in node.args.kw_defaults]
        kwarg = node.args.kwarg.arg if node.args.kwarg else None
        ret_ann = _unparse_expr(node.returns) if node.returns else None

        self.signatures.append((
            func_id,
            self.canonical_file_path,
            json.dumps(posonly),
            json.dumps(args),
            defaults_count,
            vararg,
            json.dumps(kwonly),
            json.dumps(kw_defaults),
            kwarg,
            ret_ann,
        ))

        for deco in node.decorator_list:
            deco_name = _unparse_expr(deco)
            if deco_name:
                self.edges.append((
                    func_id,
                    deco_name,
                    "decorated_by",
                    self.canonical_file_path,
                    deco.lineno,
                    getattr(deco, "col_offset", 0) or 0,
                    None,
                    json.dumps([]),
                    0,
                    0,
                    0,
                ))
                if any(k in deco_name for k in ("command", "event", "listener", "router", "route", "endpoint")):
                    hook_id = f"{func_id}:hook:{deco_name}"
                    self.lifecycle_hooks.append((
                        hook_id,
                        deco_name,
                        func_id,
                        self.canonical_file_path,
                        deco.lineno,
                        "decorator",
                        100,
                        1,
                    ))

        self.scope_stack.append((func_id, node.name, qualified, node_type))
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._extract_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._extract_function(node, is_async=True)

    def visit_Import(self, node: ast.Import) -> None:
        source_id = self._current_source_id()
        for alias in node.names:
            self.edges.append((
                source_id,
                alias.name,
                "imports",
                self.canonical_file_path,
                node.lineno,
                getattr(node, "col_offset", 0) or 0,
                None,
                json.dumps([]),
                0,
                0,
                0,
            ))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        source_id = self._current_source_id()
        module = node.module or ""
        for alias in node.names:
            target = f"{module}.{alias.name}" if module else alias.name
            self.edges.append((
                source_id,
                target,
                "imports",
                self.canonical_file_path,
                node.lineno,
                getattr(node, "col_offset", 0) or 0,
                None,
                json.dumps([]),
                0,
                0,
                0,
            ))

    def visit_Call(self, node: ast.Call) -> None:
        source_id = self._current_source_id()
        target = _unparse_expr(node.func)
        if target:
            pos_args_count = len([a for a in node.args if not isinstance(a, ast.Starred)])
            has_splat_pos = 1 if any(isinstance(a, ast.Starred) for a in node.args) else 0
            kw_names = [kw.arg for kw in node.keywords if kw.arg is not None]
            has_splat_kw = 1 if any(kw.arg is None for kw in node.keywords) else 0

            self.edges.append((
                source_id,
                target,
                "calls",
                self.canonical_file_path,
                node.lineno,
                getattr(node, "col_offset", 0) or 0,
                pos_args_count,
                json.dumps(kw_names),
                has_splat_pos,
                has_splat_kw,
                0,
            ))

        self.generic_visit(node)

def parse_python_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Parse a Python file using standard library AST."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as exc:
        return [], [], [], [], "SKIPPED", str(exc)

    try:
        tree = ast.parse(source, filename=canonical_file_path)
    except SyntaxError as exc:
        return [], [], [], [], "SYNTAX_ERROR", f"Syntax error at line {exc.lineno}: {exc.msg}"
    except Exception as exc:
        return [], [], [], [], "SYNTAX_ERROR", str(exc)

    visitor = CodebaseASTVisitor(canonical_file_path, display_path, source)
    try:
        visitor.visit(tree)
    except Exception as exc:
        return [], [], [], [], "SYNTAX_ERROR", f"AST traversal error: {exc}"

    return (
        visitor.nodes,
        visitor.signatures,
        visitor.edges,
        visitor.lifecycle_hooks,
        "SUCCESS",
        None,
    )

# --------------------------------------------------------------------------- #
# 2. JavaScript & TypeScript Extractor (Polyglot Regex/Pattern Engine)
# --------------------------------------------------------------------------- #

_JS_IMPORT_RE = re.compile(
    r"""(?m)^\s*import\s+(?:(?P<def>\w+)\s*,?\s*)?(?:\{\s*(?P<named>[^}]+)\s*\}\s*)?from\s+['"](?P<mod>[^'"]+)['"]|require\(\s*['"](?P<req_mod>[^'"]+)['"]\s*\)"""
)
_JS_FUNC_RE = re.compile(
    r"""(?m)^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+(?P<name>[A-Za-z0-9_$]+)\s*\((?P<params>[^)]*)\)(?:\s*:\s*[^{=]+)?(?:\s*=>|\s*\{)"""
)
_JS_ARROW_RE = re.compile(
    r"""(?m)^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\((?P<params>[^)]*)\)(?:\s*:\s*[^{=]+)?\s*=>"""
)
_JS_CLASS_RE = re.compile(
    r"""(?m)^\s*(?:export\s+(?:default\s+)?)?class\s+(?P<name>[A-Za-z0-9_$]+)(?:\s+extends\s+(?P<base>[A-Za-z0-9_$.]+))?"""
)
_JS_METHOD_RE = re.compile(
    r"""(?m)^[ \t]+(?:(?:public|private|protected|static|async|readonly|override)\s+)*(?P<name>[A-Za-z0-9_$]+)\s*\((?P<params>[^)]*)\)(?:\s*:\s*[^{;]+)?\s*\{"""
)
_TS_IFACE_RE = re.compile(
    r"""(?m)^\s*(?:export\s+(?:declare\s+)?)?(?:interface\s+(?P<iname>[A-Za-z0-9_$]+)(?:\s+extends\s+(?P<iext>[^{]+))?\s*\{|type\s+(?P<tname>[A-Za-z0-9_$]+)\s*=\s*\{)"""
)
_TS_DERIVED_TYPE_RE = re.compile(
    r"""(?m)^\s*(?:export\s+)?type\s+(?P<name>[A-Za-z0-9_$]+)\s*=\s*(?:(?P<op>Pick|Omit)\s*<\s*(?P<base>[A-Za-z0-9_$]+)\s*,\s*(?P<keys>[^>]+)\s*>|(?P<inter>[A-Za-z0-9_$]+(?:\s*&\s*(?:[A-Za-z0-9_$]+|\{[^}]*\}))+))\s*;?"""
)
_JS_CALL_RE = re.compile(
    r"""\b(?P<callee>[A-Za-z0-9_$]+(?:\.[A-Za-z0-9_$]+)?)\s*\("""
)

def _split_js_args(text: str, track_generics: bool = False) -> List[str]:
    """Split JS/TS parameter or argument string on top-level commas, respecting nesting and strings."""
    parts = []
    current = []
    depth_paren = 0
    depth_bracket = 0
    depth_brace = 0
    depth_angle = 0
    in_single_str = False
    in_double_str = False
    in_backtick_str = False
    escaped = False

    i = 0
    while i < len(text):
        char = text[i]
        if escaped:
            current.append(char)
            escaped = False
            i += 1
            continue

        if char == '\\' and (in_single_str or in_double_str or in_backtick_str):
            escaped = True
            current.append(char)
            i += 1
            continue

        if not in_single_str and not in_double_str and not in_backtick_str:
            if char == "'":
                in_single_str = True
                current.append(char)
            elif char == '"':
                in_double_str = True
                current.append(char)
            elif char == '`':
                in_backtick_str = True
                current.append(char)
            elif char == '(':
                depth_paren += 1
                current.append(char)
            elif char == ')':
                depth_paren = max(0, depth_paren - 1)
                current.append(char)
            elif char == '[':
                depth_bracket += 1
                current.append(char)
            elif char == ']':
                depth_bracket = max(0, depth_bracket - 1)
                current.append(char)
            elif char == '{':
                depth_brace += 1
                current.append(char)
            elif char == '}':
                depth_brace = max(0, depth_brace - 1)
                current.append(char)
            elif track_generics and char == '<':
                depth_angle += 1
                current.append(char)
            elif track_generics and char == '>':
                depth_angle = max(0, depth_angle - 1)
                current.append(char)
            elif char == ',' and depth_paren == 0 and depth_bracket == 0 and depth_brace == 0 and depth_angle == 0:
                parts.append("".join(current).strip())
                current = []
                i += 1
                continue
            else:
                current.append(char)
        else:
            if in_single_str and char == "'":
                in_single_str = False
            elif in_double_str and char == '"':
                in_double_str = False
            elif in_backtick_str and char == '`':
                in_backtick_str = False
            current.append(char)
        i += 1

    if current or not parts and text.strip():
        parts.append("".join(current).strip())
    return [p for p in parts if p]

def _parse_js_ts_params(params_str: str) -> Tuple[List[str], int, Optional[str]]:
    """Parse JS/TS parameter string into (pos_args, defaults_count, vararg)."""
    pos_args: List[str] = []
    defaults_count = 0
    vararg: Optional[str] = None

    raw_args = _split_js_args(params_str, track_generics=True)
    for arg_str in raw_args:
        if not arg_str:
            continue
        # Strip leading TS modifiers
        clean_arg = arg_str
        for mod in ("public ", "private ", "protected ", "readonly "):
            if clean_arg.startswith(mod):
                clean_arg = clean_arg[len(mod):].strip()

        # Check rest/spread parameter
        if clean_arg.startswith("..."):
            rest_part = clean_arg[3:].strip()
            # Strip type annotation if present
            if ":" in rest_part:
                rest_part = rest_part.split(":", 1)[0].strip()
            vararg = rest_part or "args"
            break

        # Check optional or default value: has top-level '=' or '?' before ':'
        is_optional = False
        # To avoid false positives inside types/nesting, scan top-level or check parts
        # A simple robust check: look for '=' or '?' outside of type annotations or split by ':'
        # In JS/TS, default is `name = defaultVal`, optional is `name?: Type`
        
        # Let's check for '='
        has_eq = "=" in clean_arg
        has_q = "?" in clean_arg

        # Distinguish '?' in ternary vs optional param name: optional param has '?' right after name or before ':'
        # Let's inspect tokens or split by first colon or equals
        name_part = clean_arg
        if ":" in clean_arg:
            parts_colon = clean_arg.split(":", 1)
            name_part = parts_colon[0].strip()
            # If '?' is in name_part (e.g. `param?`), it's optional
            if "?" in name_part:
                is_optional = True
                name_part = name_part.replace("?", "").strip()
        
        if "=" in clean_arg:
            # Default value present
            parts_eq = clean_arg.split("=", 1)
            lhs = parts_eq[0].strip()
            if ":" in lhs:
                lhs = lhs.split(":", 1)[0].strip()
            if "?" in lhs:
                is_optional = True
                lhs = lhs.replace("?", "").strip()
            name_part = lhs
            is_optional = True

        if has_q and not is_optional:
            # Check if ? is part of optional parameter name
            if "?" in name_part:
                is_optional = True
                name_part = name_part.replace("?", "").strip()

        # Handle destructuring
        if name_part.startswith("{") or name_part.startswith("["):
            param_name = "_destructured"
        else:
            # Clean identifier
            param_name = re.sub(r'[^A-Za-z0-9_$]', '', name_part)
            if not param_name:
                param_name = "arg"

        if is_optional:
            defaults_count += 1

        pos_args.append(param_name)

    return pos_args, defaults_count, vararg

def _extract_js_call_args(source: str, open_paren_idx: int) -> Tuple[int, bool]:
    """Scan from '(' to its matching ')' and return (count_non_spread, has_spread)."""
    if open_paren_idx >= len(source) or source[open_paren_idx] != '(':
        return 0, False

    depth = 0
    in_single_str = False
    in_double_str = False
    in_backtick_str = False
    escaped = False

    end_idx = open_paren_idx
    for i in range(open_paren_idx, len(source)):
        char = source[i]
        if escaped:
            escaped = False
            continue
        if char == '\\' and (in_single_str or in_double_str or in_backtick_str):
            escaped = True
            continue

        if not in_single_str and not in_double_str and not in_backtick_str:
            if char == "'":
                in_single_str = True
            elif char == '"':
                in_double_str = True
            elif char == '`':
                in_backtick_str = True
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        else:
            if in_single_str and char == "'":
                in_single_str = False
            elif in_double_str and char == '"':
                in_double_str = False
            elif in_backtick_str and char == '`':
                in_backtick_str = False

    inside = source[open_paren_idx + 1:end_idx]
    args = _split_js_args(inside)
    
    count_non_spread = 0
    has_spread = False
    for arg in args:
        if arg.startswith("..."):
            has_spread = True
        else:
            count_non_spread += 1

    return count_non_spread, has_spread

def _strip_js_comments_and_strings(text: str, strip_strings: bool = False) -> str:
    """Blanks JS/TS comments (and optionally string literals) while preserving line numbers and indices."""
    out: List[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif ch == "/" and nxt == "*":
            out.append("  ")
            i += 2
            while i < n:
                if text[i] == "*" and i + 1 < n and text[i + 1] == "/":
                    out.append("  ")
                    i += 2
                    break
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
        elif ch in ("'", '"', "`"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n:
                c = text[i]
                if c == "\\" and i + 1 < n:
                    out.append("\n" if text[i + 1] == "\n" else ("xx" if strip_strings else c + text[i + 1]))
                    i += 2
                    continue
                if c == quote:
                    out.append(c)
                    i += 1
                    break
                out.append("\n" if c == "\n" else ("x" if strip_strings else c))
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _extract_ts_object_type_fields(body: str) -> Tuple[List[str], List[bool]]:
    """Extracts top-level field names and optionality flags from a TS `{ k: T; k2?: U }` body."""
    keys: List[str] = []
    opts: List[bool] = []
    depth = 0
    buf: List[str] = []
    segments: List[str] = []
    for ch in body:
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        if depth == 0 and ch in (";", ",", "\n"):
            seg = "".join(buf).strip()
            if seg:
                segments.append(seg)
            buf = []
        else:
            buf.append(ch)
    if buf:
        seg = "".join(buf).strip()
        if seg:
            segments.append(seg)
    for seg in segments:
        m = re.match(r"^(?:readonly\s+)?(?P<k>[A-Za-z_$][A-Za-z0-9_$]*)(?P<opt>\??)\s*:", seg)
        if m:
            keys.append(m.group("k"))
            opts.append(m.group("opt") == "?")
    return keys, opts


def _extract_js_object_param_spec(params_str: str) -> Tuple[List[str], List[bool], Optional[str]]:
    """Extracts destructured/inline-typed object keys or `__ts_type__:Name` ref for single-object params."""
    raw = _split_js_args(params_str, track_generics=True)
    if len(raw) != 1:
        return [], [], None
    one = raw[0].strip()
    if one.startswith("{"):
        end_b = one.find("}")
        if end_b <= 1:
            return [], [], None
        keys: List[str] = []
        for item in _split_js_args(one[1:end_b], track_generics=True):
            k = item.split("=", 1)[0].split(":", 1)[0].strip()
            if k and not k.startswith("...") and re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", k):
                keys.append(k)
        return keys, [True] * len(keys), None
    if ":" in one and not one.startswith("..."):
        type_part = one.split(":", 1)[1].split("=", 1)[0].strip()
        if type_part.startswith("{") and type_part.endswith("}"):
            keys, opts = _extract_ts_object_type_fields(type_part[1:-1])
            return keys, opts, None
        m_ref = re.match(r"^([A-Za-z_$][A-Za-z0-9_$]*)$", type_part)
        if m_ref and m_ref.group(1) not in ("string", "number", "boolean", "any", "unknown", "object", "void", "never"):
            return [], [], f"__ts_type__:{m_ref.group(1)}"
    return [], [], None


def _find_matching_brace(text: str, open_idx: int) -> int:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(text) - 1


def parse_js_ts_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Parse JS/TS/JSX/TSX files for modules, classes, methods, functions, signatures, and imports."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            raw_source = f.read()
    except Exception as exc:
        return [], [], [], [], "SKIPPED", str(exc)

    source = _strip_js_comments_and_strings(raw_source, strip_strings=False)
    call_source = _strip_js_comments_and_strings(raw_source, strip_strings=True)

    nodes: List[Tuple] = []
    signatures: List[Tuple] = []
    edges: List[Tuple] = []
    file_stem = Path(canonical_file_path).stem
    module_id = f"{canonical_file_path}:module"
    
    nodes.append((
        module_id,
        file_stem,
        file_stem,
        canonical_file_path,
        display_path,
        1,
        source.count("\n") + 1,
        "module",
        None,
        1,
    ))

    decl_spans: List[Tuple[int, int]] = []
    decl_lines: set[int] = set()
    _JS_METHOD_SKIP = frozenset({"constructor", "if", "for", "while", "switch", "catch", "return", "super"})

    # TypeScript Interfaces & Object Type Aliases (supports extends, Pick, Omit, &)
    seen_ifaces: set[str] = set()
    for tm in _TS_IFACE_RE.finditer(source):
        tname = tm.group("iname") or tm.group("tname")
        iext = (tm.group("iext") or "").strip()
        open_b = tm.end() - 1
        end_b = _find_matching_brace(source, open_b)
        keys, opts = _extract_ts_object_type_fields(source[open_b + 1:end_b])
        parents = [p.strip().split("<")[0].strip() for p in iext.split(",") if p.strip()]
        if not keys and not parents:
            continue
        t_lineno = source[:tm.start()].count("\n") + 1
        iface_id = f"{canonical_file_path}:{tname}"
        seen_ifaces.add(tname)
        nodes.append((
            iface_id,
            tname,
            tname,
            canonical_file_path,
            display_path,
            t_lineno,
            t_lineno,
            "interface",
            None,
            1,
        ))
        signatures.append((
            iface_id,
            canonical_file_path,
            json.dumps([]),
            json.dumps([]),
            0,
            None,
            json.dumps(keys),
            json.dumps(opts),
            None,
            None,
        ))
        for parent_name in parents:
            if parent_name:
                edges.append((
                    iface_id,
                    parent_name,
                    "inherits",
                    canonical_file_path,
                    t_lineno,
                    0,
                    None,
                    json.dumps([]),
                    0,
                    0,
                    0,
                ))

    for dm in _TS_DERIVED_TYPE_RE.finditer(source):
        tname = dm.group("name")
        if tname in seen_ifaces:
            continue
        t_lineno = source[:dm.start()].count("\n") + 1
        iface_id = f"{canonical_file_path}:{tname}"
        op = dm.group("op")
        if op in ("Pick", "Omit"):
            base_name = dm.group("base")
            key_list = re.findall(r"""['"]([A-Za-z_$][A-Za-z0-9_$]*)['"]""", dm.group("keys") or "")
            if not key_list:
                continue
            tag = f"__ts_{op.lower()}__:{base_name}:{','.join(key_list)}"
            nodes.append((iface_id, tname, tname, canonical_file_path, display_path, t_lineno, t_lineno, "interface", None, 1))
            signatures.append((iface_id, canonical_file_path, json.dumps([]), json.dumps([]), 0, None, json.dumps([]), json.dumps([]), tag, None))
        elif dm.group("inter"):
            inter_str = dm.group("inter")
            parents: List[str] = []
            keys: List[str] = []
            opts: List[bool] = []
            for part in inter_str.split("&"):
                part = part.strip()
                if part.startswith("{") and part.endswith("}"):
                    ik, io = _extract_ts_object_type_fields(part[1:-1])
                    keys.extend(ik)
                    opts.extend(io)
                elif re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", part):
                    parents.append(part)
            if not parents and not keys:
                continue
            nodes.append((iface_id, tname, tname, canonical_file_path, display_path, t_lineno, t_lineno, "interface", None, 1))
            signatures.append((iface_id, canonical_file_path, json.dumps([]), json.dumps([]), 0, None, json.dumps(keys), json.dumps(opts), None, None))
            for parent_name in parents:
                edges.append((iface_id, parent_name, "inherits", canonical_file_path, t_lineno, 0, None, json.dumps([]), 0, 0, 0))

    # Classes & Class Methods
    for m in _JS_CLASS_RE.finditer(source):
        name = m.group("name")
        base = m.group("base")
        lineno = source[:m.start()].count("\n") + 1
        class_id = f"{canonical_file_path}:{name}"
        nodes.append((
            class_id,
            name,
            name,
            canonical_file_path,
            display_path,
            lineno,
            lineno,
            "class",
            None,
            1,
        ))
        if base:
            edges.append((
                class_id,
                base,
                "inherits",
                canonical_file_path,
                lineno,
                0,
                None,
                json.dumps([]),
                0,
                0,
                0,
            ))
        brace_idx = source.find("{", m.end())
        if brace_idx != -1:
            end_brace = _find_matching_brace(source, brace_idx)
            class_body = source[brace_idx + 1:end_brace]
            for mm in _JS_METHOD_RE.finditer(class_body):
                m_name = mm.group("name")
                if m_name in _JS_METHOD_SKIP:
                    continue
                abs_start = brace_idx + 1 + mm.start()
                abs_end = brace_idx + 1 + mm.end()
                m_lineno = source[:abs_start].count("\n") + 1
                m_end_ln = source[:abs_end].count("\n") + 1
                decl_spans.append((abs_start, abs_end))
                for ln in range(m_lineno, m_end_ln + 1):
                    decl_lines.add(ln)
                qname = f"{name}.{m_name}"
                meth_id = f"{canonical_file_path}:{qname}"
                nodes.append((
                    meth_id,
                    m_name,
                    qname,
                    canonical_file_path,
                    display_path,
                    m_lineno,
                    m_lineno,
                    "method",
                    None,
                    1,
                ))
                params_str = mm.group("params")
                pos_args, defaults_count, vararg = _parse_js_ts_params(params_str)
                kw_keys, kw_opts, kw_ref = _extract_js_object_param_spec(params_str)
                signatures.append((
                    meth_id,
                    canonical_file_path,
                    json.dumps([]),
                    json.dumps(pos_args),
                    defaults_count,
                    vararg,
                    json.dumps(kw_keys),
                    json.dumps(kw_opts),
                    kw_ref,
                    None,
                ))

    # Functions & Arrow Functions
    for pattern, ntype in ((_JS_FUNC_RE, "function"), (_JS_ARROW_RE, "function")):
        for m in pattern.finditer(source):
            name = m.group("name")
            start_idx = m.start()
            end_idx = m.end()
            lineno = source[:start_idx].count("\n") + 1
            end_lineno = source[:end_idx].count("\n") + 1
            decl_spans.append((start_idx, end_idx))
            for ln in range(lineno, end_lineno + 1):
                decl_lines.add(ln)

            func_id = f"{canonical_file_path}:{name}"
            nodes.append((
                func_id,
                name,
                name,
                canonical_file_path,
                display_path,
                lineno,
                lineno,
                ntype,
                None,
                1,
            ))

            params_str = m.group("params")
            pos_args, defaults_count, vararg = _parse_js_ts_params(params_str)
            kw_keys, kw_opts, kw_ref = _extract_js_object_param_spec(params_str)
            signatures.append((
                func_id,
                canonical_file_path,
                json.dumps([]),
                json.dumps(pos_args),
                defaults_count,
                vararg,
                json.dumps(kw_keys),
                json.dumps(kw_opts),
                kw_ref,
                None,
            ))

    # Imports
    for m in _JS_IMPORT_RE.finditer(source):
        mod = m.group("mod") or m.group("req_mod") or ""
        lineno = source[:m.start()].count("\n") + 1
        edges.append((
            module_id,
            mod,
            "imports",
            canonical_file_path,
            lineno,
            0,
            None,
            json.dumps([]),
            0,
            0,
            0,
        ))

    # Top calls (from comment- and string-stripped source to avoid false call edges inside strings)
    for m in _JS_CALL_RE.finditer(call_source):
        callee = m.group("callee")
        if callee in ("if", "for", "while", "switch", "catch", "function", "return", "constructor", "super", "import", "require"):
            continue

        lineno = call_source[:m.start()].count("\n") + 1
        if lineno in decl_lines:
            in_decl = False
            for start_s, end_s in decl_spans:
                if start_s <= m.start() <= end_s:
                    in_decl = True
                    break
            if in_decl:
                continue

        arg_cnt, has_splat = _extract_js_call_args(call_source, m.end() - 1)
        edges.append((
            module_id,
            callee,
            "calls",
            canonical_file_path,
            lineno,
            0,
            arg_cnt,
            json.dumps([]),
            int(has_splat),
            0,
            0,
        ))

    return nodes, signatures, edges, [], "SUCCESS", None

# --------------------------------------------------------------------------- #
# 3. Go Extractor
# --------------------------------------------------------------------------- #

_GO_PKG_RE = re.compile(r"""(?m)^\s*package\s+(?P<pkg>\w+)""")
_GO_FUNC_RE = re.compile(r"""(?m)^\s*func\s+(?:\((?P<recv>[^)]+)\)\s+)?(?P<name>\w+)\s*\(""")
_GO_TYPE_RE = re.compile(r"""(?m)^\s*type\s+(?P<name>\w+)\s+(?P<kind>struct|interface)""")
_GO_IMPORT_RE = re.compile(r"""(?m)^\s*import\s+(?:\(\s*(?P<multiline>[^)]+)\s*\)|['"](?P<single>[^'"]+)['"])""")

def parse_go_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Parse Go source files for packages, functions, methods, and structs."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as exc:
        return [], [], [], [], "SKIPPED", str(exc)

    nodes: List[Tuple] = []
    edges: List[Tuple] = []
    file_stem = Path(canonical_file_path).stem
    module_id = f"{canonical_file_path}:package"

    pkg_m = _GO_PKG_RE.search(source)
    pkg_name = pkg_m.group("pkg") if pkg_m else file_stem

    nodes.append((
        module_id,
        pkg_name,
        pkg_name,
        canonical_file_path,
        display_path,
        1,
        source.count("\n") + 1,
        "package",
        None,
        1,
    ))

    # Types (structs / interfaces)
    for m in _GO_TYPE_RE.finditer(source):
        name = m.group("name")
        kind = m.group("kind")
        lineno = source[:m.start()].count("\n") + 1
        tid = f"{canonical_file_path}:{name}"
        nodes.append((
            tid,
            name,
            name,
            canonical_file_path,
            display_path,
            lineno,
            lineno,
            kind,
            None,
            1,
        ))

    # Functions & Methods
    for m in _GO_FUNC_RE.finditer(source):
        name = m.group("name")
        recv = m.group("recv")
        lineno = source[:m.start()].count("\n") + 1
        kind = "method" if recv else "function"
        fid = f"{canonical_file_path}:{name}"
        nodes.append((
            fid,
            name,
            f"{recv}.{name}" if recv else name,
            canonical_file_path,
            display_path,
            lineno,
            lineno,
            kind,
            None,
            1,
        ))

    # Imports
    for m in _GO_IMPORT_RE.finditer(source):
        single = m.group("single")
        multiline = m.group("multiline")
        lineno = source[:m.start()].count("\n") + 1
        if single:
            edges.append((module_id, single, "imports", canonical_file_path, lineno, 0, None, json.dumps([]), 0, 0, 0))
        elif multiline:
            for p in re.finditer(r'["\']([^"\']+)["\']', multiline):
                edges.append((module_id, p.group(1), "imports", canonical_file_path, lineno, 0, None, json.dumps([]), 0, 0, 0))

    return nodes, [], edges, [], "SUCCESS", None

# --------------------------------------------------------------------------- #
# 4. Rust Extractor
# --------------------------------------------------------------------------- #

_RS_FN_RE = re.compile(r"""(?m)^\s*(?:pub(?:\([^)]+\))?\s+)?(?:async\s+)?fn\s+(?P<name>\w+)\s*\(""")
_RS_STRUCT_RE = re.compile(r"""(?m)^\s*(?:pub(?:\([^)]+\))?\s+)?(?:struct|enum|trait)\s+(?P<name>\w+)""")
_RS_USE_RE = re.compile(r"""(?m)^\s*use\s+(?P<path>[^;]+);""")

def parse_rust_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Parse Rust files for functions, structs, enums, and use statements."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as exc:
        return [], [], [], [], "SKIPPED", str(exc)

    nodes: List[Tuple] = []
    edges: List[Tuple] = []
    file_stem = Path(canonical_file_path).stem
    module_id = f"{canonical_file_path}:mod"

    nodes.append((
        module_id,
        file_stem,
        file_stem,
        canonical_file_path,
        display_path,
        1,
        source.count("\n") + 1,
        "mod",
        None,
        1,
    ))

    # Structs & Enums
    for m in _RS_STRUCT_RE.finditer(source):
        name = m.group("name")
        lineno = source[:m.start()].count("\n") + 1
        nodes.append((
            f"{canonical_file_path}:{name}",
            name,
            name,
            canonical_file_path,
            display_path,
            lineno,
            lineno,
            "struct",
            None,
            1,
        ))

    # Functions
    for m in _RS_FN_RE.finditer(source):
        name = m.group("name")
        lineno = source[:m.start()].count("\n") + 1
        nodes.append((
            f"{canonical_file_path}:{name}",
            name,
            name,
            canonical_file_path,
            display_path,
            lineno,
            lineno,
            "function",
            None,
            1,
        ))

    # Use statements
    for m in _RS_USE_RE.finditer(source):
        path = m.group("path").strip()
        lineno = source[:m.start()].count("\n") + 1
        edges.append((module_id, path, "imports", canonical_file_path, lineno, 0, None, json.dumps([]), 0, 0, 0))

    return nodes, [], edges, [], "SUCCESS", None

# --------------------------------------------------------------------------- #
# 5. Markdown & Documentation Extractor
# --------------------------------------------------------------------------- #

_MD_HEADER_RE = re.compile(r"""(?m)^(?P<level>#{1,4})\s+(?P<title>.+)""")
_MD_LINK_RE = re.compile(r"""\[(?P<text>[^\]]+)\]\((?P<url>[^)]+)\)""")
_MD_WIKILINK_RE = re.compile(r"""\[\[(?P<target>[^\]]+)\]\]""")

def parse_markdown_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Parse Markdown docs for section nodes, wikilinks, and cross-file references."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as exc:
        return [], [], [], [], "SKIPPED", str(exc)

    nodes: List[Tuple] = []
    edges: List[Tuple] = []
    file_stem = Path(canonical_file_path).stem
    doc_id = f"{canonical_file_path}:doc"

    nodes.append((
        doc_id,
        file_stem,
        display_path,
        canonical_file_path,
        display_path,
        1,
        source.count("\n") + 1,
        "doc",
        None,
        1,
    ))

    # Headers as sections
    for m in _MD_HEADER_RE.finditer(source):
        title = m.group("title").strip()
        lineno = source[:m.start()].count("\n") + 1
        sec_id = f"{canonical_file_path}:{title}"
        nodes.append((
            sec_id,
            title,
            f"{display_path}#{title}",
            canonical_file_path,
            display_path,
            lineno,
            lineno,
            "section",
            None,
            1,
        ))

    # Links
    for m in _MD_LINK_RE.finditer(source):
        url = m.group("url")
        if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("#"):
            lineno = source[:m.start()].count("\n") + 1
            edges.append((doc_id, url, "references", canonical_file_path, lineno, 0, None, json.dumps([]), 0, 0, 0))

    # Wikilinks
    for m in _MD_WIKILINK_RE.finditer(source):
        tgt = m.group("target")
        lineno = source[:m.start()].count("\n") + 1
        edges.append((doc_id, tgt, "references", canonical_file_path, lineno, 0, None, json.dumps([]), 0, 0, 0))

    return nodes, [], edges, [], "SUCCESS", None

# --------------------------------------------------------------------------- #
# 6. Universal Dispatcher Entry Point
# --------------------------------------------------------------------------- #

def parse_source_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Universal polyglot router: parses source files according to file extension."""
    suffix = Path(canonical_file_path).suffix.lower()

    if suffix in (".py", ".pyw"):
        return parse_python_file(canonical_file_path, display_path, abs_path)
    elif suffix in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
        return parse_js_ts_file(canonical_file_path, display_path, abs_path)
    elif suffix in (".go",):
        return parse_go_file(canonical_file_path, display_path, abs_path)
    elif suffix in (".rs",):
        return parse_rust_file(canonical_file_path, display_path, abs_path)
    elif suffix in (".md", ".markdown", ".mdx"):
        return parse_markdown_file(canonical_file_path, display_path, abs_path)
    else:
        # Generic module stub for other files (SQL, Shell, Configs)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except Exception as exc:
            return [], [], [], [], "SKIPPED", str(exc)

        file_stem = Path(canonical_file_path).stem
        mod_id = f"{canonical_file_path}:file"
        nodes = [(
            mod_id,
            file_stem,
            display_path,
            canonical_file_path,
            display_path,
            1,
            max(len(lines), 1),
            "file",
            None,
            1,
        )]
        return nodes, [], [], [], "SUCCESS", None
