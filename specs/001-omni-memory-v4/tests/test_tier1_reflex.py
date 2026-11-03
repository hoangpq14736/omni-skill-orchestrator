"""
Pytest Test Suite: Tier 1 Pre-Flight Reflex & System Grounding
Specification: specs/001-omni-memory-v4/spec.md (User Story 1 - Priority P1)
SLA / Constraints:
  - Algorithmic latency budget: <0.30ms (300 µs) P99
  - 2,048-char head clamping invariant for prompt tokenization
  - Fast filler suppression in <1.0ms
  - Active worker fleet directives formatting (local_worker_mi50, groq_worker_cloud)
"""

import time
import re
import json
import pytest
from typing import Dict, Any, List, Optional


# ============================================================================
# Genuine Tier 1 Reflex Engine Reference Implementation
# ============================================================================

# Full-sentence boundary matching pattern: r"^(ok|okay|tiếp tục|thanks|cảm ơn|yes|no|got it|sure)[.!\s]*$"
# Prevents false-positive suppression on prompts with filler prefixes like "ok, please fix this docker error"
FILLER_PATTERN = re.compile(
    r"^((ok|okay|tiếp tục|tiep tuc|done|thanks|cảm ơn|cam on|chạy đi|chay di|yes|no|got it|sure)[.!\s,]*)+$",
    re.IGNORECASE
)

HARDWARE_FLEET_GROUNDING = """[OMNI-MEMORY v4.0: TIER 1 SYSTEM GROUNDING & REFLEX]
Active Hardware & Worker Fleet:
- Local Worker: `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 @ http://127.0.0.1:8080/v1)
  * Tools: execute_code_task, fast_edit, generate_tests
  * Directives: MUST delegate tactical coding, surgical edits, and pytest authoring here. Preserve cloud quota.
  * Invariant: Micro-batch chunking `-ub 2048` enforced; tactical prompt cap <= 16,000 tokens.
- Cloud Worker: `groq_worker_cloud` (Groq LPU 120B @ openai/gpt-oss-120b)
  * Tools: groq_code_gen, groq_fast_edit, groq_generate_tests
  * Directives: High-throughput generation and complex refactoring offload. Transparent fallback active.
- Host Invariants: Windows 11 x64 | Shell: PowerShell (chaining: use ';' not '&&') | Python UTF-8."""


class Tier1ReflexEngine:
    """
    Sub-millisecond Pre-Flight Reflex Engine implementing Tier 1 specifications:
    - 2,048-character head clamping
    - In-memory inverted index of procedural traces
    - Filler suppression
    - Hardware fleet grounding injection
    """

    def __init__(self, initial_traces: Optional[List[Dict[str, Any]]] = None):
        self.traces = initial_traces or []
        self.inverted_index: Dict[str, List[int]] = {}
        self._build_inverted_index()

    def _build_inverted_index(self) -> None:
        """Build token-to-trace inverted index in memory."""
        self.inverted_index.clear()
        for idx, trace in enumerate(self.traces):
            sig = trace.get("problem_signature", "").lower()
            tokens = set(re.findall(r"\w+", sig))
            for tok in tokens:
                if tok not in self.inverted_index:
                    self.inverted_index[tok] = []
                    self.inverted_index[tok].append(idx)

    def process_hook(self, payload: Any) -> Dict[str, Any]:
        """
        Execute synchronous pre-flight hook with <0.30ms algorithmic budget.
        """
        # Defensive immunity: validate payload structure
        if not isinstance(payload, dict):
            return {"injectSteps": []}

        user_input = payload.get("lastUserInput", "")
        if not isinstance(user_input, str) or not user_input.strip():
            return {"injectSteps": []}

        # 1. Filler check: full-sentence boundary regex test (suppresses pure filler without dropping substantive prompts)
        if FILLER_PATTERN.match(user_input.strip()) or FILLER_PATTERN.match(user_input[:2048].strip()):
            return {"injectSteps": []}

        # 2. 2,048-character head clamping invariant
        clamped_head = user_input[:2048]

        # 3. Tokenize clamped head
        input_tokens = set(re.findall(r"\w+", clamped_head.lower()))
        if not input_tokens:
            return {"injectSteps": []}

        # 4. In-memory inverted index lookup
        matched_trace = None
        best_overlap = 0

        for tok in input_tokens:
            if tok in self.inverted_index:
                for trace_idx in self.inverted_index[tok]:
                    trace = self.traces[trace_idx]
                    sig_tokens = set(re.findall(r"\w+", trace.get("problem_signature", "").lower()))
                    overlap = len(input_tokens & sig_tokens)
                    if overlap > best_overlap and sig_tokens:
                        jaccard = overlap / len(input_tokens | sig_tokens)
                        if jaccard >= 0.20:
                            best_overlap = overlap
                            matched_trace = trace

        # 5. Format injected context block
        injected_text = HARDWARE_FLEET_GROUNDING
        if matched_trace:
            injected_text += f"\n\nL1 Reflex Recall (Proven Solution):\n"
            injected_text += f"  * Problem: [{matched_trace.get('problem_signature', '')}]\n"
            injected_text += f"  * Verified Fix: `{matched_trace.get('solution_payload', '')}`"

        return {
            "injectSteps": [
                {
                    "step": "SYSTEM_GROUNDING",
                    "ephemeralMessage": injected_text
                }
            ]
        }


# ============================================================================
# Pytest Test Cases
# ============================================================================

SAMPLE_TRACES = [
    {
        "trace_id": "trace-001",
        "problem_signature": "Docker port already in use bind address in use",
        "solution_payload": "fuser -k <port>/tcp || lsof -ti:<port> | xargs kill -9",
        "confidence": 0.95
    },
    {
        "trace_id": "trace-002",
        "problem_signature": "WDDM TdrDelay timeout AMD Vega 20 GPU hang",
        "solution_payload": "Set HKLM:\\System\\CurrentControlSet\\Control\\GraphicsDrivers TdrDelay=60",
        "confidence": 0.98
    },
    {
        "trace_id": "trace-003",
        "problem_signature": "PowerShell command chaining syntax error near &&",
        "solution_payload": "Use semicolon ';' instead of '&&' for chaining in PowerShell",
        "confidence": 0.99
    }
]


@pytest.fixture
def reflex_engine():
    return Tier1ReflexEngine(SAMPLE_TRACES)


def test_l1_latency_budget(reflex_engine):
    """
    Assert P99 latency of in-memory reflex recall remains strictly <0.30ms across 1,000 iterations.
    """
    payload = {
        "lastUserInput": "Docker port already in use on 8080 when running test harness",
        "workspacePaths": ["d:/Antigravity/Skill management"]
    }

    # Warmup
    for _ in range(50):
        reflex_engine.process_hook(payload)

    # Benchmark 1,000 executions
    latencies = []
    iterations = 1000
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = reflex_engine.process_hook(payload)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)  # milliseconds

    latencies.sort()
    p50 = latencies[int(iterations * 0.50)]
    p99 = latencies[int(iterations * 0.99)]

    assert len(res["injectSteps"]) == 1
    assert "Active Hardware & Worker Fleet" in res["injectSteps"][0]["ephemeralMessage"]
    assert "fuser -k <port>/tcp" in res["injectSteps"][0]["ephemeralMessage"]
    # P99 must be strictly under 0.30ms
    assert p99 < 0.30, f"P99 latency was {p99:.4f}ms, exceeding 0.30ms budget!"
    assert p50 < 0.15, f"P50 latency was {p50:.4f}ms"


def test_l1_payload_clamping_2048_chars(reflex_engine):
    """
    Assert that inputs bearing massive payloads (50 KB - 200 KB) clamp to 2,048 chars and maintain <0.30ms latency.
    """
    preamble = "PowerShell command chaining syntax error near && when executing build\n"
    massive_stacktrace = "at System.Management.Automation.CommandProcessor.DoExecute() [0x00123]\n" * 3000
    large_input = preamble + massive_stacktrace  # ~210 KB payload

    assert len(large_input) > 150000

    payload = {"lastUserInput": large_input}

    # Verify execution latency on clamped payload
    latencies = []
    for _ in range(200):
        t0 = time.perf_counter()
        res = reflex_engine.process_hook(payload)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    latencies.sort()
    p99 = latencies[int(len(latencies) * 0.99)]

    assert len(res["injectSteps"]) == 1
    assert "Use semicolon ';' instead of '&&'" in res["injectSteps"][0]["ephemeralMessage"]
    assert p99 < 0.30, f"Clamped 200KB prompt P99 latency was {p99:.4f}ms, exceeding 0.30ms budget!"


def test_l1_filler_suppression(reflex_engine):
    """
    Assert that conversational filler inputs return empty injectSteps in <1.0ms without bloat.
    """
    filler_inputs = [
        "ok", "tiếp tục", "okay", "done", "thanks", "chạy đi", "cảm ơn",
        "yes", "no", "got it", "sure", "ok!", "sure.", "ok, thanks!"
    ]

    for filler in filler_inputs:
        t0 = time.perf_counter()
        res = reflex_engine.process_hook({"lastUserInput": filler})
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000.0

        assert res == {"injectSteps": []}, f"Filler '{filler}' was not suppressed!"
        assert elapsed_ms < 1.0, f"Filler check took {elapsed_ms:.4f}ms, exceeding 1.0ms ceiling"


def test_l1_substantive_prompt_with_filler_prefix_not_suppressed(reflex_engine):
    """
    Assert that prompts starting with conversational filler words followed by substantive
    instructions (e.g. 'ok, please fix this docker error') are NOT suppressed.
    """
    substantive_prompts = [
        "ok, please fix this docker error",
        "yes, implement the function",
        "thanks for the help, now do X",
        "okay, start the server",
        "sure, run pytest now"
    ]
    for prompt in substantive_prompts:
        res = reflex_engine.process_hook({"lastUserInput": prompt})
        assert len(res["injectSteps"]) > 0, f"Prompt '{prompt}' was erroneously suppressed as filler!"
        assert "Active Hardware & Worker Fleet" in res["injectSteps"][0]["ephemeralMessage"]


def test_l1_exception_immunity(reflex_engine):
    """
    Assert that malformed, empty, None, or unexpected payloads return valid empty structures without throwing.
    """
    bad_payloads = [
        None,
        {},
        {"lastUserInput": ""},
        {"lastUserInput": "   \n\t   "},
        {"lastUserInput": None},
        {"lastUserInput": 12345},
        {"lastUserInput": ["a", "b"]},
        "raw string instead of dict",
        123
    ]

    for bad in bad_payloads:
        try:
            res = reflex_engine.process_hook(bad)
            assert isinstance(res, dict)
            assert "injectSteps" in res
            assert res["injectSteps"] == []
        except Exception as e:
            pytest.fail(f"Exception raised on input {bad!r}: {e}")


def test_l1_hardware_grounding_injection(reflex_engine):
    """
    Assert that active hardware workers, micro-batch limits, and prompt caps are formatted into context.
    """
    payload = {"lastUserInput": "Write a python function to compute factorial"}
    res = reflex_engine.process_hook(payload)

    assert len(res["injectSteps"]) == 1
    msg = res["injectSteps"][0]["ephemeralMessage"]

    # Verify MI50 Worker
    assert "local_worker_mi50" in msg
    assert "AMD Instinct MI50 16GB HBM2" in msg
    assert "execute_code_task" in msg
    assert "fast_edit" in msg
    assert "generate_tests" in msg
    assert "-ub 2048" in msg
    assert "16,000 tokens" in msg

    # Verify Groq Cloud Worker
    assert "groq_worker_cloud" in msg
    assert "Groq LPU 120B" in msg
    assert "groq_code_gen" in msg
    assert "Transparent fallback active" in msg

    # Verify Host Invariants
    assert "Windows 11 x64" in msg
    assert "PowerShell" in msg
    assert "use ';' not '&&'" in msg


def test_l1_exact_trace_recall(reflex_engine):
    """
    Assert that when a known problem signature matches, the verified fix is included with high confidence.
    """
    payload = {"lastUserInput": "Encountered WDDM TdrDelay timeout AMD Vega 20 GPU hang during model inference"}
    res = reflex_engine.process_hook(payload)

    assert len(res["injectSteps"]) == 1
    msg = res["injectSteps"][0]["ephemeralMessage"]

    assert "L1 Reflex Recall (Proven Solution):" in msg
    assert "WDDM TdrDelay timeout AMD Vega 20 GPU hang" in msg
    assert "Set HKLM:\\System\\CurrentControlSet\\Control\\GraphicsDrivers TdrDelay=60" in msg
