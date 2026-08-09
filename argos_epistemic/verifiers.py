"""Static verification protocol and source-independence semantics (plan §5.4).

This module is the boundary between *thematic candidate* and *proof*. A semantic
linker proposes; a verifier decides, and only for narrow, falsifiable claims it
can actually check. Nothing here executes third-party code, discovers plugins,
touches the network, or admits LLM adjudication as support.

Four structural guarantees:

**Provenance is stamped, not declared.** A verifier returns only what it claims
(``VerifierClaim``). Family, version, method, execution, target revision and
root fingerprints are attached by ``run_verifier`` from an input built by the
trusted factory ``verification_input``.

**Independence is a graph property, not a hash.** It is computed as connected
components over shared roots, executions, instrument families and derivation
edges - so partially overlapping root sets (``{x,y}`` vs ``{y,z}``) collapse,
which a per-source hash cannot express. Components are counted, never outputs.

**The instrument, not its version, is the witness.** ``pep621@1`` and
``pep621@2`` are two revisions of one instrument. Independence collapses by
family; the version is retained for reproduction and audit and binds the result
identity, but never manufactures a second witness.

**Independence must be demonstrated against a declared revision.** Sources whose
target revision differs from the one under evaluation are ignored rather than
credited, and an analysis that declares no revision cannot demonstrate
corroboration at all. Doubt collapses; it never multiplies.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .canonical import content_id, sha256_fingerprint

SUPPORTS = "supports"
REFUTES = "refutes"
UNKNOWN = "unknown"
DEGRADED = "degraded"

PROBATIVE_OUTCOMES = frozenset({SUPPORTS, REFUTES})
NON_PROBATIVE_OUTCOMES = frozenset({UNKNOWN, DEGRADED})
KNOWN_OUTCOMES = PROBATIVE_OUTCOMES | NON_PROBATIVE_OUTCOMES

VERIFIER_CONTRACT = "argos/static-verifier-v1"
INDEPENDENCE_PROFILE = "argos/source-independence-v1"
CONFIDENCE_ENCODING = "binary64-hex-v1"

AUTHORIZED_INDEPENDENCE_CLASSES: frozenset[str] = frozenset()
"""Independence classes the boundary accepts for same-family corroboration.

Empty by design. An independence class relaxes the rule that two results from
one instrument family are one witness, so admitting an arbitrary string would
reopen exactly the bypass this module exists to close.
"""


class VerifierContractError(ValueError):
    """Misuse of the trusted boundary by the embedding code, not by a target."""


@dataclass(frozen=True)
class VerificationInput:
    """Everything a verifier may see. Build it with ``verification_input``."""

    artifact_id: str
    content: str
    location: str
    target_revision: str
    goal_aspects: tuple[str, ...]
    root_fingerprints: tuple[str, ...]


def root_fingerprint(content: str) -> str:
    """Content-addressed identity of an observed artifact.

    Two ids or aliases pointing at identical content resolve to one root and
    cannot be counted as two sources.
    """
    return sha256_fingerprint({"profile": "argos/root-evidence-v1", "content": str(content)})


def _is_text(value: Any) -> bool:
    """A present, non-blank string. Never coerces."""
    return isinstance(value, str) and bool(value.strip())


def _text_items(value: Any) -> tuple[str, ...]:
    """The non-blank strings in a collection; empty for anything malformed."""
    if value is None or isinstance(value, str | bytes) or not isinstance(value, tuple | list):
        return ()
    return tuple(item for item in value if _is_text(item))


def _require_text(value: Any, field_name: str) -> str:
    """Reject non-strings outright.

    ``str(None) == "None"`` and ``str(True) == "True"``: coercing before
    validating would let those sail through as a perfectly good execution id.
    """
    if not isinstance(value, str) or not value.strip():
        raise VerifierContractError(f"{field_name} must be a non-empty string")
    return value


def _text_tuple(value: Any, field_name: str) -> tuple[tuple[str, ...], str | None]:
    """Materialise a collection of non-empty strings exactly once.

    Returns ``(items, problem)``; ``problem`` is a structured code rather than
    an exception so callers can degrade. The single materialisation matters:
    validating a generator and then rebuilding it would consume it and silently
    yield an empty collection. ``str``/``bytes`` are rejected outright because
    iterating a string yields characters, so ``derived_from="parent"`` would
    become seven single-character dependencies.
    """
    if value is None or isinstance(value, str | bytes):
        return (), f"invalid_{field_name}"
    try:
        items = list(value)
    except TypeError:
        return (), f"invalid_{field_name}"
    for item in items:
        if not isinstance(item, str) or not item.strip():
            return (), f"invalid_{field_name}"
    return tuple(items), None


def _require_text_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    items, problem = _text_tuple(value, field_name)
    if problem is not None:
        raise VerifierContractError(f"{field_name} must be a collection of non-empty strings")
    return items


def verification_input(
    artifact_id: str,
    content: str,
    location: str,
    target_revision: str,
    goal_aspects: Iterable[str],
    extra_roots: Iterable[str] = (),
) -> VerificationInput:
    """Trusted factory: the primary root is computed from content, never supplied.

    Raises ``VerifierContractError`` on misuse by the embedding code, which is a
    programming error rather than untrusted input. Malformed inputs constructed
    directly (bypassing this factory) are degraded by ``run_verifier`` instead.
    """
    _require_text(artifact_id, "artifact_id")
    _require_text(location, "location")
    _require_text(target_revision, "target_revision")
    if not isinstance(content, str):
        raise VerifierContractError("content must be a string")
    aspects = _require_text_tuple(goal_aspects, "goal_aspects")
    extras = _require_text_tuple(extra_roots, "extra_roots")
    primary = root_fingerprint(content)
    return VerificationInput(
        artifact_id=artifact_id,
        content=content,
        location=location,
        target_revision=target_revision,
        goal_aspects=aspects,
        root_fingerprints=tuple(sorted({primary, *extras})),
    )


@dataclass(frozen=True)
class VerifierClaim:
    """What a verifier asserts. Deliberately carries NO provenance fields."""

    outcome: str
    aspect: str
    claim_text: str
    scope: str
    confidence: float = 0.9
    limitations: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class VerificationResult:
    """A claim plus the provenance stamped by the boundary."""

    outcome: str
    aspect: str
    claim_text: str
    scope: str
    normalized_claim_id: str
    artifact_id: str
    location: str
    verifier_family: str
    verifier_version: str
    verification_method: str
    execution_id: str
    target_revision: str
    root_fingerprints: tuple[str, ...]
    derived_from: tuple[str, ...]
    confidence: float
    limitations: tuple[str, ...]
    degradations: tuple[str, ...]
    result_id: str

    @property
    def versioned_profile(self) -> str:
        return f"{self.verifier_family}@{self.verifier_version}"

    @property
    def is_probative(self) -> bool:
        return self.outcome in PROBATIVE_OUTCOMES


class Verifier(Protocol):
    """A narrow, deterministic checker over one artifact."""

    def __call__(self, payload: VerificationInput) -> Sequence[VerifierClaim]: ...


@dataclass(frozen=True)
class VerifierRegistration:
    """A registered instrument. Validated on construction, not only on register.

    ``run_verifier`` accepts a registration directly, so validating only inside
    ``register_verifier`` left the boundary open: a hand-built registration with
    a ``None`` family and an invented method produced ``supports``.
    """

    profile: str
    version: str
    method: str
    verifier: Verifier
    description: str = ""

    def __post_init__(self) -> None:
        _require_text(self.profile, "profile")
        _require_text(self.version, "version")
        if self.method not in ("deterministic", "symbolic-rule", "dynamic"):
            raise VerifierContractError(f"unsupported verification method: {self.method}")
        if not callable(self.verifier):
            raise VerifierContractError("verifier must be callable")

    @property
    def family(self) -> str:
        return self.profile

    @property
    def versioned_profile(self) -> str:
        return f"{self.profile}@{self.version}"


_REGISTRY: dict[str, VerifierRegistration] = {}


def register_verifier(
    profile: str,
    version: str,
    method: str,
    verifier: Verifier,
    description: str = "",
) -> None:
    """Register a verifier under a versioned profile. Explicit and deterministic."""
    _require_text(profile, "profile")
    _require_text(version, "version")
    if method not in ("deterministic", "symbolic-rule", "dynamic"):
        raise VerifierContractError(f"unsupported verification method: {method}")
    if not callable(verifier):
        raise VerifierContractError("verifier must be callable")
    key = f"{profile}@{version}"
    if key in _REGISTRY:
        raise VerifierContractError(f"verifier already registered: {key}")
    _REGISTRY[key] = VerifierRegistration(profile, version, method, verifier, description)


def unregister_verifier(profile: str, version: str) -> None:
    _REGISTRY.pop(f"{profile}@{version}", None)


def registered_verifiers() -> tuple[VerifierRegistration, ...]:
    """Registered verifiers in a deterministic order."""
    return tuple(_REGISTRY[key] for key in sorted(_REGISTRY))


def normalize_scope(scope: str) -> str:
    return " ".join(str(scope).split()).strip().lower()


def normalize_claim_text(claim_text: str) -> str:
    return " ".join(str(claim_text).split()).strip().lower()


def normalized_claim_id(aspect: str, claim_text: str, scope: str) -> str:
    """Stable identity for a claim under a declared normalisation profile.

    The normalisation is deliberately shallow: case folding and whitespace
    collapsing, applied to aspect, claim text AND scope. It does NOT establish
    semantic equivalence, so two genuinely different wordings remain different
    claims, and two different scopes remain different claims. That is the
    conservative direction: it can split a claim that should be one, but it
    cannot merge claims that are actually distinct.
    """
    return content_id(
        "claim",
        {
            "profile": "argos/normalized-claim-v1",
            "aspect": str(aspect).strip().lower(),
            "claim": normalize_claim_text(claim_text),
            "scope": normalize_scope(scope),
        },
    )


def _finite_unit(value: Any) -> float | None:
    """Accept only the numeric types the contract defines, finite and in [0,1].

    No ``float(value)`` coercion: ``float("0.9")`` would admit a *string* as a
    confidence, and ``bool`` is a subclass of ``int`` so ``float(True)`` would
    read a type confusion as full confidence.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None
    return number


def encode_confidence(confidence: float) -> str:
    """Exact, round-trippable binary64 encoding for identity binding.

    A fixed-decimal rendering silently merged values that differ beyond the
    printed precision, so two results with genuinely different confidences
    shared a ``result_id``.
    """
    return float(confidence).hex()


def compute_result_id(
    *,
    artifact_id: str,
    location: str,
    verifier_family: str,
    verifier_version: str,
    verification_method: str,
    execution_id: str,
    target_revision: str,
    root_fingerprints: tuple[str, ...],
    derived_from: tuple[str, ...],
    normalized_claim_id: str,
    aspect: str,
    claim_text: str,
    scope: str,
    outcome: str,
    confidence: float,
    limitations: tuple[str, ...],
    degradations: tuple[str, ...],
) -> str:
    """THE canonical identity of a verification result.

    Binds every field affecting identity, audit or independence - including the
    **exact** audited text of ``aspect``, ``claim_text`` and ``scope``, not only
    their normalised claim id. Corroboration still keys on
    ``normalized_claim_id``, so ``"v1"`` and ``"V1"`` remain the same claim; but
    the audited record keeps exact integrity, so rewording the stored text is
    detected even when the claim identity is unchanged.

    Result identity is NOT source independence: two aliases yield distinct
    ``result_id`` values yet collapse as sources because they share a root
    fingerprint.

    The digest proves **integrity, not authenticity**: it detects a result whose
    fields no longer match its identity, but it does not establish who produced
    it. Accepting persisted or third-party results would additionally require a
    trusted attestation, which is out of scope here.
    """
    return content_id(
        "verification",
        {
            "profile": VERIFIER_CONTRACT,
            "confidence_encoding": CONFIDENCE_ENCODING,
            "artifact_id": artifact_id,
            "location": location,
            "verifier_family": verifier_family,
            "verifier_version": verifier_version,
            "verification_method": verification_method,
            "execution_id": execution_id,
            "target_revision": target_revision,
            "root_fingerprints": list(root_fingerprints),
            "derived_from": list(derived_from),
            "normalized_claim_id": normalized_claim_id,
            "aspect": aspect,
            "claim_text": claim_text,
            "scope": scope,
            "outcome": outcome,
            "confidence": encode_confidence(confidence),
            "limitations": list(limitations),
            "degradations": list(degradations),
        },
    )


def validate_verification_result(result: Any) -> tuple[str, ...]:
    """Structured reasons a result cannot be trusted. Empty means consistent.

    Recomputes the canonical identity and compares it: a result whose fields
    were altered after stamping no longer matches its own ``result_id`` and is
    refused. Without this, ``dataclasses.replace`` on a genuine result could
    manufacture a second, independent-looking witness.
    """
    if not isinstance(result, VerificationResult):
        return ("not_a_verification_result",)
    problems: list[str] = []
    text_fields = {
        "outcome": result.outcome,
        "aspect": result.aspect,
        "claim_text": result.claim_text,
        "scope": result.scope,
        "normalized_claim_id": result.normalized_claim_id,
        "artifact_id": result.artifact_id,
        "location": result.location,
        "verifier_family": result.verifier_family,
        "verifier_version": result.verifier_version,
        "verification_method": result.verification_method,
        "execution_id": result.execution_id,
        "target_revision": result.target_revision,
        "result_id": result.result_id,
    }
    for name, value in text_fields.items():
        if not isinstance(value, str):
            problems.append(f"invalid_{name}")
    for name, collection in (
        ("root_fingerprints", result.root_fingerprints),
        ("derived_from", result.derived_from),
        ("limitations", result.limitations),
        ("degradations", result.degradations),
    ):
        if not isinstance(collection, tuple) or not all(
            isinstance(item, str) for item in collection
        ):
            problems.append(f"invalid_{name}")
    confidence = _finite_unit(result.confidence)
    if confidence is None:
        problems.append("confidence_not_a_unit_interval_value")
    # Every membership test, normalisation and hash below assumes the types
    # above. Returning first is what keeps validation from raising on hostile
    # input: ``[] not in frozenset`` raises TypeError rather than diagnosing.
    if problems:
        return tuple(sorted(set(problems)))
    if result.outcome not in KNOWN_OUTCOMES:
        problems.append("unsupported_outcome")
    if result.verification_method not in ("deterministic", "symbolic-rule", "dynamic"):
        problems.append("unsupported_verification_method")
    if result.outcome in PROBATIVE_OUTCOMES and confidence == 0.0:
        problems.append("zero_confidence_no_effect")
    if problems:
        return tuple(sorted(set(problems)))
    if result.normalized_claim_id != normalized_claim_id(
        result.aspect, result.claim_text, result.scope
    ):
        problems.append("claim_id_mismatch")
    expected = compute_result_id(
        artifact_id=result.artifact_id,
        location=result.location,
        verifier_family=result.verifier_family,
        verifier_version=result.verifier_version,
        verification_method=result.verification_method,
        execution_id=result.execution_id,
        target_revision=result.target_revision,
        root_fingerprints=result.root_fingerprints,
        derived_from=result.derived_from,
        normalized_claim_id=result.normalized_claim_id,
        aspect=result.aspect,
        claim_text=result.claim_text,
        scope=result.scope,
        outcome=result.outcome,
        confidence=result.confidence,
        limitations=result.limitations,
        degradations=result.degradations,
    )
    if expected != result.result_id:
        problems.append("result_id_mismatch")
    return tuple(sorted(set(problems)))


def _validate_claim(claim: Any, payload: VerificationInput) -> tuple[str, ...]:
    """Structured reasons this claim cannot carry probative mass. Empty if valid."""
    if not isinstance(claim, VerifierClaim):
        return ("not_a_verifier_claim",)
    problems: list[str] = []
    if not isinstance(claim.outcome, str) or claim.outcome not in KNOWN_OUTCOMES:
        problems.append("unsupported_outcome")
    if not isinstance(claim.aspect, str) or not claim.aspect.strip():
        problems.append("empty_aspect")
    elif claim.aspect not in payload.goal_aspects:
        problems.append("aspect_outside_goal")
    if not isinstance(claim.claim_text, str) or not normalize_claim_text(claim.claim_text):
        problems.append("empty_claim_text")
    if not isinstance(claim.scope, str) or not normalize_scope(claim.scope):
        problems.append("empty_scope")
    confidence = _finite_unit(claim.confidence)
    if confidence is None:
        problems.append("confidence_not_a_unit_interval_value")
    elif confidence == 0.0 and isinstance(claim.outcome, str) and (
        claim.outcome in PROBATIVE_OUTCOMES
    ):
        # Same rule as strength==0 for declared relations: a probative claim
        # asserted with zero confidence asserts nothing, and admitting it would
        # let a verifier emit weightless supports that still count as
        # independent sources for corroboration.
        problems.append("zero_confidence_no_effect")
    if not isinstance(claim.limitations, tuple | list) or not all(
        isinstance(item, str) for item in claim.limitations
    ):
        problems.append("invalid_limitations")
    return tuple(problems)


def _validate_payload(payload: Any, execution_id: Any) -> tuple[str, ...]:
    """Strict, no coercion. Non-strings are rejected, not stringified."""
    problems: list[str] = []
    if not isinstance(execution_id, str) or not execution_id.strip():
        problems.append("missing_execution_id")
    if not isinstance(payload, VerificationInput):
        return (*problems, "invalid_payload_type")
    if not isinstance(payload.target_revision, str) or not payload.target_revision.strip():
        problems.append("missing_target_revision")
    if not isinstance(payload.artifact_id, str) or not payload.artifact_id.strip():
        problems.append("invalid_artifact_id")
    if not isinstance(payload.location, str) or not payload.location.strip():
        problems.append("invalid_location")
    if not isinstance(payload.content, str):
        problems.append("invalid_content")
    if not isinstance(payload.goal_aspects, tuple | list) or not all(
        isinstance(aspect, str) for aspect in payload.goal_aspects
    ):
        # Checked before any membership test: ``claim.aspect not in None`` would
        # raise TypeError out of run_verifier instead of degrading.
        problems.append("invalid_goal_aspects")
    if not isinstance(payload.root_fingerprints, tuple | list) or not all(
        isinstance(root, str) for root in payload.root_fingerprints
    ):
        problems.append("invalid_root_fingerprints")
    elif not payload.root_fingerprints:
        problems.append("missing_root_fingerprints")
    elif isinstance(payload.content, str) and (
        root_fingerprint(payload.content) not in payload.root_fingerprints
    ):
        problems.append("root_fingerprint_mismatch")
    return tuple(problems)


_DEGRADED_PAYLOAD = VerificationInput("", "", "", "", (), ())


def run_verifier(
    registration: VerifierRegistration,
    payload: VerificationInput,
    execution_id: str,
    derived_from: Iterable[str] = (),
) -> tuple[VerificationResult, ...]:
    """Run one verifier and stamp trusted provenance onto its claims.

    The payload is validated BEFORE the verifier is invoked: running an
    instrument against a malformed input could have side effects and its output
    could never be trusted anyway, so an invalid payload short-circuits to a
    degraded result and the callable is never called. When a returned claim
    fails validation, a fresh synthetic ``VerifierClaim`` is stamped rather
    than reusing ``claim`` itself: being a ``VerifierClaim`` instance does not
    mean its FIELDS are safe types, and reusing ``claim.aspect``/``claim_text``/
    ``scope`` (the very fields that made ``problems`` non-empty, e.g.
    ``aspect=object()``) would let a hostile value reach
    ``compute_result_id``'s canonicalization and raise out of a function that
    must never raise on untrusted verifier output.
    """
    derived_items, derived_problem = _text_tuple(derived_from, "derived_from")
    derived = tuple(sorted(set(derived_items)))
    payload_problems = _validate_payload(payload, execution_id)
    if derived_problem is not None:
        payload_problems = (*payload_problems, derived_problem)
    safe_payload = payload if isinstance(payload, VerificationInput) else _DEGRADED_PAYLOAD
    safe_execution = execution_id if isinstance(execution_id, str) else ""
    if payload_problems:
        return (
            _stamp(
                VerifierClaim(DEGRADED, "", "invalid verification input", "", 0.0),
                registration, safe_payload, safe_execution, derived,
                outcome=DEGRADED, degradations=payload_problems,
            ),
        )
    try:
        returned = registration.verifier(payload)
        claims = list(returned) if isinstance(returned, Sequence) else None
    except Exception as exc:
        return (
            _stamp(
                VerifierClaim(DEGRADED, "", f"verifier failed: {type(exc).__name__}", "", 0.0),
                registration, safe_payload, safe_execution, derived,
                outcome=DEGRADED, degradations=("verifier_raised",),
            ),
        )
    if claims is None:
        return (
            _stamp(
                VerifierClaim(DEGRADED, "", "verifier returned a non-sequence", "", 0.0),
                registration, safe_payload, safe_execution, derived,
                outcome=DEGRADED, degradations=("non_sequence_return",),
            ),
        )
    results: list[VerificationResult] = []
    for claim in claims:
        problems = _validate_claim(claim, safe_payload)
        if problems:
            safe = VerifierClaim(DEGRADED, "", "invalid verifier output", "", 0.0)
            results.append(
                _stamp(safe, registration, safe_payload, safe_execution, derived,
                       outcome=DEGRADED, degradations=problems)
            )
            continue
        results.append(_stamp(claim, registration, safe_payload, safe_execution, derived))
    return tuple(results)


def _stamp(
    claim: VerifierClaim,
    registration: VerifierRegistration,
    payload: VerificationInput,
    execution_id: str,
    derived_from: tuple[str, ...],
    outcome: str | None = None,
    degradations: tuple[str, ...] = (),
) -> VerificationResult:
    effective_outcome = outcome or claim.outcome
    probative = effective_outcome in PROBATIVE_OUTCOMES
    confidence = (_finite_unit(claim.confidence) or 0.0) if probative else 0.0
    claim_id = normalized_claim_id(claim.aspect, claim.claim_text, claim.scope)
    # Defensive: a payload that failed validation still reaches _stamp so the
    # degradation can be reported, so nothing here may assume well-formed input.
    raw_roots = payload.root_fingerprints
    roots = (
        tuple(sorted({r for r in raw_roots if isinstance(r, str)}))
        if isinstance(raw_roots, tuple | list)
        else ()
    )
    limitations = (
        tuple(str(i) for i in claim.limitations if isinstance(i, str))
        if isinstance(claim.limitations, tuple | list)
        else ()
    )
    degradations = tuple(sorted(set(degradations)))
    result_id = compute_result_id(
        artifact_id=payload.artifact_id,
        location=payload.location,
        verifier_family=registration.family,
        verifier_version=registration.version,
        verification_method=registration.method,
        execution_id=execution_id,
        target_revision=payload.target_revision,
        root_fingerprints=roots,
        derived_from=derived_from,
        normalized_claim_id=claim_id,
        aspect=claim.aspect,
        claim_text=claim.claim_text,
        scope=claim.scope,
        outcome=effective_outcome,
        confidence=confidence,
        limitations=limitations,
        degradations=degradations,
    )
    return VerificationResult(
        outcome=effective_outcome,
        aspect=claim.aspect,
        claim_text=claim.claim_text,
        scope=claim.scope,
        normalized_claim_id=claim_id,
        artifact_id=payload.artifact_id,
        location=payload.location,
        verifier_family=registration.family,
        verifier_version=registration.version,
        verification_method=registration.method,
        execution_id=execution_id,
        target_revision=payload.target_revision,
        root_fingerprints=roots,
        derived_from=derived_from,
        confidence=confidence,
        limitations=limitations,
        degradations=degradations,
        result_id=result_id,
    )


@dataclass(frozen=True)
class IndependenceSource:
    """Provenance a candidate source must expose to be grouped.

    ``verifier_family`` is the instrument; ``verifier_version`` is retained for
    audit but does NOT create a second witness. Only classes listed in
    ``AUTHORIZED_INDEPENDENCE_CLASSES`` relax the same-family rule.
    """

    source_id: str
    source_kind: str = "legacy_evidence"
    normalized_claim_id: str = ""
    verifier_family: str = ""
    verifier_version: str = ""
    verification_method: str = ""
    execution_id: str = ""
    target_revision: str = ""
    root_fingerprints: tuple[str, ...] = field(default_factory=tuple)
    derived_from: tuple[str, ...] = field(default_factory=tuple)
    independence_class: str = ""

    @property
    def authorized_independence_class(self) -> str:
        if not isinstance(self.independence_class, str):
            return ""
        return (
            self.independence_class
            if self.independence_class in AUTHORIZED_INDEPENDENCE_CLASSES
            else ""
        )

    @property
    def provenance_complete(self) -> bool:
        """Whether independence can be *demonstrated* for this source.

        Every field is type-checked here rather than assumed, so a malformed
        source is incomplete provenance instead of an exception raised in the
        middle of deduplication, grouping or counting. Whitespace-only values
        are missing values: treating ``execution_id="  "`` as present would be a
        one-character bypass of the entire gate. Non-textual values are never
        coerced with ``str()``.
        """
        required_text = (
            self.source_id,
            self.verifier_family,
            self.execution_id,
            self.target_revision,
        )
        if not all(_is_text(value) for value in required_text):
            return False
        # Auxiliary fields need not be populated, but a malformed one means the
        # record itself is untrustworthy, so it fails closed rather than being
        # partially believed.
        optional_text = (
            self.source_kind,
            self.normalized_claim_id,
            self.verifier_version,
            self.verification_method,
            self.independence_class,
        )
        if not all(isinstance(value, str) for value in optional_text):
            return False
        for collection in (self.root_fingerprints, self.derived_from):
            if collection is None or not isinstance(collection, tuple | list):
                return False
            if not all(isinstance(item, str) for item in collection):
                return False
        return bool(_text_items(self.root_fingerprints))


def source_from_result(result: VerificationResult) -> IndependenceSource | None:
    """Convert a result into a corroborating source, or ``None``.

    Only a valid, positively-supporting result becomes a source. Checking
    integrity but not outcome let two ``unknown`` results from different
    families count as two independent witnesses, and corroboration is about
    positive support: agreeing that nothing is known is not agreement that
    something holds. A refutation is real evidence, but it is negative evidence
    and belongs to the risk term, never to the positive-corroboration count.

    The gate lives here rather than in the caller so no caller can forget it.
    """
    if validate_verification_result(result):
        return None
    if result.outcome != SUPPORTS or result.confidence <= 0.0:
        return None
    return IndependenceSource(
        source_id=result.result_id,
        source_kind="verification_result",
        normalized_claim_id=result.normalized_claim_id,
        verifier_family=result.verifier_family,
        verifier_version=result.verifier_version,
        verification_method=result.verification_method,
        execution_id=result.execution_id,
        target_revision=result.target_revision,
        root_fingerprints=result.root_fingerprints,
        derived_from=result.derived_from,
    )


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self._parent.setdefault(item, item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, left: str, right: str) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


def _linkage_keys(source: IndependenceSource) -> list[str]:
    """Every key that, if shared, makes two sources dependent.

    Keyed on the instrument FAMILY, not the versioned profile: two versions of
    one checker are one instrument, and treating them as two witnesses would let
    a version bump manufacture corroboration. Derivation keys are namespaced so
    a shared *external* parent links its children even when that parent is not
    part of the cohort.
    """
    keys = [f"root:{root.strip()}" for root in _text_items(source.root_fingerprints)]
    if _is_text(source.execution_id):
        keys.append(f"run:{source.execution_id.strip()}")
    if _is_text(source.verifier_family) and not source.authorized_independence_class:
        keys.append(f"family:{source.verifier_family.strip()}")
    keys += [f"dep:{parent.strip()}" for parent in _text_items(source.derived_from)]
    if _is_text(source.source_id):
        keys.append(f"dep:{source.source_id.strip()}")
    return keys


def _group(items: Sequence[IndependenceSource]) -> list[list[str]]:
    """Pure union-find over already-prepared sources. Never called on raw input."""
    union = _UnionFind()
    by_key: dict[str, str] = {}
    for item in items:
        union.find(item.source_id)
        for key in _linkage_keys(item):
            if key in by_key:
                union.union(by_key[key], item.source_id)
            else:
                by_key[key] = item.source_id
    grouped: dict[str, list[str]] = {}
    for item in items:
        grouped.setdefault(union.find(item.source_id), []).append(item.source_id)
    return [sorted(members) for _, members in sorted(grouped.items())]


def independence_groups(
    sources: Iterable[Any],
    required_target_revision: str | None = None,
    required_normalized_claim_id: str | None = None,
) -> list[list[str]]:
    """Connected components over shared roots, runs, families and derivation.

    Applies the same preparation as the counting APIs, so a malformed source
    cannot reach the union-find keys: it is dropped, not coerced, and never
    raises. Optional revision and claim constraints are honoured when supplied.
    """
    prepared = prepare_sources(
        sources, required_target_revision, required_normalized_claim_id
    )
    return _group(prepared.usable)


_SOURCE_FIELDS = (
    "source_id",
    "source_kind",
    "normalized_claim_id",
    "verifier_family",
    "verifier_version",
    "verification_method",
    "execution_id",
    "target_revision",
    "root_fingerprints",
    "derived_from",
    "independence_class",
)


def _safe_value(value: Any) -> Any:
    """A comparable stand-in built only from accepted types. Total, non-recursive.

    Contract collections are FLAT tuples of strings, so there is nothing to
    recurse into. Descending into arbitrary containers turned a
    self-referential list into a ``RecursionError`` in every public API, and a
    deeply nested one into a latent depth bomb. A collection holding any
    non-string element degrades to a single invalid marker without being
    traversed further, and no ``__eq__``, ``__hash__`` or ``repr`` of a supplied
    object is ever invoked.
    """
    if isinstance(value, str):
        return ("s", value)
    if isinstance(value, tuple | list):
        items: list[str] = []
        for element in value:
            if not isinstance(element, str):
                return ("c-invalid", type(value).__name__, len(items))
            items.append(element)
        return ("c", tuple(items))
    return ("t", type(value).__name__)


def _scope_constraints(
    required_target_revision: Any, required_normalized_claim_id: Any
) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Resolve the MANDATORY constraints of the corroboration APIs.

    Distinguishes a deliberately absent filter in the generic topological view
    from an invalid mandatory constraint here. A blank, non-textual or missing
    value is never reinterpreted as "no filter": doing so let a truthy-invalid
    revision clear the guard and then credit every revision at once.
    """
    problems: list[str] = []
    revision = required_target_revision if _is_text(required_target_revision) else None
    if revision is None:
        problems.append("missing_or_invalid_target_revision")
    claim = (
        required_normalized_claim_id if _is_text(required_normalized_claim_id) else None
    )
    if claim is None:
        problems.append("missing_or_invalid_normalized_claim_id")
    return revision, claim, tuple(sorted(problems))


def _canonical_key(item: Any) -> Any:
    """Identity of a candidate source, computed without trusting the object."""
    if not isinstance(item, IndependenceSource):
        return ("<not-a-source>", type(item).__name__)
    return tuple(_safe_value(getattr(item, name)) for name in _SOURCE_FIELDS)


@dataclass(frozen=True)
class PreparedSources:
    """The conservative, order-independent view every counting API shares."""

    usable: tuple[IndependenceSource, ...]
    in_scope_incomplete: tuple[str, ...]
    invalid_sources: int
    conflicting_source_ids: tuple[str, ...]
    ignored_revision_mismatch: tuple[str, ...]
    ignored_claim_mismatch: tuple[str, ...]


def prepare_sources(
    sources: Iterable[Any],
    required_target_revision: str | None = None,
    required_normalized_claim_id: str | None = None,
) -> PreparedSources:
    """THE single preparation shared by grouping, counting and reporting.

    Acyclic on purpose: this never calls the grouping or counting functions, so
    they can all build on it without recursion. Applying it in one place is what
    stops a public entry point from being reachable with a laxer contract than
    the others - ``independence_groups`` used ``source_id`` directly as a
    union-find key, so an unhashable id raised ``TypeError`` out of a public API.

    Conservative at every step: malformed sources are dropped, an id carrying
    two different provenances is excluded rather than resolved by arrival order,
    and sources belonging to another revision or another normalised claim are
    ignored and reported instead of being credited.
    """
    # Deduplication and conflict detection run on a canonical key built only
    # from accepted types - never on ``==`` of the input. An object supplied by
    # a caller can define ``__eq__`` that raises or returns a non-bool, and
    # comparing it would take down every public API here.
    seen: dict[Any, Any] = {}
    for item in sources:
        seen.setdefault(_canonical_key(item), item)
    # A blank constraint means "no constraint", not "must equal the empty
    # string": treating "" as a revision to match would mark every source as a
    # mismatch and empty the in-scope diagnostics.
    revision_filter = required_target_revision if _is_text(required_target_revision) else None
    claim_filter = (
        required_normalized_claim_id if _is_text(required_normalized_claim_id) else None
    )
    valid: list[IndependenceSource] = []
    invalid = 0
    for item in seen.values():
        if isinstance(item, IndependenceSource) and _is_text(item.source_id):
            valid.append(item)
        else:
            invalid += 1
    by_id: dict[str, tuple[Any, IndependenceSource]] = {}
    conflicts: set[str] = set()
    for item in valid:
        key = _canonical_key(item)
        existing = by_id.get(item.source_id)
        if existing is None:
            by_id[item.source_id] = (key, item)
        elif existing[0] != key:
            conflicts.add(item.source_id)
    deduped = [item for key in sorted(by_id) if key not in conflicts for _, item in [by_id[key]]]

    revision_mismatch: list[str] = []
    claim_mismatch: list[str] = []
    in_scope_incomplete: list[str] = []
    usable: list[IndependenceSource] = []
    for item in deduped:
        # Scope is decided BEFORE provenance: a source from another revision or
        # another claim is out of scope entirely and must neither be credited
        # nor justify the conservative floor.
        # ``_is_text`` first: comparing a non-string field would dispatch to a
        # caller-defined ``__eq__`` and could raise out of every public API.
        if revision_filter is not None and (
            not _is_text(item.target_revision)
            or item.target_revision != revision_filter
        ):
            revision_mismatch.append(item.source_id)
            continue
        if claim_filter is not None and (
            not _is_text(item.normalized_claim_id)
            or item.normalized_claim_id != claim_filter
        ):
            claim_mismatch.append(item.source_id)
            continue
        if not item.provenance_complete:
            in_scope_incomplete.append(item.source_id)
            continue
        usable.append(item)
    return PreparedSources(
        usable=tuple(usable),
        in_scope_incomplete=tuple(sorted(in_scope_incomplete)),
        invalid_sources=invalid,
        conflicting_source_ids=tuple(sorted(conflicts)),
        ignored_revision_mismatch=tuple(sorted(revision_mismatch)),
        ignored_claim_mismatch=tuple(sorted(claim_mismatch)),
    )


def _component_id(members: Sequence[str]) -> str:
    """Stable id derived from the members, not from input order."""
    return content_id(
        "component",
        {"profile": INDEPENDENCE_PROFILE, "members": sorted(members)},
    )


def independent_source_count(
    sources: Iterable[Any],
    required_target_revision: str = "",
    required_normalized_claim_id: str | None = None,
) -> int:
    """Independent components demonstrated for ONE claim at ONE revision.

    Both constraints are explicit inputs and both are enforced here rather than
    by the caller. Corroboration is per normalised claim: summing components
    across different claims would count agreement about different things as
    agreement about one, and this function is public API that E may call
    directly, so the invariant cannot live only in ``min_sources_met``.

    Without a required claim, or without a required revision, corroboration
    cannot be demonstrated and the result is capped at one.
    """
    items = list(sources)
    if not items:
        return 0
    revision, claim, problems = _scope_constraints(
        required_target_revision, required_normalized_claim_id
    )
    if problems:
        # Scope cannot be checked, so corroboration cannot be demonstrated: cap
        # at one, and only when there is a structurally valid source at all.
        probe = prepare_sources(items)
        return 1 if (probe.usable or probe.in_scope_incomplete) else 0
    prepared = prepare_sources(items, revision, claim)
    if prepared.usable:
        return len(_group(prepared.usable))
    # The floor of one exists for evidence that IS in scope but whose provenance
    # is too incomplete to demonstrate independence. Evidence excluded because
    # it belongs to another claim or revision, carries a conflicting identity or
    # is malformed is out of scope: ignoring it must not also credit it.
    return 1 if prepared.in_scope_incomplete else 0


def independence_report(
    sources: Iterable[Any],
    required_sources: int,
    required_target_revision: str = "",
    required_normalized_claim_id: str | None = None,
) -> dict[str, Any]:
    """Auditable explanation of how a claim's independent sources were counted."""
    items = list(sources)
    revision, claim, missing_scope = _scope_constraints(
        required_target_revision, required_normalized_claim_id
    )
    count = independent_source_count(items, revision or "", claim)
    if missing_scope:
        # Without a scope, nothing was demonstrated, so publishing components
        # would contradict the count. The reason is stated instead of implied.
        probe = prepare_sources(items)
        return {
            "evaluated_target_revision": "",
            "evaluated_normalized_claim_id": "",
            "required_sources": required_sources,
            "independent_components": count,
            "missing_scope_constraints": list(missing_scope),
            "components_by_revision": {},
            "conflicting_source_ids": list(probe.conflicting_source_ids),
            "ignored_revision_mismatch": [],
            "ignored_claim_mismatch": [],
            "invalid_sources": probe.invalid_sources,
            "unevaluated_scope_sources": sorted(
                [item.source_id for item in probe.usable] + list(probe.in_scope_incomplete)
            ),
            "sources_with_incomplete_provenance": list(probe.in_scope_incomplete),
            "components": [],
        }
    prepared = prepare_sources(items, revision, claim)
    by_id = {item.source_id: item for item in prepared.usable}
    components = []
    for members in _group(prepared.usable):
        group = [by_id[m] for m in members]
        components.append(
            {
                "component_id": _component_id(members),
                "verification_result_ids": sorted(
                    g.source_id for g in group if g.source_kind == "verification_result"
                ),
                "legacy_evidence_ids": sorted(
                    g.source_id for g in group if g.source_kind != "verification_result"
                ),
                "verifier_families": sorted({g.verifier_family for g in group}),
                "verifier_versions": sorted({g.verifier_version for g in group}),
                "verification_methods": sorted({g.verification_method for g in group}),
                "execution_ids": sorted({g.execution_id for g in group}),
                "root_fingerprints": sorted({r for g in group for r in g.root_fingerprints}),
                "derived_from": sorted({d for g in group for d in g.derived_from}),
            }
        )
    # Keeps the evaluated claim and varies only the revision: this section
    # explains ONE claim, so a source ignored for claim mismatch must not
    # reappear here under a different heading.
    across_revisions = prepare_sources(items, None, claim)
    components_by_revision: dict[str, int] = {}
    # NOT named ``revision``: shadowing the evaluated constraint here silently
    # replaced it with whichever revision the loop ended on.
    for bucket_revision in sorted({i.target_revision for i in across_revisions.usable}):
        bucket = [i for i in across_revisions.usable if i.target_revision == bucket_revision]
        components_by_revision[bucket_revision] = len(_group(bucket))
    return {
        "evaluated_target_revision": revision or "",
        "evaluated_normalized_claim_id": claim or "",
        "required_sources": required_sources,
        "independent_components": count,
        "missing_scope_constraints": [],
        "unevaluated_scope_sources": [],
        "components_by_revision": components_by_revision,
        "conflicting_source_ids": list(prepared.conflicting_source_ids),
        "ignored_revision_mismatch": list(prepared.ignored_revision_mismatch),
        "ignored_claim_mismatch": list(prepared.ignored_claim_mismatch),
        "invalid_sources": prepared.invalid_sources,
        # Derived from the deduplicated view, never the raw input: listing the
        # same id twice would make the report non-idempotent under duplication.
        # In-scope only: out-of-scope sources are already reported under their
        # own mismatch keys and must not be double-counted here.
        "sources_with_incomplete_provenance": list(prepared.in_scope_incomplete),
        # Sorted by content-addressed component id so the whole report is
        # byte-identical under permutation of the inputs.
        "components": sorted(components, key=lambda c: c["component_id"]),
    }
