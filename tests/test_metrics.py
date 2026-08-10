from __future__ import annotations

import pytest

from argos_epistemic import Budget, analyze_system
from argos_epistemic.algorithm import (
    Proposition,
    aspect_score,
    compute_coverage,
    compute_coverage_metrics,
)
from argos_epistemic.verifiers import (
    REFUTES,
    UNKNOWN,
    VerifierClaim,
    VerifierRegistration,
    run_verifier,
    verification_input,
)


def _support(
    evidence_id: str,
    claim_id: str,
    confidence: float = 0.6,
    *,
    root: str = "",
    family: str = "",
    execution: str = "",
    revision: str = "",
) -> Proposition:
    return Proposition(
        aspect="write",
        polarity=1.0,
        claim="writes are durable",
        evidence_id=evidence_id,
        confidence=confidence,
        method="static",
        scope="core",
        relation="supports",
        claim_id=claim_id,
        claim_text="writes are durable",
        verification_result_id=evidence_id if family else "",
        verifier_family=family,
        verifier_version="1" if family else "",
        verification_method_profile="static" if family else "",
        execution_id=execution,
        target_revision=revision,
        root_fingerprints=(root,) if root else (),
    )


def test_different_claims_on_one_aspect_do_not_corroborate_each_other():
    aspects = [{"name": "write", "weight": 1.0}]
    first = _support("e1", "claim:a")
    second = _support("e2", "claim:b")

    assert compute_coverage([first, second], aspects) == compute_coverage([first], aspects)


def test_independent_components_of_the_same_claim_add_mass():
    aspects = [{"name": "write", "weight": 1.0}]
    first = _support(
        "result:1",
        "claim:same",
        family="pep621",
        execution="run:1",
        root="root:1",
        revision="rev:1",
    )
    second = _support(
        "result:2",
        "claim:same",
        family="pep508",
        execution="run:2",
        root="root:2",
        revision="rev:1",
    )

    assert compute_coverage([first], aspects, required_target_revision="rev:1") == pytest.approx(
        1 / 3
    )
    assert compute_coverage(
        [first, second], aspects, required_target_revision="rev:1"
    ) == pytest.approx(2 / 3)


def test_shared_root_collapses_to_the_strongest_component_confidence():
    aspects = [{"name": "write", "weight": 1.0}]
    first = _support(
        "result:1",
        "claim:same",
        0.6,
        family="pep621",
        execution="run:1",
        root="root:shared",
        revision="rev:1",
    )
    second = _support(
        "result:2",
        "claim:same",
        0.9,
        family="pep508",
        execution="run:2",
        root="root:shared",
        revision="rev:1",
    )

    assert compute_coverage(
        [first, second], aspects, required_target_revision="rev:1"
    ) == pytest.approx(0.5)


def test_ten_thousand_duplicates_are_bit_identical_to_one():
    aspects = [{"name": "write", "weight": 1.0}]
    proposition = _support("e1", "claim:same")

    assert compute_coverage([proposition] * 10_000, aspects) == compute_coverage(
        [proposition], aspects
    )


def test_component_aggregation_is_permutation_invariant():
    aspects = [{"name": "write", "weight": 1.0}]
    sources = [
        _support(
            "result:1",
            "claim:same",
            0.6,
            family="pep621",
            execution="run:1",
            root="root:1",
            revision="rev:1",
        ),
        _support(
            "result:2",
            "claim:same",
            0.9,
            family="pep508",
            execution="run:2",
            root="root:2",
            revision="rev:1",
        ),
    ]

    assert compute_coverage(
        sources, aspects, required_target_revision="rev:1"
    ) == compute_coverage(
        list(reversed(sources)), aspects, required_target_revision="rev:1"
    )


def test_cyclic_provenance_fails_closed_without_recursion():
    cycle = []
    cycle.append(cycle)
    proposition = _support("e1", "claim:same")
    proposition.derived_from = cycle

    assert compute_coverage(
        [proposition], [{"name": "write", "weight": 1.0}]
    ) == pytest.approx(1 / 3)


def test_aspect_score_ignores_propositions_from_other_aspects():
    write = _support("write", "claim:write")
    other = _support("other", "claim:other")
    other.aspect = "read"

    assert aspect_score([write, other]) == aspect_score([write])


def test_malformed_claim_cannot_create_retrieval_or_probatory_capability():
    proposition = _support("e1", "")
    proposition.claim = ""
    proposition.claim_text = ""
    metrics = compute_coverage_metrics(
        [proposition], [{"name": "write", "weight": 1.0}]
    )

    assert metrics.evidential_coverage == 0.0
    assert metrics.retrieval_coverage == 0.0
    assert metrics.coverage_capability == "unavailable"
    assert "invalid_claim_identity" in metrics.diagnostics


@pytest.mark.parametrize("weight", [None, "1", True, float("nan"), -1.0])
def test_invalid_goal_weights_fail_closed_without_raising(weight):
    report = analyze_system(
        {"name": "invalid-weight", "artifacts": []},
        {"name": "g", "aspects": [{"name": "write", "weight": weight}]},
        Budget(tokens_remaining=0, tool_remaining=0),
    )

    assert report["coverage"] == 0.0
    assert report["coverage_capability"] == "unavailable"
    assert report["complete"] is False


def test_duplicate_goal_aspects_do_not_duplicate_weight():
    proposition = _support("e1", "claim:same")
    metrics = compute_coverage_metrics(
        [proposition],
        [{"name": "write", "weight": 0.5}, {"name": "write", "weight": 0.5}],
    )

    assert metrics.evidential_coverage == pytest.approx(1 / 3)
    assert metrics.evidential_aspect_scores == {"write": pytest.approx(1 / 3)}


@pytest.mark.parametrize("corroboration", [None, "1.8", True, 0, -1, float("nan")])
def test_invalid_corroboration_fails_closed(corroboration):
    metrics = compute_coverage_metrics(
        [_support("e1", "claim:same")],
        [{"name": "write", "weight": 1.0}],
        corroboration,
    )

    assert metrics.evidential_coverage == 0.0
    assert metrics.diagnostics == ("invalid_corroboration",)


def test_report_separates_retrieval_structure_and_evidence():
    report = analyze_system(
        {
            "name": "retrieval-only",
            "artifacts": [
                {
                    "id": "tests.py",
                    "content": "tests write",
                    "level": 2,
                    "relevance": 1.0,
                    "kind": "test",
                    "tests": [{"aspect": "write"}],
                }
            ],
        },
        {
            "name": "g",
            "aspects": ["write"],
            "theta_coverage": 0.1,
            "rho_risk": 1.0,
            "min_sources_per_aspect": 1,
        },
        Budget(tokens_remaining=10_000, tool_remaining=10),
    )

    assert report["coverage"] == report["evidential_coverage"] == 0.0
    assert report["aspect_scores"] == report["evidential_aspect_scores"]
    assert report["retrieval_coverage"] == 1.0
    assert report["structural_coverage"] == 1.0
    assert report["coverage_capability"] == "unavailable"
    assert report["coverage_profile"] == "argos/claim-component-coverage-v1"
    assert report["complete"] is False


def test_empty_goal_is_not_vacuously_probatory():
    report = analyze_system(
        {"name": "empty", "artifacts": []},
        {"name": "g", "aspects": []},
        Budget(tokens_remaining=0, tool_remaining=0),
    )

    assert report["coverage_capability"] == "unavailable"
    assert report["coverage"] == 0.0
    assert report["complete"] is False


def test_non_probative_verifier_is_observed_once_without_creating_capability():
    registration = VerifierRegistration(
        "observed-family",
        "1",
        "deterministic",
        lambda _: [VerifierClaim(UNKNOWN, "write", "not established", "core")],
    )
    payload = verification_input(
        "artifact",
        "content",
        "artifact.txt",
        "rev:1",
        ["write"],
    )
    result = run_verifier(registration, payload, "run:1")[0]
    report = analyze_system(
        {"name": "observed", "artifacts": []},
        {"name": "g", "aspects": ["write"], "target_revision": "rev:1"},
        Budget(tokens_remaining=0, tool_remaining=0),
        verification_results=[result, result],
    )

    assert report["coverage_capability"] == "unavailable"
    assert report["verification_profiles"]["executed"] == [
        {
            "family": "observed-family",
            "versions": ["1"],
            "methods": ["deterministic"],
            "aspects": ["write"],
            "result_count": 1,
            "probative_result_count": 0,
        }
    ]
    assert report["verification_admission"]["verification_propositions_admitted"] == 0
    assert report["complete"] is False


def test_refutation_demonstrates_probatory_capability_but_never_positive_coverage():
    registration = VerifierRegistration(
        "refuting-family",
        "1",
        "deterministic",
        lambda _: [VerifierClaim(REFUTES, "write", "writes are durable", "core")],
    )
    payload = verification_input(
        "artifact",
        "content",
        "artifact.txt",
        "rev:1",
        ["write"],
    )
    result = run_verifier(registration, payload, "run:1")[0]
    report = analyze_system(
        {"name": "refuted", "artifacts": []},
        {"name": "g", "aspects": ["write"], "target_revision": "rev:1"},
        Budget(tokens_remaining=0, tool_remaining=0),
        verification_results=[result],
    )

    assert report["coverage_capability"] == "probatory"
    assert report["coverage"] == 0.0
    assert report["complete"] is False
    assert "negative_proposition" in report["completion"]["reason_codes"]
