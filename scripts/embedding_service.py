"""
Topology A Host CPU Embedding Generator for Omni-Memory v4.1.
Provides dense vector generation using fine-tuned google/embeddinggemma-2-omni (INT8 quantized, MRL 256d)
with mandatory asymmetric prefixes ("task: search result | query: " for queries, "title: none | text: " for indexing).
Gracefully falls back to None if onnxruntime/tokenizers is not installed or model is unavailable.
"""

import os
import sys
from typing import List, Optional

MODEL_NAME = "google/embeddinggemma-2-omni"
DIMENSIONS = 256

_MODEL_INSTANCE = None
_TOKENIZER_INSTANCE = None
_MODEL_FAILED = False


def _resolve_model_dir() -> Optional[str]:
    """Resolve directory containing model.onnx and tokenizer.json."""
    candidate_dirs = [
        # Relative to current file: ../models/embeddinggemma2_int8
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models", "embeddinggemma2_int8"),
        # Plugin canonical location
        os.path.join(os.path.expanduser("~"), ".gemini", "config", "plugins", "omni-skill-orchestrator", "models", "embeddinggemma2_int8"),
        # Workspace fallback
        r"D:\Antigravity\Skill management\models\embeddinggemma2_int8",
    ]
    for d in candidate_dirs:
        if os.path.isdir(d):
            m_path = os.path.join(d, "model.onnx")
            t_path = os.path.join(d, "tokenizer.json")
            if os.path.isfile(m_path) and os.path.isfile(t_path):
                return d
    return None


def _get_engine():
    """Lazily load ONNX Runtime session and Tokenizer on Host CPU."""
    global _MODEL_INSTANCE, _TOKENIZER_INSTANCE, _MODEL_FAILED
    if _MODEL_FAILED:
        return None, None
    if _MODEL_INSTANCE is not None and _TOKENIZER_INSTANCE is not None:
        return _MODEL_INSTANCE, _TOKENIZER_INSTANCE

    try:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        model_dir = _resolve_model_dir()
        if not model_dir:
            sys.stderr.write("[!] Warning: embeddinggemma-2 model files not found in candidate paths.\n")
            _MODEL_FAILED = True
            return None, None

        tok_path = os.path.join(model_dir, "tokenizer.json")
        model_path = os.path.join(model_dir, "model.onnx")

        tok = Tokenizer.from_file(tok_path)
        tok.enable_padding()
        tok.enable_truncation(max_length=128)

        # CPU Execution Provider with standard session options
        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 2
        opts.intra_op_num_threads = 4
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        session = ort.InferenceSession(model_path, sess_options=opts, providers=["CPUExecutionProvider"])

        _MODEL_INSTANCE = session
        _TOKENIZER_INSTANCE = tok
        return _MODEL_INSTANCE, _TOKENIZER_INSTANCE
    except Exception as e:
        sys.stderr.write(f"[!] Warning: Failed to initialize embeddinggemma-2 engine: {e}\n")
        _MODEL_FAILED = True
        return None, None


def get_embedding(text: str, is_query: bool = True) -> Optional[List[float]]:
    """
    Generate dense vector embedding using fine-tuned google/embeddinggemma-2-omni (INT8, MRL 256d) on Host CPU.

    MANDATORY ASYMMETRIC PREFIXES:
    - is_query=True: Prepends "task: search result | query: " (essential for query representation).
    - is_query=False: Prepends "title: none | text: " for indexing document/episodic text.
    - Returns 256-dimensional list of floats (L2 normalized), or None if embedding runtime is offline.
    """
    if not text:
        return None

    session, tok = _get_engine()
    if session is None or tok is None:
        return None

    try:
        import numpy as np

        prefix = "task: search result | query: " if is_query else "title: none | text: "
        prefixed_text = prefix + text

        enc = tok.encode(prefixed_text)
        inputs = {
            "input_ids": np.array([enc.ids], dtype=np.int64),
            "attention_mask": np.array([enc.attention_mask], dtype=np.int64),
        }

        # Run forward pass
        raw_out = session.run(["sentence_embedding"], inputs)[0]
        if raw_out is None or len(raw_out) == 0:
            return None

        # Matryoshka Representation Learning (MRL): Truncate to DIMENSIONS (256)
        vec = raw_out[0][:DIMENSIONS].astype(np.float32)

        # L2 Re-normalization
        norm = float(np.linalg.norm(vec))
        if norm > 0.0:
            vec = vec / norm

        return vec.tolist()
    except Exception as e:
        sys.stderr.write(f"[!] Warning: get_embedding failed: {e}\n")
        return None
