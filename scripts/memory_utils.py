"""
Memory Utilities Module for Omni-Memory v4.1.
Provides diacritic folding, defensive FTS5 query sanitization, and workspace hashing.
"""

import hashlib
import os
import re
import unicodedata
from typing import Optional


def fold_vietnamese(text: Optional[str]) -> str:
    """
    Application-level diacritic removal preserving dual-column FTS5 precision.
    Pre-converts stroked consonants (đ/Đ -> d/D) before NFD decomposition
    because Unicode NFD does not separate the horizontal bar from 'đ'.
    Strips combining diacritical marks (category 'Mn').
    Returns lowercased string.
    """
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    return stripped.lower()


# Backward-compatible alias
normalize_vietnamese_diacritics = fold_vietnamese


def sanitize_fts5_query(query: Optional[str], fold: bool = False) -> str:
    """
    Sanitize technical developer queries for safe SQLite FTS5 MATCH execution.

    CRITICAL RUNTIME GUARDRAIL:
    - fold=False (Default): Preserves original characters and accents (for :raw_q against content_exact).
    - fold=True: Applies fold_vietnamese() (for :folded_q against content_folded).
    - Replaces FTS5 reserved punctuation characters [.:-><()*\"'] with whitespace.
    - Strips standalone FTS5 boolean and proximity operators (AND, OR, NOT, NEAR).
    - Encloses individual alphanumeric terms in double quotes.
    - Returns '""' when query is empty or produces no searchable tokens.
    """
    if not query:
        return '""'

    target = fold_vietnamese(query) if fold else query

    # Replace FTS5 reserved punctuation characters with whitespace
    reserved = ".:-><()*\"'"
    trans_table = str.maketrans({ch: " " for ch in reserved})
    cleaned = target.translate(trans_table)

    # Tokenize on whitespace and strip standalone operators
    tokens = cleaned.split()
    ops = {"AND", "OR", "NOT", "NEAR"}
    filtered = [t for t in tokens if t.upper() not in ops]

    if not filtered:
        return '""'

    return " ".join(f'"{token}"' for token in filtered)


def canonical_workspace_hash(path: Optional[str]) -> str:
    """
    Generate deterministic MD5 hash for workspace partition isolation.
    Mandates os.path.normcase(os.path.normpath(os.path.abspath(path))) prior to hashing
    so case-insensitive Windows drive letters (d:\\ vs D:\\) and mixed slashes
    generate identical partition keys.
    Idempotent: If path is already a 32-char hex MD5 string, returns it lowercase.
    """
    if not path:
        return hashlib.md5(b"global_fallback").hexdigest()
    if len(path) == 32 and all(c in "0123456789abcdefABCDEF" for c in path):
        return path.lower()
    canonical = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    return hashlib.md5(canonical.encode("utf-8")).hexdigest()
