"""
Empirical Verification & Adversarial Stress Harness for Omni-Graph Signature Contract Guard.
Author: Teamwork Challenger (critic, specialist)
Reference: specs/003-omni-graph/spec.md & plan.md
"""

import ast
import hashlib
import os
import sys
import tempfile
import time
from typing import Any


class PlanSignatureContractValidator:
    """
    Verbatim implementation of SignatureContractValidator from specs/003-omni-graph/plan.md (lines 430-553).
    Used as the baseline empirical benchmark.
    """
    def __init__(self, posonly: list[str], args: list[str], defaults_count: int,
                 vararg: str | None, kwonly: list[str], kw_defaults: list[bool],
                 kwarg: str | None, is_async: bool, node_type: str = "function",
                 decorators: list[str] | None = None):
        self.node_type = node_type
        self.decorators = decorators or []
        self.vararg = vararg
        self.kwarg = kwarg
        self.is_async = is_async
        self.kwonly = kwonly
        self.kw_defaults = kw_defaults
        
        # Method Receiver Parameter Normalization (Addressing False FAIL-02 on methods)
        # For instance and class methods, the first parameter ('self' or 'cls') is supplied implicitly
        # by Python's descriptor binding at runtime. Static methods retain all parameters.
        is_method = node_type in ("method", "async_method")
        is_static = any("staticmethod" in d for d in self.decorators)
        is_classmethod = any("classmethod" in d for d in self.decorators)
        
        clean_posonly = list(posonly)
        clean_args = list(args)
        adjusted_defaults = defaults_count
        
        if is_method and not is_static:
            # Strip the leading receiver parameter (self or cls)
            if clean_posonly:
                removed = clean_posonly.pop(0)
            elif clean_args:
                removed = clean_args.pop(0)
            # If the stripped receiver had a default (edge case), adjust defaults_count
            total_remaining = len(clean_posonly) + len(clean_args)
            adjusted_defaults = min(adjusted_defaults, total_remaining)
            
        self.posonly = clean_posonly
        self.args = clean_args
        self.defaults_count = adjusted_defaults
        
        all_pos = self.posonly + self.args
        num_req = len(all_pos) - self.defaults_count
        self.required_pos = set(all_pos[:num_req])
        self.optional_pos = set(all_pos[num_req:])
        self.required_kwonly = {k for k, has_def in zip(kwonly, kw_defaults) if not has_def}

    def validate_call(self, pos_count: int, kw_names: list[str],
                       has_splat_pos: bool = False, has_splat_kw: bool = False,
                       is_awaited: bool = False, is_unbound_class_call: bool = False) -> list[tuple[str, str]]:
        """
        Validates a call site against this signature.
        Supports bound method calls (default: self/cls omitted by caller) and
        unbound class calls (e.g. MyClass.func(instance, ...)).
        Returns list of (violation_code, diagnostic_message).
        """
        violations = []
        all_pos_params = self.posonly + self.args
        max_pos_capacity = len(all_pos_params)
        
        # Check FAIL-08: Un-awaited coroutine call
        if self.is_async and not is_awaited:
            violations.append((
                "FAIL-08",
                "UN_AWAITED_ASYNC_CALL: Coroutine called without await or task schedule"
            ))

        # Check FAIL-01: Positional argument overflow
        if not has_splat_pos and not self.vararg:
            if pos_count > max_pos_capacity:
                violations.append((
                    "FAIL-01",
                    f"TOO_MANY_POSITIONAL_ARGS: Expected at most {max_pos_capacity} positional args, but received {pos_count}"
                ))

        bound_pos_names = set(all_pos_params[:min(pos_count, max_pos_capacity)])
        bound_kw_names = set()
        posonly_set = set(self.posonly)
        args_set = set(self.args)
        kwonly_set = set(self.kwonly)
        
        # Check keyword arguments
        for k in kw_names:
            # Check FAIL-04: Positional-only passed as keyword
            if k in posonly_set:
                violations.append((
                    "FAIL-04",
                    f"POSITIONAL_ONLY_AS_KEYWORD: Parameter '{k}' is positional-only but passed as keyword"
                ))
            # Check FAIL-05: Multiple values for argument
            elif k in bound_pos_names:
                violations.append((
                    "FAIL-05",
                    f"MULTIPLE_VALUES_FOR_ARG: Parameter '{k}' passed both positionally and as keyword"
                ))
            elif k in args_set or k in kwonly_set:
                bound_kw_names.add(k)
            # Check FAIL-03 / FAIL-07: Unexpected keyword argument
            elif not self.kwarg and not has_splat_kw:
                violations.append((
                    "FAIL-03",
                    f"UNEXPECTED_KEYWORD_ARG: Callable received unexpected keyword argument '{k}'"
                ))
            else:
                bound_kw_names.add(k)
                
        # Check FAIL-02: Missing required positional arguments
        if not has_splat_pos and not has_splat_kw:
            missing_pos = [name for name in all_pos_params 
                           if name in self.required_pos and name not in bound_pos_names and name not in bound_kw_names]
            if missing_pos:
                violations.append((
                    "FAIL-02",
                    f"MISSING_REQUIRED_POSITIONAL_ARG: Missing required positional argument(s): {missing_pos}"
                ))
                
        # Check FAIL-06: Missing required keyword-only arguments
        if not has_splat_kw:
            missing_kw = [k for k in self.required_kwonly if k not in bound_kw_names]
            if missing_kw:
                violations.append((
                    "FAIL-06",
                    f"MISSING_REQUIRED_KEYWORD_ARG: Missing required keyword-only argument(s): {missing_kw}"
                ))
                
        return violations


class HardenedSignatureContractValidator(PlanSignatureContractValidator):
    """
    Hardened implementation resolving the 4 architectural gaps found by the Challenger:
    1. Distinguishes FAIL-07 (RENAMED_PARAMETER_DRIFT) via renamed_params mapping.
    2. Respects is_unbound_class_call to prevent false FAIL-01 on unbound method calls.
    3. Handles posonly args when **kwargs is present (Python 3.8+ PEP 570 semantics).
    4. Suppresses redundant FAIL-02 when parameter is already flagged under FAIL-04.
    """
    def __init__(self, posonly: list[str], args: list[str], defaults_count: int,
                 vararg: str | None, kwonly: list[str], kw_defaults: list[bool],
                 kwarg: str | None, is_async: bool, node_type: str = "function",
                 decorators: list[str] | None = None,
                 renamed_params: dict[str, str] | None = None):
        super().__init__(posonly, args, defaults_count, vararg, kwonly, kw_defaults, kwarg, is_async, node_type, decorators)
        self.renamed_params = renamed_params or {}

    def validate_call(self, pos_count: int, kw_names: list[str],
                       has_splat_pos: bool = False, has_splat_kw: bool = False,
                       is_awaited: bool = False, is_unbound_class_call: bool = False) -> list[tuple[str, str]]:
        violations = []
        all_pos_params = self.posonly + self.args
        max_pos_capacity = len(all_pos_params)

        # Fix GAP-2: Unbound class call receiver normalization
        effective_pos_count = pos_count
        is_instance_method = self.node_type in ("method", "async_method") and not any("staticmethod" in d for d in self.decorators)
        if is_unbound_class_call and is_instance_method:
            effective_pos_count = max(0, pos_count - 1)
        
        # Check FAIL-08: Un-awaited coroutine call
        if self.is_async and not is_awaited:
            violations.append((
                "FAIL-08",
                "UN_AWAITED_ASYNC_CALL: Coroutine called without await or task schedule"
            ))

        # Check FAIL-01: Positional argument overflow
        if not has_splat_pos and not self.vararg:
            if effective_pos_count > max_pos_capacity:
                violations.append((
                    "FAIL-01",
                    f"TOO_MANY_POSITIONAL_ARGS: Expected at most {max_pos_capacity} positional args, but received {effective_pos_count}"
                ))

        bound_pos_names = set(all_pos_params[:min(effective_pos_count, max_pos_capacity)])
        bound_kw_names = set()
        posonly_set = set(self.posonly)
        args_set = set(self.args)
        kwonly_set = set(self.kwonly)
        posonly_flagged_kw = set()
        
        # Check keyword arguments
        for k in kw_names:
            # Fix GAP-3: Positional-only parameter passed as keyword with **kwargs support
            if k in posonly_set:
                if not self.kwarg and not has_splat_kw:
                    violations.append((
                        "FAIL-04",
                        f"POSITIONAL_ONLY_AS_KEYWORD: Parameter '{k}' is positional-only but passed as keyword"
                    ))
                    posonly_flagged_kw.add(k)
                else:
                    # Captured into **kwargs in Python runtime
                    bound_kw_names.add(k)
            # Check FAIL-05: Multiple values for argument
            elif k in bound_pos_names:
                violations.append((
                    "FAIL-05",
                    f"MULTIPLE_VALUES_FOR_ARG: Parameter '{k}' passed both positionally and as keyword"
                ))
            elif k in args_set or k in kwonly_set:
                bound_kw_names.add(k)
            # Fix GAP-1: Differentiate FAIL-07 vs FAIL-03
            elif not self.kwarg and not has_splat_kw:
                if k in self.renamed_params:
                    violations.append((
                        "FAIL-07",
                        f"RENAMED_PARAMETER_DRIFT: Caller passes deprecated parameter '{k}' (renamed to '{self.renamed_params[k]}')"
                    ))
                else:
                    violations.append((
                        "FAIL-03",
                        f"UNEXPECTED_KEYWORD_ARG: Callable received unexpected keyword argument '{k}'"
                    ))
            else:
                bound_kw_names.add(k)
                
        # Check FAIL-02: Missing required positional arguments
        if not has_splat_pos and not has_splat_kw:
            # Fix GAP-4: Suppress duplicate FAIL-02 when already flagged under FAIL-04
            missing_pos = [name for name in all_pos_params 
                           if name in self.required_pos and name not in bound_pos_names and name not in bound_kw_names and name not in posonly_flagged_kw]
            if missing_pos:
                violations.append((
                    "FAIL-02",
                    f"MISSING_REQUIRED_POSITIONAL_ARG: Missing required positional argument(s): {missing_pos}"
                ))
                
        # Check FAIL-06: Missing required keyword-only arguments
        if not has_splat_kw:
            missing_kw = [k for k in self.required_kwonly if k not in bound_kw_names]
            if missing_kw:
                violations.append((
                    "FAIL-06",
                    f"MISSING_REQUIRED_KEYWORD_ARG: Missing required keyword-only argument(s): {missing_kw}"
                ))
                
        return violations


def extract_validator_from_ast(fn_node: ast.FunctionDef | ast.AsyncFunctionDef, node_type: str = "function",
                               cls_type: type = PlanSignatureContractValidator,
                               renamed_params: dict[str, str] | None = None) -> PlanSignatureContractValidator:
    """Helper to extract SignatureContractValidator from standard ast nodes."""
    posonly = [a.arg for a in getattr(fn_node.args, "posonlyargs", [])]
    args = [a.arg for a in fn_node.args.args]
    defaults_count = len(fn_node.args.defaults)
    vararg = fn_node.args.vararg.arg if fn_node.args.vararg else None
    kwonly = [a.arg for a in fn_node.args.kwonlyargs]
    kw_defaults = [d is not None for d in fn_node.args.kw_defaults]
    kwarg = fn_node.args.kwarg.arg if fn_node.args.kwarg else None
    is_async = isinstance(fn_node, ast.AsyncFunctionDef)
    decorators = []
    for dec in fn_node.decorator_list:
        if isinstance(dec, ast.Name):
            decorators.append(dec.id)
        elif isinstance(dec, ast.Attribute):
            decorators.append(dec.attr)
            
    kwargs: dict[str, Any] = {
        "posonly": posonly,
        "args": args,
        "defaults_count": defaults_count,
        "vararg": vararg,
        "kwonly": kwonly,
        "kw_defaults": kw_defaults,
        "kwarg": kwarg,
        "is_async": is_async,
        "node_type": node_type,
        "decorators": decorators,
    }
    if issubclass(cls_type, HardenedSignatureContractValidator):
        kwargs["renamed_params"] = renamed_params
    return cls_type(**kwargs)


def validate_ast_call(validator: PlanSignatureContractValidator, call_node: ast.Call,
                      is_awaited: bool = False, is_unbound_class_call: bool = False) -> list[tuple[str, str]]:
    """Helper to validate an ast.Call node against a validator."""
    pos_count = 0
    has_splat_pos = False
    for arg in call_node.args:
        if isinstance(arg, ast.Starred):
            has_splat_pos = True
        else:
            pos_count += 1
            
    kw_names = []
    has_splat_kw = False
    for kw in call_node.keywords:
        if kw.arg is None:
            has_splat_kw = True
        else:
            kw_names.append(kw.arg)
            
    return validator.validate_call(
        pos_count=pos_count,
        kw_names=kw_names,
        has_splat_pos=has_splat_pos,
        has_splat_kw=has_splat_kw,
        is_awaited=is_awaited,
        is_unbound_class_call=is_unbound_class_call,
    )


# ==============================================================================
# Two-Tier Dirty Checking Engine
# ==============================================================================

class TwoTierDirtyChecker:
    def __init__(self):
        # Database simulated cache: path -> (mtime, size_bytes, sha256)
        self.cache: dict[str, tuple[float, int, str]] = {}

    def cold_index(self, file_paths: list[str]) -> tuple[int, float]:
        start = time.perf_counter()
        count = 0
        for path in file_paths:
            stat = os.stat(path)
            with open(path, "rb") as f:
                digest = hashlib.sha256(f.read()).hexdigest()
            self.cache[path] = (stat.st_mtime, stat.st_size, digest)
            count += 1
        elapsed = time.perf_counter() - start
        return count, elapsed

    def incremental_sweep(self, file_paths: list[str]) -> tuple[dict[str, str], float]:
        """
        Runs two-tier dirty check:
        Tier 1: os.stat() mtime and size comparison (<5us)
        Tier 2: SHA-256 computation if stat differs
        Returns: (results_dict: {path: 'CLEAN' | 'TOUCHED_MATCH' | 'DIRTY_DIFF'}, elapsed_seconds)
        """
        start = time.perf_counter()
        results = {}
        for path in file_paths:
            cached = self.cache.get(path)
            if not cached:
                results[path] = "NEW"
                continue
            cached_mtime, cached_size, cached_sha = cached
            stat = os.stat(path)
            
            # Tier 1: Fast Stat check
            if stat.st_mtime == cached_mtime and stat.st_size == cached_size:
                results[path] = "CLEAN"
                continue
            
            # Tier 2: Content Hash check
            with open(path, "rb") as f:
                current_sha = hashlib.sha256(f.read()).hexdigest()
                
            if current_sha == cached_sha:
                # Update mtime in cache, skip AST parse
                self.cache[path] = (stat.st_mtime, stat.st_size, current_sha)
                results[path] = "TOUCHED_MATCH"
            else:
                self.cache[path] = (stat.st_mtime, stat.st_size, current_sha)
                results[path] = "DIRTY_DIFF"
                
        elapsed = time.perf_counter() - start
        return results, elapsed


# ==============================================================================
# Baseline Tests for FAIL-01 through FAIL-08 on Plan Architecture
# ==============================================================================

def test_fail_01_too_many_positional_args():
    tree = ast.parse("def add(a, b): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("add(1, 2, 3)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-01" in codes, f"Expected FAIL-01, got {codes}"


def test_fail_02_missing_required_positional_arg():
    tree = ast.parse("def query(sql, timeout=30): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("query()").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-02" in codes, f"Expected FAIL-02, got {codes}"


def test_fail_03_unexpected_keyword_arg():
    tree = ast.parse("def send(msg, retries=3): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("send(msg, retry_count=3)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-03" in codes, f"Expected FAIL-03, got {codes}"


def test_fail_04_positional_only_as_keyword():
    tree = ast.parse("def render(canvas, /, mode='2d'): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("render(canvas=c)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-04" in codes, f"Expected FAIL-04, got {codes}"


def test_fail_05_multiple_values_for_arg():
    tree = ast.parse("def log(msg, level='INFO'): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("log('hi', 'DEBUG', msg='test')").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-05" in codes, f"Expected FAIL-05, got {codes}"


def test_fail_06_missing_required_keyword_arg():
    tree = ast.parse("def run(cmd, *, check=False, timeout): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("run('ls', check=True)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-06" in codes, f"Expected FAIL-06, got {codes}"


def test_fail_07_renamed_parameter_drift_defect_in_plan():
    """
    CRITICAL FINDING: plan.md algorithm emits FAIL-03 instead of FAIL-07!
    """
    tree = ast.parse("def consult_critic(prompt, *, timeout_sec=30): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("consult_critic('test', timeout_ms=30)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    # In plan.md, FAIL-07 is absent and collapsed into FAIL-03
    assert "FAIL-03" in codes
    assert "FAIL-07" not in codes


def test_fail_08_un_awaited_async_call():
    tree = ast.parse("async def fetch(url): pass")
    v = extract_validator_from_ast(tree.body[0], node_type="function")
    call = ast.parse("fetch('https://example.com')").body[0].value
    
    # 1. Sync / un-awaited context
    violations_unawaited = validate_ast_call(v, call, is_awaited=False)
    codes_unawaited = [c for c, _ in violations_unawaited]
    assert "FAIL-08" in codes_unawaited, f"Expected FAIL-08, got {codes_unawaited}"
    
    # 2. Awaited context
    violations_awaited = validate_ast_call(v, call, is_awaited=True)
    assert len(violations_awaited) == 0, f"Expected no violations for awaited call, got {violations_awaited}"


# ==============================================================================
# Method Receiver Normalization & Edge Cases
# ==============================================================================

def test_method_receiver_normalization_instance_method():
    tree = ast.parse("""
class Engine:
    def execute(self, task_id, priority=1):
        pass
""")
    fn = tree.body[0].body[0]
    v = extract_validator_from_ast(fn, node_type="method")
    
    call = ast.parse("engine.execute('T-123')").body[0].value
    violations = validate_ast_call(v, call)
    assert len(violations) == 0, f"Bound instance method call should NOT flag FAIL-02 for self, got {violations}"
    
    call2 = ast.parse("engine.execute('T-123', priority=2)").body[0].value
    violations2 = validate_ast_call(v, call2)
    assert len(violations2) == 0, f"Bound instance method call with kwarg failed: {violations2}"


def test_method_receiver_normalization_classmethod():
    tree = ast.parse("""
class Factory:
    @classmethod
    def create(cls, kind, count=1):
        pass
""")
    fn = tree.body[0].body[0]
    v = extract_validator_from_ast(fn, node_type="method")
    
    call = ast.parse("Factory.create('worker')").body[0].value
    violations = validate_ast_call(v, call)
    assert len(violations) == 0, f"Bound classmethod call should NOT flag FAIL-02 for cls, got {violations}"


def test_method_receiver_normalization_staticmethod():
    tree = ast.parse("""
class Math:
    @staticmethod
    def add(x, y):
        pass
""")
    fn = tree.body[0].body[0]
    v = extract_validator_from_ast(fn, node_type="method")
    
    call = ast.parse("Math.add(1, 2)").body[0].value
    violations = validate_ast_call(v, call)
    assert len(violations) == 0, f"Staticmethod call Math.add(1, 2) should pass, got {violations}"
    
    call_missing = ast.parse("Math.add(1)").body[0].value
    violations_missing = validate_ast_call(v, call_missing)
    codes = [c for c, _ in violations_missing]
    assert "FAIL-02" in codes, f"Staticmethod call Math.add(1) must flag FAIL-02, got {codes}"


def test_unbound_class_call_adversarial_defect_in_plan():
    """
    CRITICAL FINDING: plan.md algorithm causes false positive FAIL-01 on unbound class calls.
    """
    tree = ast.parse("""
class Worker:
    def work(self, job_id):
        pass
""")
    fn = tree.body[0].body[0]
    v = extract_validator_from_ast(fn, node_type="method")
    call = ast.parse("Worker.work(w_instance, 'job-99')").body[0].value
    violations = validate_ast_call(v, call, is_unbound_class_call=True)
    codes = [c for c, _ in violations]
    # Defect: FAIL-01 falsely flagged
    assert "FAIL-01" in codes


def test_posonly_with_kwargs_adversarial_defect_in_plan():
    """
    CRITICAL FINDING: plan.md algorithm falsely flags FAIL-04 when **kwargs is present.
    """
    tree = ast.parse("def f(a, /, **kwargs): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("f(1, a=2)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    # Defect: FAIL-04 falsely flagged despite PEP 570 compliance
    assert "FAIL-04" in codes


def test_posonly_passed_as_keyword_duplicate_violation_in_plan():
    """
    OBSERVATION: plan.md emits both FAIL-04 AND FAIL-02 for render(canvas=c).
    """
    tree = ast.parse("def render(canvas, /, mode='2d'): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("render(canvas=c)").body[0].value
    violations = validate_ast_call(v, call)
    codes = [c for c, _ in violations]
    assert "FAIL-04" in codes
    assert "FAIL-02" in codes


def test_edge_cases_varargs_and_splat():
    # 1. *args at def accepts variable args
    tree = ast.parse("def var_func(a, *args): pass")
    v = extract_validator_from_ast(tree.body[0])
    call = ast.parse("var_func(1, 2, 3, 4, 5)").body[0].value
    assert len(validate_ast_call(v, call)) == 0
    
    # 2. *args at call site bypasses overflow
    tree2 = ast.parse("def fixed_func(a, b): pass")
    v2 = extract_validator_from_ast(tree2.body[0])
    call2 = ast.parse("fixed_func(*my_args)").body[0].value
    assert len(validate_ast_call(v2, call2)) == 0
    
    # 3. **kwargs at def accepts extra keywords
    tree3 = ast.parse("def kw_func(a, **kwargs): pass")
    v3 = extract_validator_from_ast(tree3.body[0])
    call3 = ast.parse("kw_func(1, extra=99, other='abc')").body[0].value
    assert len(validate_ast_call(v3, call3)) == 0
    
    # 4. **kwargs at call site bypasses missing keyword check
    tree4 = ast.parse("def req_kw(*, secret_key): pass")
    v4 = extract_validator_from_ast(tree4.body[0])
    call4 = ast.parse("req_kw(**options)").body[0].value
    assert len(validate_ast_call(v4, call4)) == 0


# ==============================================================================
# Hardened Validator Verification (Proving the Proposed Solutions)
# ==============================================================================

def test_hardened_validator_resolves_all_defects():
    # 1. Verify FAIL-07 emitted cleanly
    tree1 = ast.parse("def consult_critic(prompt, *, timeout_sec=30): pass")
    v1 = extract_validator_from_ast(tree1.body[0], cls_type=HardenedSignatureContractValidator,
                                    renamed_params={"timeout_ms": "timeout_sec"})
    call1 = ast.parse("consult_critic('test', timeout_ms=30)").body[0].value
    viol1 = validate_ast_call(v1, call1)
    codes1 = [c for c, _ in viol1]
    assert codes1 == ["FAIL-07"], f"Expected only FAIL-07, got {codes1}"

    # 2. Verify unbound class call succeeds
    tree2 = ast.parse("class Worker:\n    def work(self, job_id): pass")
    v2 = extract_validator_from_ast(tree2.body[0].body[0], node_type="method",
                                    cls_type=HardenedSignatureContractValidator)
    call2 = ast.parse("Worker.work(w_instance, 'job-99')").body[0].value
    viol2 = validate_ast_call(v2, call2, is_unbound_class_call=True)
    assert len(viol2) == 0, f"Unbound call should have 0 violations, got {viol2}"

    # 3. Verify posonly with **kwargs succeeds
    tree3 = ast.parse("def f(a, /, **kwargs): pass")
    v3 = extract_validator_from_ast(tree3.body[0], cls_type=HardenedSignatureContractValidator)
    call3 = ast.parse("f(1, a=2)").body[0].value
    viol3 = validate_ast_call(v3, call3)
    assert len(viol3) == 0, f"PEP 570 posonly with kwargs should have 0 violations, got {viol3}"

    # 4. Verify no duplicate FAIL-02 when FAIL-04 is emitted
    tree4 = ast.parse("def render(canvas, /, mode='2d'): pass")
    v4 = extract_validator_from_ast(tree4.body[0], cls_type=HardenedSignatureContractValidator)
    call4 = ast.parse("render(canvas=c)").body[0].value
    viol4 = validate_ast_call(v4, call4)
    codes4 = [c for c, _ in viol4]
    assert codes4 == ["FAIL-04"], f"Expected single FAIL-04 violation, got {codes4}"


# ==============================================================================
# Empirical Performance Benchmark (Two-Tier Dirty Checking)
# ==============================================================================

def run_dirty_check_benchmark(file_count: int = 100) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        file_paths = []
        for i in range(file_count):
            p = os.path.join(tmpdir, f"module_{i:03d}.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(f"# Python source file {i}\ndef process_{i}(data, count=1):\n    return data * count\n")
            file_paths.append(p)
            
        checker = TwoTierDirtyChecker()
        
        # 1. Cold sweep
        indexed_count, cold_time = checker.cold_index(file_paths)
        cold_ms = cold_time * 1000.0
        
        # 2. Incremental sweep (Zero change)
        res_zero, zero_time = checker.incremental_sweep(file_paths)
        zero_ms = zero_time * 1000.0
        assert all(v == "CLEAN" for v in res_zero.values())
        
        # 3. Incremental sweep (1 file touched, same content)
        touched_file = file_paths[0]
        st = os.stat(touched_file)
        os.utime(touched_file, (st.st_atime + 10, st.st_mtime + 10))
        res_touch, touch_time = checker.incremental_sweep(file_paths)
        touch_ms = touch_time * 1000.0
        assert res_touch[touched_file] == "TOUCHED_MATCH"
        assert sum(1 for v in res_touch.values() if v == "CLEAN") == file_count - 1
        
        # 4. Incremental sweep (1 file modified, content changed)
        mod_file = file_paths[1]
        with open(mod_file, "a", encoding="utf-8") as f:
            f.write("\n# Additional function\ndef extra_func(): pass\n")
        res_mod, mod_time = checker.incremental_sweep(file_paths)
        mod_ms = mod_time * 1000.0
        assert res_mod[mod_file] == "DIRTY_DIFF"
        assert sum(1 for v in res_mod.values() if v == "CLEAN") == file_count - 1
        
        speedup_zero = cold_ms / zero_ms if zero_ms > 0 else float("inf")
        speedup_touch = cold_ms / touch_ms if touch_ms > 0 else float("inf")
        
        return {
            "file_count": file_count,
            "cold_ms": cold_ms,
            "cold_per_file_us": (cold_ms / file_count) * 1000.0,
            "zero_ms": zero_ms,
            "zero_per_file_us": (zero_ms / file_count) * 1000.0,
            "touch_ms": touch_ms,
            "mod_ms": mod_ms,
            "speedup_zero": speedup_zero,
            "speedup_touch": speedup_touch,
        }


def main():
    print("=" * 80)
    print("EMPIRICAL TEST HARNESS & ADVERSARIAL CHALLENGER FOR OMNI-GRAPH SPEC 003")
    print("=" * 80)
    
    print("\n[+] SECTION 1: Standard Failure Modes (FAIL-01 to FAIL-08)")
    test_fail_01_too_many_positional_args()
    print("  ✓ FAIL-01 (TOO_MANY_POSITIONAL_ARGS): Verified")
    
    test_fail_02_missing_required_positional_arg()
    print("  ✓ FAIL-02 (MISSING_REQUIRED_POSITIONAL_ARG): Verified")
    
    test_fail_03_unexpected_keyword_arg()
    print("  ✓ FAIL-03 (UNEXPECTED_KEYWORD_ARG): Verified")
    
    test_fail_04_positional_only_as_keyword()
    print("  ✓ FAIL-04 (POSITIONAL_ONLY_AS_KEYWORD): Verified")
    
    test_fail_05_multiple_values_for_arg()
    print("  ✓ FAIL-05 (MULTIPLE_VALUES_FOR_ARG): Verified")
    
    test_fail_06_missing_required_keyword_arg()
    print("  ✓ FAIL-06 (MISSING_REQUIRED_KEYWORD_ARG): Verified")
    
    test_fail_07_renamed_parameter_drift_defect_in_plan()
    print("  ⚠ FAIL-07 (RENAMED_PARAMETER_DRIFT): Confirmed missing from plan.md (emits FAIL-03 instead)")
    
    test_fail_08_un_awaited_async_call()
    print("  ✓ FAIL-08 (UN_AWAITED_ASYNC_CALL): Verified")
    
    print("\n[+] SECTION 2: Method Receiver Normalization")
    test_method_receiver_normalization_instance_method()
    print("  ✓ Bound Instance Method (self stripping): Verified (0 false FAIL-02)")
    
    test_method_receiver_normalization_classmethod()
    print("  ✓ Classmethod (cls stripping): Verified (0 false FAIL-02)")
    
    test_method_receiver_normalization_staticmethod()
    print("  ✓ Staticmethod (no stripping): Verified")
    
    test_unbound_class_call_adversarial_defect_in_plan()
    print("  ⚠ Unbound Class Call `Worker.work(instance, job_id)`:")
    print("    Confirmed false positive FAIL-01 in plan.md (unused `is_unbound_class_call`)")
        
    print("\n[+] SECTION 3: Positional-Only Edge Cases & Semantic Conflicts")
    test_posonly_with_kwargs_adversarial_defect_in_plan()
    print("  ⚠ `def f(a, /, **kwargs):` called with `f(1, a=2)`:")
    print("    Confirmed false positive FAIL-04 in plan.md (PEP 570 violation)")
        
    test_posonly_passed_as_keyword_duplicate_violation_in_plan()
    print("  ⚠ `def render(canvas, /, mode='2d'):` called with `render(canvas=c)`:")
    print("    Confirmed double violation emitted (FAIL-04 AND FAIL-02)")

    print("\n[+] SECTION 4: Splat and Varargs Edge Cases")
    test_edge_cases_varargs_and_splat()
    print("  ✓ *args, **kwargs, *splat, **splat edge cases verified")
    
    print("\n[+] SECTION 5: Hardened Validator Resolution")
    test_hardened_validator_resolves_all_defects()
    print("  ✓ HardenedSignatureContractValidator resolves all 4 defects with 100% precision")

    print("\n[+] SECTION 6: Two-Tier Dirty Checking Latency Benchmark (100 files)")
    bench = run_dirty_check_benchmark(100)
    print(f"  - Files: {bench['file_count']}")
    print(f"  - Cold Scan: {bench['cold_ms']:.2f} ms ({bench['cold_per_file_us']:.2f} µs/file)")
    print(f"  - Zero-Change Incremental Scan: {bench['zero_ms']:.2f} ms ({bench['zero_per_file_us']:.2f} µs/file)")
    print(f"  - Touched File Incremental Scan: {bench['touch_ms']:.2f} ms")
    print(f"  - Modified File Incremental Scan: {bench['mod_ms']:.2f} ms")
    print(f"  - Measured Speedup (Zero-Change vs Cold): {bench['speedup_zero']:.1f}x")
    print(f"  - Measured Speedup (Touch vs Cold): {bench['speedup_touch']:.1f}x")
    print("=" * 80)


if __name__ == "__main__":
    main()
