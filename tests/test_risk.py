"""Property tests for residual risk (plan §3.2 invariants, §5.2, §6.2 matrix).

These encode the non-negotiable invariants BEFORE any particular formula, so a
recalibration that breaks them fails here rather than silently shipping.
"""

from argos_epistemic.algorithm import Proposition, compute_residual_risk

ASPECT = [{"name": "write", "weight": 1.0}]
TWO_ASPECTS = [{"name": "write", "weight": 0.5}, {"name": "read", "weight": 0.5}]


def _p(aspect, relation, *, claim="c1", scope=None, evidence_id="e1"):
    polarity = {"supports": 1.0, "refutes": -1.0}.get(relation, 0.0)
    scope = aspect if scope is None else scope
    return Proposition(
        aspect=aspect,
        polarity=polarity,
        claim=claim,
        evidence_id=evidence_id,
        confidence=0.9,
        method="symbolic",
        scope=scope,
        relation=relation,
        claim_id=f"claim:{aspect}:{claim}:{scope}",
        claim_text=claim,
    )


def test_no_required_aspect_supported_means_maximum_risk():
    """§3.2.1 + §5.2: missing_share=1 implies risk=1, unconditionally."""
    assert compute_residual_risk([], ASPECT, {}) == 1.0
    # Support exists, but for an aspect the goal never asked about: the required
    # aspect is still wholly unsupported, so risk must stay maximal.
    off_goal = [_p("unrelated", "supports")]
    assert compute_residual_risk(off_goal, ASPECT, {}) == 1.0


def test_mentions_only_scores_the_same_as_no_evidence():
    """§6.2 row 'sólo mentions': retrieval without proof is not progress."""
    mentions = [_p("write", "mentions", evidence_id=f"m{i}") for i in range(5)]
    assert compute_residual_risk(mentions, ASPECT, {}) == 1.0


def test_mentions_plus_refutes_is_still_maximum_risk():
    """§6.2 row 'mentions + refutes'."""
    props = [_p("write", "mentions", evidence_id="m1"), _p("write", "refutes")]
    assert compute_residual_risk(props, ASPECT, {}) == 1.0


def test_duplicating_a_mention_does_not_change_the_score():
    """§5.2 acceptance criterion."""
    base = [_p("write", "supports"), _p("write", "mentions", evidence_id="m1")]
    once = compute_residual_risk(base, ASPECT, {})
    duplicated = compute_residual_risk(
        [*base, _p("write", "mentions", evidence_id="m1")], ASPECT, {}
    )
    assert duplicated == once


def test_adding_mentions_never_reduces_risk():
    """§3.2.2, as a property over increasing volumes of thematic noise."""
    base = [_p("write", "supports")]
    baseline = compute_residual_risk(base, TWO_ASPECTS, {})
    noise = list(base)
    for i in range(20):
        noise.append(_p("read", "mentions", evidence_id=f"m{i}"))
        assert compute_residual_risk(noise, TWO_ASPECTS, {}) >= baseline


def test_adding_mentions_never_dilutes_a_refutation():
    """§3.2.3: thematic volume must not wash out negative evidence."""
    contested = [_p("write", "supports"), _p("write", "refutes", evidence_id="r1")]
    baseline = compute_residual_risk(contested, ASPECT, {})
    flooded = [*contested] + [
        _p("write", "mentions", evidence_id=f"m{i}") for i in range(50)
    ]
    assert compute_residual_risk(flooded, ASPECT, {}) == baseline


def test_adding_a_refutation_never_reduces_risk():
    """§3.2.4, including the case where the refutation opens a NEW claim.

    A naive contradicted/total ratio breaks here: a refutation on a fresh claim
    grows the denominator and can lower the share. Risk must be monotonic
    regardless of which claim the refutation lands on.
    """
    cases = [
        [_p("write", "supports")],
        [_p("write", "supports"), _p("write", "refutes", evidence_id="r0")],
        [_p("write", "supports"), _p("read", "supports", claim="c2")],
    ]
    for base in cases:
        before = compute_residual_risk(base, TWO_ASPECTS, {})
        for new in (
            _p("write", "refutes", evidence_id="rx"),
            _p("read", "refutes", claim="c9", evidence_id="ry"),
        ):
            after = compute_residual_risk([*base, new], TWO_ASPECTS, {})
            assert after >= before, f"refutation reduced risk: {before} -> {after}"


def test_only_positive_support_reduces_the_missing_component():
    """§3.2.5: neither mentions nor refutations may mark an aspect covered."""
    unsupported = [
        _p("write", "mentions", evidence_id="m1"),
        _p("write", "refutes", evidence_id="r1"),
    ]
    assert compute_residual_risk(unsupported, ASPECT, {}) == 1.0
    assert compute_residual_risk([_p("write", "supports")], ASPECT, {}) < 1.0


def test_risk_aggregates_by_claim_not_by_proposition_volume():
    """§3.2.6 + plan §5.2: duplicates must not multiply or dilute risk.

    Ten corroborating readings of the SAME claim are one claim, not ten. If the
    contradiction share were computed over raw propositions, piling on
    duplicate supports would bury the refutation.
    """
    contested = [
        _p("write", "supports", evidence_id="s1"),
        _p("write", "refutes", evidence_id="r1"),
    ]
    baseline = compute_residual_risk(contested, ASPECT, {})
    padded = [*contested] + [
        _p("write", "supports", evidence_id=f"s{i}") for i in range(2, 12)
    ]
    assert compute_residual_risk(padded, ASPECT, {}) == baseline


def test_support_plus_contradiction_increases_risk_over_clean_support():
    """§6.2 row 'soporte + contradicción': riesgo aumentado."""
    clean = compute_residual_risk([_p("write", "supports")], ASPECT, {})
    contested = compute_residual_risk(
        [_p("write", "supports"), _p("write", "refutes", evidence_id="r1")], ASPECT, {}
    )
    assert contested > clean


def test_off_goal_evidence_cannot_move_the_risk_at_all():
    """Mandated regression: only required aspects participate in the score."""
    supported = [_p("write", "supports")]
    assert compute_residual_risk(supported, ASPECT, {}) == 0.0
    # A refutation about something the goal never asked about must leave a
    # fully-supported goal at exactly zero, not merely "close to" zero.
    with_off_goal = [*supported, _p("telemetry", "refutes", claim="c9", evidence_id="r9")]
    assert compute_residual_risk(with_off_goal, ASPECT, {}) == 0.0


def test_off_goal_support_cannot_cover_a_required_aspect():
    """Adversarial: off-goal supports must not sneak past the missing term."""
    off_goal_only = [_p("telemetry", "supports", claim="c9")]
    assert compute_residual_risk(off_goal_only, ASPECT, {}) == 1.0


def test_off_goal_refutation_cannot_dilute_an_in_goal_contradiction():
    """Adversarial: padding the denominator from outside the goal is refused."""
    contested = [
        _p("write", "supports", evidence_id="s1"),
        _p("write", "refutes", evidence_id="r1"),
    ]
    baseline = compute_residual_risk(contested, ASPECT, {})
    padded = [*contested] + [
        _p("telemetry", "supports", claim=f"c{i}", evidence_id=f"o{i}") for i in range(20)
    ]
    assert compute_residual_risk(padded, ASPECT, {}) == baseline


def test_partial_coverage_lands_between_the_extremes():
    """Adversarial: two required aspects, one supported, must not read as 0 or 1."""
    half = [_p("write", "supports")]
    risk = compute_residual_risk(half, TWO_ASPECTS, {})
    assert 0.0 < risk < 1.0
    assert risk == 0.5


def test_claim_identity_falls_back_when_claim_id_is_absent():
    """Adversarial: propositions without claim_id must still dedupe by content."""
    bare = [
        Proposition(
            aspect="write",
            polarity=1.0,
            claim="same claim",
            evidence_id=f"e{i}",
            confidence=0.9,
            method="symbolic",
            scope="write",
            relation="supports",
        )
        for i in range(5)
    ]
    contested = [
        *bare,
        Proposition(
            aspect="write",
            polarity=-1.0,
            claim="same claim",
            evidence_id="r1",
            confidence=0.9,
            method="symbolic",
            scope="write",
            relation="refutes",
        ),
    ]
    # One claim, contradicted: five duplicate readings must not dilute it.
    assert compute_residual_risk(contested, ASPECT, {}) == 1.0


def test_risk_stays_within_unit_interval():
    props = [
        _p("write", "supports"),
        _p("write", "refutes", evidence_id="r1"),
        _p("read", "refutes", claim="c2", evidence_id="r2"),
        _p("read", "mentions", claim="c3", evidence_id="m1"),
    ]
    assert 0.0 <= compute_residual_risk(props, TWO_ASPECTS, {}) <= 1.0
