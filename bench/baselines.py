"""Baselines de selección de evidencia para el benchmark (P2).

Cada baseline devuelve el conjunto de artefactos seleccionado para un objetivo;
el harness mide precision/recall contra el gold y el costo (tokens de contenido).
Son adrede simples (lectura completa, búsqueda léxica, aleatorio) para comparar
contra la selección por utilidad de argos.
"""

from __future__ import annotations

import random
from typing import Any

from argos_epistemic.algorithm import _tokens


def _cost(artifacts: list[dict[str, Any]], ids: set[str]) -> int:
    return sum(max(10, len(str(a.get("content", ""))) // 4) for a in artifacts if a["id"] in ids)


def full_read(artifacts: list[dict[str, Any]], goal: dict[str, Any]) -> set[str]:
    return {a["id"] for a in artifacts}


def lexical_topk(artifacts: list[dict[str, Any]], goal: dict[str, Any], k: int) -> set[str]:
    aspect_tokens = set()
    for a in goal.get("aspects", []):
        aspect_tokens |= _tokens(a)
    if not aspect_tokens:
        return {a["id"] for a in artifacts[:k]}

    def score(a):
        toks = _tokens(str(a.get("content", "")) + " " + str(a.get("id", "")))
        return len(toks & aspect_tokens)

    ranked = sorted(artifacts, key=score, reverse=True)
    return {a["id"] for a in ranked[:k]}


def random_k(artifacts: list[dict[str, Any]], goal: dict[str, Any], k: int, seed: int = 0) -> set[str]:
    rng = random.Random(seed)
    return {a["id"] for a in rng.sample(artifacts, min(k, len(artifacts)))}


def cost(artifacts: list[dict[str, Any]], ids: set[str]) -> int:
    return _cost(artifacts, ids)
