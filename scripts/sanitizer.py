"""
Zero-Trust Credential Redaction Module for Omni-Memory v4.0.
Scrubs sensitive API keys, private keys, and authentication tokens before
storage or telemetry logging.
"""

import re
from typing import Optional

PATTERNS = [
    # Groq API Keys
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "[REDACTED_GROQ_KEY]"),
    # OpenAI API Keys
    (re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "[REDACTED_OPENAI_KEY]"),
    # GitHub Personal Access Tokens
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "[REDACTED_GITHUB_TOKEN]"),
    # PKCS#8 and OpenSSL Private Keys
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # Generic high-entropy assignments (passwords, tokens, api keys)
    (re.compile(r'(?i)(password|api_key|secret|token)\s*=\s*["\'][A-Za-z0-9+/=_-]{16,}["\']'), r'\1="[REDACTED]"'),
]


def redact_credentials(text: Optional[str]) -> str:
    """
    Scrub credentials and high-entropy sensitive secrets from text.
    Returns sanitized string. Safely handles None or empty input.
    """
    if not text:
        return ""
    
    sanitized = text
    for pattern, replacement in PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized
