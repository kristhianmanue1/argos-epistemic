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
        original = str(self.content)
        self.digest = f"phi:{abs(hash(original)) & 0xFFFFFFFF:08x}"
        self.content = f"<compressed:{self.digest}>"
        self.compressed = True


EVIDENCE_CAPACITY = 8


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
        capacity = EVIDENCE_CAPACITY
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


def compute_coverage(
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    aspects: list[dict[str, Any]],
) -> float:
    if not aspects:
        return 0.0
    supported_confidence = sum(b.confidence for b in beliefs if b.status == "supported")
    weak_confidence = sum(b.confidence for b in beliefs if b.status == "weak") * 0.5
    return min(1.0, (supported_confidence + weak_confidence) / len(aspects))


def compute_residual_risk(
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    goal: dict[str, Any],
) -> float:
    if not beliefs:
        return 1.0
    avg_confidence = sum(b.confidence for b in beliefs) / len(beliefs)
    unknown_share = sum(1 for b in beliefs if b.status == "unknown") / len(beliefs)
    return max(0.0, min(1.0, (1.0 - avg_confidence) * 0.7 + unknown_share * 0.3))


def _confidence_for(method: str) -> float:
    """Confianza por método de verificación (§9.1).

    deterministic/dynamic -> 0.9; historical -> 0.8; symbolic/other -> 0.6.
    """
    if method in ("deterministic", "dynamic"):
        return 0.9
    if method == "historical":
        return 0.8
    return 0.6


def should_stop(
    coverage: float,
    residual_risk: float,
    conflicts: ConflictStore,
    goal: dict[str, Any],
    budget: Budget,
) -> bool:
    theta = goal.get("theta_coverage", budget.theta_coverage)
    rho = goal.get("rho_risk", budget.rho_risk)
    if coverage >= theta and residual_risk <= rho and not conflicts.critical():
        return True
    return False


def prerequisites_satisfied(action: Action, evidence: EvidenceStore, beliefs: BeliefStore) -> bool:
    return all(evidence.has(prereq) or any(prereq == b.claim for b in beliefs) for prereq in action.prerequisites)


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
                estimated_cost=Cost(tokens=int(50 * artifact.get("relevance", 1.0)), tool=1),
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
                    estimated_cost=Cost(tokens=int(40 * artifact.get("relevance", 1.0)), tool=1),
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
    if nf is None:
        kind = artifact.get("kind", "artifact")
        content = artifact["content"]
        location = artifact.get("location", artifact["id"])
    else:
        kind = f"nf:{nf}"
        content = artifact.get(f"nf_{nf}", f"{nf}:{artifact['content']}")
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
    return ActionResult(evidence=evidence, verification=verification, actual_cost=action.estimated_cost)


def normalize_evidence(result: ActionResult) -> Evidence:
    return result.evidence


def verify_evidence(
    evidence: Evidence,
    method: str,
    system: dict[str, Any],
) -> Verification:
    return Verification(
        confidence=_confidence_for(method),
        status="supported" if _confidence_for(method) >= 0.7 else "weak",
        provenance=evidence.id,
        method=method,
        timestamp=evidence.timestamp,
    )


def detect_conflicts(
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    *,
    similarity: Callable[[frozenset[str], frozenset[str]], float] = _jaccard,
    threshold: float = 0.5,
) -> list[Conflict]:
    """Detect divergent beliefs at the same scope.

    Two beliefs ``conflict`` when their positions are not near-equivalent:
    ``similarity(a, b) < threshold``. Default similarity is lexical Jaccard over
    token sets — it tolerates case/punctuation/word-order reformulation but is
    NOT semantic equivalence (that requires an LLM/embedding approximator, i.e.
    ``S_semantic``). Inject ``similarity`` to plug a richer one.
    """
    by_scope: dict[str, list[Belief]] = {}
    for belief in beliefs:
        by_scope.setdefault(belief.scope, []).append(belief)
    conflicts: list[Conflict] = []
    for scope, group in by_scope.items():
        if len(group) < 2:
            continue
        primary = group[0].position
        evidence_for: list[str] = []
        evidence_against: list[str] = []
        for belief in group:
            if similarity(primary, belief.position) >= threshold:
                evidence_for.extend(belief.dependencies)
            else:
                evidence_against.extend(belief.dependencies)
        if not evidence_against:
            continue
        confidences = [b.confidence for b in group]
        severity = min(1.0, 0.5 + max(confidences) - min(confidences))
        conflicts.append(
            Conflict(
                claim=f"divergencia en {scope}",
                evidence_for=tuple(evidence_for),
                evidence_against=tuple(evidence_against),
                scope=scope,
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
    conflicts: ConflictStore,
    coverage: float,
    residual_risk: float,
    budget: Budget,
) -> dict[str, Any]:
    return {
        "system": system.get("name"),
        "goal": goal.get("name"),
        "evidence_count": len(evidence),
        "belief_count": len(beliefs),
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
        "budget_remaining": {
            "tokens": budget.tokens_remaining,
            "tool": budget.tool_remaining,
        },
        "levels_covered": sorted(evidence.levels()),
        "conclusions": [
            {"claim": b.claim, "confidence": b.confidence, "status": b.status}
            for b in beliefs
        ],
        "complete": coverage >= goal.get("theta_coverage", budget.theta_coverage)
        and residual_risk <= goal.get("rho_risk", budget.rho_risk),
    }


def analyze_system(system: dict[str, Any], goal: dict[str, Any], budget: Budget, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = EvidenceStore()
    beliefs = BeliefStore()
    conflicts = ConflictStore()
    required_aspects = derive_goal_aspects(goal)
    enabled_nf = select_non_functional_extractors(goal)
    coverage = 0.0
    residual_risk = 1.0
    while budget.has_capacity():
        coverage = compute_coverage(evidence, beliefs, required_aspects)
        residual_risk = compute_residual_risk(evidence, beliefs, goal)
        if should_stop(coverage, residual_risk, conflicts, goal, budget):
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
        new_evidence = normalize_evidence(result)
        evidence.add(new_evidence)
        verification = verify_evidence(new_evidence, action.verification_method, system)
        beliefs.update(new_evidence, verification, goal["name"])
        conflicts.merge(
            detect_conflicts(
                evidence,
                beliefs,
                similarity=goal.get("conflict_similarity") or _jaccard,
                threshold=goal.get("conflict_threshold", 0.5),
            )
        )
        beliefs.mark_conflicted(conflicts.open_scopes())
        protected_ids: set[str] = set()
        for conflict in conflicts:
            protected_ids.update(conflict.evidence_for)
            protected_ids.update(conflict.evidence_against)
        evidence.compress(budget, preserve_provenance=True, preserve_invariants=protected_ids)
    return synthesize_report(system, goal, evidence, beliefs, conflicts, coverage, residual_risk, budget)


def run(system: dict[str, Any] | None = None, goal: dict[str, Any] | None = None, budget: Budget | None = None) -> dict[str, Any]:
    if system is None:
        system = {
            "name": "argos",
            "artifacts": [
                {"id": "readme.md", "content": "Modelo Epistemico Unificado", "level": 0, "relevance": 1.0, "kind": "doc"},
                {"id": "pyproject.toml", "content": "build manifest", "level": 2, "relevance": 0.6, "kind": "config"},
                {"id": "argos_epistemic/algorithm.py", "content": "reference impl", "level": 4, "relevance": 0.8, "kind": "code"},
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
