"""S_semantic denso opcional via sentence-transformers (audit P2 seguimiento).

El surrogate de char-n-gramas (``embedding_semantic``) resulto NO discriminativo
(benchmark: ~0.5 para cualquier par). Este modulo aporta un S_semantic DENSO real
cuando ``sentence-transformers`` esta instalado (extra ``[semantic]``): carga
perezosa de un modelo pequeño, cosine entre embeddings normalizados.

Si la dependencia no esta presente, ``dense_semantic_available()`` es False y los
callers deben caer a otro linker (no se importa torch por la fuerza).
"""

from __future__ import annotations

from functools import lru_cache


def dense_semantic_available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def dense_semantic(artifact_text: str, goal_text: str) -> float:
    """Cosine (mapeada a [0,1]) entre embeddings densos de oraciones.

    Asume ``dense_semantic_available()``; los callers deben verificar disponibilidad.
    """
    model = _model()
    import numpy as np

    emb = model.encode([artifact_text, goal_text], normalize_embeddings=True)
    cosine = float(np.dot(emb[0], emb[1]))
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))
