"""Implementacion de referencia ejecutable del algoritmo de la seccion 22.

Es una version minima, funcional y terminante del esqueleto declarativo de
``MODEL.md``. No es una implementacion optimizada del modelo completo: expone
los tipos y el flujo principal para que puedan ejecutarse pruebas de humo y
verificar que el algoritmo termina, decide y sintetiza un reporte trazable.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .canonical import CANONICALIZATION_PROFILE, content_id, fingerprinted_document
from .verifiers import (
    INDEPENDENCE_PROFILE,
    VERIFIER_CONTRACT,
    IndependenceSource,
    VerificationResult,
    independence_report,
    independent_source_count,
    root_fingerprint,
    validate_verification_result,
)


@dataclass
class Cost:
    tokens: int = 0
    tool: int = 0
    latency: float = 0.0
    compute: float = 0.0

    def dominates(self, other: Cost) -> bool:
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
    """Adaptive compression capacity (MODEL.md §8): the store keeps at most
    ``capacity`` items uncompressed, derived from the remaining token budget.
    As ``budget.tokens_remaining`` shrinks during a run, capacity shrinks and
    compression becomes stricter. Floor is ``EVIDENCE_CAPACITY``.
    """
    derived = budget.tokens_remaining // EVIDENCE_TOKENS_PER_SLOT
    return max(EVIDENCE_CAPACITY, int(derived))


def _tokens(content: Any) -> frozenset[str]:
    """Lexical surrogate for a position: lowercase alphanumeric token set.

    True semantic identity needs embeddings/LLM (``S_semantic``, LLM-approximated
    per MODEL.md §6.1). This frozenset is the deterministic default; a richer
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

    def __iter__(self) -> Iterator[Evidence]:
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

    def __iter__(self) -> Iterator[Belief]:
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
    kind: str = "contradiction"
    claim_id: str = ""


class ConflictStore:
    def __init__(self) -> None:
        self._items: list[Conflict] = []

    def __iter__(self) -> Iterator[Conflict]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def merge(self, conflicts: list[Conflict]) -> None:
        for conflict in conflicts:
            key = (conflict.scope, conflict.claim_id or conflict.claim)
            if any((c.scope, c.claim_id or c.claim) == key for c in self._items):
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
    """A candidate extraction, with its capability and separated expectations.

    The four expectation fields model *different* goods and must not be
    collapsed: retrieving an informative file, proving an aspect, discovering a
    contradiction and lowering residual risk are distinct outcomes, and most
    actions can deliver only some of them. ``capability`` states which.
    """

    name: str
    target_id: str
    level: int
    estimated_cost: Cost
    verification_method: str
    prerequisites: tuple[str, ...] = ()
    capability: str = "retrieval_only"
    expected_retrieval_gain: float = 0.0
    expected_delta_coverage: float = 0.0
    expected_contradiction_discovery: float = 0.0
    expected_delta_risk_reduction: float = 0.0
    expected_delta_confidence: float = 0.1
    calibration_profile: str = "uncalibrated-v0"
    requested_calibration_profile: str = "uncalibrated-v0"
    expectation_uncertainty: str = "unbounded"
    declaration_diagnostics: tuple[str, ...] = field(default_factory=tuple)


def derive_goal_aspects(goal: dict[str, Any]) -> list[dict[str, Any]]:
    aspects: list[dict[str, Any]] = []
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

    This is the keystone layer (MODEL.md §7, §12, §23): evidence becomes a
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
    impact: float = 0.0
    relation: str = "supports"
    claim_id: str = ""
    claim_text: str = ""
    authority_class: str = "unknown"
    extraction_profile: str = "legacy-proposition-v1"
    verification_result_id: str = ""
    verifier_family: str = ""
    verifier_version: str = ""
    verification_method_profile: str = ""
    execution_id: str = ""
    target_revision: str = ""
    root_fingerprints: tuple[str, ...] = ()
    derived_from: tuple[str, ...] = ()
    independence_class: str = ""


class PropositionStore:
    def __init__(self) -> None:
        self._items: list[Proposition] = []

    def __iter__(self) -> Iterator[Proposition]:
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

    Impact prior (``goal["link_impact_weight"]``, default 0 = off): ``S_semantic`` is
    non-faithful (MODEL.md §6.1) and, on real repos, short topically-saturated docs
    beat large diluted code files on cosine, so documentation over-links and code never
    links. Lifting the effective link by ``w * Impact(x)`` lets production code
    (``impact > 0``) link at lower semantic similarity, restoring recall without
    fitting theta to gold. No-op when impact is absent (fixtures) or the weight is 0.
    """
    if artifact is None:
        return {}
    entries, _diagnostics = parse_declared_relations(artifact, aspect_names)
    supports = {
        item["aspect"]: item["strength"]
        for item in entries
        if item["relation"] == "supports"
    }
    if supports:
        return supports
    threshold = goal.get("link_threshold")
    if threshold is None:
        from .extractors import default_link_threshold

        threshold = default_link_threshold(linker)
    content = str(artifact.get("content", "")) + " " + str(artifact.get("id", ""))
    impact_w = float(goal.get("link_impact_weight", 0.0) or 0.0)
    impact = float(artifact.get("impact", 0.0) or 0.0) if impact_w > 0.0 else 0.0
    lift = impact_w * impact
    linked: dict[str, float] = {}
    for aspect in aspect_names:
        strength = linker(content, aspect)
        if lift > 0.0 and impact > 0.0:
            strength = min(1.0, strength + lift)
        if strength >= threshold:
            linked[aspect] = strength
    return linked


def _authority_class(method: str, declared: bool) -> str:
    if method == "dynamic":
        return "direct_verification"
    if not declared:
        return "semantic_relevance"
    if method == "historical":
        return "historical_evidence"
    return "explicit_artifact_claim"


_DECLARABLE_RELATIONS = (
    "supports",
    "refutes",
    "mentions",
    "tests",
    "implements",
    "configures",
)


def parse_declared_relations(
    artifact: dict[str, Any], aspect_names: Iterable[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """THE normalizer for declared relations. Returns (entries, diagnostics).

    This is the single parser shared by capability classification, expectation
    generation, proposition derivation and diagnostic serialisation. Keeping two
    parsers with different tolerances is what let ``strength="bad"`` raise a raw
    ``ValueError`` from inside ``analyze_system`` and let ``strength=NaN`` reach
    coverage as if it were a normal support.

    Fails closed: every malformed entry is dropped and reported. A dropped entry
    never becomes a proposition, so it can contribute neither coverage nor risk.

    Transitional semantics of ``strength``:

    - ``0.0`` means the relation does not hold, so for ``supports``/``refutes``
      it is an admission criterion that rejects the entry outright;
    - values in ``(0, 1]`` are admissible;
    - until the aggregation is redefined (PR F), ``strength`` is ONLY an
      admission criterion. It is not applied as a weight on coverage and must
      not be presented as one.
    """
    if not any(relation in artifact for relation in _DECLARABLE_RELATIONS):
        # Fast path: the overwhelming majority of discovered artifacts declare
        # nothing. This is called per artifact per link evaluation, so parsing
        # unconditionally here dominated the whole analysis.
        return [], []
    required = set(aspect_names)
    entries: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    for relation in _DECLARABLE_RELATIONS:
        declared = artifact.get(relation)
        if declared is None:
            continue
        if not isinstance(declared, list):
            diagnostics.append(f"{relation}:not_a_list")
            continue
        for entry in declared:
            if not isinstance(entry, dict):
                diagnostics.append(f"{relation}:entry_not_a_mapping")
                continue
            aspect = entry.get("aspect")
            if not isinstance(aspect, str):
                diagnostics.append(f"{relation}:aspect_not_a_string")
                continue
            strength = 1.0
            if "strength" in entry:
                parsed = _finite(entry["strength"])
                if parsed is None:
                    diagnostics.append(f"{relation}:strength_not_finite")
                    continue
                if not 0.0 <= parsed <= 1.0:
                    diagnostics.append(f"{relation}:strength_out_of_range")
                    continue
                if parsed == 0.0 and relation in _PROBATORY_RELATIONS:
                    # Zero strength states that the relation does NOT hold. Admitting
                    # it as a support produced a false completion: coverage 0.3333,
                    # risk 0.0 and complete=True from a declaration asserting nothing.
                    diagnostics.append(f"{relation}:zero_strength_no_effect")
                    continue
                strength = parsed
            malformed_text = [
                field_name
                for field_name in ("claim", "scope")
                if field_name in entry and not isinstance(entry[field_name], str)
            ]
            if malformed_text:
                diagnostics += [f"{relation}:{name}_not_a_string" for name in malformed_text]
                continue
            if aspect not in required:
                continue
            entries.append(
                {
                    "aspect": aspect,
                    "relation": relation,
                    "strength": strength,
                    "claim_text": str(entry.get("claim", f"{aspect} holds")),
                    "scope": str(entry.get("scope", aspect)),
                    "declared": True,
                }
            )
    by_relation: dict[str, set[str]] = {}
    for item in entries:
        by_relation.setdefault(item["relation"], set()).add(item["aspect"])
    if by_relation.get("supports", set()) & by_relation.get("refutes", set()):
        diagnostics.append("self_contradictory_declaration")
    return entries, sorted(set(diagnostics))


def _declared_relations(
    artifact: dict[str, Any], aspect_names: list[str]
) -> list[dict[str, Any]]:
    entries, _diagnostics = parse_declared_relations(artifact, aspect_names)
    return entries


def relate_artifact_to_aspects(
    artifact: dict[str, Any] | None,
    aspect_names: list[str],
    goal: dict[str, Any],
    linker,
) -> list[dict[str, Any]]:
    if artifact is None:
        return []
    declared = _declared_relations(artifact, aspect_names)
    if declared:
        return declared
    return [
        {
            "aspect": aspect,
            "relation": "mentions",
            "strength": strength,
            "claim_text": f"{aspect} mentioned",
            "scope": aspect,
            "declared": False,
        }
        for aspect, strength in link_aspects(artifact, aspect_names, goal, linker).items()
    ]


def derive_propositions(
    evidence: Evidence,
    verification: Verification,
    artifact: dict[str, Any] | None,
    aspect_names: list[str],
    goal_name: str,
    goal: dict[str, Any],
    linker,
) -> list[Proposition]:
    relations = relate_artifact_to_aspects(artifact, aspect_names, goal, linker)
    props: list[Proposition] = []
    for item in relations:
        relation = item["relation"]
        if verification.method == "dynamic" and relation == "mentions":
            relation = "refutes" if verification.status == "contradicted" else "supports"
            item["claim_text"] = f"{item['aspect']} runtime verification passes"
        if verification.status == "contradicted" and relation == "supports":
            relation = "refutes"
        sign = 1.0 if relation == "supports" else (-1.0 if relation == "refutes" else 0.0)
        claim_text = item["claim_text"]
        scope = item["scope"]
        claim_identity = content_id(
            "claim",
            {
                "profile": "argos/claim-identity-v1",
                "aspect": item["aspect"],
                "claim": claim_text,
                "scope": scope,
            },
        )
        props.append(
            Proposition(
                aspect=item["aspect"],
                polarity=sign,
                claim=claim_text,
                evidence_id=evidence.id,
                confidence=verification.confidence,
                method=verification.method,
                scope=scope,
                timestamp=evidence.timestamp,
                dependencies=(evidence.id,),
                strength=item["strength"],
                position=_tokens(str(artifact.get("content", ""))) if artifact else frozenset(),
                impact=float(artifact.get("impact", 0.0) or 0.0) if artifact else 0.0,
                relation=relation,
                claim_id=claim_identity,
                claim_text=claim_text,
                authority_class=_authority_class(verification.method, item["declared"]),
                extraction_profile="argos/typed-proposition-v1",
                # Provenance is NOT read from the artifact: the analyzed target
                # must not be able to declare execution_id, verifier_profile or
                # roots, since those are the inputs to independence. A legacy
                # declared support therefore carries only the content-addressed
                # root and counts as one undemonstrated source.
                root_fingerprints=(
                    (root_fingerprint(str(artifact.get("content", ""))),) if artifact else ()
                ),
            )
        )
    return props


CORROBORATION = 1.8


def _claim_record(proposition: Proposition) -> dict[str, Any]:
    return fingerprinted_document(
        {
            "schema": "argos/claim-record-v1",
            "canonicalization": CANONICALIZATION_PROFILE,
            "claim_id": proposition.claim_id,
            "claim_text": proposition.claim_text,
            "aspect": proposition.aspect,
            "relation": proposition.relation,
            "scope": proposition.scope,
            "evidence_id": proposition.evidence_id,
            "confidence": str(proposition.confidence),
            "strength": str(proposition.strength),
            "authority_class": proposition.authority_class,
            "method": proposition.method,
            "timestamp": proposition.timestamp,
            "extraction_profile": proposition.extraction_profile,
        }
    )


def aspect_score(props: list[Proposition], corroboration: float = CORROBORATION) -> float:
    """Coverage of one aspect (MODEL.md §12), calibrated to reward corroboration.

    ``score = clamp01( Σ_pos polarity·conf / corroboration )``: a single source
    does NOT saturate the aspect (it scores conf/corroboration, e.g. 0.9/1.8 =
    0.5); reaching ~0.8 requires 2+ independent supporting propositions. This
    closes the overconfidence gap exposed by the P2 benchmark, where 1 artifact
    linking all aspects falsely reported coverage ≈ 0.9.
    """
    pos_mass = sum(
        p.polarity * p.confidence
        for p in props
        if p.relation == "supports" and p.polarity > 0
    )
    return max(0.0, min(1.0, pos_mass / max(0.0001, corroboration)))


def compute_coverage(
    propositions: Iterable[Proposition],
    aspects: list[dict[str, Any]],
    corroboration: float = CORROBORATION,
) -> float:
    """Per-aspect coverage (MODEL.md §12): Cov = Σ w_i · aspect_score(t_i).

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
    propositions: Iterable[Proposition],
    aspects: list[dict[str, Any]],
    goal: dict[str, Any],
) -> float:
    """Residual risk over PROBATIVE claims (MODEL.md §13, plan §3.2/§5.2).

    ``risk = missing_share + (1 - missing_share) * contradiction_share``

    Both terms are computed over ``supports``/``refutes`` **whose aspect belongs
    to the goal's required aspects**, aggregated by claim identity rather than
    by proposition volume. Evidence about aspects the goal never asked for is
    off-scope: it can neither cover a requirement nor contaminate the
    contradiction term of an unrelated evaluation.

    - ``missing_share``: required aspects with no positive support. Only
      positive support can lower it, so neither retrieval nor refutation can
      mark an aspect covered.
    - ``contradiction_share``: distinct probative claims carrying at least one
      refutation, over distinct probative claims. Counting *claims* (not
      propositions) is what stops duplicate readings of one claim from either
      multiplying risk or burying a refutation under corroboration.

    The nesting gives the invariants structurally rather than by convention:

    - ``missing_share == 1`` forces ``risk == 1``, because the second term is
      scaled by ``(1 - missing_share) == 0``. No special case on the number of
      propositions is needed.
    - ``mentions`` appear in no numerator and no denominator, so adding any
      volume of them leaves the score bit-identical - never reduced, diluted.
    - a refutation never lowers the score: it cannot reduce ``missing_share``,
      and on the contradiction term it either lands on a claim already counted
      (share unchanged), converts a supported claim to contradicted (share
      rises), or opens a new claim, where ``(c+1)/(n+1) >= c/n`` holds for all
      ``c <= n``.

    Calibration of this aggregation is plan decision §12.1 and remains subject
    to human approval; the invariants above are not negotiable regardless of
    the weights finally chosen.
    """
    if not aspects:
        return 0.0
    names = [a["name"] for a in aspects]
    required = set(names)
    probative = [
        p
        for p in propositions
        if p.relation in ("supports", "refutes") and p.aspect in required
    ]
    supported = {
        p.aspect for p in probative if p.relation == "supports" and p.polarity > 0
    }
    missing_share = sum(1 for n in names if n not in supported) / len(names)
    claims: dict[Any, bool] = {}
    for prop in probative:
        identity = prop.claim_id or (prop.aspect, prop.claim_text or prop.claim, prop.scope)
        claims[identity] = claims.get(identity, False) or prop.relation == "refutes"
    contradiction_share = (
        sum(1 for contradicted in claims.values() if contradicted) / len(claims)
        if claims
        else 0.0
    )
    risk = missing_share + (1.0 - missing_share) * contradiction_share
    return max(0.0, min(1.0, risk))


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
    propositions: Iterable[Proposition],
    aspects: list[dict[str, Any]],
    min_sources: int,
    required_target_revision: str = "",
) -> bool:
    """Every required aspect has a claim backed by >= min_sources INDEPENDENT sources.

    Structural anti-overconfidence, and the gate that keeps ``complete`` honest
    while legacy coverage still aggregates by proposition volume (see PR F).
    Counting distinct ``evidence_id`` was not enough: two ids pointing at
    identical content, two profiles reading one file, or two runs of one
    verifier are one source, not several. Sources are therefore grouped into
    connected components over shared observed roots, shared executions and
    derivation edges, and the components are counted.

    Corroboration is evaluated **per normalised claim**: supports for different
    claims of the same aspect do not add up, because agreeing about different
    things is not corroboration. An aspect is satisfied when at least one of its
    claims reaches the threshold.
    """
    if not aspects or min_sources <= 0:
        return True
    by_claim = claim_independence_sources(propositions)
    for aspect in aspects:
        name = aspect["name"]
        claims = [
            (claim_key, sources)
            for (asp, claim_key), sources in by_claim.items()
            if asp == name
        ]
        if not any(
            independent_source_count(sources, required_target_revision, claim_key)
            >= min_sources
            for claim_key, sources in claims
        ):
            return False
    return True


def proposition_from_verification(
    result: VerificationResult, goal_name: str
) -> Proposition | None:
    """The single, fail-closed conversion from a verification result.

    Returns ``None`` for anything non-probative OR internally inconsistent, so
    neither a degraded result nor one whose fields were altered after stamping
    can become a proposition. This is the only supported way to turn verifier
    output into evidence: reconstructing propositions by hand would reopen the
    path where provenance is asserted rather than carried.

    The consistency check proves integrity, not authenticity: it detects a
    result that no longer matches its canonical identity, but it does not
    establish who produced it. Accepting persisted or third-party results would
    additionally require a trusted attestation.
    """
    if validate_verification_result(result) or not result.is_probative:
        return None
    sign = 1.0 if result.outcome == "supports" else -1.0
    return Proposition(
        aspect=result.aspect,
        polarity=sign,
        claim=result.claim_text,
        evidence_id=result.artifact_id,
        confidence=result.confidence,
        method=result.verification_method,
        scope=result.scope,
        relation=result.outcome,
        claim_id=result.normalized_claim_id,
        claim_text=result.claim_text,
        authority_class="direct_verification",
        extraction_profile=VERIFIER_CONTRACT,
        verification_result_id=result.result_id,
        verifier_family=result.verifier_family,
        verifier_version=result.verifier_version,
        verification_method_profile=result.verification_method,
        execution_id=result.execution_id,
        target_revision=result.target_revision,
        root_fingerprints=result.root_fingerprints,
        derived_from=result.derived_from,
    )


def claim_independence_sources(
    propositions: Iterable[Proposition],
) -> dict[tuple[str, str], list[IndependenceSource]]:
    """Positive supports grouped by (aspect, normalised claim) with full provenance.

    The source id is the stamped ``verification_result_id`` when one exists;
    ``evidence_id`` is a fallback reserved for legacy evidence, and the report
    labels the two kinds separately so a legacy id is never presented as a
    verification result.
    """
    by_claim: dict[tuple[str, str], list[IndependenceSource]] = {}
    for prop in propositions:
        if prop.relation != "supports" or prop.polarity <= 0:
            continue
        key = (prop.aspect, prop.claim_id or prop.claim_text or prop.claim)
        verified = bool(prop.verification_result_id)
        by_claim.setdefault(key, []).append(
            IndependenceSource(
                source_id=prop.verification_result_id or prop.evidence_id,
                source_kind="verification_result" if verified else "legacy_evidence",
                normalized_claim_id=prop.claim_id,
                verifier_family=prop.verifier_family,
                verifier_version=prop.verifier_version,
                verification_method=prop.verification_method_profile or prop.method,
                execution_id=prop.execution_id,
                target_revision=prop.target_revision,
                root_fingerprints=prop.root_fingerprints,
                derived_from=prop.derived_from,
                independence_class=prop.independence_class,
            )
        )
    return by_claim


def system_has_production(system: dict[str, Any]) -> bool:
    """Whether the system carries L3 call-graph data (MODEL.md §6.1, Impact).

    Production code artifacts expose ``impact > 0`` from the call graph. Fixtures
    and systems analyzed without a call graph have no such field, so the
    production-evidence gate (``production_sources_met``) falls back to vacuous
    True there, preserving prior behavior.
    """
    return any(
        isinstance(a, dict) and float(a.get("impact", 0.0) or 0.0) > 0.0
        for a in system.get("artifacts", [])
    )


def production_sources_met(
    propositions: Iterable[Proposition],
    aspects: list[dict[str, Any]],
) -> bool:
    """Every required aspect has >= 1 supporting proposition from production code.

    Anti-overclaim sibling of ``min_sources_met``: it is not enough to amass
    peripheral evidence (docs, examples, config, typing stubs), because such
    artifacts talk *about* an aspect without being the implementation (MODEL.md
    §4 levels). When L3 data is available, an aspect counts as satisfied for
    ``complete``/``should_stop`` only if at least one positive proposition rests
    on a production (``impact > 0``) artifact. This kills the overclaim where the
    dense linker over-enlaza docs/examples and saturates coverage while recovering
    none of the implementation gold.
    """
    if not aspects:
        return True
    by_aspect: dict[str, set[str]] = {}
    for prop in propositions:
        if prop.relation == "supports" and prop.polarity > 0 and prop.impact > 0.0:
            by_aspect.setdefault(prop.aspect, set()).add(prop.evidence_id)
    return all(by_aspect.get(a["name"], set()) for a in aspects)


def should_stop(
    coverage: float,
    residual_risk: float,
    conflicts: ConflictStore,
    goal: dict[str, Any],
    budget: Budget,
    breadth_ok: bool = True,
    prod_ok: bool = True,
) -> bool:
    theta = goal.get("theta_coverage", budget.theta_coverage)
    rho = goal.get("rho_risk", budget.rho_risk)
    return (
        coverage >= theta
        and residual_risk <= rho
        and not conflicts.critical()
        and breadth_ok
        and prod_ok
    )


def prerequisites_satisfied(action: Action, evidence: EvidenceStore, beliefs: BeliefStore) -> bool:
    return all(evidence.has(prereq) or any(prereq == b.claim for b in beliefs) for prereq in action.prerequisites)


def _size_cost(artifact: Any, tool: int = 1) -> Cost:
    """Estimated extraction cost from artifact size, not epistemic relevance.

    Prefers a declared ``size`` (cheap stat at discovery) so that selection can
    gate on cost BEFORE the expensive extraction runs (MODEL.md §15, §16, and
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


CAPABILITY_RETRIEVAL_ONLY = "retrieval_only"
CAPABILITY_STRUCTURAL = "structural_relation"
CAPABILITY_PROBATORY_STATIC = "probatory_static"
CAPABILITY_PROBATORY_DYNAMIC = "probatory_dynamic"

_PROBATORY_RELATIONS = ("supports", "refutes")
_STRUCTURAL_RELATIONS = ("tests", "implements", "configures")


PROBATIVE_CALIBRATION_PROFILES: dict[str, dict[str, Any]] = {
    "uncalibrated-v0": {
        "support_success_probability": 0.0,
        "refutation_discovery_probability": 0.0,
        "uncertainty": "unbounded",
        "empirical": False,
        "requires_opt_in": False,
        "status": "conservative_zero_bound",
        "basis": "conservative zero bound because no empirical calibration exists",
    },
    "demo-linear-v0": {
        "support_success_probability": 0.5,
        "refutation_discovery_probability": 0.5,
        "uncertainty": "illustrative_only",
        "empirical": False,
        "requires_opt_in": True,
        "status": "illustrative_only",
        "basis": (
            "fixed illustrative constants for tests and demos; NOT measured. "
            "Requires goal['allow_non_empirical_calibration'] = True"
        ),
    },
}
DEFAULT_CALIBRATION_PROFILE = "uncalibrated-v0"
"""Versioned priors for probative expectations.

A profile supplies the *probability* that an action delivers support or
surfaces a refutation. The *magnitude* of the resulting change is never an
invented constant: it is simulated with the real ``compute_coverage`` and
``compute_residual_risk`` against the current state, so the expectation cannot
drift from the metric it claims to predict.

Probative expectations must never be derived from ``relevance``: relevance is a
retrieval signal and says nothing about the probability that an artifact
*proves* an aspect. Absent an empirical calibration the honest probability is
zero, so the default profile promises nothing and declares unbounded
uncertainty. ``demo-linear-v0`` exists to exercise the guards under non-zero
values, is flagged ``empirical: False`` and is refused unless the goal opts in
explicitly.
"""


def resolve_calibration(goal: dict[str, Any]) -> tuple[str, str, dict[str, Any], list[str]]:
    """Resolve the calibration profile. Returns (requested, effective, profile, diagnostics).

    Never silently reports an unknown or refused profile under its requested
    name: requested and effective are reported separately alongside a structured
    diagnostic, so a typo cannot masquerade as a configured calibration.
    """
    raw = goal.get("probative_calibration", DEFAULT_CALIBRATION_PROFILE)
    diagnostics: list[str] = []
    if not isinstance(raw, str):
        # A sanitised marker, never repr(raw): the goal is caller-supplied and
        # echoing it back into the report would leak arbitrary data.
        return (
            f"<non-string:{type(raw).__name__}>",
            DEFAULT_CALIBRATION_PROFILE,
            PROBATIVE_CALIBRATION_PROFILES[DEFAULT_CALIBRATION_PROFILE],
            ["calibration_profile:not_a_string"],
        )
    if raw not in PROBATIVE_CALIBRATION_PROFILES:
        return (
            raw,
            DEFAULT_CALIBRATION_PROFILE,
            PROBATIVE_CALIBRATION_PROFILES[DEFAULT_CALIBRATION_PROFILE],
            ["calibration_profile:unknown"],
        )
    profile = PROBATIVE_CALIBRATION_PROFILES[raw]
    if profile.get("requires_opt_in", True) and not goal.get(
        "allow_non_empirical_calibration", False
    ):
        return (
            raw,
            DEFAULT_CALIBRATION_PROFILE,
            PROBATIVE_CALIBRATION_PROFILES[DEFAULT_CALIBRATION_PROFILE],
            ["calibration_profile:non_empirical_requires_opt_in"],
        )
    return raw, raw, profile, diagnostics


def _simulate_support(
    propositions: Iterable[Proposition],
    aspects: list[dict[str, Any]],
    goal: dict[str, Any],
    target_aspects: Iterable[str],
    confidence: float,
) -> tuple[float, float]:
    """Conservatively simulate adding one support per target aspect.

    Reuses the production ``compute_coverage``/``compute_residual_risk`` rather
    than re-deriving their algebra, so the predicted delta cannot disagree with
    the metric it predicts, and a change to either formula propagates here
    automatically. Returns ``(coverage_gain, risk_reduction)``, both clamped at
    zero from below.
    """
    targets = list(target_aspects)
    if not targets:
        return 0.0, 0.0
    corroboration = goal.get("corroboration", CORROBORATION)
    current = list(propositions)
    before_coverage = compute_coverage(current, aspects, corroboration)
    before_risk = compute_residual_risk(current, aspects, goal)
    simulated = current + [
        Proposition(
            aspect=name,
            polarity=1.0,
            claim=f"{name} simulated",
            evidence_id="__simulated__",
            confidence=confidence,
            method="symbolic",
            scope=name,
            relation="supports",
            claim_id=f"__simulated__:{name}",
        )
        for name in targets
    ]
    after_coverage = compute_coverage(simulated, aspects, corroboration)
    after_risk = compute_residual_risk(simulated, aspects, goal)
    return (
        max(0.0, after_coverage - before_coverage),
        max(0.0, before_risk - after_risk),
    )


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def declared_relations_for(
    artifact: dict[str, Any], required: set[str]
) -> tuple[dict[str, set[str]], list[str]]:
    """Aspect sets per relation, derived from the single shared parser."""
    entries, diagnostics = parse_declared_relations(artifact, required)
    declared: dict[str, set[str]] = {}
    for item in entries:
        declared.setdefault(item["relation"], set()).add(item["aspect"])
    return declared, diagnostics


def action_capability(
    artifact: dict[str, Any],
    verification_method: str,
    aspect_names: list[str],
    declared: dict[str, set[str]] | None = None,
) -> str:
    """Classify what extracting this artifact CAN produce for THIS goal.

    Mirrors ``relate_artifact_to_aspects``/``derive_propositions`` exactly:

    - ``probatory_dynamic``: the artifact carries a dynamic verification method,
      the only path that promotes an inferred relation to ``supports``;
    - ``probatory_static``: it declares valid ``supports``/``refutes`` on an
      aspect the goal actually requires;
    - ``structural_relation``: it declares ``tests``/``implements``/
      ``configures`` on a required aspect - typed, but never proof;
    - ``retrieval_only``: everything else, including declarations aimed at
      aspects outside the goal and declarations that fail validation, which
      ``_declared_relations`` discards before falling back to ``mentions``.

    Capability is a property of the artifact *and the goal*, never of the L0-L5
    level or the nominal confidence of the method.

    ``probatory_dynamic`` describes the *method that produced the artifact*; it
    does not assert that the run was authorized and confers no authority to run
    anything. Authorization for dynamic execution is enforced upstream, at the
    extraction boundary (``analyze_path(run_dynamic=...)``), never inferred from
    a capability label here.
    """
    if verification_method == "dynamic":
        return CAPABILITY_PROBATORY_DYNAMIC
    required = set(aspect_names)
    if declared is None:
        declared, _ = declared_relations_for(artifact, required)
    if any(declared.get(rel) for rel in _PROBATORY_RELATIONS):
        return CAPABILITY_PROBATORY_STATIC
    if any(declared.get(rel) for rel in _STRUCTURAL_RELATIONS):
        return CAPABILITY_STRUCTURAL
    return CAPABILITY_RETRIEVAL_ONLY


def _expectations(
    artifact: dict[str, Any],
    capability: str,
    aspect_names: list[str],
    declared: dict[str, set[str]],
    propositions: Iterable[Proposition],
    aspects: list[dict[str, Any]],
    goal: dict[str, Any],
    calibration: dict[str, Any],
    confidence: float,
    scale: float,
) -> tuple[dict[str, float], list[str]]:
    """Separate the goods an action can deliver, given the CURRENT state.

    ``retrieval_gain`` is the only good available to every action and the only
    one scaled by ``relevance``: reading a relevant artifact is informative
    regardless of whether it can prove anything. The probative expectations come
    from a versioned calibration profile, never from relevance, and default to
    zero because no empirical calibration exists yet.

    They are *deltas* against the current state, not capabilities. The magnitude
    is obtained by simulating the addition with the real coverage and risk
    formulas, so a partially-covered aspect still has headroom: coverage is
    gradual via ``aspect_score``, and treating "has some support" as "saturated"
    would zero out a genuinely useful second, independent source.

    An artifact that also declares a refutation gets no expected risk reduction,
    since by the risk invariant a refutation can only hold risk steady or raise
    it - promising a reduction there was provably wrong.
    """
    diagnostics: list[str] = []
    relevance = _finite(artifact.get("relevance", 0.1))
    if relevance is None or not 0.0 <= relevance <= 1.0:
        diagnostics.append("relevance:not_a_unit_interval_value")
        relevance = 0.0
    retrieval_gain = relevance * scale
    zero = {
        "retrieval_gain": retrieval_gain,
        "coverage": 0.0,
        "contradiction": 0.0,
        "risk_reduction": 0.0,
    }
    if capability not in (CAPABILITY_PROBATORY_STATIC, CAPABILITY_PROBATORY_DYNAMIC):
        return zero, diagnostics
    if capability == CAPABILITY_PROBATORY_DYNAMIC:
        supports = set(aspect_names)
        refutes: set[str] = set()
    else:
        supports = declared.get("supports", set())
        refutes = declared.get("refutes", set())
    p_support = float(calibration["support_success_probability"])
    p_refute = float(calibration["refutation_discovery_probability"])
    if p_support > 0.0:
        coverage_gain, risk_reduction = _simulate_support(
            propositions, aspects, goal, supports, confidence
        )
    else:
        # The simulation is exact but costs a full coverage+risk recomputation per
        # candidate. Under a zero-probability profile the product is zero anyway,
        # so skipping it changes no result and keeps the default path cheap.
        coverage_gain = risk_reduction = 0.0
    return {
        "retrieval_gain": retrieval_gain,
        "coverage": p_support * coverage_gain,
        "contradiction": p_refute if refutes else 0.0,
        "risk_reduction": 0.0 if refutes else p_support * risk_reduction,
    }, diagnostics


def generate_candidate_actions(
    system: dict[str, Any],
    goal: dict[str, Any],
    evidence: EvidenceStore,
    beliefs: BeliefStore,
    conflicts: ConflictStore,
    enabled_nf: list[str],
    propositions: PropositionStore | None = None,
) -> list[Action]:
    aspects = derive_goal_aspects(goal)
    aspect_names = [a["name"] for a in aspects]
    required = set(aspect_names)
    current = list(propositions or ())
    requested_profile, profile_name, calibration, calibration_diagnostics = (
        resolve_calibration(goal)
    )
    actions: list[Action] = []
    for artifact in system.get("artifacts", []):
        if evidence.has(artifact["id"]):
            continue
        verification_method = artifact.get("verification_method") or (
            "deterministic" if artifact["level"] <= 2 else "symbolic"
        )
        declared, diagnostics = declared_relations_for(artifact, required)
        capability = action_capability(
            artifact, verification_method, aspect_names, declared
        )
        expected, extra = _expectations(
            artifact, capability, aspect_names, declared, current, aspects, goal,
            calibration, _confidence_for(verification_method), 0.2,
        )
        actions.append(
            Action(
                name=f"extract_L{artifact['level']}",
                target_id=artifact["id"],
                level=artifact["level"],
                estimated_cost=_size_cost(artifact),
                verification_method=verification_method,
                prerequisites=tuple(artifact.get("prerequisites", [])),
                capability=capability,
                expected_retrieval_gain=expected["retrieval_gain"],
                expected_delta_coverage=expected["coverage"],
                expected_contradiction_discovery=expected["contradiction"],
                expected_delta_risk_reduction=expected["risk_reduction"],
                expected_delta_confidence=_confidence_for(verification_method) * 0.2,
                calibration_profile=profile_name,
                requested_calibration_profile=requested_profile,
                expectation_uncertainty=str(calibration["uncertainty"]),
                declaration_diagnostics=tuple(
                    sorted(set(diagnostics) | set(extra) | set(calibration_diagnostics))
                ),
            )
        )
    for nf in enabled_nf:
        for artifact in system.get("artifacts", []):
            if nf not in artifact.get("nf", []):
                continue
            nf_id = f"{artifact['id']}#nf:{nf}"
            if evidence.has(nf_id):
                continue
            nf_declared, nf_diagnostics = declared_relations_for(artifact, required)
            nf_capability = action_capability(
                artifact, "symbolic", aspect_names, nf_declared
            )
            nf_expected, nf_extra = _expectations(
                artifact, nf_capability, aspect_names, nf_declared, current, aspects,
                goal, calibration, _confidence_for("symbolic"), 0.15,
            )
            actions.append(
                Action(
                    name=f"extract_nf:{nf}",
                    target_id=nf_id,
                    level=artifact["level"],
                    estimated_cost=_size_cost(artifact),
                    verification_method="symbolic",
                    prerequisites=tuple(artifact.get("prerequisites", [])),
                    capability=nf_capability,
                    expected_retrieval_gain=nf_expected["retrieval_gain"],
                    expected_delta_coverage=nf_expected["coverage"],
                    expected_contradiction_discovery=nf_expected["contradiction"],
                    expected_delta_risk_reduction=nf_expected["risk_reduction"],
                    expected_delta_confidence=_confidence_for("symbolic") * 0.15,
                    calibration_profile=profile_name,
                    requested_calibration_profile=requested_profile,
                    expectation_uncertainty=str(calibration["uncertainty"]),
                    declaration_diagnostics=tuple(
                        sorted(
                            set(nf_diagnostics) | set(nf_extra) | set(calibration_diagnostics)
                        )
                    ),
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
    """Utility over the four separated goods (plan §5.3).

    ``expected_delta_confidence`` is deliberately absent: it describes the
    nominal confidence of the verification method and is retained on ``Action``
    for consumers, but folding it in here once made it a stand-in for
    relevance, which quietly restored the coverage-shaped incentive this
    separation exists to remove. Relevance now enters through
    ``expected_retrieval_gain``, under its own name.
    """
    alpha = goal.get("alpha", 0.4)
    beta = goal.get("beta", 0.3)
    gamma = goal.get("gamma", 0.3)
    epsilon = goal.get("epsilon", 0.2)
    value = (
        alpha * action.expected_delta_coverage
        + beta * action.expected_retrieval_gain
        + epsilon * action.expected_contradiction_discovery
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
        artifact.get("run") if (artifact := _find_artifact(system, evidence.id)) else None
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
    """Contradicciones verificables entre claims equivalentes y relaciones opuestas."""
    _ = similarity, threshold
    grouped: dict[tuple[str, str], list[Proposition]] = {}
    for prop in propositions:
        if not prop.claim_id or prop.relation not in {"supports", "refutes"}:
            continue
        grouped.setdefault((prop.claim_id, prop.scope), []).append(prop)
    conflicts: list[Conflict] = []
    for (claim_id, scope), props in grouped.items():
        supporting = [prop for prop in props if prop.relation == "supports"]
        refuting = [prop for prop in props if prop.relation == "refutes"]
        if supporting and refuting:
            claim_text = supporting[0].claim_text or supporting[0].claim
            conflicts.append(
                Conflict(
                    claim=claim_text,
                    evidence_for=tuple(prop.evidence_id for prop in supporting),
                    evidence_against=tuple(prop.evidence_id for prop in refuting),
                    scope=scope,
                    severity=0.9,
                    resolution_status="open",
                    kind="contradiction",
                    claim_id=claim_id,
                )
            )
    return conflicts


def propagate_confidence(
    items: Iterable[Any],
    resolver: Callable[[str], float | None],
) -> None:
    """Propagación de confianza conservativa (MODEL.md §10).

    Impone ``Conf(b) <= min_{d in Dep(b)} Conf(d)``: una conclusión no puede
    superar la confianza de su dependencia más débil. Las dependencias se
    resuelven por id vía ``resolver`` (devuelve la confianza actual del
    dependency, o None para omitirlo). La iteración por punto fijo cubre cadenas
    transitivas (una inferencia que descansa en otra inferencia). ``items`` debe
    ser mutable en ``confidence`` (Belief, Proposition).
    """
    materialized = list(items)
    if not materialized:
        return
    for _ in range(len(materialized)):
        changed = False
        for item in materialized:
            deps = getattr(item, "dependencies", ())
            if not deps:
                continue
            bound: float | None = None
            for dep in deps:
                value = resolver(dep)
                if value is None:
                    continue
                bound = value if bound is None else min(bound, value)
            if bound is None:
                continue
            clamped = min(float(item.confidence), float(bound))
            if clamped != float(item.confidence):
                item.confidence = clamped
                changed = True
        if not changed:
            break


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


_PROBATORY_REASON_CODES = frozenset(
    {"threshold_not_met", "insufficient_sources", "missing_production_evidence"}
)

_NEXT_ACTION_SPECS: dict[str, dict[str, Any]] = {
    "increase_artifact_cap": {
        "resolves": frozenset({"artifact_cap_reached"}),
        "capability_required": CAPABILITY_RETRIEVAL_ONLY,
        "sufficiency_provable": True,
        "expected_effect": (
            "widen the observed corpus; surfaces more candidate evidence but "
            "creates no probative mass by itself"
        ),
    },
    "increase_read_limit": {
        "resolves": frozenset({"content_truncated"}),
        "capability_required": CAPABILITY_RETRIEVAL_ONLY,
        "sufficiency_provable": True,
        "expected_effect": (
            "read truncated artifacts in full; diagnostic only, it cannot turn "
            "retrieval into supports or refutes"
        ),
    },
    "increase_budget": {
        "resolves": frozenset({"budget_exhausted", "no_affordable_actions"}),
        "capability_required": CAPABILITY_RETRIEVAL_ONLY,
        "sufficiency_provable": True,
        "expected_effect": (
            "allow more actions within the currently enabled capability set"
        ),
    },
    "enable_probative_verifier": {
        "resolves": _PROBATORY_REASON_CODES,
        "capability_required": CAPABILITY_PROBATORY_STATIC,
        "sufficiency_provable": False,
        "expected_effect": (
            "register a deterministic verifier able to emit supports or refutes "
            "for the named targets; proposal only, nothing is executed"
        ),
    },
}
"""``sufficiency_provable`` marks whether clearing the reason code *can* be a
checkable postcondition - it is a precondition for sufficiency, never proof of it.

Sufficiency additionally requires a concrete computed target: an action that
says "raise the limit" without saying *to what* has no verifiable
postcondition, so it cannot be declared sufficient. ``increase_read_limit`` and
``increase_artifact_cap`` can compute their target from the inventory
(``bytes_discovered``, ``files_discovered``); ``increase_budget`` cannot, and
``enable_probative_verifier`` never can - registering a verifier does not
guarantee it finds support, still less from enough independent sources to
satisfy ``min_sources``. Sufficiency that cannot be demonstrated is false.
"""


def _sufficiency_target(
    action_name: str, inventory: dict[str, Any]
) -> dict[str, Any] | None:
    """Concrete target value whose application provably clears the reason code."""
    if action_name == "increase_read_limit":
        discovered = int(inventory.get("bytes_discovered", 0) or 0)
        if discovered <= 0:
            return None
        return {"parameter": "read_limit_bytes", "target_value": discovered}
    if action_name == "increase_artifact_cap":
        discovered = int(inventory.get("files_discovered", 0) or 0)
        if discovered <= 0:
            return None
        return {"parameter": "artifact_cap", "target_value": discovered}
    return None


def _verifier_targets(
    propositions: PropositionStore,
    aspects: list[dict[str, Any]],
    goal: dict[str, Any],
    system: dict[str, Any],
    aspect_scores: dict[str, float],
) -> dict[str, Any]:
    """Distinguish *why* each aspect is short of probative evidence.

    'No support at all', 'supported but under-corroborated', 'supported only by
    non-production artifacts' and 'contradicted' need different verifiers, so
    collapsing them into ``aspect_score <= 0`` both mislabels the reason and
    hands back an empty target list precisely when support exists but
    ``min_sources`` is unmet.
    """
    names = [a["name"] for a in aspects]
    min_sources = int(goal.get("min_sources_per_aspect", 2))
    by_aspect: dict[str, set[str]] = {}
    production: dict[str, set[str]] = {}
    for prop in propositions:
        if prop.relation == "supports" and prop.polarity > 0:
            by_aspect.setdefault(prop.aspect, set()).add(prop.evidence_id)
            if prop.impact > 0.0:
                production.setdefault(prop.aspect, set()).add(prop.evidence_id)
    unsupported = [n for n in names if not by_aspect.get(n)]
    under_corroborated = [
        n for n in names if by_aspect.get(n) and len(by_aspect[n]) < min_sources
    ]
    missing_production = (
        [n for n in names if by_aspect.get(n) and not production.get(n)]
        if goal.get("require_production_evidence", True) and system_has_production(system)
        else []
    )
    contradicted = sorted(
        {prop.claim_id or prop.claim for prop in propositions if prop.relation == "refutes"}
    )
    if unsupported and not any(by_aspect.get(n) for n in names):
        reason = "no_probative_evidence_available"
    elif under_corroborated:
        reason = "insufficient_corroboration"
    elif missing_production:
        reason = "missing_production_evidence"
    elif contradicted:
        reason = "contradicted_claims"
    else:
        reason = "insufficient_probative_evidence"
    targets = sorted(set(unsupported) | set(under_corroborated) | set(missing_production))
    return {
        "reason": reason,
        "aspects": targets or sorted(aspect_scores),
        "aspects_without_support": unsupported,
        "aspects_under_corroborated": under_corroborated,
        "aspects_without_production_evidence": missing_production,
        "contradicted_claims": contradicted,
        "min_sources_per_aspect": min_sources,
    }
"""What each proposed next_action can and cannot resolve.

Only ``enable_probative_verifier`` touches the probative reason codes, because
no amount of extra budget, reads or artifact-cap headroom manufactures
evidence. Proposing it is not running it: the report never enables a verifier
or executes a dynamic action on its own, and ``authorization_required`` stays
true for every entry.
"""


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
    cost: dict[str, Any] | None = None,
    termination_reason: str = "unknown",
    declaration_diagnostics: list[dict[str, Any]] | None = None,
    verification_admission: dict[str, Any] | None = None,
    dependency_verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_aspect: dict[str, list[Proposition]] = {}
    for prop in propositions:
        by_aspect.setdefault(prop.aspect, []).append(prop)
    corroboration = goal.get("corroboration", CORROBORATION)
    aspect_scores = {
        a["name"]: round(aspect_score(by_aspect.get(a["name"], []), corroboration), 4)
        for a in aspects
    }
    thresholds_met = (
        coverage >= goal.get("theta_coverage", budget.theta_coverage)
        and residual_risk <= goal.get("rho_risk", budget.rho_risk)
    )
    no_negative = not any(p.relation == "refutes" for p in propositions)
    no_critical_conflicts = not conflicts.critical()
    sources_met = min_sources_met(
        propositions,
        aspects,
        int(goal.get("min_sources_per_aspect", 2)),
        str(goal.get("target_revision", "") or ""),
    )
    production_met = (
        not (goal.get("require_production_evidence", True) and system_has_production(system))
        or production_sources_met(propositions, aspects)
    )
    inventory = system.get("inventory") or {}
    degradations = list(inventory.get("degradations", []))
    accepted_degradations = set(goal.get("accepted_degradations", []))
    blocking_degradations = [
        degradation
        for degradation in degradations
        if degradation in {"artifact_cap_reached", "content_truncated"}
        and degradation not in accepted_degradations
    ]
    complete = (
        thresholds_met
        and no_negative
        and no_critical_conflicts
        and sources_met
        and production_met
        and not blocking_degradations
    )
    reason_codes: list[str] = []
    if not thresholds_met:
        reason_codes.append("threshold_not_met")
    if not no_negative:
        reason_codes.append("negative_proposition")
    if not no_critical_conflicts:
        reason_codes.append("blocking_conflict")
    if not sources_met:
        reason_codes.append("insufficient_sources")
    if not production_met:
        reason_codes.append("missing_production_evidence")
    reason_codes.extend(blocking_degradations)
    if termination_reason not in {"thresholds_met", "unknown"}:
        reason_codes.append(termination_reason)
    reason_codes = list(dict.fromkeys(reason_codes))
    next_actions: list[dict[str, Any]] = []
    if "artifact_cap_reached" in reason_codes:
        excluded = inventory.get("exclusions", [])
        next_actions.append(
            {
                "action": "increase_artifact_cap",
                "reason": "artifact_cap_reached",
                "estimated_tokens": sum(int(item.get("estimated_bytes", 0)) for item in excluded)
                // 4,
                "authorization_required": True,
            }
        )
    if "content_truncated" in reason_codes:
        next_actions.append(
            {
                "action": "increase_read_limit",
                "reason": "content_truncated",
                "authorization_required": True,
            }
        )
    if termination_reason in {"budget_exhausted", "no_affordable_actions"}:
        next_actions.append(
            {
                "action": "increase_budget",
                "reason": termination_reason,
                "authorization_required": True,
            }
        )
    if _PROBATORY_REASON_CODES & set(reason_codes):
        targets = _verifier_targets(propositions, aspects, goal, system, aspect_scores)
        next_actions.append(
            {
                "action": "enable_probative_verifier",
                "authorization_required": True,
                **targets,
            }
        )
    for entry in next_actions:
        spec = _NEXT_ACTION_SPECS.get(entry["action"], {})
        resolves = sorted(spec.get("resolves", frozenset()) & set(reason_codes))
        remaining = sorted(set(reason_codes) - set(resolves))
        entry["addresses_reason_codes"] = resolves
        entry["remaining_blockers"] = remaining
        entry["expected_effect"] = spec.get("expected_effect", "unspecified")
        entry["capability_required"] = spec.get(
            "capability_required", CAPABILITY_RETRIEVAL_ONLY
        )
        target = _sufficiency_target(entry["action"], inventory)
        if target is not None:
            entry.update(target)
        entry["sufficient_if_successful"] = bool(
            not remaining and spec.get("sufficiency_provable", False) and target is not None
        )
        entry.setdefault("authorization_required", True)
    return {
        "system": system.get("name"),
        "goal": goal.get("name"),
        "evidence_count": len(evidence),
        "belief_count": len(beliefs),
        "verification_admission": verification_admission or {
            "verification_candidates_offered": 0,
            "verification_results_valid": 0,
            "verification_propositions_admitted": 0,
            "verification_candidates_rejected": 0,
            "verification_rejection_reasons": [],
        },
        "proposition_count": len(propositions),
        "conflict_count": len(conflicts),
        "compressed_count": sum(1 for e in evidence if e.compressed),
        "evidence_kinds": sorted({e.kind for e in evidence}),
        "conflicts": [
            {
                "claim": c.claim,
                "claim_id": c.claim_id,
                "kind": c.kind,
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
        "declaration_diagnostics": list(declaration_diagnostics or []),
        "source_independence": {
            "profile": INDEPENDENCE_PROFILE,
            "required_sources": int(goal.get("min_sources_per_aspect", 2)),
            "evaluated_target_revision": str(goal.get("target_revision", "") or ""),
            "claims": [
                {
                    "aspect": aspect,
                    "normalized_claim_id": claim_key,
                    **independence_report(
                        sources,
                        int(goal.get("min_sources_per_aspect", 2)),
                        str(goal.get("target_revision", "") or ""),
                        claim_key,
                    ),
                }
                for (aspect, claim_key), sources in sorted(
                    claim_independence_sources(propositions).items()
                )
            ],
        },
        "budget_remaining": {
            "tokens": budget.tokens_remaining,
            "tool": budget.tool_remaining,
        },
        "cost": cost or {"estimated_tokens": 0, "observed_tokens": 0},
        "dependency_verification": dependency_verification or {"enabled": False},
        "inventory": inventory,
        "completion": {
            "procedure_complete": complete,
            "thresholds_met": thresholds_met,
            "degradations": degradations,
            "blocking_degradations": blocking_degradations,
            "reason_codes": reason_codes,
            "termination_reason": termination_reason,
            "next_actions": next_actions,
        },
        "levels_covered": sorted(evidence.levels()),
        "claims": [_claim_record(proposition) for proposition in propositions],
        "conclusions": [
            {
                "claim": p.claim,
                "claim_id": p.claim_id,
                "claim_text": p.claim_text,
                "aspect": p.aspect,
                "relation": p.relation,
                "authority_class": p.authority_class,
                "extraction_profile": p.extraction_profile,
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
        "complete": complete,
    }


_REJECTION_INVALID_RESULT = "invalid_result"
_REJECTION_ASPECT_OUTSIDE_GOAL = "aspect_outside_goal"
_REJECTION_REVISION_MISMATCH = "revision_mismatch"
_REJECTION_NON_PROBATIVE = "non_probative"


def _admit_verification_results(
    propositions: PropositionStore,
    verification_results: Iterable[Any],
    allowed_aspects: frozenset[str],
    required_target_revision: str,
) -> dict[str, Any]:
    """THE only admission path for externally-produced verification evidence.

    Order (P1-1): (1) ``validate_verification_result`` - a hand-built
    ``Proposition``, a tampered ``VerificationResult`` (``result_id`` no longer
    matches its own fields) or an object of any other type is rejected here,
    before anything else, because fabricating authority by constructing a
    ``Proposition`` directly and feeding it to this function is not possible -
    this function never accepts a ``Proposition`` as input; (2) the result's
    ``aspect`` must belong to THIS goal's real required aspects - a genuine,
    valid result produced for a DIFFERENT goal must never contaminate this
    one's coverage/risk/conflicts/completion; (3) the result's
    ``target_revision`` must match exactly what THIS analysis declared - a
    genuine, valid, in-scope result from a stale revision must never count
    either; (4) only then ``proposition_from_verification``, the sole
    conversion, which additionally refuses anything non-probative.

    Returns structured, sanitized counters - never raw rejected objects (which
    could be anything, including a hostile ``__repr__``). A non-iterable
    ``verification_results`` (e.g. an int) yields nothing: the caller error is
    invisible in the counters rather than crashing the whole analysis.
    """
    offered = 0
    valid = 0
    admitted = 0
    rejected = 0
    reasons: set[str] = set()
    try:
        iterator = iter(verification_results)
    except TypeError:
        iterator = iter(())
    for candidate in iterator:
        offered += 1
        if validate_verification_result(candidate):
            rejected += 1
            reasons.add(_REJECTION_INVALID_RESULT)
            continue
        valid += 1
        if candidate.aspect not in allowed_aspects:
            rejected += 1
            reasons.add(_REJECTION_ASPECT_OUTSIDE_GOAL)
            continue
        if candidate.target_revision != required_target_revision:
            rejected += 1
            reasons.add(_REJECTION_REVISION_MISMATCH)
            continue
        prop = proposition_from_verification(candidate, "")
        if prop is None:
            rejected += 1
            reasons.add(_REJECTION_NON_PROBATIVE)
            continue
        propositions.add(prop)
        admitted += 1
    return {
        "verification_candidates_offered": offered,
        "verification_results_valid": valid,
        "verification_propositions_admitted": admitted,
        "verification_candidates_rejected": rejected,
        "verification_rejection_reasons": sorted(reasons),
    }


def _admit_dependency_verification(
    outcome: Any, goal: dict[str, Any]
) -> tuple[dict[str, Any] | None, tuple[Any, ...], int, int]:
    """Derive the public report section and cost from a TYPED outcome only
    (P1-6) - never from a caller-supplied dict.

    A caller cannot hand ``analyze_system`` an arbitrary "summary" dict and
    have it trusted as if it were real: the only accepted shape is
    ``dependency_verifiers.DependencyVerificationOutcome`` (or ``None``), and
    the public section AND its cost are both derived from that ONE object,
    inside this boundary, using the same fields the caller cannot fabricate
    independently of each other (results/diagnostics/cost all come from one
    place, so they cannot go incongruent). An object of the wrong type is
    never trusted: it is ignored, with a diagnostic recorded, rather than
    raising or being read defensively field-by-field.

    Returns ``(dependency_verification, results, dependency_tokens, dependency_tool)``.
    """
    if outcome is None:
        return None, (), 0, 0
    from .dependency_verifiers import (
        DependencyVerificationOutcome,
        dependency_verification_report,
    )

    if not isinstance(outcome, DependencyVerificationOutcome):
        return (
            {"enabled": False, "diagnostics": ["invalid_dependency_verification_outcome"]},
            (),
            0,
            0,
        )
    tokens = outcome.charged_tokens
    tool = outcome.charged_tool
    cost_diagnostics: list[str] = []
    if isinstance(tokens, bool) or not isinstance(tokens, int) or tokens < 0:
        cost_diagnostics.append("invalid_dependency_verification_cost")
        tokens = 0
    if isinstance(tool, bool) or not isinstance(tool, int) or tool < 0:
        cost_diagnostics.append("invalid_dependency_verification_cost")
        tool = 0
    report = dependency_verification_report(
        outcome, str(goal.get("target_revision", "") or "")
    )
    if cost_diagnostics:
        report = dict(report)
        report["cost"] = {"tokens": tokens, "tool": tool}
        report["diagnostics"] = sorted({*report.get("diagnostics", []), *cost_diagnostics})
    return report, outcome.results, tokens, tool


def analyze_system(
    system: dict[str, Any],
    goal: dict[str, Any],
    budget: Budget,
    policy: dict[str, Any] | None = None,
    verification_results: Iterable[Any] = (),
    dependency_verification_outcome: Any = None,
) -> dict[str, Any]:
    """``verification_results`` are externally-produced ``VerificationResult``
    objects admitted before the budgeted loop starts, subject to the SAME
    aspect-membership and target-revision scoping this goal's own extraction
    loop is subject to (see ``_admit_verification_results``) - a genuine
    result produced for a different goal or a stale revision cannot affect
    this analysis. They are converted to ``Proposition`` exclusively through
    ``proposition_from_verification``; this function never accepts a
    ``Proposition`` directly through this parameter, so a caller cannot
    manufacture authority by constructing one by hand and passing it in as if
    it had been verified.

    ``dependency_verification_outcome``, when supplied, MUST be a
    ``dependency_verifiers.DependencyVerificationOutcome`` (never a plain
    dict) - the public report section and its cost are both derived from that
    ONE typed object inside this function (see
    ``_admit_dependency_verification``), so a caller cannot supply a "results"
    list and a separately-fabricated, incongruent public summary. This
    parameter is deliberately SEPARATE from ``verification_results``: passing
    the outcome's own ``.results`` through ``verification_results`` is still
    required for its findings to become propositions - this parameter alone
    only contributes the sanitized report section and cost, and cannot by
    itself fabricate a proposition, coverage or completion.

    Conflicts from the initially-admitted evidence are computed BEFORE the
    loop's first threshold/capacity check (P2-1): a genuine SUPPORTS and a
    genuine REFUTES on the same normalized claim, admitted up front, must be
    visible as a conflict even when budget is 0/0 and the loop body never runs.
    In the loop, thresholds are checked BEFORE budget capacity (P1-3): if the
    externally-admitted evidence already satisfies the goal, the fact that
    ``verify_dependency_targets`` spent the LAST unit of budget doing so must
    never be reported as ``budget_exhausted`` overriding an already-met
    ``thresholds_met`` - ``complete=True`` always implies
    ``termination_reason == "thresholds_met"``, never a blocking reason code.
    """
    evidence = EvidenceStore()
    beliefs = BeliefStore()
    propositions = PropositionStore()
    required_aspects = derive_goal_aspects(goal)
    aspect_names = [a["name"] for a in required_aspects]
    evaluated_revision = str(goal.get("target_revision", "") or "")
    verification_admission = _admit_verification_results(
        propositions, verification_results, frozenset(aspect_names), evaluated_revision
    )
    dependency_verification, _dep_results, dependency_tokens, dependency_tool = (
        _admit_dependency_verification(dependency_verification_outcome, goal)
    )
    conflicts = ConflictStore()
    conflicts.merge(
        detect_proposition_conflicts(
            propositions,
            similarity=goal.get("conflict_similarity") or _jaccard,
            threshold=goal.get("conflict_threshold", 0.5),
        )
    )
    enabled_nf = select_non_functional_extractors(goal)
    linker = goal.get("aspect_linker") or _default_linker
    min_sources = int(goal.get("min_sources_per_aspect", 2))
    require_production = goal.get("require_production_evidence", True) and system_has_production(system)
    coverage = 0.0
    residual_risk = 1.0
    cost_estimated = dependency_tokens
    cost_observed = dependency_tokens
    termination_reason = "unknown"
    ev_conf: dict[str, float] = {}
    declaration_diagnostics: list[dict[str, Any]] = []
    while True:
        coverage = compute_coverage(propositions, required_aspects, goal.get("corroboration", CORROBORATION))
        residual_risk = compute_residual_risk(propositions, required_aspects, goal)
        breadth_ok = min_sources_met(
            propositions, required_aspects, min_sources, evaluated_revision
        )
        prod_ok = (not require_production) or production_sources_met(propositions, required_aspects)
        if should_stop(coverage, residual_risk, conflicts, goal, budget, breadth_ok, prod_ok):
            termination_reason = "thresholds_met"
            break
        if not budget.has_capacity():
            termination_reason = "budget_exhausted"
            break
        actions = generate_candidate_actions(
            system, goal, evidence, beliefs, conflicts, enabled_nf, propositions
        )
        eligible = [
            action
            for action in actions
            if prerequisites_satisfied(action, evidence, beliefs) and budget.can_afford(action.estimated_cost)
        ]
        if not eligible:
            prerequisites_met = [
                action
                for action in actions
                if prerequisites_satisfied(action, evidence, beliefs)
            ]
            termination_reason = (
                "no_affordable_actions" if prerequisites_met else "no_eligible_actions"
            )
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
        ev_conf[new_evidence.id] = verification.confidence
        beliefs.update(new_evidence, verification, goal["name"])
        artifact = _resolve_artifact(system, new_evidence.id)
        if artifact is not None:
            _, artifact_diagnostics = parse_declared_relations(artifact, aspect_names)
            if artifact_diagnostics:
                declaration_diagnostics.append(
                    {
                        "evidence_id": new_evidence.id,
                        "location": new_evidence.location,
                        "diagnostics": artifact_diagnostics,
                    }
                )
        for prop in derive_propositions(
            new_evidence, verification, artifact, aspect_names, goal["name"], goal, linker
        ):
            propositions.add(prop)
        propagate_confidence(propositions, lambda d: ev_conf.get(d))
        propagate_confidence(beliefs, lambda d: ev_conf.get(d))
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
    phases: dict[str, Any] = {
        "discovery": {
            "files": int((system.get("inventory") or {}).get("files_discovered", 0)),
            "bytes": int((system.get("inventory") or {}).get("bytes_discovered", 0)),
        },
        "extraction": {
            "files": int((system.get("inventory") or {}).get("files_selected", 0)),
            "bytes": int((system.get("inventory") or {}).get("bytes_read", 0)),
        },
        "analysis": {
            "estimated_tokens": cost_estimated - dependency_tokens,
            "observed_tokens": cost_observed - dependency_tokens,
        },
    }
    if dependency_verification is not None:
        phases["dependency_verification"] = {
            "tokens": dependency_tokens,
            "tools": dependency_tool,
            "manifests_inspected": list(dependency_verification.get("manifests_inspected", [])),
            "executions": dependency_verification.get("verification_result_count", 0),
        }
    return synthesize_report(
        system, goal, evidence, beliefs, propositions, conflicts, required_aspects,
        coverage,
        residual_risk,
        budget,
        {
            "estimated_tokens": cost_estimated,
            "observed_tokens": cost_observed,
            "phases": phases,
        },
        termination_reason,
        declaration_diagnostics,
        verification_admission,
        dependency_verification,
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
