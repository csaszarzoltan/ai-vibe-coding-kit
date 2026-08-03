"""Pre-development stub for the MCP memory server embedding module.

Contract: analysis/memory-architecture.md §5.

Public API (interface tests pass immediately against this stub):
    MODEL_NAME          — sentence-transformers model id ("all-MiniLM-L6-v2")
    FALLBACK_DIM        — hash-fallback vector dimension (256)
    embed_text()        — (vector, source) for a text
    cosine_similarity() — real cosine similarity over two vectors
    serialize_vector()  — list[float] -> bytes (float32)
    deserialize_vector()— bytes -> list[float]

All behavioral functions raise NotImplementedError until the developer
implements them per the spec.
"""

from __future__ import annotations

MODEL_NAME = "all-MiniLM-L6-v2"
FALLBACK_DIM = 256


def embed_text(text: str) -> tuple[list[float], str]:
    """Return (vector, source) for a text; source is mode-pinned per DB.

    Implemented per spec §5.1: sentence-transformers primary, deterministic
    sha256 bag-of-words fallback; both L2-normalized.
    """
    raise NotImplementedError("memory_embedding.embed_text not implemented yet")


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Return real cosine similarity in [-1.0, 1.0]; 0.0 for zero vectors."""
    raise NotImplementedError(
        "memory_embedding.cosine_similarity not implemented yet"
    )


def serialize_vector(vec: list[float]) -> bytes:
    """Serialize a float vector to a float32 BLOB (stdlib array, no numpy)."""
    raise NotImplementedError(
        "memory_embedding.serialize_vector not implemented yet"
    )


def deserialize_vector(blob: bytes) -> list[float]:
    """Deserialize a float32 BLOB back into list[float]."""
    raise NotImplementedError(
        "memory_embedding.deserialize_vector not implemented yet"
    )
