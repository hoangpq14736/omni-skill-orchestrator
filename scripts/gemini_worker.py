#!/usr/bin/env python3
"""
Gemini worker for Omni‑Kernel v4.3.0.

- Loads GEMINI_API_KEY from the environment or a .env file (searched up to 5 parent dirs).
- Calls the Gemini REST API via urllib (no external dependencies).
- Supports CLI options for task, model, context, image, output, temperature, max‑tokens and timeout.
- Retries on 429/503 with exponential back‑off + jitter.
- Returns specific exit codes:
    0 – success
    2 – authentication / quota error
    3 – network / timeout error
    4 – CLI usage error
    5 – API‑level failure
"""

import argparse
import base64
import json
import logging
import mimetypes
import os
import pathlib
import random
import sys
import time
import urllib.error
import urllib.request

# --------------------------------------------------------------------------- #
# Logging (never logs the API key)
# --------------------------------------------------------------------------- #
log = logging.getLogger("gemini_worker")
handler = logging.StreamHandler()
formatter = logging.Formatter("%(levelname)s: %(message)s")
handler.setFormatter(formatter)
log.addHandler(handler)
log.setLevel(logging.INFO)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def load_api_key() -> str:
    """Return GEMINI_API_KEY from env or a .env file (searching cwd and script parents)."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key:
        return key.strip()

    search_roots = [pathlib.Path.cwd(), pathlib.Path(__file__).resolve().parent]
    for root in search_roots:
        curr = root
        for _ in range(6):
            env_path = curr / ".env"
            if env_path.is_file():
                try:
                    with env_path.open(encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line or line.startswith("#"):
                                continue
                            if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                                return line.split("=", 1)[1].strip().strip("'\"")
                except Exception:
                    pass
            if curr.parent == curr:
                break
            curr = curr.parent
    raise RuntimeError("GEMINI_API_KEY not found in environment or .env file")


def read_text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def read_image(path: pathlib.Path) -> dict:
    """Return a dict suitable for Gemini's inline_data field."""
    mime, _ = mimetypes.guess_type(str(path))
    mime = mime or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return {"mime_type": mime, "data": data}


def build_payload(args, context_text: str, image_part: dict | None) -> bytes:
    parts = [{"text": context_text}] if context_text else []
    if image_part:
        parts.append({"inline_data": image_part})

    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": args.temperature,
            "maxOutputTokens": args.max_tokens,
        },
    }
    return json.dumps(payload).encode("utf-8")


def exponential_backoff(attempt: int, base: float = 1.0) -> float:
    jitter = random.uniform(0, 0.5)
    return base * (2 ** attempt) + jitter


# --------------------------------------------------------------------------- #
# Main execution
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gemini worker (standard‑library only)."
    )
    parser.add_argument("--task", required=True, help="Task description (unused, kept for compatibility).")
    parser.add_argument(
        "--model",
        default="gemini-3.5-flash-lite",
        choices=["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-4-argon"],
        help="Model name.",
    )
    parser.add_argument("--context-file", type=pathlib.Path, help="Path to a text file used as prompt.")
    parser.add_argument("--image-file", type=pathlib.Path, help="Path to an image to include.")
    parser.add_argument("--out", type=pathlib.Path, help="File to write the generated text to.")
    parser.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature.")
    parser.add_argument("--max-tokens", type=int, default=1024, help="Maximum output tokens.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Overall request timeout in seconds.")
    args = parser.parse_args()

    # ------------------------------------------------------------------- #
    # Load credentials
    # ------------------------------------------------------------------- #
    try:
        api_key = load_api_key()
    except Exception as exc:
        log.error("Failed to obtain API key: %s", exc)
        return 4

    # ------------------------------------------------------------------- #
    # Prepare request data
    # ------------------------------------------------------------------- #
    context_text = ""
    if args.context_file:
        try:
            context_text = read_text(args.context_file)
            context_text += f"\n{args.task}"
        except Exception as exc:
            log.error("Unable to read context file: %s", exc)
            return 4
    else:
        context_text = args.task

    image_part = None

    if args.image_file:
        try:
            image_part = read_image(args.image_file)
        except Exception as exc:
            log.error("Unable to read image file: %s", exc)
            return 4

    payload = build_payload(args, context_text, image_part)

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{args.model}:generateContent?key={api_key}"
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # ------------------------------------------------------------------- #
    # Perform request with retries
    # ------------------------------------------------------------------- #
    deadline = time.monotonic() + args.timeout
    attempt = 0
    max_attempts = 5

    while True:
        remaining = max(0.0, deadline - time.monotonic())
        if remaining <= 0:
            log.error("Operation timed out after %.1f seconds", args.timeout)
            return 3

        try:
            with urllib.request.urlopen(request, timeout=remaining) as resp:
                resp_data = resp.read()
                resp_json = json.loads(resp_data)
                # Extract generated text
                try:
                    text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    log.error("Unexpected API response structure.")
                    return 5
                # Write output
                if args.out:
                    args.out.write_text(text, encoding="utf-8")
                else:
                    sys.stdout.write(text)
                return 0

        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                log.error("Authentication or quota error (HTTP %s).", e.code)
                return 2
            if e.code in (429, 503):
                if attempt >= max_attempts - 1:
                    log.error("Maximum retries exceeded (HTTP %s).", e.code)
                    return 5
                backoff = exponential_backoff(attempt)
                log.info("Retryable HTTP %s – sleeping %.2f s", e.code, backoff)
                time.sleep(backoff)
                attempt += 1
                continue
            # Other HTTP errors are treated as API failures
            log.error("API returned HTTP %s: %s", e.code, e.read().decode(errors="ignore"))
            return 5

        except urllib.error.URLError as e:
            # Includes timeout errors
            log.error("Network error: %s", e.reason)
            return 3

        except Exception as e:
            log.error("Unexpected error: %s", e)
            return 5


if __name__ == "__main__":
    sys.exit(main())