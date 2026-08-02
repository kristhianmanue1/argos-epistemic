"""Implementacion de referencia ejecutable del algoritmo de la seccion 22.

Es una version minima, funcional y terminante del esqueleto declarativo de
``readme.md``. No es una implementacion optimizada del modelo completo: expone
los tipos y el flujo principal para que puedan ejecutarse pruebas de humo y
verificar que el algoritmo termina, decide y sintetiza un reporte trazable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


@dataclass
class Cost:
    tokens: int = 0
    tool: int = 0
    latency: float = 0.0
    compute: float = 0.0

    def dominates(self, other: "Cost") -> bool:
        return (
            self.tokens <= other.tokens
            and self.tool <= other.tool
            and self.latency <= other.latency
            and self.compute <= other.compute
        )


@dataclass
class Budget:
    tokens_remaining: int
    tool_remaining: int
    latency_remaining: float = float("inf")
    compute_remaining: float = float("inf")
    theta_coverage: float = 0.95
    rho_risk: float = 0.05

    def has_capacity(self) -> bool:
        return self.tokens_remaining > 0 and self.tool_remaining > 0

    def can_afford(self, cost: Cost) -> bool:
        return (
            cost.tokens <= self.tokens_remaining
            and cost.tool <= self.tool_remaining
            and cost.latency <= self.latency_remaining
            and cost.compute <= self.compute_remaining
        )

    def consume(self, cost: Cost) -> None:
        self.tokens_remaining -= cost.tokens
        self.tool_remaining -= cost.tool
        self.latency_remaining -= cost.latency
        self.compute_remaining -= cost.compute


@dataclass
class Evidence:
    id: str
    content: Any
    kind: str
    source: str
    location: str
    level: int
    timestamp: int = 0
    compressed: bool = False
    digest: str | None = None

    def compress_in_place(self) -> None:
        if self.compressed:
            return
        import hashlib

        original = str(self.content)
        self.digest = "phi:" + hashlib.sha256(original.encode("utf-8")).hexdigest()[:16]
        self.content = f"<compressed:{self.digest}>"
        self.compressed = True


EVIDENCE_CAPACITY = 4
EVIDENCE_TOKENS_PER_SLOT = 1024


def capacity_for_budget(budget: Budget) -> int:
    """Adaptive compression capacity (readme.md §6): the store keeps at most
    ``capacity`` items uncompressed, derived from the remaining token budget.
    As ``budget.tokens_remaining`` shrinks during a run, capacity shrinks and
    compression becomes stricter. Floor is ``EVIDENCE_CAPACITY``.
    """
    derived = budget.tokens_remaining // EVIDENCE_TOKENS_PER_SLOT
    return max(EVIDENCE_CAPACITY, int(derived))


def _tokens(content: Any) -> frozenset[str]:
    """Lexical surrogate for a position: lowercase alphanumeric token set.

    True semantic identity needs embeddings/LLM (``S_semantic``, LLM-approximated
    per readme.md §6.1). This frozenset is the deterministic default; a richer
    ``similarity`` callable can be injected into ``detect_conflicts``.
    """
    import re

    return frozenset(t for t in re.findall(r"[0-9a-záéíóúñ]+", str(content).lower()) if t)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _position_of(content: Any) -> frozenset[str]:
    return _tokens(content)


@dataclass
class Verification:
    confidence: float
    status: str
    provenance: str
    method: str
    timestamp: int = 0


class EvidenceStore:
    def __init__(self) -> None:
        self._items: list[Evidence] = []

    def __iter__(self) -> Iterable[Evidence]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def add(self, evidence: Evidence) -> None:
        if not any(item.id == evidence.id for item in self._items):
            self._items.append(evidence)

    def get(self, evidence_id: str) -> Evidence | None:
        return next((item for item in self._items if item.id == evidence_id), None)

    def has(self, evidence_id: str) -> bool:
        return any(item.id == evidence_id for item in self._items)

    def levels(self) -> set[int]:
        return {item.level for item in self._items}

    def compress(self, budget: Budget, preserve_provenance: bool, preserve_invariants) -> None:
        capacity = capacity_for_budget(budget)
        protected = set(preserve_invariants or [])
        uncompressed = [x for x in self._items if not x.compressed]
        if len(uncompressed) <= capacity:
            return
        for item in uncompressed:
            if len([x for x in self._items if not x.compressed]) <= capacity:
                break
            if item.id in protected:
                continue
            item.compress_in_place()


@dataclass
class Belief:
    claim: str
    confidence: float
    status: str
    provenance: str
    dependencies: tuple[str, ...] = ()
    scope: str = ""
    position: frozenset[str] = frozenset()


class BeliefStore:
    def __init__(self) -> None:
        self._items: list[Belief] = []

    def __iter__(self) -> Iterable[Belief]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def update(self, new_evidence: Evidence, verification: Verification, goal: str) -> None:
        claim = f"{new_evidence.kind}@{new_evidence.location} observado para '{goal}'"
        self._items.append(
            Belief(
                claim=claim,
                confidence=verification.confidence,
                status=verification.status,
                provenance=verification.provenance,
                dependencies=(new_evidence.id,),
                scope=new_evidence.location,
                position=_position_of(new_evidence.content),
            )
        )

    def mark_conflicted(self, scopes) -> None:
        scope_set = set(scopes)
        for belief in self._items:
            if belief.scope in scope_set and belief.status not in ("conflicted", "contradicted"):
                belief.status = "conflicted"


@dataclass
class Conflict:
    claim: str
    evidence_for: tuple[str, ...]
    evidence_against: tuple[str, ...]
    scope: str
    severity: float
    resolution_status: str = "open"


class ConflictStore:
    def __init__(self) -> None:
        self._items: list[Conflict] = []

    def __iter__(self) -> Iterable[Conflict]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def merge(self, conflicts: list[Conflict]) -> None:
        for conflict in conflicts:
            key = (conflict.scope, conflict.claim)
            if any((c.scope, c.claim) == key for c in self._items):
                continue
            self._items.append(conflict)

    def critical(self) -> list[Conflict]:
        return [c for c in self._items if c.severity >= 0.8 and c.resolution_status != "resolved"]

    def open_scopes(self) -> set[str]:
        return {c.scope for c in self._items if c.resolution_status == "open"}


@dataclass
class ActionResult:
    evidence: Evidence
    verification: Verification
    actual_cost: Cost


@dataclass
class Action:
    name: str
    target_id: str
    level: int
    estimated_cost: Cost
    verification_method: str
    prerequisites: tuple[str, ...] = ()
    expected_delta_coverage: float = 0.1
    expected_delta_confidence: float = 0.1
    expected_delta_risk_reduction: float = 0.1


def derive_goal_aspects(goal: dict[str, Any]) -> list[dict[str, Any]]:
    aspects = []
    for raw in goal.get("aspects", []):
        if isinstance(raw, str):
            aspects.append({"name": raw, "weight": 1.0 / max(len(goal["aspects"]), 1)})
        else:
            aspects.append(raw)
    total = sum(a["weight"] for a in aspects) or 1.0
    for aspect in aspects:
        aspect["weight"] = aspect["weight"] / total
    return aspects


def select_non_functional_extractors(goal: dict[str, Any]) -> list[str]:
    return list(goal.get("non_functional", []))


@dataclass
class Proposition:
    """An aspect-linked claim derived from verified evidence.

    This is the keystone layer (readme.md §7, §12, §23): evidence becomes a
    proposition about a *specific* aspect of the goal, with polarity and
    confidence. Coverage is computed per aspect over propositions, so evidence
    unrelated to an aspect contributes exactly zero. Conflicts are detected
    between propositions on the same aspect (see ``detect_proposition_conflicts``).
    """

    aspect: str
    polarity: float
    claim: str
    evidence_id: str
    confidence: float
    method: str
    scope: str
    timestamp: int = 0
    dependencies: tuple[str, ...] = ()
    strength: float = 1.0
    position: frozenset[str] = frozenset()


class PropositionStore:
    def __init__(self) -> None:
        self._items: list[Proposition] = []

    def __iter__(self) -> Iterable[Proposition]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def add(self, proposition: Proposition) -> None:
        self._items.append(proposition)

    def for_aspect(self, aspect: str) -> list[Proposition]:
        return [p for p in self._items if p.aspect == aspect]


def _polarity_for(status: str) -> float:
    if status == "contradicted":
        return -1.0
    if status == "weak":
        return 0.5
    if status == "unknown":
        return 0.0
    return 1.0


def _epistemic_status(polarity: float, confidence: float) -> str:
    if polarity < 0:
        return "contradicted"
    if polarity == 0:
        return "unknown"
    return "supported" if confidence >= 0.7 else "weak"


def _default_linker(text: str, aspect: str) -> float:
    return _jaccard(_tokens(text), _tokens(aspect))


def _resolve_artifact(system: dict[str, Any], evidence_id: str) -> dict[str, Any] | None:
    base = evidence_id.split("#nf:", 1)[0] if "#nf:" in evidence_id else evidence_id
    return next((a for a in system.get("artifacts", []) if a.get("id") == base), None)


def link_aspects(
    artifact: dict[str, Any] | None,
    aspect_names: list[str],
    goal: dict[str, Any],
    linker,
) -> dict[str, float]:
    """Return {aspect: strength} for the aspects this artifact speaks to.

    Honors an explicit ``artifact["supports"] = [{"aspect": ..., "strength": ...}]``
    declaration; otherwise infers linkage via ``linker(content, aspect)`` above a
    threshold (so unrelated evidence contributes zero).
    """
    if artifact is None:
        return {}
    declared = artifact.get("supports")
    if isinstance(declared, list) and declared:
        out: dict[str, float] = {}
        for entry in declared:
            name = entry.get("aspect") if isinstance(entry, dict) else None
            if name:
                out[str(name)] = float(entry.get("strength", 1.0)) if isinstance(entry, dict) else 1.0
        return out
    threshold = goal.get("link_threshold", 0.05)
    content = str(artifact.get("content", "")) + " " + str(artifact.get("id", ""))
    return {
        aspect: strength
        for aspect in aspect_names
        if (strength := linker(content, aspect)) >= threshold
    }


def derive_propositions(
    evidence: Evidence,
    verification: Verification,
    artifact: dict[str, Any] | None,
    aspect_names: list[str],
    goal_name: str,
    goal: dict[str, Any],
    linker,
) -> list[Proposition]:
    polarity = _polarity_for(verification.status)
    links = link_aspects(artifact, aspect_names, goal, linker)
    props: list[Proposition] = []
    for aspect, strength in links.items():
        sign = polarity
        if sign == 0.0 and verification.status == "weak":
            sign = 0.5
        props.append(
            Proposition(
                aspect=aspect,
                polarity=sign,
                claim=f"{evidence.kind}@{evidence.location} -> {aspect} ({verification.method})",
                evidence_id=evidence.id,
                confidence=verification.confidence,
                method=verification.method,
                scope=evidence.location,
                timestamp=evidence.timestamp,
                dependencies=(evidence.id,),
                strength=strength,
                position=_tokens(str(artifact.get("content", ""))) if artifact else frozenset(),
            )
        )
    return props


CORROBORATION = 1.8


def aspect_score(props: list["Proposition"], corroboration: float = CORROBORATION) -> float:
    """Coverage of one aspect (readme.md §12), calibrated to reward corroboration.

    ``score = clamp01( Σ_pos polarity·conf / corroboration )``: a single source
    does NOT saturate the aspect (it scores conf/corroboration, e.g. 0.9/1.8 =
    0.5); reaching ~0.8 requires 2+ independent supporting propositions. This
    closes the overconfidence gap exposed by the P2 benchmark, where 1 artifact
    linking all aspects falsely reported coverage ≈ 0.9.
    """
    pos_mass = sum(p.polarity * p.confidence for p in props if p.polarity > 0)
    return max(0.0, min(1.0, pos_mass / max(0.0001, corroboration)))


def compute_coverage(
    propositions: PropositionStore,
    aspects: list[dict[str, Any]],
    corroboration: float = CORROBORATION,
) -> float:
    """Per-aspect coverage (readme.md §12): Cov = Σ w_i · aspect_score(t_i).

    aspect_score rewards corroboration (see ``aspect_score``); aspects with no
    supporting proposition score 0 (evidence irrelevant to the goal contributes
    nothing).
    """
    if not aspects:
        return 0.0
    by_aspect: dict[str, list[Proposition]] = {}
    for prop in propositions:
        by_aspect.setdefault(prop.aspect, []).append(prop)
    total = 0.0
    for aspect in aspects:
        total += aspect["weight"] * aspect_score(by_aspect.get(aspect["name"], []), corroboration)
    return max(0.0, min(1.0, total))


def compute_residual_risk(
    propositions: PropositionStore,
    aspects: list[dict[str, Any]],
    goal: dict[str, Any],
) -> float:
    """Risk from missing aspects and contradictions, not average confidence.

    Driven by the share of required aspects with no positive support and the
    share of contradicting propositions. No propositions at all => max risk.
    """
    if not propositions:
        return 1.0
    if not aspects:
        return 0.0
    names = [a["name"] for a in aspects]
    by_aspect: dict[str, list[Proposition]] = {}
    for prop in propositions:
        by_aspect.setdefault(prop.aspect, []).append(prop)
    missing = sum(
        1 for n in names if not any(p.polarity > 0 for p in by_aspect.get(n, []))
    ) / len(names)
    contra = sum(1 for p in propositions if p.polarity < 0)
    contra_share = contra / len(propositions)
    return max(0.0, min(1.0, 0.7 * missing + 0.3 * contra_share))


def _confidence_for(method: str) -> float:
    """Confianza por método de verificación (§9.1).

    deterministic/dynamic -> 0.9; historical -> 0.8; symbolic/other -> 0.6.
    """
    if method in ("deterministic", "dynamic"):
        return 0.9
    if method == "historical":
        return 0.8
    return 0.6


def min_sources_met(
    propositions: PropositionStore,
    aspects: list[dict[str, Any]],
    min_sources: int,
) -> bool:
    """Every required aspect has >= min_sources distinct supporting propositions.

    Structural anti-overconfidence (complements corroboration): an aspect is not
    'done' until it rests on multiple independent sources, regardless of the
    surrogate coverage number. This avoids declaring complete after 1-2
    multi-aspect artifacts and is epistemically defensible (don't rest a
    conclusion on a single source) rather than overfitting theta to gold.
    """
    if not aspects or min_sources <= 0:
        return True
    by_aspect: dict[str, set[str]] = {}
    for prop in propositions:
        if prop.polarity > 0:
            by_aspect.setdefault(prop.aspect, set()).add(prop.evidence_id)
    return all(len(by_aspect.get(a["name"], set())) >= min_sources for a in aspects)


def should_stop(
    coverage: float,
    residual_risk: float,
    conflicts: ConflictStore,
    goal: dict[str, Any],
    budget: Budget,
    breadth_ok: bool = True,
) -> bool:
    theta = goal.get("theta_coverage", budget.theta_coverage)
    rho = goal.get("rho_risk", budget.rho_risk)
    if (
        coverage >= theta
        and residual_risk <= rho
        and not conflicts.critical()
        and breadth_ok
    ):
        return True
    return False


def prerequisites_satisfied(action: Action, evidence: EvidenceStore, beliefs: BeliefStore) -> bool:
    return all(evidence.has(prereq) or any(prereq == b.claim for b in beliefs) for prereq in action.prerequisites)


def _size_cost(artifact: Any, tool: int = 1) -> Cost:
    """Estimated extraction cost from artifact size, not epistemic relevance.

    Prefers a declared ``size`` (cheap stat at discovery) so that selection can
    gate on cost BEFORE the expensive extraction runs (readme.md §15, §16, and
    the §3 budget that must bound real work, not just post-hoc accounting).
    """
    if isinstance(artifact, dict):
        size = artifact.get("size")
        if size is None:
            size = len(str(artifact.get("content", "")))
    else:
        size = len(str(artifact))
    return Cost(tokens=max(10, int(size) // 4), tool=tool)


def _resolve_lazy(artifact: dict[str, Any]) -> None:
    """Materialize content on demand (H4): the extractor runs only when selected.

    Deferred extractors (dynamic/history/logs) expose a ``loader`` returning a
    dict with ``content`` and optionally ``run``; file artifacts may carry a
    loader to read their content lazily. Discovery pays only a stat; extraction
    pays the real I/O/subprocess, accounted as observed cost.
    """
    if artifact.get("content"):
        return
    loader = artifact.get("loader")
    if not callable(loader):
        return
    resolved = loader() or {}
    if isinstance(resolved, dict):
        if resolved.get("content") is not None:
            artifact["content"] = resolved["content"]
        if "run" in resolved:
            artifact["run"] = resolved["run"]
    else:
        artifact["content"] = str(resolved)


def generate_candidate_actions(
    system: dict[str, Any],
    goal: dict[str, Any],
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    conflicts: ConflictStore,
    enabled_nf: list[str],
) -> list[Action]:
    actions: list[Action] = []
    for artifact in system.get("artifacts", []):
        if evidence.has(artifact["id"]):
            continue
        actions.append(
            Action(
                name=f"extract_L{artifact['level']}",
                target_id=artifact["id"],
                level=artifact["level"],
                estimated_cost=_size_cost(artifact),
                verification_method=artifact.get("verification_method")
                or ("deterministic" if artifact["level"] <= 2 else "symbolic"),
                prerequisites=tuple(artifact.get("prerequisites", [])),
                expected_delta_coverage=artifact.get("relevance", 0.1) * 0.2,
                expected_delta_confidence=0.2,
                expected_delta_risk_reduction=0.15,
            )
        )
    for nf in enabled_nf:
        for artifact in system.get("artifacts", []):
            if nf not in artifact.get("nf", []):
                continue
            nf_id = f"{artifact['id']}#nf:{nf}"
            if evidence.has(nf_id):
                continue
            actions.append(
                Action(
                    name=f"extract_nf:{nf}",
                    target_id=nf_id,
                    level=artifact["level"],
                    estimated_cost=_size_cost(artifact),
                    verification_method="symbolic",
                    prerequisites=tuple(artifact.get("prerequisites", [])),
                    expected_delta_coverage=artifact.get("relevance", 0.1) * 0.15,
                    expected_delta_confidence=0.15,
                    expected_delta_risk_reduction=0.25,
                )
            )
    return actions


def expected_utility(
    action: Action,
    goal: dict[str, Any],
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    budget: Budget,
) -> float:
    alpha = goal.get("alpha", 0.4)
    beta = goal.get("beta", 0.3)
    gamma = goal.get("gamma", 0.3)
    value = (
        alpha * action.expected_delta_coverage
        + beta * action.expected_delta_confidence
        + gamma * action.expected_delta_risk_reduction
    )
    cost_weight = max(action.estimated_cost.tokens, 1) + max(action.estimated_cost.tool, 1)
    return value / cost_weight


def execute_action(action: Action, system: dict[str, Any]) -> ActionResult:
    target_id = action.target_id
    nf: str | None = None
    if "#nf:" in target_id:
        base_id, nf = target_id.split("#nf:", 1)
    else:
        base_id = target_id
    artifact = next(a for a in system["artifacts"] if a["id"] == base_id)
    _resolve_lazy(artifact)
    if nf is None:
        kind = artifact.get("kind", "artifact")
        content = artifact.get("content", "")
        location = artifact.get("location", artifact["id"])
    else:
        kind = f"nf:{nf}"
        content = artifact.get(f"nf_{nf}", f"{nf}:{artifact.get('content','')}")
        location = f"{base_id}#{nf}"
    evidence = Evidence(
        id=target_id,
        content=content,
        kind=kind,
        source=artifact.get("source", "disk"),
        location=location,
        level=artifact["level"],
        timestamp=artifact.get("timestamp", 0),
    )
    confidence = _confidence_for(action.verification_method)
    status = "supported" if confidence >= 0.7 else "weak"
    verification = Verification(
        confidence=confidence,
        status=status,
        provenance=target_id,
        method=action.verification_method,
        timestamp=evidence.timestamp,
    )
    observed_tokens = max(10, len(str(content)) // 4)
    return ActionResult(
        evidence=evidence,
        verification=verification,
        actual_cost=Cost(tokens=observed_tokens, tool=1),
    )


def normalize_evidence(result: ActionResult) -> Evidence:
    return result.evidence


def _find_artifact(system: dict[str, Any], evidence_id: str) -> dict[str, Any] | None:
    return next((a for a in system.get("artifacts", []) if a.get("id") == evidence_id), None)


def _verification_from_run(run: dict[str, Any] | None) -> tuple[float, str] | None:
    """Map a dynamic/logs/history run status to (confidence, epistemic status).

    Returns None when there is no overriding run signal (fall back to method).
    A failing suite or error-bearing logs must NOT become ``supported``: this is
    the core §11 guarantee that negative evidence is preserved, not inverted.
    """
    if not isinstance(run, dict):
        return None
    status = run.get("status")
    if status == "contradicted":
        return 0.15, "contradicted"
    if status == "unavailable":
        return 0.0, "unknown"
    if status == "weak":
        return 0.4, "weak"
    return None


def verify_evidence(
    evidence: Evidence,
    method: str,
    system: dict[str, Any],
) -> Verification:
    override = _verification_from_run(
        _find_artifact(system, evidence.id).get("run") if _find_artifact(system, evidence.id) else None
    )
    if override is None:
        confidence = _confidence_for(method)
        status = "supported" if confidence >= 0.7 else "weak"
    else:
        confidence, status = override
    return Verification(
        confidence=confidence,
        status=status,
        provenance=evidence.id,
        method=method,
        timestamp=evidence.timestamp,
    )


def detect_proposition_conflicts(
    propositions: PropositionStore,
    *,
    similarity: Callable[[frozenset[str], frozenset[str]], float] = _jaccard,
    threshold: float = 0.5,
) -> list[Conflict]:
    """Contradictions between propositions, not between files (readme.md §11).

    Two signals per aspect:
    * polarity contradiction (strong): the aspect has both a positive and a
      negative proposition (e.g. a passing and a failing test on the same
      aspect) -> severity 0.9.
    * claim divergence (weaker): same polarity but divergent positions
      (``similarity < threshold``) -> severity from the confidence gap.

    Identity is stable: keyed by ``(aspect, claim)`` so the store dedups across
    loop iterations instead of accumulating.
    """
    by_aspect: dict[str, list[Proposition]] = {}
    for prop in propositions:
        by_aspect.setdefault(prop.aspect, []).append(prop)
    conflicts: list[Conflict] = []
    for aspect, props in by_aspect.items():
        if len(props) < 2:
            continue
        pos = [p for p in props if p.polarity > 0]
        neg = [p for p in props if p.polarity < 0]
        if pos and neg:
            conflicts.append(
                Conflict(
                    claim=f"contradiccion en {aspect}",
                    evidence_for=tuple(p.evidence_id for p in pos),
                    evidence_against=tuple(p.evidence_id for p in neg),
                    scope=aspect,
                    severity=0.9,
                    resolution_status="open",
                )
            )
            continue
        ref = props[0]
        against = [p for p in props[1:] if similarity(ref.position, p.position) < threshold]
        if against:
            confs = [p.confidence for p in props]
            severity = min(1.0, 0.5 + max(confs) - min(confs))
            conflicts.append(
                Conflict(
                    claim=f"divergencia en {aspect}",
                    evidence_for=tuple(ref.evidence_id for _ in range(1)),
                    evidence_against=tuple(p.evidence_id for p in against),
                    scope=aspect,
                    severity=severity,
                    resolution_status="open",
                )
            )
    return conflicts


def q_g_invariant(evidence: EvidenceStore, beliefs: BeliefStore) -> bool:
    """Traceability invariant (§20): every belief resolves to retained evidence.

    ``Q_G(E) = Q_G(φ_E(E))`` requires that compressing ``E`` does not destroy the
    evidence needed to verify a current conclusion. Operationally we check that
    each belief dependency is present with its identifying fields intact
    (``id``, ``level``, a non-empty ``content`` or ``digest``, and ``source``).
    """
    for belief in beliefs:
        for dep in belief.dependencies:
            item = evidence.get(dep)
            if item is None:
                return False
            if not (item.content or item.digest):
                return False
            if not item.source:
                return False
    return True


def synthesize_report(
    system: dict[str, Any],
    goal: dict[str, Any],
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    propositions: PropositionStore,
    conflicts: ConflictStore,
    aspects: list[dict[str, Any]],
    coverage: float,
    residual_risk: float,
    budget: Budget,
    cost: dict[str, int] | None = None,
) -> dict[str, Any]:
    by_aspect: dict[str, list[Proposition]] = {}
    for prop in propositions:
        by_aspect.setdefault(prop.aspect, []).append(prop)
    corroboration = goal.get("corroboration", CORROBORATION)
    aspect_scores = {
        a["name"]: round(aspect_score(by_aspect.get(a["name"], []), corroboration), 4)
        for a in aspects
    }
    return {
        "system": system.get("name"),
        "goal": goal.get("name"),
        "evidence_count": len(evidence),
        "belief_count": len(beliefs),
        "proposition_count": len(propositions),
        "conflict_count": len(conflicts),
        "compressed_count": sum(1 for e in evidence if e.compressed),
        "evidence_kinds": sorted({e.kind for e in evidence}),
        "conflicts": [
            {
                "claim": c.claim,
                "scope": c.scope,
                "severity": round(c.severity, 4),
                "evidence_for": list(c.evidence_for),
                "evidence_against": list(c.evidence_against),
                "resolution_status": c.resolution_status,
            }
            for c in conflicts
        ],
        "coverage": round(coverage, 4),
        "residual_risk": round(residual_risk, 4),
        "aspect_scores": aspect_scores,
        "budget_remaining": {
            "tokens": budget.tokens_remaining,
            "tool": budget.tool_remaining,
        },
        "cost": cost or {"estimated_tokens": 0, "observed_tokens": 0},
        "levels_covered": sorted(evidence.levels()),
        "conclusions": [
            {
                "claim": p.claim,
                "aspect": p.aspect,
                "confidence": p.confidence,
                "status": _epistemic_status(p.polarity, p.confidence),
                "polarity": p.polarity,
                "evidence": p.evidence_id,
                "dependencies": list(p.dependencies),
                "method": p.method,
                "scope": p.scope,
                "timestamp": p.timestamp,
            }
            for p in propositions
        ],
        "complete": coverage >= goal.get("theta_coverage", budget.theta_coverage)
        and residual_risk <= goal.get("rho_risk", budget.rho_risk)
        and not any(p.polarity < 0 for p in propositions)
        and not conflicts.critical()
        and min_sources_met(propositions, aspects, int(goal.get("min_sources_per_aspect", 2))),
    }


def analyze_system(system: dict[str, Any], goal: dict[str, Any], budget: Budget, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = EvidenceStore()
    beliefs = BeliefStore()
    propositions = PropositionStore()
    conflicts = ConflictStore()
    required_aspects = derive_goal_aspects(goal)
    aspect_names = [a["name"] for a in required_aspects]
    enabled_nf = select_non_functional_extractors(goal)
    linker = goal.get("aspect_linker") or _default_linker
    min_sources = int(goal.get("min_sources_per_aspect", 2))
    coverage = 0.0
    residual_risk = 1.0
    cost_estimated = 0
    cost_observed = 0
    while budget.has_capacity():
        coverage = compute_coverage(propositions, required_aspects, goal.get("corroboration", CORROBORATION))
        residual_risk = compute_residual_risk(propositions, required_aspects, goal)
        breadth_ok = min_sources_met(propositions, required_aspects, min_sources)
        if should_stop(coverage, residual_risk, conflicts, goal, budget, breadth_ok):
            break
        actions = generate_candidate_actions(system, goal, evidence, beliefs, conflicts, enabled_nf)
        eligible = [
            action
            for action in actions
            if prerequisites_satisfied(action, evidence, beliefs) and budget.can_afford(action.estimated_cost)
        ]
        if not eligible:
            break
        action = max(
            eligible,
            key=lambda candidate: expected_utility(candidate, goal, evidence, beliefs, budget),
        )
        result = execute_action(action, system)
        budget.consume(result.actual_cost)
        cost_estimated += action.estimated_cost.tokens
        cost_observed += result.actual_cost.tokens
        new_evidence = normalize_evidence(result)
        evidence.add(new_evidence)
        verification = verify_evidence(new_evidence, action.verification_method, system)
        beliefs.update(new_evidence, verification, goal["name"])
        artifact = _resolve_artifact(system, new_evidence.id)
        for prop in derive_propositions(
            new_evidence, verification, artifact, aspect_names, goal["name"], goal, linker
        ):
            propositions.add(prop)
        conflicts.merge(
            detect_proposition_conflicts(
                propositions,
                similarity=goal.get("conflict_similarity") or _jaccard,
                threshold=goal.get("conflict_threshold", 0.5),
            )
        )
        protected_ids: set[str] = set()
        for conflict in conflicts:
            protected_ids.update(conflict.evidence_for)
            protected_ids.update(conflict.evidence_against)
        evidence.compress(budget, preserve_provenance=True, preserve_invariants=protected_ids)
    coverage = compute_coverage(propositions, required_aspects, goal.get("corroboration", CORROBORATION))
    residual_risk = compute_residual_risk(propositions, required_aspects, goal)
    return synthesize_report(
        system, goal, evidence, beliefs, propositions, conflicts, required_aspects,
        coverage, residual_risk, budget, {"estimated_tokens": cost_estimated, "observed_tokens": cost_observed},
    )


def run(system: dict[str, Any] | None = None, goal: dict[str, Any] | None = None, budget: Budget | None = None) -> dict[str, Any]:
    if system is None:
        system = {
            "name": "argos",
            "artifacts": [
                {"id": "readme.md", "content": "Modelo Epistemico Unificado: proposito y estructura", "level": 0, "relevance": 1.0, "kind": "doc",
                 "supports": [{"aspect": "proposito"}, {"aspect": "estructura"}]},
                {"id": "pyproject.toml", "content": "build manifest del entorno", "level": 2, "relevance": 0.6, "kind": "config",
                 "supports": [{"aspect": "entorno"}]},
                {"id": "argos_epistemic/algorithm.py", "content": "reference impl de contratos y comportamiento", "level": 4, "relevance": 0.8, "kind": "code",
                 "supports": [{"aspect": "contratos"}, {"aspect": "comportamiento"}]},
            ],
        }
    if goal is None:
        goal = {
            "name": "autoanalisis",
            "aspects": ["proposito", "estructura", "entorno", "contratos", "comportamiento"],
            "non_functional": ["sec"],
            "theta_coverage": 0.8,
            "rho_risk": 0.3,
        }
    if budget is None:
        budget = Budget(tokens_remaining=10000, tool_remaining=50)
    return analyze_system(system, goal, budget)
