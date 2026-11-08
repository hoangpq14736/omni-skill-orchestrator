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
    r"""(?m)^\s*(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z0-9_$]+)\s*\((?P<params>[^)]*)\)"""
)
_JS_ARROW_RE = re.compile(
    r"""(?m)^\s*(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\((?P<params>[^)]*)\)\s*=>"""
)
_JS_CLASS_RE = re.compile(
    r"""(?m)^\s*(?:export\s+)?class\s+(?P<name>[A-Za-z0-9_$]+)(?:\s+extends\s+(?P<base>[A-Za-z0-9_$.]+))?"""
)
_JS_CALL_RE = re.compile(
    r"""\b(?P<callee>[A-Za-z0-9_$]+(?:\.[A-Za-z0-9_$]+)?)\s*\("""
)

def parse_js_ts_file(
    canonical_file_path: str,
    display_path: str,
    abs_path: str,
) -> Tuple[List[Tuple], List[Tuple], List[Tuple], List[Tuple], str, Optional[str]]:
    """Parse JS/TS/JSX/TSX files for modules, classes, functions, and imports."""
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except Exception as exc:
        return [], [], [], [], "SKIPPED", str(exc)

    nodes: List[Tuple] = []
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

    # Classes
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

    # Functions & Arrow Functions
    for pattern, ntype in ((_JS_FUNC_RE, "function"), (_JS_ARROW_RE, "function")):
        for m in pattern.finditer(source):
            name = m.group("name")
            lineno = source[:m.start()].count("\n") + 1
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

    # Top calls
    for m in _JS_CALL_RE.finditer(source):
        callee = m.group("callee")
        if callee in ("if", "for", "while", "switch", "catch", "function", "return"):
            continue
        lineno = source[:m.start()].count("\n") + 1
        edges.append((
            module_id,
            callee,
            "calls",
            canonical_file_path,
            lineno,
            0,
            0,
            json.dumps([]),
            0,
            0,
            0,
        ))

    return nodes, [], edges, [], "SUCCESS", None

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
