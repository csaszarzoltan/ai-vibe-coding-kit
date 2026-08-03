"""Embedding helpers for the MCP agent memory server (spec §5).

Contract: analysis/memory-architecture.md §5.

Primary mode uses sentence-transformers ``all-MiniLM-L6-v2`` (384-dim,
L2-normalized). A deterministic sha256 bag-of-words fallback (256-dim,
L2-normalized) keeps the server functional offline. Both modes return
L2-normalized vectors, so cosine similarity equals the dot product.
"""

from __future__ import annotations

import hashlib
import importlib.util
import math
import re
import sys
from array import array
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer
else:
    SentenceTransformer = object  # runtime: only used as an annotation

MODEL_NAME = "all-MiniLM-L6-v2"
FALLBACK_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Lazy-loaded sentence-transformers model. ``_vectorizer_attempted`` guards
# the one-time load so a failed attempt falls back without retrying.
_vectorizer: SentenceTransformer | None = None
_vectorizer_attempted = False


def _load_vectorizer() -> object | None:
    """Load and cache the SentenceTransformer; None if unavailable."""
    global _vectorizer, _vectorizer_attempted
    if _vectorizer_attempted:
        return _vectorizer
    _vectorizer_attempted = True
    try:
        from sentence_transformers import SentenceTransformer

        _vectorizer = SentenceTransformer(MODEL_NAME)
    except Exception as exc:  # ImportError / OSError / RuntimeError etc.
        print(
            "memory_embedding: sentence-transformers unavailable, "
            "using hash-fallback embeddings "
            f"({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        _vectorizer = None
    return _vectorizer


def _hash_fallback(text: str) -> list[float]:
    """Deterministic sha256 bag-of-words vector (spec §5.1)."""
    vec = [0.0] * FALLBACK_DIM
    for token in _TOKEN_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % FALLBACK_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0.0:
        vec = [x / norm for x in vec]
    return vec


def current_mode() -> str:
    """Return the embedding mode this process would use, without loading it.

    Uses a cheap module probe; once the model has actually been attempted,
    the observed outcome wins.
    """
    if _vectorizer_attempted:
        return "sentence-transformers" if _vectorizer is not None else "hash-fallback"
    try:
        if importlib.util.find_spec("sentence_transformers") is not None:
            return "sentence-transformers"
    except (ImportError, ValueError):
        pass
    return "hash-fallback"


def embed_text(text: str) -> tuple[list[float], str]:
    """Embed ``text``; returns ``(vector, source)``.

    ``source`` is ``"sentence-transformers"`` (384-dim MiniLM) or
    ``"hash-fallback"`` (256-dim deterministic lexical vector); both modes
    return L2-normalized vectors.
    """
    if not isinstance(text, str):
        raise ValueError(f"text must be a string, got {type(text).__name__}")
    model = _load_vectorizer()
    if model is not None:
        encoded = model.encode([text], normalize_embeddings=True)[0]
        return [float(x) for x in encoded.tolist()], "sentence-transformers"
    return _hash_fallback(text), "hash-fallback"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return the cosine similarity of two equal-length vectors.

    Result is in ``[-1.0, 1.0]``; ``0.0`` when either vector is all zeros.
    Raises ``ValueError`` when the vectors have different lengths (§5.2).
    """
    if len(a) != len(b):
        raise ValueError(f"vector dimension mismatch: {len(a)} != {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=False):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    cosine = dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
    return max(-1.0, min(1.0, cosine))


def serialize_vector(vec: list[float]) -> bytes:
    """Serialize a float vector to a float32 BLOB (stdlib array)."""
    return array("f", vec).tobytes()


def deserialize_vector(blob: bytes) -> list[float]:
    """Deserialize a float32 BLOB back into ``list[float]``."""
    arr = array("f")
    arr.frombytes(blob)
    return arr.tolist()
