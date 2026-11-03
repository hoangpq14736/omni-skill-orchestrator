"""
Zero-Trust Credential Redaction Module for Omni-Memory v4.1.
Scrubs sensitive API keys, private keys, and authentication tokens before
storage or telemetry logging per Constitution Principle II.2.
"""

import re
from typing import Optional

PATTERNS = [
    # Groq API Keys
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "[REDACTED_GROQ_KEY]"),
    # OpenAI API Keys
    (re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "[REDACTED_OPENAI_KEY]"),
    # Anthropic API Keys
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"), "[REDACTED_ANTHROPIC_KEY]"),
    # GitHub Personal Access Tokens (Classic & Fine-Grained)
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{22,}"), "[REDACTED_GITHUB_TOKEN]"),
    # PKCS#8 and OpenSSL Private Keys
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED_PRIVATE_KEY]"),
    # Bearer Tokens (Scrubbed if not matched by specific provider above)
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]{20,}"), r"\g<1>[REDACTED_BEARER_TOKEN]"),
    # Generic high-entropy assignments (passwords, tokens, api keys, unquoted and quoted .env secrets)
    (re.compile(r'(?i)(password|api_key|secret|token|deepseek_api_key)\s*=\s*(?:["\'][A-Za-z0-9+/=_-]{16,}["\']|[A-Za-z0-9+/=_-]{16,})'), r'\1="[REDACTED]"'),
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
