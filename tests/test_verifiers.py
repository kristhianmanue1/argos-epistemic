"""Contract tests for the static verification protocol and independence (PR D).

Independence is the gate that keeps ``complete`` honest while legacy coverage
still aggregates by proposition volume, so these tests are adversarial by
design: every way of making one source look like several is enumerated and
refused.

Note on scope: D deliberately has **no** positive end-to-end completion test.
Reaching ``complete=True`` without manually declared supports is E's job; here
the manual-supports path is asserted to stay incomplete.
"""

import dataclasses
import math

import pytest

from argos_epistemic import Budget, analyze_system
from argos_epistemic.algorithm import Proposition, min_sources_met
from argos_epistemic.verifiers import (
    DEGRADED,
    SUPPORTS,
    IndependenceSource,
    VerifierClaim,
    VerifierRegistration,
    independence_groups,
    independence_report,
    independent_source_count,
    normalized_claim_id,
    root_fingerprint,
    run_verifier,
    verification_input,
)

ASPECTS = [{"name": "write", "weight": 1.0}]
REV = "rev-1"


def _src(
    source_id,
    *,
    profile="p1",
    version="1",
    execution_id="run-1",
    revision=REV,
    roots=("root-default",),
    derived_from=(),
    independence_class="",
    source_kind="verification_result",
):
    """A source with COMPLETE provenance unless a field is explicitly emptied."""
    return IndependenceSource(
        source_id=source_id,
        source_kind=source_kind,
        normalized_claim_id="claim-1",
        verifier_family=profile,
        verifier_version=version,
        verification_method="deterministic",
        execution_id=execution_id,
        target_revision=revision,
        root_fingerprints=tuple(roots),
        derived_from=tuple(derived_from),
        independence_class=independence_class,
    )


def _prop(
    evidence_id,
    *,
    claim="c1",
    aspect="write",
    profile="p1",
    version="1",
    execution_id="run-1",
    revision=REV,
    roots=("root-default",),
    derived=(),
    result_id=None,
):
    return Proposition(
        aspect=aspect,
        polarity=1.0,
        claim=claim,
        evidence_id=evidence_id,
        confidence=0.9,
        method="symbolic",
        scope=aspect,
        relation="supports",
        claim_id=normalized_claim_id(aspect, claim, aspect),
        claim_text=claim,
        verification_result_id=result_id if result_id is not None else f"vr-{evidence_id}",
        verifier_family=profile,
        verifier_version=version,
        verification_method_profile="deterministic",
        execution_id=execution_id,
        target_revision=revision,
        root_fingerprints=tuple(roots),
        derived_from=tuple(derived),
    )


def _count(sources, revision=REV, claim="claim-1"):
    return independent_source_count(sources, revision, claim)


def _met(props, min_sources, revision=REV):
    return min_sources_met(props, ASPECTS, min_sources, revision)


# --------------------------------------------------------------------------
# Independence: duplicates and aliases
# --------------------------------------------------------------------------


def test_duplicate_proposition_counts_once():
    prop = _prop("e1")
    assert _met([prop, prop, prop], 2) is False


def test_duplicate_evidence_id_counts_once():
    assert independent_source_count([_src('e1'), _src('e1')]) == 1


def test_distinct_ids_with_the_same_root_fingerprint_count_once():
    shared = root_fingerprint("identical content")
    sources = [
        _src("alias-a", profile="pA", version="1", execution_id="run-a", roots=(shared,)),
        _src("alias-b", profile="pB", version="1", execution_id="run-b", roots=(shared,)),
    ]
    assert _count(sources) == 1


# --------------------------------------------------------------------------
# Independence: the profile / execution / revision matrix
# --------------------------------------------------------------------------


def test_same_profile_with_distinct_roots_and_runs_does_not_corroborate():
    """One instrument used twice is one witness."""
    sources = [
        _src("a", profile="same", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="same", version="1", execution_id="run-2", roots=("r2",)),
    ]
    assert _count(sources) == 1


def test_distinct_profiles_over_the_same_root_do_not_corroborate():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("shared",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("shared",)),
    ]
    assert _count(sources) == 1


def test_distinct_profiles_and_roots_but_shared_execution_do_not_corroborate():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pB", version="1", execution_id="run-1", roots=("r2",)),
    ]
    assert _count(sources) == 1


def test_distinct_profiles_roots_and_executions_do_corroborate():
    """The one shape that genuinely counts as two."""
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
    ]
    assert _count(sources) == 2


def test_same_family_different_versions_is_one_witness():
    """pep621@1 and pep621@2 are two revisions of one instrument."""
    sources = [
        _src("a", profile="pep621", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pep621", version="2", execution_id="run-2", roots=("r2",)),
    ]
    assert _count(sources) == 1


def test_distinct_families_corroborate_regardless_of_version():
    sources = [
        _src("a", profile="pep621", version="7", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pep508", version="1", execution_id="run-2", roots=("r2",)),
    ]
    assert _count(sources) == 2


def test_version_change_alters_result_id_but_not_independence():
    base = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    bumped = run_verifier(_reg(_valid, version="2"), _payload(), execution_id="run-1")[0]
    assert base.result_id != bumped.result_id
    assert base.verifier_family == bumped.verifier_family
    from argos_epistemic.verifiers import source_from_result

    sources = [source_from_result(base), source_from_result(bumped)]
    assert independent_source_count(sources, REV, base.normalized_claim_id) == 1


def test_stale_revision_with_more_evidence_does_not_win_over_the_current_one():
    """Two sources in rev-old must not satisfy a gate evaluated at rev-current."""
    sources = [
        _src("old-a", profile="pA", version="1", execution_id="run-1", roots=("r1",),
             revision="rev-old"),
        _src("old-b", profile="pB", version="1", execution_id="run-2", roots=("r2",),
             revision="rev-old"),
        _src("cur", profile="pC", version="1", execution_id="run-3", roots=("r3",),
             revision="rev-current"),
    ]
    assert independent_source_count(sources, "rev-current", "claim-1") == 1
    section = independence_report(sources, 2, "rev-current", "claim-1")
    assert section["evaluated_target_revision"] == "rev-current"
    assert section["components_by_revision"]["rev-old"] == 2
    assert section["independent_components"] == 1
    assert sorted(section["ignored_revision_mismatch"]) == ["old-a", "old-b"]


def test_absent_evaluated_revision_fails_closed_for_min_sources_above_one():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
    ]
    assert independent_source_count(sources, "") == 1
    props = [
        _prop("e1", claim="same", profile="pA", execution_id="run-1", roots=("r1",)),
        _prop("e2", claim="same", profile="pB", execution_id="run-2", roots=("r2",)),
    ]
    assert min_sources_met(props, ASPECTS, 2, "") is False
    assert min_sources_met(props, ASPECTS, 2, REV) is True


def test_results_about_different_revisions_do_not_corroborate_each_other():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",), revision="rev-1"),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",), revision="rev-2"),
    ]
    assert _count(sources) == 1


def test_unauthorized_independence_class_cannot_unlock_the_same_profile_gate():
    """An arbitrary class string must not relax corroboration.

    Found in self-review: any truthy ``independence_class`` used to bypass the
    same-profile rule, which would be a one-field escape from the whole gate if
    that value ever reached the field from untrusted data.
    """
    sources = [
        _src("a", profile="same", version="1", execution_id="run-1", roots=("r1",),
             independence_class="i-declare-myself-independent"),
        _src("b", profile="same", version="1", execution_id="run-2", roots=("r2",),
             independence_class="i-declare-myself-independent"),
    ]
    assert _count(sources) == 1
    assert sources[0].authorized_independence_class == ""


def test_authorized_independence_classes_are_empty_by_default():
    from argos_epistemic.verifiers import AUTHORIZED_INDEPENDENCE_CLASSES

    assert frozenset() == AUTHORIZED_INDEPENDENCE_CLASSES


@pytest.mark.parametrize(
    "field_name,value",
    [
        ("execution_id", "   "),
        ("profile", "  "),
        ("revision", "\t"),
    ],
)
def test_whitespace_only_provenance_is_treated_as_missing(field_name, value):
    """Found in self-review: whitespace is truthy, so it bypassed the check."""
    kwargs = {"profile": "pA@1", "execution_id": "run-1", "revision": REV, "roots": ("r1",)}
    kwargs[field_name] = value
    assert _src("a", **kwargs).provenance_complete is False


def test_empty_root_fingerprint_is_treated_as_missing():
    assert _src("a", roots=("",)).provenance_complete is False
    assert _src("a", roots=("", "  ")).provenance_complete is False
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("",)),
    ]
    assert _count(sources) == 1


# --------------------------------------------------------------------------
# Independence: overlapping roots and derivation
# --------------------------------------------------------------------------


def test_partially_overlapping_root_sets_land_in_one_component():
    """{x,y} and {y,z} share y; a per-source hash would miss this."""
    sources = [
        _src("A", profile="pA", version="1", execution_id="run-1", roots=("x", "y")),
        _src("B", profile="pB", version="1", execution_id="run-2", roots=("y", "z")),
    ]
    assert _count(sources) == 1
    assert independence_groups(sources) == [["A", "B"]]


def test_transitively_overlapping_roots_collapse():
    sources = [
        _src("A", profile="pA", version="1", execution_id="run-1", roots=("x", "y")),
        _src("B", profile="pB", version="1", execution_id="run-2", roots=("y", "z")),
        _src("C", profile="pC", version="1", execution_id="run-3", roots=("z", "w")),
    ]
    assert _count(sources) == 1


def test_result_derived_from_a_present_parent_is_not_independent():
    sources = [
        _src("base", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("derived", profile="pB", version="1", execution_id="run-2", roots=("r2",),
             derived_from=("base",)),
    ]
    assert _count(sources) == 1


def test_shared_external_derivative_parent_collapses_even_when_absent():
    """The parent need not be in the cohort for its children to be dependent."""
    sources = [
        _src("A", profile="pA", version="1", execution_id="run-1", roots=("r1",),
             derived_from=("external-index",)),
        _src("B", profile="pB", version="1", execution_id="run-2", roots=("r2",),
             derived_from=("external-index",)),
    ]
    assert _count(sources) == 1


def test_derivative_chain_with_present_and_absent_parents_collapses():
    sources = [
        _src("A", profile="pA", version="1", execution_id="run-1", roots=("r1",),
             derived_from=("ghost",)),
        _src("B", profile="pB", version="1", execution_id="run-2", roots=("r2",),
             derived_from=("ghost",)),
        _src("C", profile="pC", version="1", execution_id="run-3", roots=("r3",),
             derived_from=("B",)),
    ]
    assert _count(sources) == 1


def test_derivation_cycle_terminates():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",), derived_from=("b",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",), derived_from=("a",)),
    ]
    assert _count(sources) == 1


# --------------------------------------------------------------------------
# Independence must be demonstrated
# --------------------------------------------------------------------------


def test_absent_provenance_collapses_rather_than_multiplies():
    bare = [
        IndependenceSource(source_id="a"),
        IndependenceSource(source_id="b"),
        IndependenceSource(source_id="c"),
    ]
    # Without a claim or revision to scope against, corroboration cannot be
    # demonstrated at all: three unknown sources are capped at one, never three.
    assert independent_source_count(bare, "", None) == 1


@pytest.mark.parametrize(
    "missing", ["profile", "execution_id", "revision", "roots"]
)
def test_incomplete_provenance_never_adds_a_group(missing):
    """A demonstrated group plus an undemonstrated source is still one group."""
    kwargs = {"profile": "pB@1", "execution_id": "run-2", "revision": REV, "roots": ("r2",)}
    kwargs[missing] = () if missing == "roots" else ""
    sources = [
        _src("known", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("partial", **kwargs),
    ]
    assert _count(sources) == 1


def test_min_sources_above_one_cannot_be_met_by_legacy_sources_alone():
    legacy = [
        _prop("e1", profile="", execution_id="", revision="", roots=(root_fingerprint("a"),)),
        _prop("e2", profile="", execution_id="", revision="", roots=(root_fingerprint("b"),)),
    ]
    # Legacy sources declare no revision, so they are out of scope for an
    # evaluated revision and cannot satisfy corroboration at any threshold.
    assert _met(legacy, 2) is False
    assert _met(legacy, 1) is False


# --------------------------------------------------------------------------
# Corroboration by claim
# --------------------------------------------------------------------------


def test_different_claims_of_the_same_aspect_do_not_add_up():
    props = [
        _prop("e1", claim="writes use compare-and-swap", profile="pA", version="1",
              execution_id="run-1", roots=("r1",)),
        _prop("e2", claim="writes are journalled", profile="pB", version="1",
              execution_id="run-2", roots=("r2",)),
    ]
    assert _met(props, 2) is False


def test_same_claim_from_two_independent_sources_satisfies_corroboration():
    props = [
        _prop("e1", claim="same claim", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _prop("e2", claim="same claim", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
    ]
    assert _met(props, 2) is True


# --------------------------------------------------------------------------
# complete protection
# --------------------------------------------------------------------------


def _analyze(system, min_sources=2):
    goal = {"name": "g", "aspects": ["write"], "theta_coverage": 0.9, "rho_risk": 0.1,
            "min_sources_per_aspect": min_sources}
    return analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=20))


def test_legacy_coverage_one_from_duplicates_still_cannot_complete():
    """Binding until PR F replaces the legacy aggregation."""
    identical = {"content": "cas", "level": 4, "relevance": 1.0, "kind": "code",
                 "supports": [{"aspect": "write", "claim": "writes use cas", "scope": "v1"}]}
    report = _analyze({
        "name": "dupes",
        "artifacts": [{"id": f"{name}.py", **identical} for name in ("a", "b", "c")],
    })
    assert report["coverage"] >= 0.99, "legacy coverage does inflate from duplicates"
    assert report["complete"] is False
    assert "insufficient_sources" in report["completion"]["reason_codes"]


def test_manually_declared_supports_across_two_files_do_not_complete():
    """Self-declared authority is not verification.

    These artifacts carry no verifier profile, execution or revision, so they
    are undemonstrated sources. The first honest ``complete=True`` belongs to E.
    """
    claim = {"aspect": "write", "claim": "writes use cas", "scope": "v1"}
    report = _analyze({
        "name": "manual",
        "artifacts": [
            {"id": "pyproject.toml", "content": "declares cas", "level": 2, "relevance": 1.0,
             "kind": "config", "supports": [claim]},
            {"id": "requirements.txt", "content": "pins cas", "level": 2, "relevance": 1.0,
             "kind": "config", "supports": [claim]},
        ],
    })
    assert report["complete"] is False
    assert "insufficient_sources" in report["completion"]["reason_codes"]


def test_target_cannot_obtain_independence_by_declaring_execution_id():
    """The analyzed target must not be able to declare its own provenance."""
    claim = {"aspect": "write", "claim": "writes use cas", "scope": "v1"}
    report = _analyze({
        "name": "forged",
        "artifacts": [
            {"id": "a.py", "content": "one", "level": 4, "relevance": 1.0, "kind": "code",
             "supports": [claim], "execution_id": "run-1",
             "verifier_profile": "trusted@1", "target_revision": "rev-1"},
            {"id": "b.py", "content": "two", "level": 4, "relevance": 1.0, "kind": "code",
             "supports": [claim], "execution_id": "run-2",
             "verifier_profile": "trusted@2", "target_revision": "rev-1"},
        ],
    })
    assert report["complete"] is False
    for entry in report["source_independence"]["claims"]:
        for component in entry["components"]:
            assert component["execution_ids"] == [] or all(
                not e for e in component["execution_ids"]
            )


# --------------------------------------------------------------------------
# Auditability
# --------------------------------------------------------------------------


def test_report_lets_the_min_sources_decision_be_reconstructed():
    identical = {"content": "cas", "level": 4, "relevance": 1.0, "kind": "code",
                 "supports": [{"aspect": "write", "claim": "writes use cas", "scope": "v1"}]}
    report = _analyze({
        "name": "dupes",
        "artifacts": [{"id": f"{n}.py", **identical} for n in ("a", "b")],
    })
    section = report["source_independence"]
    assert section["profile"] == "argos/source-independence-v1"
    assert section["required_sources"] == 2
    entry = section["claims"][0]
    assert entry["aspect"] == "write"
    assert entry["normalized_claim_id"]
    assert entry["independent_components"] < section["required_sources"]
    assert entry["sources_with_incomplete_provenance"]


def test_independence_report_exposes_component_membership():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
    ]
    section = independence_report(sources, 2, REV, "claim-1")
    assert section["independent_components"] == 2
    assert section["evaluated_target_revision"] == REV
    assert len(section["components"]) == 2
    component = section["components"][0]
    assert set(component) >= {
        "component_id", "verification_result_ids", "legacy_evidence_ids",
        "verifier_families", "verifier_versions", "execution_ids",
        "root_fingerprints", "derived_from",
    }


# --------------------------------------------------------------------------
# Verifier protocol: fail-closed
# --------------------------------------------------------------------------


def _payload(content="body", aspects=("write",), revision=REV):
    return verification_input("a", content, "a", revision, aspects)


def _reg(fn, profile="test", version="1", method="deterministic"):
    return VerifierRegistration(profile, version, method, fn, "test verifier")


def test_verifier_exception_degrades_and_carries_no_probative_mass():
    def boom(payload):
        raise RuntimeError("internal failure")

    results = run_verifier(_reg(boom), _payload(), execution_id="run-1")
    assert [r.outcome for r in results] == [DEGRADED]
    assert results[0].is_probative is False
    assert results[0].confidence == 0.0
    assert "verifier_raised" in results[0].degradations


@pytest.mark.parametrize(
    "returned,expected_degradation",
    [
        (None, "non_sequence_return"),
        (42, "non_sequence_return"),
        ({"outcome": "supports"}, "non_sequence_return"),
    ],
)
def test_non_sequence_returns_degrade(returned, expected_degradation):
    results = run_verifier(_reg(lambda payload: returned), _payload(), execution_id="run-1")
    assert [r.outcome for r in results] == [DEGRADED]
    assert expected_degradation in results[0].degradations


def test_element_that_is_not_a_verifier_claim_degrades_without_raising():
    def dict_element(payload):
        return [{"outcome": "supports", "aspect": "write"}]

    results = run_verifier(_reg(dict_element), _payload(), execution_id="run-1")
    assert [r.outcome for r in results] == [DEGRADED]
    assert "not_a_verifier_claim" in results[0].degradations


@pytest.mark.parametrize(
    "confidence",
    [float("nan"), float("inf"), float("-inf"), -0.5, 1.5, "high", None, True, False],
)
def test_invalid_confidence_degrades_and_never_supports(confidence):
    def claim(payload):
        return [VerifierClaim(SUPPORTS, "write", "c", "v1", confidence=confidence)]

    results = run_verifier(_reg(claim), _payload(), execution_id="run-1")
    assert results[0].outcome == DEGRADED
    assert "confidence_not_a_unit_interval_value" in results[0].degradations
    assert results[0].confidence == 0.0
    assert math.isfinite(results[0].confidence)


@pytest.mark.parametrize(
    "claim,degradation",
    [
        (VerifierClaim("definitely_true", "write", "c", "v1"), "unsupported_outcome"),
        (VerifierClaim(SUPPORTS, "telemetry", "c", "v1"), "aspect_outside_goal"),
        (VerifierClaim(SUPPORTS, "", "c", "v1"), "empty_aspect"),
        (VerifierClaim(SUPPORTS, "write", "   ", "v1"), "empty_claim_text"),
        (VerifierClaim(SUPPORTS, "write", "c", "  "), "empty_scope"),
        (VerifierClaim(SUPPORTS, "write", "c", "v1", limitations=(1, 2)), "invalid_limitations"),
    ],
)
def test_invalid_claim_fields_degrade(claim, degradation):
    results = run_verifier(_reg(lambda payload: [claim]), _payload(), execution_id="run-1")
    assert results[0].outcome == DEGRADED
    assert degradation in results[0].degradations


def _valid(payload):
    return [VerifierClaim(SUPPORTS, "write", "declared", "v1")]


@pytest.mark.parametrize(
    "execution_id,revision,degradation",
    [
        ("", REV, "missing_execution_id"),
        ("run-1", "", "missing_target_revision"),
    ],
)
def test_missing_execution_or_revision_degrades(execution_id, revision, degradation):
    from argos_epistemic.verifiers import VerificationInput

    payload = VerificationInput(
        "a", "body", "a", revision, ("write",), (root_fingerprint("body"),)
    )
    results = run_verifier(_reg(_valid), payload, execution_id=execution_id)
    assert results[0].outcome == DEGRADED
    assert degradation in results[0].degradations


def test_root_fingerprints_must_match_the_content():
    """A caller cannot supply arbitrary roots to manufacture independence."""
    from argos_epistemic.verifiers import VerificationInput

    forged = VerificationInput("a", "real body", "a", REV, ("write",), ("root-i-made-up",))
    results = run_verifier(_reg(_valid), forged, execution_id="run-1")
    assert results[0].outcome == DEGRADED
    assert "root_fingerprint_mismatch" in results[0].degradations

    empty = VerificationInput("a", "real body", "a", REV, ("write",), ())
    results = run_verifier(_reg(_valid), empty, execution_id="run-1")
    assert "missing_root_fingerprints" in results[0].degradations


# --------------------------------------------------------------------------
# Result binding and determinism
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [None, True, False, 42, object()])
def test_non_string_execution_id_degrades_without_coercion(bad):
    """str(None) == 'None' would otherwise pass as a valid execution id."""
    results = run_verifier(_reg(_valid), _payload(), execution_id=bad)
    assert results[0].outcome == DEGRADED
    assert "missing_execution_id" in results[0].degradations


@pytest.mark.parametrize("bad", [None, True, 42, object(), "not-an-input"])
def test_payload_of_the_wrong_type_degrades_without_raising(bad):
    results = run_verifier(_reg(_valid), bad, execution_id="run-1")
    assert results[0].outcome == DEGRADED
    assert "invalid_payload_type" in results[0].degradations


@pytest.mark.parametrize(
    "field_name,value,degradation",
    [
        ("goal_aspects", None, "invalid_goal_aspects"),
        ("goal_aspects", ("write", 7), "invalid_goal_aspects"),
        ("root_fingerprints", (123,), "invalid_root_fingerprints"),
        ("root_fingerprints", None, "invalid_root_fingerprints"),
    ],
)
def test_malformed_payload_collections_degrade_without_raising(
    field_name, value, degradation
):
    """Found in self-review: ``claim.aspect not in None`` raised out of run_verifier,
    and non-string roots were coerced with ``str()`` and accepted."""
    from argos_epistemic.verifiers import VerificationInput

    fields = {
        "artifact_id": "a", "content": "body", "location": "l",
        "target_revision": REV, "goal_aspects": ("write",),
        "root_fingerprints": (root_fingerprint("body"),),
    }
    fields[field_name] = value
    results = run_verifier(_reg(_valid), VerificationInput(**fields), execution_id="run-1")
    assert results[0].outcome == DEGRADED
    assert degradation in results[0].degradations


def test_extra_roots_must_be_non_empty_strings():
    from argos_epistemic.verifiers import VerifierContractError

    for bad in ((123,), (None,), ("",), ("  ",)):
        with pytest.raises(VerifierContractError):
            verification_input("a", "b", "l", REV, ("write",), extra_roots=bad)


def test_invalid_payload_does_not_invoke_the_verifier():
    """An instrument must not run against an input whose output could not be trusted."""
    calls = []

    def sentinel(payload):
        calls.append(payload)
        return [VerifierClaim(SUPPORTS, "write", "c", "v1")]

    results = run_verifier(_reg(sentinel), object(), execution_id="run-1")
    assert calls == [], "verifier was invoked despite an invalid payload"
    assert results[0].outcome == DEGRADED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"profile": "", "version": "1"},
        {"profile": "  ", "version": "1"},
        {"profile": "p", "version": ""},
        {"profile": None, "version": "1"},
        {"profile": "p", "version": 3},
    ],
)
def test_registration_rejects_empty_or_non_textual_profile_and_version(kwargs):
    from argos_epistemic.verifiers import VerifierContractError, register_verifier

    with pytest.raises(VerifierContractError):
        register_verifier(method="deterministic", verifier=lambda p: [], **kwargs)


def test_registration_rejects_a_non_callable_verifier():
    from argos_epistemic.verifiers import VerifierContractError, register_verifier

    with pytest.raises(VerifierContractError):
        register_verifier("p", "1", "deterministic", "not-callable")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"artifact_id": ""},
        {"artifact_id": None},
        {"location": ""},
        {"target_revision": ""},
        {"target_revision": None},
        {"content": None},
    ],
)
def test_verification_input_factory_rejects_boundary_misuse(kwargs):
    from argos_epistemic.verifiers import VerifierContractError

    base = {"artifact_id": "a", "content": "b", "location": "l",
            "target_revision": REV, "goal_aspects": ("write",)}
    with pytest.raises(VerifierContractError):
        verification_input(**{**base, **kwargs})


def test_confidence_differing_beyond_six_decimals_changes_result_id():
    """A fixed-decimal encoding merged these; binary64-exact encoding does not."""
    def a(payload):
        return [VerifierClaim(SUPPORTS, "write", "c", "v1", confidence=0.9000001)]

    def b(payload):
        return [VerifierClaim(SUPPORTS, "write", "c", "v1", confidence=0.90000012)]

    first = run_verifier(_reg(a), _payload(), execution_id="run-1")[0]
    second = run_verifier(_reg(b), _payload(), execution_id="run-1")[0]
    assert first.confidence != second.confidence
    assert first.result_id != second.result_id


def test_artifact_id_and_location_are_bound_into_result_id():
    base = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    other_id = run_verifier(
        _reg(_valid),
        verification_input("other-id", "body", "a", REV, ("write",)),
        execution_id="run-1",
    )[0]
    other_loc = run_verifier(
        _reg(_valid),
        verification_input("a", "body", "other/loc", REV, ("write",)),
        execution_id="run-1",
    )[0]
    assert base.result_id != other_id.result_id
    assert base.result_id != other_loc.result_id
    # Different results, but the same observation: they still collapse as sources.
    from argos_epistemic.verifiers import source_from_result

    assert independent_source_count(
        [source_from_result(base), source_from_result(other_loc)],
        REV, base.normalized_claim_id,
    ) == 1


def test_proposition_conversion_preserves_provenance_and_fails_closed():
    from argos_epistemic.algorithm import proposition_from_verification
    from argos_epistemic.verifiers import UNKNOWN

    result = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    prop = proposition_from_verification(result, "g")
    assert prop is not None
    assert prop.verification_result_id == result.result_id
    assert prop.verifier_family == result.verifier_family
    assert prop.verifier_version == result.verifier_version
    assert prop.execution_id == result.execution_id
    assert prop.target_revision == result.target_revision
    assert prop.root_fingerprints == result.root_fingerprints
    assert prop.claim_id == result.normalized_claim_id
    assert prop.authority_class == "direct_verification"

    def unknown(payload):
        return [VerifierClaim(UNKNOWN, "write", "c", "v1")]

    non_probative = run_verifier(_reg(unknown), _payload(), execution_id="run-1")[0]
    assert proposition_from_verification(non_probative, "g") is None


MUTABLE_BOUND_FIELDS = [
    "result_id", "verifier_family", "verifier_version", "verification_method",
    "execution_id", "target_revision", "artifact_id", "location",
    "normalized_claim_id", "outcome", "confidence",
]


@pytest.mark.parametrize("field_name", MUTABLE_BOUND_FIELDS)
def test_altered_result_cannot_become_a_proposition_or_a_source(field_name):
    """dataclasses.replace on a genuine result must not manufacture a witness."""
    import dataclasses

    from argos_epistemic.algorithm import proposition_from_verification
    from argos_epistemic.verifiers import source_from_result, validate_verification_result

    genuine = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    replacement = {
        "confidence": 0.1,
        "outcome": "refutes",
    }.get(field_name, "tampered")
    forged = dataclasses.replace(genuine, **{field_name: replacement})

    assert validate_verification_result(forged), f"{field_name} was not bound"
    assert proposition_from_verification(forged, "g") is None
    assert source_from_result(forged) is None


def test_altered_result_cannot_satisfy_min_sources():
    import dataclasses

    from argos_epistemic.algorithm import proposition_from_verification

    genuine = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    forged = dataclasses.replace(
        genuine, result_id="fake", verifier_family="other",
        execution_id="run-2", root_fingerprints=("other-root",),
    )
    props = [
        p for p in (
            proposition_from_verification(genuine, "g"),
            proposition_from_verification(forged, "g"),
        ) if p is not None
    ]
    assert len(props) == 1
    assert min_sources_met(props, ASPECTS, 2, REV) is False


@pytest.mark.parametrize("outcome", [SUPPORTS, "refutes"])
def test_zero_confidence_probative_claim_asserts_nothing(outcome):
    """Found in self-review: mirrors the strength==0 rule from PR C.

    A weightless support contributed no coverage but still counted as an
    independent source for corroboration.
    """
    from argos_epistemic.algorithm import proposition_from_verification

    def weightless(payload):
        return [VerifierClaim(outcome, "write", "c", "v1", confidence=0.0)]

    result = run_verifier(_reg(weightless), _payload(), execution_id="run-1")[0]
    assert result.outcome == DEGRADED
    assert "zero_confidence_no_effect" in result.degradations
    assert proposition_from_verification(result, "g") is None


def test_a_genuine_result_validates_and_converts():
    from argos_epistemic.verifiers import source_from_result, validate_verification_result

    genuine = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    assert validate_verification_result(genuine) == ()
    assert source_from_result(genuine) is not None


def test_registration_validates_on_construction_not_only_on_register():
    """run_verifier accepts a registration directly, so the dataclass must guard itself."""
    from argos_epistemic.verifiers import VerifierContractError

    for kwargs in (
        {"profile": None, "version": "1", "method": "deterministic"},
        {"profile": "p", "version": "", "method": "deterministic"},
        {"profile": "p", "version": "1", "method": "invented"},
    ):
        with pytest.raises(VerifierContractError):
            VerifierRegistration(verifier=lambda p: [], **kwargs)
    with pytest.raises(VerifierContractError):
        VerifierRegistration("p", "1", "deterministic", "not-callable")


@pytest.mark.parametrize(
    "bad", [None, "parent", b"parent", (7,), ("",), ("  ",), 42]
)
def test_invalid_derived_from_degrades_without_invoking_the_verifier(bad):
    """derived_from='parent' would otherwise become seven single-char dependencies."""
    calls = []

    def sentinel(payload):
        calls.append(payload)
        return [VerifierClaim(SUPPORTS, "write", "c", "v1")]

    results = run_verifier(_reg(sentinel), _payload(), execution_id="run-1", derived_from=bad)
    assert results[0].outcome == DEGRADED
    assert "invalid_derived_from" in results[0].degradations
    assert calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"goal_aspects": None},
        {"goal_aspects": (7,)},
        {"goal_aspects": "write"},
        {"goal_aspects": ("",)},
        {"extra_roots": None},
        {"extra_roots": "root"},
        {"extra_roots": (7,)},
    ],
)
def test_factory_rejects_malformed_text_collections(kwargs):
    from argos_epistemic.verifiers import VerifierContractError

    base = {"artifact_id": "a", "content": "b", "location": "l",
            "target_revision": REV, "goal_aspects": ("write",)}
    with pytest.raises(VerifierContractError):
        verification_input(**{**base, **kwargs})


def test_text_collections_are_materialised_exactly_once():
    """A generator validated and then rebuilt would be consumed and vanish."""
    payload = verification_input(
        "a", "body", "l", REV,
        (aspect for aspect in ("write",)),
        extra_roots=(root for root in ("extra-root",)),
    )
    assert payload.goal_aspects == ("write",)
    assert "extra-root" in payload.root_fingerprints
    assert root_fingerprint("body") in payload.root_fingerprints


def test_report_is_identical_under_permutation_and_duplication():
    """Full-report equality, not merely the same set of ids."""
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
        _src("c", profile="pC", version="1", execution_id="run-3", roots=("r3",)),
    ]
    base = independence_report(sources, 2, REV)
    assert independence_report(list(reversed(sources)), 2, REV) == base
    assert independence_report([*sources, *sources], 2, REV) == base
    assert independence_report([sources[1], sources[2], sources[0]], 2, REV) == base


def test_conflicting_provenance_for_one_source_id_is_excluded_not_resolved():
    """An ambiguous identity is never credited to either of its provenances."""
    conflicting = [
        _src("dup", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("dup", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
    ]
    section = independence_report(conflicting, 2, REV, "claim-1")
    assert section["conflicting_source_ids"] == ["dup"]
    # A conflicted identity is out of scope, not merely undemonstrated: it is
    # excluded entirely, so it credits nothing at all.
    assert section["independent_components"] == 0
    assert section["components"] == []


# --------------------------------------------------------------------------
# Only positive supports corroborate (P1-1)
# --------------------------------------------------------------------------


def _result(outcome, family, content, execution_id, confidence=0.9):
    def checker(payload):
        return [VerifierClaim(outcome, "write", "c", "v1", confidence=confidence)]

    return run_verifier(
        _reg(checker, profile=family),
        verification_input("a", content, "l", REV, ("write",)),
        execution_id=execution_id,
    )[0]


@pytest.mark.parametrize("outcome", ["unknown", "degraded", "refutes"])
def test_non_positive_outcomes_never_become_independent_sources(outcome):
    """Two witnesses that assert nothing positive are not corroboration.

    Integrity of the result was checked, but not its outcome, so two `unknown`
    results from different families counted as two independent sources.
    """
    from argos_epistemic.verifiers import source_from_result

    first = _result(outcome, "pA", "body-1", "run-1")
    second = _result(outcome, "pB", "body-2", "run-2")
    sources = [source_from_result(first), source_from_result(second)]
    assert sources == [None, None]
    assert independent_source_count([s for s in sources if s], REV) == 0


def test_zero_confidence_supports_never_become_independent_sources():
    from argos_epistemic.verifiers import source_from_result

    first = _result(SUPPORTS, "pA", "body-1", "run-1", confidence=0.0)
    second = _result(SUPPORTS, "pB", "body-2", "run-2", confidence=0.0)
    assert [first.outcome, second.outcome] == [DEGRADED, DEGRADED]
    sources = [source_from_result(first), source_from_result(second)]
    assert sources == [None, None]
    assert independent_source_count([s for s in sources if s], REV) == 0


def test_positive_supports_do_become_independent_sources():
    """Positive control for the outcome gate."""
    from argos_epistemic.verifiers import source_from_result

    sources = [
        source_from_result(_result(SUPPORTS, "pA", "body-1", "run-1")),
        source_from_result(_result(SUPPORTS, "pB", "body-2", "run-2")),
    ]
    assert all(s is not None for s in sources)
    assert independent_source_count(sources, REV, sources[0].normalized_claim_id) == 2


@pytest.mark.parametrize("outcome", ["unknown", "degraded", "refutes"])
def test_non_positive_outcomes_cannot_satisfy_min_sources_end_to_end(outcome):
    from argos_epistemic.algorithm import proposition_from_verification

    props = [
        proposition_from_verification(_result(outcome, "pA", "body-1", "run-1"), "g"),
        proposition_from_verification(_result(outcome, "pB", "body-2", "run-2"), "g"),
    ]
    positive = [p for p in props if p is not None and p.relation == "supports"]
    assert min_sources_met(positive, ASPECTS, 2, REV) is False


# --------------------------------------------------------------------------
# Conflicting provenance must not depend on order (P1-2)
# --------------------------------------------------------------------------


def _conflict_fixture():
    shared = _src("dup", profile="pA", version="1", execution_id="run-1", roots=("r-shared",))
    other_provenance = _src(
        "dup", profile="pB", version="1", execution_id="run-2", roots=("r-other",)
    )
    legit = _src("other", profile="pC", version="1", execution_id="run-3", roots=("r-shared",))
    return shared, other_provenance, legit


def test_conflicting_source_id_count_is_order_independent():
    """Keeping whichever provenance arrived first made the count depend on order."""
    a, b, c = _conflict_fixture()
    counts = {
        independent_source_count(order, REV)
        for order in ([a, b, c], [b, a, c], [c, a, b], [c, b, a], [a, c, b], [b, c, a])
    }
    assert len(counts) == 1, f"count varies with input order: {counts}"


def test_conflicting_provenance_never_fabricates_corroboration():
    a, b, c = _conflict_fixture()
    for order in ([a, b, c], [b, a, c], [c, b, a]):
        assert independent_source_count(order, REV) < 2


def test_report_is_identical_under_conflicting_permutations():
    a, b, c = _conflict_fixture()
    base = independence_report([a, b, c], 2, REV)
    for order in ([b, a, c], [c, a, b], [c, b, a], [a, c, b], [b, c, a]):
        assert independence_report(order, 2, REV) == base
    assert base["conflicting_source_ids"] == ["dup"]


# --------------------------------------------------------------------------
# validate_verification_result must never raise (P2-1)
# --------------------------------------------------------------------------


HOSTILE_RESULT_FIELDS = [
    ("outcome", []),
    ("outcome", None),
    ("outcome", 7),
    ("aspect", None),
    ("aspect", []),
    ("claim_text", 7),
    ("scope", None),
    ("normalized_claim_id", None),
    ("artifact_id", []),
    ("location", None),
    ("verifier_family", None),
    ("verifier_version", 1),
    ("verification_method", None),
    ("execution_id", []),
    ("target_revision", None),
    ("root_fingerprints", None),
    ("root_fingerprints", "root"),
    ("root_fingerprints", (7,)),
    ("derived_from", None),
    ("derived_from", "parent"),
    ("limitations", None),
    ("limitations", (7,)),
    ("degradations", None),
    ("confidence", "0.9"),
    ("confidence", None),
    ("confidence", True),
    ("confidence", float("nan")),
    ("confidence", float("inf")),
    ("confidence", -0.5),
    ("confidence", 1.5),
    ("result_id", None),
    ("result_id", 7),
]


@pytest.mark.parametrize("field_name,value", HOSTILE_RESULT_FIELDS)
def test_validation_fails_closed_for_hostile_field_types(field_name, value):
    """Never raises, always diagnoses, never converts into evidence."""
    import dataclasses

    from argos_epistemic.algorithm import proposition_from_verification
    from argos_epistemic.verifiers import source_from_result, validate_verification_result

    genuine = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    hostile = dataclasses.replace(genuine, **{field_name: value})

    problems = validate_verification_result(hostile)
    assert problems, f"{field_name}={value!r} was accepted"
    assert proposition_from_verification(hostile, "g") is None
    assert source_from_result(hostile) is None


def test_validation_rejects_a_non_verification_result_object():
    from argos_epistemic.verifiers import validate_verification_result

    for junk in (None, 7, "result", {}, []):
        assert validate_verification_result(junk) == ("not_a_verification_result",)


# --------------------------------------------------------------------------
# Identity binds the exact audited text (P2-2)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field_name,value",
    [("aspect", "WRITE"), ("claim_text", " declared "), ("scope", " V1 ")],
)
def test_normalisation_equivalent_text_still_changes_result_id(field_name, value):
    """The audited record must keep exact integrity, not merely claim identity."""
    import dataclasses

    from argos_epistemic.verifiers import validate_verification_result

    genuine = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    altered = dataclasses.replace(genuine, **{field_name: value})
    assert validate_verification_result(altered), f"{field_name} is not bound exactly"


# --------------------------------------------------------------------------
# Malformed IndependenceSource fails closed (P2-3)
# --------------------------------------------------------------------------


HOSTILE_SOURCE_FIELDS = [
    ("source_id", None),
    ("source_id", 7),
    ("verifier_family", None),
    ("verifier_family", 7),
    ("verifier_version", None),
    ("verification_method", None),
    ("execution_id", None),
    ("execution_id", 7),
    ("target_revision", None),
    ("root_fingerprints", None),
    ("root_fingerprints", "root"),
    ("root_fingerprints", (7,)),
    ("derived_from", None),
    ("derived_from", "parent"),
    ("independence_class", None),
    ("source_kind", None),
]


@pytest.mark.parametrize("field_name,value", HOSTILE_SOURCE_FIELDS)
def test_malformed_independence_source_never_raises_and_never_corroborates(
    field_name, value
):
    base = {
        "source_id": "s1", "source_kind": "verification_result",
        "normalized_claim_id": "c", "verifier_family": "pA", "verifier_version": "1",
        "verification_method": "deterministic", "execution_id": "run-1",
        "target_revision": REV, "root_fingerprints": ("r1",), "derived_from": (),
        "independence_class": "",
    }
    hostile = IndependenceSource(**{**base, field_name: value})
    healthy = _src("s2", profile="pB", version="1", execution_id="run-2", roots=("r2",))

    assert hostile.provenance_complete is False
    assert independent_source_count([hostile], REV) <= 1
    assert independent_source_count([hostile, healthy], REV) == 1
    section = independence_report([hostile, healthy], 2, REV)
    assert section["independent_components"] == 1
    assert independence_report([healthy, hostile], 2, REV) == section


# --------------------------------------------------------------------------
# Corroboration is per normalised claim, inside the counting boundary (P1)
# --------------------------------------------------------------------------


def _support_for(claim_text, family, content, execution_id):
    from argos_epistemic.verifiers import source_from_result

    def checker(payload):
        return [VerifierClaim(SUPPORTS, "write", claim_text, "v1")]

    result = run_verifier(
        _reg(checker, profile=family),
        verification_input("a", content, "l", REV, ("write",)),
        execution_id=execution_id,
    )[0]
    return result, source_from_result(result)


def test_sources_for_different_claims_never_sum_to_two():
    """The per-claim invariant must live inside the counting boundary.

    ``independent_source_count`` and ``independence_report`` are public API; a
    caller such as E could use them directly, so relying on ``min_sources_met``
    to group first left the defect reachable.
    """
    first, source_a = _support_for("claim uno", "pA", "b1", "run-1")
    second, source_b = _support_for("claim dos", "pB", "b2", "run-2")
    assert first.normalized_claim_id != second.normalized_claim_id

    for claim_id in (first.normalized_claim_id, second.normalized_claim_id):
        assert independent_source_count([source_a, source_b], REV, claim_id) == 1
        section = independence_report([source_a, source_b], 2, REV, claim_id)
        assert section["independent_components"] == 1
        assert section["ignored_claim_mismatch"]


def test_sources_for_different_aspects_never_sum():
    from argos_epistemic.verifiers import source_from_result

    def make(aspect, family, content, execution_id):
        def checker(payload):
            return [VerifierClaim(SUPPORTS, aspect, "same words", "v1")]

        result = run_verifier(
            _reg(checker, profile=family),
            verification_input("a", content, "l", REV, ("write", "read")),
            execution_id=execution_id,
        )[0]
        return result, source_from_result(result)

    first, source_a = make("write", "pA", "b1", "run-1")
    _second, source_b = make("read", "pB", "b2", "run-2")
    assert independent_source_count(
        [source_a, source_b], REV, first.normalized_claim_id
    ) == 1


def test_two_independent_sources_for_the_same_claim_do_count_as_two():
    """Positive control for the per-claim gate."""
    first, source_a = _support_for("same claim", "pA", "b1", "run-1")
    second, source_b = _support_for("same claim", "pB", "b2", "run-2")
    assert first.normalized_claim_id == second.normalized_claim_id
    assert independent_source_count(
        [source_a, source_b], REV, first.normalized_claim_id
    ) == 2


@pytest.mark.parametrize("claim_id", ["", "   ", None, [], 7])
def test_source_without_a_valid_claim_id_is_not_demonstrated(claim_id):
    healthy = _src("ok", profile="pA", version="1", execution_id="run-1", roots=("r1",))
    healthy = dataclasses.replace(healthy, normalized_claim_id="claim-1")
    broken = dataclasses.replace(
        _src("broken", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
        normalized_claim_id=claim_id,
    )
    assert independent_source_count([healthy, broken], REV, "claim-1") == 1


def test_absent_required_claim_fails_closed_for_min_sources_above_one():
    _first, source_a = _support_for("same claim", "pA", "b1", "run-1")
    _second, source_b = _support_for("same claim", "pB", "b2", "run-2")
    assert independent_source_count([source_a, source_b], REV, "") == 1
    assert independent_source_count([source_a, source_b], REV, None) == 1


def test_claim_and_revision_are_applied_simultaneously():
    first, source_a = _support_for("same claim", "pA", "b1", "run-1")
    _second, source_b = _support_for("same claim", "pB", "b2", "run-2")
    stale = dataclasses.replace(source_b, target_revision="rev-old")
    claim_id = first.normalized_claim_id
    assert independent_source_count([source_a, stale], REV, claim_id) == 1
    section = independence_report([source_a, stale], 2, REV, claim_id)
    assert section["ignored_revision_mismatch"] == [stale.source_id]


def test_mixed_claim_cohort_is_invariant_under_permutation_and_duplication():
    first, source_a = _support_for("claim uno", "pA", "b1", "run-1")
    _second, source_b = _support_for("claim dos", "pB", "b2", "run-2")
    _third, source_c = _support_for("claim uno", "pC", "b3", "run-3")
    claim_id = first.normalized_claim_id
    cohort = [source_a, source_b, source_c]
    base = independence_report(cohort, 2, REV, claim_id)
    for order in ([source_c, source_b, source_a], [source_b, source_a, source_c]):
        assert independence_report(order, 2, REV, claim_id) == base
    assert independence_report([*cohort, *cohort], 2, REV, claim_id) == base
    assert base["independent_components"] == 2


def test_min_sources_met_receives_unfiltered_propositions_including_refutes():
    """The gate itself must exclude refutes; the test must not pre-filter."""
    from argos_epistemic.algorithm import proposition_from_verification

    def refuter(payload):
        return [VerifierClaim("refutes", "write", "same claim", "v1")]

    supporting, _ = _support_for("same claim", "pA", "b1", "run-1")
    refuting = run_verifier(
        _reg(refuter, profile="pB"),
        verification_input("a", "b2", "l", REV, ("write",)),
        execution_id="run-2",
    )[0]
    everything = [
        proposition_from_verification(supporting, "g"),
        proposition_from_verification(refuting, "g"),
    ]
    assert all(p is not None for p in everything)
    assert {p.relation for p in everything} == {"supports", "refutes"}
    assert min_sources_met(everything, ASPECTS, 2, REV) is False


# --------------------------------------------------------------------------
# Mandatory scope constraints must never be reinterpreted as "no filter"
# --------------------------------------------------------------------------

INVALID_CONSTRAINTS = [None, "", "   ", "\t", 0, 7, True, False, [], {}, b"x", object(), ()]


def _two_independent(claim="claim-a", revision=REV):
    shared = {
        "source_kind": "verification_result", "normalized_claim_id": claim,
        "verifier_version": "1", "verification_method": "deterministic",
        "derived_from": (), "independence_class": "",
    }
    return [
        IndependenceSource("a", verifier_family="pA", execution_id="r1",
                           target_revision=revision, root_fingerprints=("x",), **shared),
        IndependenceSource("b", verifier_family="pB", execution_id="r2",
                           target_revision=revision, root_fingerprints=("y",), **shared),
    ]


@pytest.mark.parametrize("revision", INVALID_CONSTRAINTS)
def test_invalid_target_revision_can_never_demonstrate_more_than_one_source(revision):
    """A truthy-but-invalid revision passed the truthiness guard and then removed
    the filter entirely, crediting every revision at once."""
    sources = _two_independent()
    assert independent_source_count(sources, revision, "claim-a") <= 1
    section = independence_report(sources, 2, revision, "claim-a")
    assert section["independent_components"] <= 1
    assert section["components"] == []
    assert section["evaluated_target_revision"] == ""


@pytest.mark.parametrize("claim", INVALID_CONSTRAINTS)
def test_invalid_claim_can_never_demonstrate_more_than_one_source(claim):
    sources = _two_independent()
    assert independent_source_count(sources, REV, claim) <= 1
    section = independence_report(sources, 2, REV, claim)
    assert section["independent_components"] <= 1
    assert section["components"] == []
    assert section["evaluated_normalized_claim_id"] == ""


def test_a_different_textual_revision_produces_mismatch_not_a_disabled_filter():
    sources = _two_independent(revision="rev-other")
    assert independent_source_count(sources, REV, "claim-a") == 0
    section = independence_report(sources, 2, REV, "claim-a")
    assert sorted(section["ignored_revision_mismatch"]) == ["a", "b"]
    assert section["components"] == []


def test_valid_revision_with_invalid_claim_fails_closed():
    assert independent_source_count(_two_independent(), REV, 7) <= 1


def test_valid_claim_with_invalid_revision_fails_closed():
    assert independent_source_count(_two_independent(), "   ", "claim-a") <= 1


def test_report_never_publishes_more_components_than_it_counted():
    """The count and the components must come from one prepared view."""
    sources = _two_independent()
    for revision, claim in (
        ("", "claim-a"), (REV, None), ("", None), ("   ", "claim-a"), (REV, "   "),
        (7, "claim-a"), (REV, 7), (REV, "claim-a"),
    ):
        section = independence_report(sources, 2, revision, claim)
        count = section["independent_components"]
        assert len(section["components"]) <= count
        if count == 0:
            assert section["components"] == []


# One representative per equivalence class: missing, empty, blank, falsy
# non-string, truthy non-string, boolean, container, arbitrary object, and the
# three textual values that actually matter. The full 16-value list was
# redundant and quadrupled suite runtime for no additional coverage.
CONSTRAINT_VALUES = [
    None, "", "   ", 0, 7, True, [], object(), REV, "another-revision", "claim-a",
]


@pytest.mark.parametrize("revision", CONSTRAINT_VALUES)
@pytest.mark.parametrize("claim", CONSTRAINT_VALUES)
def test_constraint_matrix_is_total_across_all_three_public_apis(revision, claim):
    """Cartesian hostility over the CONSTRAINT arguments, not only the sources.

    All three APIs must share one behaviour: never raise, never overcount
    without a scope, and never publish more components than were counted.
    """
    sources = _two_independent()

    assert isinstance(independence_groups(sources, revision, claim), list)
    count = independent_source_count(sources, revision, claim)
    section = independence_report(sources, 2, revision, claim)

    assert section["independent_components"] == count
    assert len(section["components"]) <= count
    if count == 0:
        assert section["components"] == []
    scoped = (
        isinstance(revision, str) and revision.strip()
        and isinstance(claim, str) and claim.strip()
    )
    if not scoped:
        assert count <= 1, "corroboration without a valid scope"
        assert section["components"] == []
    assert independence_report(list(reversed(sources)), 2, revision, claim) == section
    assert independence_report([*sources, *sources], 2, revision, claim) == section


def test_missing_scope_constraints_are_reported_explicitly():
    sources = _two_independent()
    for revision, claim, expected in (
        ("", "claim-a", ["missing_or_invalid_target_revision"]),
        (REV, None, ["missing_or_invalid_normalized_claim_id"]),
        ("", None, ["missing_or_invalid_normalized_claim_id",
                    "missing_or_invalid_target_revision"]),
        (REV, "claim-a", []),
    ):
        section = independence_report(sources, 2, revision, claim)
        assert sorted(section["missing_scope_constraints"]) == sorted(expected)


def test_two_valid_independent_sources_still_count_and_are_explained():
    sources = _two_independent()
    section = independence_report(sources, 2, REV, "claim-a")
    assert section["independent_components"] == 2
    assert len(section["components"]) == 2
    assert section["missing_scope_constraints"] == []


@pytest.mark.parametrize(
    "revision,claim",
    [("", "claim-a"), (REV, None), ("", None), ("   ", 7), (REV, "claim-a")],
)
def test_report_is_invariant_under_permutation_and_duplication_for_any_constraints(
    revision, claim
):
    sources = _two_independent()
    base = independence_report(sources, 2, revision, claim)
    assert independence_report(list(reversed(sources)), 2, revision, claim) == base
    assert independence_report([*sources, *sources], 2, revision, claim) == base


# --------------------------------------------------------------------------
# Canonicalisation must be total: no recursion into arbitrary containers
# --------------------------------------------------------------------------


def _cyclic_list():
    cycle: list = []
    cycle.append(cycle)
    return cycle


@pytest.mark.parametrize(
    "collection",
    [
        _cyclic_list(),
        [[[[[[[[[["deep"]]]]]]]]]],
        [("nested",)],
        [{"a": 1}],
        [[]],
    ],
)
@pytest.mark.parametrize("field_name", ["root_fingerprints", "derived_from"])
def test_cyclic_or_nested_collections_fail_closed_without_recursion(
    field_name, collection
):
    """Contract collections are flat tuples of strings; recursing into arbitrary
    containers turned a self-referential list into a RecursionError."""
    source = dataclasses.replace(_scoped("h"), **{field_name: collection})
    assert isinstance(independence_groups([source]), list)
    count = independent_source_count([source], REV, "claim-a")
    assert count <= 1
    section = independence_report([source], 2, REV, "claim-a")
    assert section["independent_components"] == count
    assert independence_report([source, source], 2, REV, "claim-a") == section


def test_cyclic_collection_contributes_no_component():
    source = dataclasses.replace(_scoped("h"), root_fingerprints=_cyclic_list())
    healthy = _scoped("ok", verifier_family="pB", execution_id="run-2",
                      root_fingerprints=("r2",))
    assert independent_source_count([source, healthy], REV, "claim-a") == 1


# --------------------------------------------------------------------------
# The conservative floor must not credit out-of-scope evidence
# --------------------------------------------------------------------------


def _scoped(source_id, **overrides):
    base = _src(source_id, profile="pA", version="1", execution_id="run-1", roots=("r1",))
    fields = {"normalized_claim_id": "claim-a"}
    fields.update(overrides)
    return dataclasses.replace(base, **fields)


def test_cohort_of_only_foreign_claims_counts_zero():
    """Ignoring a source must not also credit it."""
    foreign = _scoped("x", normalized_claim_id="claim-b")
    assert independent_source_count([foreign], REV, "claim-a") == 0
    section = independence_report([foreign], 2, REV, "claim-a")
    assert section["independent_components"] == 0
    assert section["components"] == []
    assert section["ignored_claim_mismatch"] == ["x"]


def test_cohort_of_only_stale_revisions_counts_zero():
    stale = _scoped("y", target_revision="rev-old")
    assert independent_source_count([stale], REV, "claim-a") == 0
    section = independence_report([stale], 2, REV, "claim-a")
    assert section["independent_components"] == 0
    assert section["components"] == []


def test_cohort_of_only_invalid_entries_counts_zero():
    for junk in ({"junk": 1}, None, 7, "source"):
        assert independent_source_count([junk], REV, "claim-a") == 0


def test_cohort_of_only_conflicting_identities_counts_zero():
    a = _scoped("dup", verifier_family="pA", execution_id="run-1")
    b = _scoped("dup", verifier_family="pB", execution_id="run-2")
    assert independent_source_count([a, b], REV, "claim-a") == 0


def test_floor_of_one_survives_for_in_scope_but_undemonstrated_evidence():
    """The floor exists for evidence that IS in scope yet cannot prove independence."""
    in_scope_incomplete = _scoped("z", execution_id="")
    assert in_scope_incomplete.provenance_complete is False
    assert independent_source_count([in_scope_incomplete], REV, "claim-a") == 1
    section = independence_report([in_scope_incomplete], 2, REV, "claim-a")
    assert section["independent_components"] == 1
    assert section["sources_with_incomplete_provenance"] == ["z"]


def test_min_sources_one_is_not_satisfied_by_stale_evidence_alone():
    stale = Proposition(
        aspect="write", polarity=1.0, claim="c", evidence_id="e", confidence=0.9,
        method="symbolic", scope="write", relation="supports", claim_id="claim-a",
        claim_text="c", verification_result_id="vr", verifier_family="pA",
        verifier_version="1", verification_method_profile="deterministic",
        execution_id="run-1", target_revision="rev-old", root_fingerprints=("r1",),
    )
    assert min_sources_met([stale], ASPECTS, 1, REV) is False


def test_report_count_and_components_stay_semantically_coherent():
    """A non-zero count must be explained by at least one component or by
    in-scope incomplete provenance - never by evidence that was ignored."""
    for cohort in (
        [_scoped("a", normalized_claim_id="claim-b")],
        [_scoped("b", target_revision="rev-old")],
        [_scoped("c", execution_id="")],
        [_scoped("d")],
    ):
        section = independence_report(cohort, 2, REV, "claim-a")
        count = section["independent_components"]
        if count == 0:
            assert section["components"] == []
        elif not section["components"]:
            assert section["sources_with_incomplete_provenance"]


# --------------------------------------------------------------------------
# Untrusted equality must never be executed (P2a)
# --------------------------------------------------------------------------


class _HostileEquality(IndependenceSource):
    def __eq__(self, other):
        raise RuntimeError("__eq__ must never be called on unvalidated input")

    def __hash__(self):
        return 1


class _NonBoolEquality(IndependenceSource):
    def __eq__(self, other):
        return "not a bool"

    def __hash__(self):
        return 2


@pytest.mark.parametrize("hostile_type", [_HostileEquality, _NonBoolEquality])
def test_independence_apis_never_invoke_untrusted_equality(hostile_type):
    fields = {
        "source_kind": "verification_result", "normalized_claim_id": "claim-a",
        "verifier_family": "pA", "verifier_version": "1",
        "verification_method": "deterministic", "execution_id": "run-1",
        "target_revision": REV, "root_fingerprints": ("r1",), "derived_from": (),
        "independence_class": "",
    }
    first = hostile_type("h1", **fields)
    second = hostile_type("h2", **{**fields, "verifier_family": "pB",
                                   "execution_id": "run-2", "root_fingerprints": ("r2",)})
    cohort = [first, second]
    assert isinstance(independence_groups(cohort), list)
    count = independent_source_count(cohort, REV, "claim-a")
    section = independence_report(cohort, 2, REV, "claim-a")
    assert section["independent_components"] == count
    assert independence_report(list(reversed(cohort)), 2, REV, "claim-a") == section


@pytest.mark.parametrize("field_name", ["target_revision", "normalized_claim_id"])
def test_scope_comparison_never_invokes_untrusted_equality(field_name):
    """Found in self-review: the revision comparison dispatched to caller __eq__."""
    class _Bomb:
        def __eq__(self, other):
            raise RuntimeError("boom")

        def __hash__(self):
            return 9

    source = dataclasses.replace(_scoped("s"), **{field_name: _Bomb()})
    assert independent_source_count([source], REV, "claim-a") == 0
    assert isinstance(independence_groups([source]), list)
    section = independence_report([source], 2, REV, "claim-a")
    assert section["independent_components"] == 0


def test_hostile_equality_inside_a_collection_field_is_also_safe():
    class _Bomb:
        def __eq__(self, other):
            raise RuntimeError("boom")

        def __hash__(self):
            return 3

    source = dataclasses.replace(_scoped("s"), root_fingerprints=(_Bomb(),))
    # In scope for the claim and revision, but its roots are unusable, so it is
    # undemonstrated evidence: the conservative floor, never corroboration.
    assert independent_source_count([source], REV, "claim-a") == 1
    assert isinstance(independence_groups([source]), list)


# --------------------------------------------------------------------------
# components_by_revision stays within the evaluated claim (P2b)
# --------------------------------------------------------------------------


def test_components_by_revision_does_not_readmit_other_claims():
    foreign = _scoped("x", normalized_claim_id="claim-b")
    section = independence_report([foreign], 2, REV, "claim-a")
    assert section["ignored_claim_mismatch"] == ["x"]
    assert section["components_by_revision"] == {}, (
        "a source ignored for claim mismatch must not reappear in the per-revision view"
    )


def test_components_by_revision_still_spans_revisions_for_the_evaluated_claim():
    current = _scoped("cur")
    stale = _scoped("old", target_revision="rev-old",
                    verifier_family="pB", execution_id="run-2", root_fingerprints=("r2",))
    section = independence_report([current, stale], 2, REV, "claim-a")
    assert section["components_by_revision"] == {"rev-1": 1, "rev-old": 1}
    assert section["ignored_revision_mismatch"] == ["old"]


# --------------------------------------------------------------------------
# Full cartesian hostility across every independence boundary (P2)
# --------------------------------------------------------------------------

HOSTILE_VALUES = [None, [], {}, 7, True, b"x", object(), set(), "", "   "]

SOURCE_FIELDS = [
    "source_id", "source_kind", "normalized_claim_id", "verifier_family",
    "verifier_version", "verification_method", "execution_id", "target_revision",
    "root_fingerprints", "derived_from", "independence_class",
]


@pytest.mark.parametrize("field_name", SOURCE_FIELDS)
@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_every_independence_boundary_survives_every_hostile_value(field_name, value):
    """A real cartesian product. The selected-pairs matrix let source_id=[] escape."""
    healthy = dataclasses.replace(
        _src("healthy", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        normalized_claim_id="claim-1",
    )
    overrides = {"normalized_claim_id": "claim-1"}
    overrides[field_name] = value
    hostile = dataclasses.replace(
        _src("hostile", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
        **overrides,
    )
    cohort = [healthy, hostile]

    # 1. No public entry point may raise.
    assert isinstance(independence_groups(cohort), list)
    count = independent_source_count(cohort, REV, "claim-1")
    section = independence_report(cohort, 2, REV, "claim-1")

    # 2. The report agrees with the count and is permutation-invariant.
    assert section["independent_components"] == count
    assert independence_report(list(reversed(cohort)), 2, REV, "claim-1") == section
    assert independence_report([*cohort, *cohort], 2, REV, "claim-1") == section

    # 3. Corroboration only when the hostile source is genuinely usable: a value
    #    that leaves the record well-formed (an empty optional label) may still
    #    corroborate; anything that breaks provenance or the claim may not.
    usable = hostile.provenance_complete and hostile.normalized_claim_id == "claim-1"
    assert count == (2 if usable else 1)


@pytest.mark.parametrize("value", HOSTILE_VALUES)
def test_independence_groups_never_raises_for_a_hostile_source_id(value):
    source = IndependenceSource(source_id=value)
    assert independence_groups([source]) == [] or all(
        isinstance(group, list) for group in independence_groups([source])
    )


def test_component_ids_are_stable_under_input_reordering():
    sources = [
        _src("a", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("b", profile="pB", version="1", execution_id="run-2", roots=("r2",)),
    ]
    forward = independence_report(sources, 2, REV)
    backward = independence_report(list(reversed(sources)), 2, REV)
    assert {c["component_id"] for c in forward["components"]} == {
        c["component_id"] for c in backward["components"]
    }


def test_report_distinguishes_verification_results_from_legacy_evidence():
    sources = [
        _src("vr-1", profile="pA", version="1", execution_id="run-1", roots=("r1",)),
        _src("legacy-1", profile="pB", version="1", execution_id="run-2", roots=("r2",),
             source_kind="legacy_evidence"),
    ]
    section = independence_report(sources, 2, REV, "claim-1")
    ids = {
        "results": [i for c in section["components"] for i in c["verification_result_ids"]],
        "legacy": [i for c in section["components"] for i in c["legacy_evidence_ids"]],
    }
    assert ids["results"] == ["vr-1"]
    assert ids["legacy"] == ["legacy-1"]


def test_same_input_and_profile_produce_identical_output():
    first = run_verifier(_reg(_valid), _payload(), execution_id="run-1")
    second = run_verifier(_reg(_valid), _payload(), execution_id="run-1")
    assert first == second
    assert first[0].result_id == second[0].result_id


def test_result_id_binds_every_field_affecting_identity_or_independence():
    base = run_verifier(_reg(_valid), _payload(), execution_id="run-1")[0]
    mutations = {
        "content": run_verifier(_reg(_valid), _payload(content="other"), execution_id="run-1"),
        "revision": run_verifier(_reg(_valid), _payload(revision="rev-2"), execution_id="run-1"),
        "execution": run_verifier(_reg(_valid), _payload(), execution_id="run-2"),
        "profile": run_verifier(_reg(_valid, profile="other"), _payload(), execution_id="run-1"),
        "version": run_verifier(_reg(_valid, version="2"), _payload(), execution_id="run-1"),
        "method": run_verifier(
            _reg(_valid, method="symbolic-rule"), _payload(), execution_id="run-1"
        ),
        "derived_from": run_verifier(
            _reg(_valid), _payload(), execution_id="run-1", derived_from=("parent",)
        ),
    }
    for name, results in mutations.items():
        assert results[0].result_id != base.result_id, f"{name} did not change result_id"


def test_verifier_cannot_forge_provenance_fields():
    results = run_verifier(_reg(_valid, profile="honest", version="2"), _payload(),
                           execution_id="run-9")
    result = results[0]
    assert result.verifier_family == "honest"
    assert result.verifier_version == "2"
    assert result.versioned_profile == "honest@2"
    assert result.execution_id == "run-9"
    assert result.target_revision == REV
    assert result.root_fingerprints == (root_fingerprint("body"),)
    assert "execution_id" not in VerifierClaim.__dataclass_fields__
    assert "verifier_profile" not in VerifierClaim.__dataclass_fields__
    assert "root_fingerprints" not in VerifierClaim.__dataclass_fields__


def test_tampering_with_evidence_changes_the_root_fingerprint():
    assert root_fingerprint("original body") != root_fingerprint("original body ")


def test_claim_normalisation_folds_case_and_whitespace_but_not_scope():
    a = normalized_claim_id("write", "  Writes  use   CAS ", "v1")
    b = normalized_claim_id("write", "writes use cas", "V1")
    c = normalized_claim_id("write", "writes use cas", "v2")
    d = normalized_claim_id("write", "compare-and-swap is used for writes", "v1")
    assert a == b
    assert a != c
    # Shallow normalisation does NOT prove semantic equivalence.
    assert a != d


def test_registry_is_explicit_versioned_and_deterministically_ordered():
    from argos_epistemic.verifiers import (
        register_verifier,
        registered_verifiers,
        unregister_verifier,
    )

    def noop(payload):
        return []

    try:
        register_verifier("zeta", "1", "deterministic", noop)
        register_verifier("alpha", "1", "deterministic", noop)
        profiles = [r.profile for r in registered_verifiers()]
        assert profiles == sorted(profiles)
        with pytest.raises(ValueError, match="already registered"):
            register_verifier("alpha", "1", "deterministic", noop)
        with pytest.raises(ValueError, match="unsupported verification method"):
            register_verifier("beta", "1", "telepathy", noop)
    finally:
        unregister_verifier("zeta", "1")
        unregister_verifier("alpha", "1")
