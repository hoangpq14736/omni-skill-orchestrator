"""Signature Contract Guard and Validator for Omni-Graph (Graphify)."""

from __future__ import annotations

import difflib
import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

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
            # Total required positional count across posonly and args
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
