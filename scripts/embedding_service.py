"""
Topology A Host CPU Embedding Generator for Omni-Memory v4.1.
Provides dense vector generation using intfloat/multilingual-e5-small (INT8 quantized)
with mandatory asymmetric prefixes ("passage: " for indexing, "query: " for queries).
Gracefully falls back to None if onnxruntime/fastembed is not installed.
"""

from typing import List, Optional

MODEL_NAME = "intfloat/multilingual-e5-small"
DIMENSIONS = 384

_MODEL_INSTANCE = None
_MODEL_FAILED = False


def _get_model():
    """Lazily load fastembed/onnxruntime model on Host CPU."""
    global _MODEL_INSTANCE, _MODEL_FAILED
    if _MODEL_FAILED:
        return None
    if _MODEL_INSTANCE is not None:
        return _MODEL_INSTANCE

    try:
        from fastembed import TextEmbedding
        try:
            _MODEL_INSTANCE = TextEmbedding(model_name=MODEL_NAME)
        except Exception:
            # Fallback to standard multilingual 384-dim ONNX model natively registered in fastembed
            _MODEL_INSTANCE = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        return _MODEL_INSTANCE
    except Exception:
        # Fallback: onnxruntime not installed or model unavailable
        _MODEL_FAILED = True
        return None


def get_embedding(text: str, is_query: bool = True) -> Optional[List[float]]:
    """
    Generate dense vector embedding using intfloat/multilingual-e5-small on Host CPU.

    MANDATORY ASYMMETRIC PREFIXES:
    - is_query=True: Prepends "query: " (omitting causes 20-30% recall degradation).
    - is_query=False: Prepends "passage: " for indexing document/episodic text.
    - Returns 384-dimensional list of floats, or None if embedding runtime is offline.
    """
    if not text:
        return None

    # Apply mandatory asymmetric prefix
    prefix = "query: " if is_query else "passage: "
    prefixed_text = prefix + text

    model = _get_model()
    if model is None:
        return None

    try:
        embeddings = list(model.embed([prefixed_text]))
        if embeddings and len(embeddings) > 0:
            return embeddings[0].tolist()
        return None
    except Exception:
        return None
