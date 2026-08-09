"""Contract tests for the PEP 621 / PEP 508 dependency verifiers (PR E).

The claim under test is deliberately narrow: "the repository declares
dependency X under constraint Y for scope Z at revision R." No test here may
assert that a dependency is installed, importable, resolvable or functional -
only declaration is checked.
"""


import pytest

from argos_epistemic.algorithm import proposition_from_verification
from argos_epistemic.dependency_verifiers import (
    DependencyTarget,
    looks_pip_compile_generated_from,
    make_pep508_verifier,
    make_pep621_verifier,
    parse_pyproject_dependencies,
    parse_requirements_txt,
)
from argos_epistemic.verifiers import (
    DEGRADED,
    REFUTES,
    SUPPORTS,
    UNKNOWN,
    VerifierRegistration,
    independent_source_count,
    root_fingerprint,
    run_verifier,
    source_from_result,
    verification_input,
)

REV = "rev-1"


def _pep621(content, target, execution_id="run-pep621", revision=REV, derived_from=()):
    reg = VerifierRegistration("pep621-dependencies", "1", "deterministic",
                               make_pep621_verifier(target), "")
    payload = verification_input("pyproject.toml", content, "pyproject.toml", revision,
                                 (target.canonical_name,))
    return run_verifier(reg, payload, execution_id, derived_from)[0]


def _pep508(content, target, execution_id="run-pep508", revision=REV, derived_from=()):
    reg = VerifierRegistration("pep508-requirements", "1", "deterministic",
                               make_pep508_verifier(target), "")
    payload = verification_input("requirements.txt", content, "requirements.txt", revision,
                                 (target.canonical_name,))
    return run_verifier(reg, payload, execution_id, derived_from)[0]


PYPROJECT_BASIC = """
[project]
name = "demo"
dependencies = ["requests>=2.0"]

[project.optional-dependencies]
test = ["pytest>=8"]
"""

REQUIREMENTS_BASIC = "requests>=2.0\n"


# --------------------------------------------------------------------------
# 1. Equivalent, valid dependency in both files -> corroboration
# --------------------------------------------------------------------------


def test_matching_dependency_in_both_files_produces_two_independent_supports():
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    r1 = _pep621(PYPROJECT_BASIC, target, execution_id="run-1")
    r2 = _pep508(REQUIREMENTS_BASIC, target, execution_id="run-2")
    assert r1.outcome == r2.outcome == SUPPORTS
    assert r1.normalized_claim_id == r2.normalized_claim_id

    sources = [source_from_result(r1), source_from_result(r2)]
    assert all(s is not None for s in sources)
    assert independent_source_count(sources, REV, r1.normalized_claim_id) == 2

    props = [proposition_from_verification(r1, "g"), proposition_from_verification(r2, "g")]
    assert all(p is not None for p in props)
    from argos_epistemic.algorithm import min_sources_met

    assert min_sources_met(props, [{"name": "requests", "weight": 1.0}], 2, REV) is True


# --------------------------------------------------------------------------
# 2. Different specifiers -> distinct claims, never corroboration
# --------------------------------------------------------------------------


def test_different_specifiers_produce_distinct_claim_ids():
    a = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    b = DependencyTarget(name="requests", specifier=">=3.0", scope="core")
    r_a = _pep621(PYPROJECT_BASIC, a)
    r_b = _pep621(PYPROJECT_BASIC, b)
    assert r_a.outcome == SUPPORTS
    assert r_b.outcome == REFUTES  # same name+scope, contradicting specifier
    assert r_a.normalized_claim_id != r_b.normalized_claim_id


def test_conflicting_specifier_in_same_scope_is_refutes_not_support():
    target = DependencyTarget(name="requests", specifier=">=3.0", scope="core")
    result = _pep621(PYPROJECT_BASIC, target)
    assert result.outcome == REFUTES
    assert result.is_probative
    prop = proposition_from_verification(result, "g")
    assert prop is not None
    assert prop.relation == "refutes"


# --------------------------------------------------------------------------
# 3. Different marker -> different claim
# --------------------------------------------------------------------------


def test_different_marker_produces_distinct_claim():
    plain = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    marked = DependencyTarget(
        name="requests", specifier=">=2.0", marker='python_version >= "3.9"', scope="core"
    )
    assert plain.claim_text() != marked.claim_text()
    r_plain = _pep621(PYPROJECT_BASIC, plain)
    r_marked = _pep621(PYPROJECT_BASIC, marked)
    assert r_plain.outcome == SUPPORTS
    assert r_marked.outcome == REFUTES
    assert r_plain.normalized_claim_id != r_marked.normalized_claim_id


# --------------------------------------------------------------------------
# 4. Different extra -> different scope, no automatic corroboration
# --------------------------------------------------------------------------


def test_optional_dependency_scope_does_not_corroborate_core():
    core_target = DependencyTarget(name="pytest", specifier=">=8", scope="core")
    extra_target = DependencyTarget(name="pytest", specifier=">=8", scope="extra:test")
    r_core = _pep621(PYPROJECT_BASIC, core_target)
    r_extra = _pep621(PYPROJECT_BASIC, extra_target)
    assert r_core.outcome == UNKNOWN  # pytest is not in core dependencies
    assert r_extra.outcome == SUPPORTS
    assert r_core.normalized_claim_id != r_extra.normalized_claim_id


def test_optional_dependency_vs_central_dependency():
    """5. Optional dependency vs core: distinguishing the two is the point."""
    optional = DependencyTarget(name="requests", specifier=">=2.0", scope="extra:test")
    result = _pep621(PYPROJECT_BASIC, optional)
    # requests is declared in core, NOT under the "test" extra.
    assert result.outcome == UNKNOWN


# --------------------------------------------------------------------------
# 6. project.dynamic dependencies
# --------------------------------------------------------------------------


PYPROJECT_DYNAMIC = """
[project]
name = "demo"
dynamic = ["dependencies"]
"""


def test_dynamic_dependencies_never_produce_refutes():
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    result = _pep621(PYPROJECT_DYNAMIC, target)
    assert result.outcome == UNKNOWN
    assert "dependencies_declared_dynamic" in result.limitations


def test_dynamic_and_static_conflict_is_diagnosed():
    conflicting = """
[project]
name = "demo"
dynamic = ["dependencies"]
dependencies = ["requests>=2.0"]
"""
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    result = _pep621(conflicting, target)
    assert result.outcome != SUPPORTS
    assert "dynamic_and_static_conflict" in result.limitations


# --------------------------------------------------------------------------
# 7. TOML invalid
# --------------------------------------------------------------------------


def test_invalid_toml_degrades():
    target = DependencyTarget(name="requests", scope="core")
    result = _pep621("[project\nbroken = ", target)
    assert result.outcome == DEGRADED
    assert "toml_parse_error" in result.limitations


def test_missing_project_table_degrades():
    target = DependencyTarget(name="requests", scope="core")
    result = _pep621("[tool.other]\nx = 1\n", target)
    assert result.outcome == DEGRADED
    assert "missing_project_table" in result.limitations


# --------------------------------------------------------------------------
# 8. Invalid PEP 621 dependency types
# --------------------------------------------------------------------------


def test_non_list_dependencies_is_diagnosed_not_raised():
    target = DependencyTarget(name="requests", scope="core")
    result = _pep621('[project]\nname="x"\ndependencies="not-a-list"\n', target)
    assert result.outcome == UNKNOWN
    assert "invalid_dependencies_type" in result.limitations


def test_non_string_dependency_entry_is_diagnosed_not_raised():
    target = DependencyTarget(name="requests", scope="core")
    result = _pep621('[project]\nname="x"\ndependencies=[7]\n', target)
    assert result.outcome == UNKNOWN
    assert "invalid_dependency_entry_type" in result.limitations


def test_invalid_pep508_line_inside_pyproject_is_diagnosed():
    target = DependencyTarget(name="requests", scope="core")
    result = _pep621('[project]\nname="x"\ndependencies=["not a valid === req"]\n', target)
    assert result.outcome == UNKNOWN
    assert "invalid_pep508_line" in result.limitations


# --------------------------------------------------------------------------
# 9. Invalid PEP 508 requirement (requirements.txt)
# --------------------------------------------------------------------------


def test_invalid_pep508_requirement_line_degrades_gracefully():
    target = DependencyTarget(name="requests", scope="core")
    result = _pep508("this is === not >>> a valid requirement\n", target)
    assert result.outcome == UNKNOWN
    assert "invalid_pep508_line" in result.limitations
    assert "not_declared_in_inspected_scope" in result.limitations


# --------------------------------------------------------------------------
# 10. Unresolved includes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("directive", ["-r other.txt", "--requirement other.txt",
                                       "-c constraints.txt", "--constraint constraints.txt",
                                       "-r=other.txt", "--requirement=other.txt",
                                       "-c=constraints.txt", "--constraint=constraints.txt"])
def test_unresolved_includes_never_produce_refutes_for_absence(directive):
    target = DependencyTarget(name="flask", scope="core")
    content = f"requests>=2.0\n{directive}\n"
    result = _pep508(content, target)
    assert result.outcome == UNKNOWN
    assert result.outcome != REFUTES
    assert "unresolved_include" in result.limitations
    assert "unresolved_includes_may_hide_declaration" in result.limitations


@pytest.mark.parametrize(
    "content",
    [
        "requests\n-c constraints.txt\n",
        "requests>=3\n-r more.txt\n",
        "requests>=3\n-r=more.txt\n",
    ],
)
def test_mismatch_with_unresolved_include_is_unknown_not_refutes(content):
    """BLOQUEO 2: an unresolved include can hide the exact match elsewhere, so a
    mismatched OBSERVED entry must not be read as a confident contradiction.

    Precedence: exact match found -> SUPPORTS; no exact match AND not fully
    inspected -> UNKNOWN; only a fully-inspected mismatch -> REFUTES.
    """
    target = DependencyTarget(name="requests", specifier=">=2", scope="core")
    result = _pep508(content, target)
    assert result.outcome == UNKNOWN
    assert result.outcome != REFUTES
    assert "unresolved_include" in result.limitations
    assert "unresolved_includes_may_hide_declaration" in result.limitations


def test_fully_inspected_mismatch_still_refutes():
    """The positive control: without any include, a real mismatch IS refutes."""
    target = DependencyTarget(name="requests", specifier=">=2", scope="core")
    result = _pep508("requests>=3\n", target)
    assert result.outcome == REFUTES


# --------------------------------------------------------------------------
# 11. Pip directives are not evidence
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "directive",
    [
        "--index-url https://pypi.example/simple",
        "--extra-index-url https://pypi.example/simple",
        "--find-links ./wheels",
        "-e .",
        "--editable .",
        "--no-index",
        "--trusted-host pypi.example",
    ],
)
def test_pip_directives_do_not_cause_refutation_or_exception(directive):
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    content = f"requests>=2.0\n{directive}\n"
    result = _pep508(content, target)
    assert result.outcome == SUPPORTS  # the real requirement line is still found


def test_pip_directive_alone_absent_target_is_unknown_not_refutes():
    target = DependencyTarget(name="flask", scope="core")
    content = "--index-url https://pypi.example/simple\n-e .\nrequests>=2.0\n"
    result = _pep508(content, target)
    assert result.outcome == UNKNOWN
    assert result.outcome != REFUTES


# --------------------------------------------------------------------------
# 12. Sentinel credential URL is never leaked
# --------------------------------------------------------------------------


SENTINEL_SECRET = "s3cr3t-token-DO-NOT-LEAK"


def test_credential_url_in_requirement_never_reaches_verification_result():
    target = DependencyTarget(name="pkg", scope="core")
    content = f"pkg @ https://user:{SENTINEL_SECRET}@example.com/pkg.whl\n"
    result = _pep508(content, target)
    blob = repr(result)
    assert SENTINEL_SECRET not in blob
    assert SENTINEL_SECRET not in result.claim_text
    assert all(SENTINEL_SECRET not in item for item in result.limitations)
    assert all(SENTINEL_SECRET not in item for item in result.degradations)


# --------------------------------------------------------------------------
# BLOQUEO 4: direct references (URLs) are not identity-bearing; never SUPPORTS
# --------------------------------------------------------------------------


def test_direct_reference_url_is_never_probative():
    """A URL requirement carries no name/specifier identity matching our
    target model; treating it as a match for DependencyTarget(name='pkg') with
    no specifier let ANY direct reference silently satisfy ANY unconstrained
    target."""
    target = DependencyTarget(name="pkg", scope="core")
    content = "pkg @ https://example.com/a.whl\n"
    result = _pep508(content, target)
    assert result.outcome != SUPPORTS
    assert result.outcome != REFUTES
    assert result.is_probative is False


@pytest.mark.parametrize(
    "url_suffix",
    [
        f"https://user:{SENTINEL_SECRET}@example.com/a.whl",
        f"https://example.com/a.whl?token={SENTINEL_SECRET}",
        f"https://example.com/a.whl#{SENTINEL_SECRET}",
    ],
)
def test_direct_reference_sentinel_never_appears_anywhere(url_suffix):
    target = DependencyTarget(name="pkg", scope="core")
    content = f"pkg @ {url_suffix}\n"
    result = _pep508(content, target)
    assert result.outcome != SUPPORTS
    blob = repr(result)
    assert SENTINEL_SECRET not in blob
    assert SENTINEL_SECRET not in result.claim_text
    assert all(SENTINEL_SECRET not in item for item in result.limitations)
    assert all(SENTINEL_SECRET not in item for item in result.degradations)


# --------------------------------------------------------------------------
# P1-5: no URL (userinfo, query OR fragment secrets) is ever RETAINED in
# ParseOutcome - the conservative fix is not "sanitize the URL" (a query
# string or fragment carries a secret exactly as userinfo does) but "never
# store the URL at all": only a count and a diagnostic survive.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        f"https://user:{SENTINEL_SECRET}@example.com/a.whl",
        f"https://example.com/a.whl?token={SENTINEL_SECRET}",
        f"https://example.com/a.whl#{SENTINEL_SECRET}",
    ],
)
def test_requirements_txt_parse_outcome_never_retains_the_url(url):
    outcome = parse_requirements_txt(f"pkg @ {url}\n")
    assert SENTINEL_SECRET not in repr(outcome)
    assert outcome.direct_reference_count == 1
    assert "direct_reference_not_supported" in outcome.diagnostics


@pytest.mark.parametrize(
    "url",
    [
        f"https://user:{SENTINEL_SECRET}@example.com/a.whl",
        f"https://example.com/a.whl?token={SENTINEL_SECRET}",
        f"https://example.com/a.whl#{SENTINEL_SECRET}",
    ],
)
def test_pyproject_parse_outcome_never_retains_the_url(url):
    content = f'[project]\nname="x"\ndependencies=["pkg @ {url}"]\n'
    outcome = parse_pyproject_dependencies(content)
    assert SENTINEL_SECRET not in repr(outcome)
    assert outcome.direct_reference_count == 1
    assert "direct_reference_not_supported" in outcome.diagnostics


def test_credential_url_never_reaches_the_public_report_via_real_pipeline():
    """Routed through the real automatic boundary (BLOQUEO 1), not a vacuous
    construction that builds a Proposition and never uses it."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="pkg", specifier=">=1.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\nname="x"\ndependencies=["pkg>=1.0"]\n', encoding="utf-8"
        )
        (root / "requirements.txt").write_text(
            f"pkg @ https://user:{SENTINEL_SECRET}@example.com/pkg.whl\n", encoding="utf-8"
        )
        goal = {
            "name": "g",
            "aspects": [target.canonical_name],
            "dependency_targets": [target],
            "target_revision": "rev-1",
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    assert SENTINEL_SECRET not in repr(report)


# --------------------------------------------------------------------------
# BLOQUEO 5: inline comments are an explicit, tested boundary
# --------------------------------------------------------------------------


def test_inline_comment_is_documented_as_unsupported_not_silently_wrong():
    """Full-line comments are stripped; inline comments are NOT parsed as
    PEP 508 (avoiding ambiguity with URL fragments and markers containing '#').
    This is a deliberate, tested boundary, not an accidental gap."""
    target = DependencyTarget(name="requests", specifier=">=2", scope="core")
    result = _pep508("requests>=2 # comentario\n", target)
    assert result.outcome == UNKNOWN
    assert "invalid_pep508_line" in result.limitations


# --------------------------------------------------------------------------
# 13. Absent dependency in a fully-inspected file
# --------------------------------------------------------------------------


def test_absent_dependency_in_fully_inspected_file_never_produces_expected_claim():
    target = DependencyTarget(name="flask", specifier=">=3.0", scope="core")
    result = _pep508(REQUIREMENTS_BASIC, target)
    assert result.outcome == UNKNOWN
    assert result.outcome != SUPPORTS
    assert "not_declared_in_inspected_scope" in result.limitations
    prop = proposition_from_verification(result, "g")
    assert prop is None  # non-probative, never becomes evidence


# --------------------------------------------------------------------------
# 14. Alias / duplicate file collapses by root fingerprint
# --------------------------------------------------------------------------


def test_duplicate_file_content_collapses_by_root_fingerprint():
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    r1 = _pep508(REQUIREMENTS_BASIC, target, execution_id="run-a")
    r2 = _pep508(REQUIREMENTS_BASIC, target, execution_id="run-b")  # same content, different run
    assert r1.root_fingerprints == r2.root_fingerprints == (root_fingerprint(REQUIREMENTS_BASIC),)
    sources = [source_from_result(r1), source_from_result(r2)]
    assert independent_source_count(sources, REV, r1.normalized_claim_id) == 1


# --------------------------------------------------------------------------
# 15. derived_from collapses generated files
# --------------------------------------------------------------------------


def test_generated_requirements_file_is_detected_and_collapses_via_derived_from():
    generated = (
        "# This file is autogenerated by pip-compile from pyproject.toml\n"
        "requests>=2.0\n"
    )
    assert looks_pip_compile_generated_from(generated, "pyproject.toml") is True

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    r_pyproject = _pep621(PYPROJECT_BASIC, target, execution_id="run-1")
    # derived_from links via the PARENT's result_id, not a root fingerprint:
    # D's union-find matches a child's derived_from entry against the parent's
    # own source_id (see _linkage_keys in verifiers.py).
    r_generated = _pep508(generated, target, execution_id="run-2",
                          derived_from=(r_pyproject.result_id,))

    assert r_generated.derived_from == (r_pyproject.result_id,)
    sources = [source_from_result(r_pyproject), source_from_result(r_generated)]
    assert independent_source_count(sources, REV, r_pyproject.normalized_claim_id) == 1


def test_independently_authored_files_are_not_auto_linked():
    assert looks_pip_compile_generated_from(REQUIREMENTS_BASIC, "pyproject.toml") is False
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    r_pyproject = _pep621(PYPROJECT_BASIC, target, execution_id="run-1")
    r_requirements = _pep508(REQUIREMENTS_BASIC, target, execution_id="run-2")
    assert r_requirements.derived_from == ()
    sources = [source_from_result(r_pyproject), source_from_result(r_requirements)]
    assert independent_source_count(
        sources, REV, r_pyproject.normalized_claim_id
    ) == 2


# --------------------------------------------------------------------------
# 16-17. claims/scopes distinct; syntax valid but dependency absent
# --------------------------------------------------------------------------


def test_distinct_claims_never_summed_by_min_sources():
    from argos_epistemic.algorithm import min_sources_met

    a = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    b = DependencyTarget(name="requests", specifier=">=2.0", marker='sys_platform == "linux"',
                         scope="core")
    r_a = _pep621(PYPROJECT_BASIC, a, execution_id="run-1")
    r_b = _pep508(REQUIREMENTS_BASIC, b, execution_id="run-2")
    assert r_a.outcome == SUPPORTS
    assert r_b.outcome == REFUTES  # same name+scope, mismatched marker
    assert r_a.normalized_claim_id != r_b.normalized_claim_id

    props = [proposition_from_verification(r_a, "g"), proposition_from_verification(r_b, "g")]
    props = [p for p in props if p is not None]
    # Both are probative (one supports, one refutes) but belong to DIFFERENT
    # claims, so neither claim individually reaches two independent sources.
    assert len(props) == 2
    assert min_sources_met(props, [{"name": "requests", "weight": 1.0}], 2, REV) is False


# --------------------------------------------------------------------------
# 18. refutes preserved and excluded from corroboration
# --------------------------------------------------------------------------


def test_refutes_result_is_preserved_and_never_corroborates():
    target = DependencyTarget(name="requests", specifier=">=5.0", scope="core")
    result = _pep621(PYPROJECT_BASIC, target)
    assert result.outcome == REFUTES
    prop = proposition_from_verification(result, "g")
    assert prop is not None
    assert prop.relation == "refutes"
    source = source_from_result(result)
    assert source is None  # refutes never becomes a corroborating source


# --------------------------------------------------------------------------
# 19. Order, duplication and whitespace/comment metamorphism
# --------------------------------------------------------------------------


def test_whitespace_and_comment_metamorphism_does_not_change_the_outcome():
    variants = [
        "requests>=2.0\n",
        "requests>=2.0  \n\n",
        "  requests>=2.0\n# a comment\n",
        "# leading comment\nrequests>=2.0\n\n\n",
    ]
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    outcomes = {_pep508(v, target).outcome for v in variants}
    assert outcomes == {SUPPORTS}


def test_reordering_dependency_declarations_does_not_change_the_outcome():
    a = '[project]\nname="x"\ndependencies=["requests>=2.0", "flask>=3.0"]\n'
    b = '[project]\nname="x"\ndependencies=["flask>=3.0", "requests>=2.0"]\n'
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    assert _pep621(a, target).outcome == _pep621(b, target).outcome == SUPPORTS


def test_duplicate_declaration_of_the_same_dependency_is_still_one_support():
    content = '[project]\nname="x"\ndependencies=["requests>=2.0", "requests>=2.0"]\n'
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    result = _pep621(content, target)
    assert result.outcome == SUPPORTS


# --------------------------------------------------------------------------
# 20. Zero third-party execution, zero network
# --------------------------------------------------------------------------


def test_verifiers_never_touch_the_network(monkeypatch):
    import socket

    def _blocked(*a, **kw):
        raise RuntimeError("no network access permitted")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    assert _pep621(PYPROJECT_BASIC, target).outcome == SUPPORTS
    assert _pep508(REQUIREMENTS_BASIC, target).outcome == SUPPORTS


def test_verifiers_never_execute_subprocesses(monkeypatch):
    import subprocess

    def _blocked(*a, **kw):
        raise RuntimeError("no subprocess execution permitted")

    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    assert _pep621(PYPROJECT_BASIC, target).outcome == SUPPORTS
    assert _pep508(REQUIREMENTS_BASIC, target).outcome == SUPPORTS


# --------------------------------------------------------------------------
# BLOQUEO 1: mandatory end-to-end liveness test through analyze_path
# --------------------------------------------------------------------------


def _write_fixture(root, pyproject_deps, requirements_lines):
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\ndependencies = ' + repr(pyproject_deps) + "\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text("\n".join(requirements_lines) + "\n", encoding="utf-8")


@pytest.mark.parametrize("bad_targets", [7, "not-a-list", object(), 3.5])
def test_verify_dependency_targets_never_raises_on_hostile_targets_collection(bad_targets):
    """Found in self-review: targets=7 raised TypeError from `for spec in targets`,
    and a bare string silently iterated its characters as individual specs."""
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(".", bad_targets, "rev-1", None)
    assert outcome.results == ()
    assert "invalid_dependency_targets_collection" in outcome.diagnostics


def test_end_to_end_liveness_through_analyze_path_reaches_complete_true():
    """The mandatory positive control (plan §5.5).

    Two INDEPENDENTLY written manifest files declare the same DependencyTarget.
    No min_sources=1, no artificially low theta, no accepted_degradations, no
    manual supports anywhere in the fixture - only the two static verifiers,
    run automatically by analyze_path because the goal opts in with
    dependency_targets, produce the evidence.
    """
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["requests>=2.0"], ["requests>=2.0"])
        goal = {
            "name": "dependency-audit",
            "aspects": [target.canonical_name],
            "dependency_targets": [target],
            "target_revision": "rev-1",
            # Deliberately NOT set: theta_coverage, rho_risk, min_sources_per_aspect,
            # accepted_degradations. Defaults only.
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))

    assert {c["relation"] for c in report["conclusions"]} >= {"supports"}
    assert all(c["authority_class"] != "explicit_artifact_claim" for c in report["conclusions"]
              if c["relation"] == "supports")

    section = report["source_independence"]
    claim_entries = [c for c in section["claims"] if c["aspect"] == target.canonical_name]
    assert len(claim_entries) == 1
    entry = claim_entries[0]
    assert entry["independent_components"] == 2
    # Two SEPARATE components (independence means they do NOT share family,
    # root or execution) - not one merged component with two families.
    assert len(entry["components"]) == 2
    families = {f for c in entry["components"] for f in c["verifier_families"]}
    assert families == {"pep621-dependencies", "pep508-requirements"}

    assert report["coverage"] >= 0.95
    assert report["residual_risk"] <= 0.05
    assert report["complete"] is True


def test_end_to_end_mutation_retracts_completion():
    """Mutating requirements.txt to contradict the target must explainably
    change coverage, residual_risk or completion, and complete must become False.

    A revision denotes an IMMUTABLE snapshot (P2-3): the three states below
    are three genuinely different snapshots of the repository, so each is
    evaluated at its OWN ``target_revision`` - reusing one revision string for
    two different contents would teach that a single revision can name two
    different mutated roots, which is exactly the confusion the revision
    scoping in D exists to prevent.
    """
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")

    def _goal(revision):
        return {
            "name": "dependency-audit",
            "aspects": [target.canonical_name],
            "dependency_targets": [target],
            "target_revision": revision,
        }

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["requests>=2.0"], ["requests>=2.0"])
        before = analyze_path(root, goal=_goal("rev-1"),
                              budget=Budget(tokens_remaining=10000, tool_remaining=50))
    assert before["complete"] is True

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["requests>=2.0"], ["requests>=5.0"])  # contradicts
        after = analyze_path(root, goal=_goal("rev-2"),
                             budget=Budget(tokens_remaining=10000, tool_remaining=50))
    assert after["complete"] is False
    assert (
        after["coverage"] < before["coverage"]
        or after["residual_risk"] > before["residual_risk"]
    )
    assert any(c["relation"] == "refutes" for c in after["conclusions"])

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["requests>=2.0"], [])  # retracted entirely
        retracted = analyze_path(root, goal=_goal("rev-3"),
                                 budget=Budget(tokens_remaining=10000, tool_remaining=50))
    assert retracted["complete"] is False


def test_end_to_end_repeated_analysis_is_deterministic():
    """NOT an alias/duplicate-content test (P2-2 correction of the prior name -
    it ran the SAME analysis twice and only proved determinism). Alias/shared-
    root collapsing via ``root_fingerprint`` is already covered by D's own
    contract tests (``test_duplicate_file_content_collapses_by_root_fingerprint``
    above). This test proves exactly what it claims: two independent runs of
    the whole pipeline against identical inputs produce byte-identical reports.
    """
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\nname="fixture"\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
        )
        (root / "requirements.txt").write_text("requests>=2.0\n", encoding="utf-8")
        goal = {
            "name": "g",
            "aspects": [target.canonical_name],
            "dependency_targets": [target],
            "target_revision": "rev-1",
        }
        r1 = analyze_path(root, goal=dict(goal), budget=Budget(tokens_remaining=10000, tool_remaining=50))
        r2 = analyze_path(root, goal=dict(goal), budget=Budget(tokens_remaining=10000, tool_remaining=50))
    assert r1["coverage"] == r2["coverage"]
    assert r1["source_independence"] == r2["source_independence"]


def test_end_to_end_canonically_duplicated_targets_never_multiply_work_or_coverage():
    """P2-1/P2-2: 1000 canonically-duplicated targets (same name, scope,
    specifier, marker, extras up to whitespace/case) must dedupe to ONE piece
    of work, not 1000 - coverage, proposition/result counts and charged cost
    must be IDENTICAL to submitting the target once."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    duplicated = [
        {"name": "Requests", "specifier": " >=2.0", "scope": "core"} for _ in range(1000)
    ]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["requests>=2.0"], ["requests>=2.0"])
        goal_one = {
            "name": "g", "aspects": [target.canonical_name],
            "dependency_targets": [target], "target_revision": "rev-1",
        }
        goal_many = {
            "name": "g", "aspects": [target.canonical_name],
            "dependency_targets": duplicated, "target_revision": "rev-1",
        }
        budget_one = Budget(tokens_remaining=10000, tool_remaining=50)
        budget_many = Budget(tokens_remaining=10000, tool_remaining=50)
        one = analyze_path(root, goal=goal_one, budget=budget_one)
        many = analyze_path(root, goal=goal_many, budget=budget_many)

    assert many["dependency_verification"]["requested_targets"] == 1000
    assert many["dependency_verification"]["accepted_targets"] == 1  # deduped
    assert many["proposition_count"] == one["proposition_count"]
    assert many["coverage"] == one["coverage"]
    assert many["dependency_verification"]["verification_result_count"] == (
        one["dependency_verification"]["verification_result_count"]
    )
    assert many["dependency_verification"]["cost"] == one["dependency_verification"]["cost"]
    assert budget_many.tool_remaining == budget_one.tool_remaining
    assert budget_many.tokens_remaining == budget_one.tokens_remaining


def test_end_to_end_generated_requirements_collapses_via_derived_from():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\nname="fixture"\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
        )
        (root / "requirements.txt").write_text(
            "# This file is autogenerated by pip-compile from pyproject.toml\n"
            "requests>=2.0\n",
            encoding="utf-8",
        )
        goal = {
            "name": "g",
            "aspects": [target.canonical_name],
            "dependency_targets": [target],
            "target_revision": "rev-1",
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))

    section = report["source_independence"]
    entry = next(c for c in section["claims"] if c["aspect"] == target.canonical_name)
    assert entry["independent_components"] == 1  # collapsed via derived_from
    assert report["complete"] is False  # min_sources=2 default cannot be met


# --------------------------------------------------------------------------
# Semantic scope tests: build-system / tool.* never become runtime claims
# --------------------------------------------------------------------------


def test_build_system_requires_is_never_read_as_a_runtime_dependency():
    content = """
[project]
name = "demo"
dependencies = []

[build-system]
requires = ["setuptools>=68"]
"""
    target = DependencyTarget(name="setuptools", scope="core")
    result = _pep621(content, target)
    assert result.outcome == UNKNOWN
    assert result.outcome != SUPPORTS


def test_tool_section_is_never_read_as_a_runtime_dependency():
    content = """
[project]
name = "demo"
dependencies = []

[tool.some-plugin]
dependencies = ["setuptools>=68"]
"""
    target = DependencyTarget(name="setuptools", scope="core")
    result = _pep621(content, target)
    assert result.outcome == UNKNOWN


# --------------------------------------------------------------------------
# Extras on the requirement itself (not the optional-dependencies group)
# --------------------------------------------------------------------------


def test_requirement_extras_are_part_of_the_claim_identity():
    plain = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    with_extra = DependencyTarget(name="requests", specifier=">=2.0", scope="core",
                                  extras=("socks",))
    content = '[project]\nname="x"\ndependencies=["requests[socks]>=2.0"]\n'
    assert _pep621(content, plain).outcome == REFUTES  # same name+scope, different extras
    assert _pep621(content, with_extra).outcome == SUPPORTS


# --------------------------------------------------------------------------
# Claim never asserts more than declaration
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# BLOQUEO 3: DependencyTarget must reject hostile types, not widen the claim
# --------------------------------------------------------------------------

HOSTILE_NON_TEXT = [None, False, 0, [], {}, True, 7, object(), b"x", set()]


@pytest.mark.parametrize("specifier", HOSTILE_NON_TEXT)
def test_target_rejects_non_string_specifier(specifier):
    """A non-string specifier silently became 'any version' - the claim widened
    itself instead of failing. Configuration errors must raise, not degrade the
    claim into something looser than what was asked."""
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name="pkg", specifier=specifier, scope="core")


@pytest.mark.parametrize("marker", HOSTILE_NON_TEXT)
def test_target_rejects_non_string_marker(marker):
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name="pkg", marker=marker, scope="core")


@pytest.mark.parametrize("name", [None, "", "   ", 7, [], {}, "not a valid name!!", object()])
def test_target_rejects_invalid_name(name):
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name=name, scope="core")


@pytest.mark.parametrize("scope", [None, "", "   ", 7, [], object()])
def test_target_rejects_invalid_scope(scope):
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name="pkg", scope=scope)


@pytest.mark.parametrize(
    "extras", [None, "socks", (None,), (7,), ("",), ("  ",), (b"x",), ([],)]
)
def test_target_rejects_invalid_extras(extras):
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name="pkg", scope="core", extras=extras)


def test_target_rejects_syntactically_invalid_specifier_text():
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name="pkg", specifier="not a specifier !!!", scope="core")


def test_target_rejects_syntactically_invalid_marker_text():
    with pytest.raises((TypeError, ValueError)):
        DependencyTarget(name="pkg", marker="not a marker !!!", scope="core")


def test_valid_target_still_constructs():
    target = DependencyTarget(name="Requests", specifier=">=2.0", scope="core", extras=("Socks",))
    assert target.canonical_name == "requests"
    assert target.canonical_extras == ("socks",)


# --------------------------------------------------------------------------
# BLOQUEO 3b: a hostile VerifierClaim must never escape run_verifier
# --------------------------------------------------------------------------

HOSTILE_CLAIM_FIELDS = [
    ("aspect", object()),
    ("aspect", b"x"),
    ("aspect", 7),
    ("claim_text", object()),
    ("claim_text", b"x"),
    ("scope", object()),
    ("scope", b"x"),
    ("outcome", object()),
]


@pytest.mark.parametrize("field_name,value", HOSTILE_CLAIM_FIELDS)
def test_hostile_verifier_claim_never_escapes_run_verifier(field_name, value):
    """D's validation must run BEFORE canonical identity computation: a
    non-string aspect/claim_text/scope must never reach compute_result_id,
    which raised CanonicalizationError out of run_verifier."""
    from argos_epistemic.verifiers import DEGRADED as _DEGRADED
    from argos_epistemic.verifiers import VerifierClaim as _Claim

    fields = {"outcome": SUPPORTS, "aspect": "pkg", "claim_text": "c", "scope": "v1"}
    fields[field_name] = value

    def hostile(payload):
        return [_Claim(**fields)]

    reg = VerifierRegistration("p", "1", "deterministic", hostile, "")
    payload = verification_input("a", "body", "a", REV, ("pkg",))
    results = run_verifier(reg, payload, "run-1")
    assert results[0].outcome == _DEGRADED
    assert results[0].is_probative is False


def test_claim_text_never_asserts_installation_or_functionality():
    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    text = target.claim_text().lower()
    for forbidden in ("install", "import", "runtime", "resolv", "functional", "production"):
        assert forbidden not in text
    assert "declares" in text


# --------------------------------------------------------------------------
# P1-1: seed_propositions is GONE. Only VerificationResult flows through
# analyze_system's verification_results parameter; a hand-built Proposition
# is not a VerificationResult and must never reach completion.
# --------------------------------------------------------------------------


def _fabricated_proposition(aspect="requests"):
    from argos_epistemic.algorithm import Proposition

    return Proposition(
        aspect=aspect, polarity=1.0, claim="fabricated", evidence_id="fake",
        confidence=0.9, method="deterministic", scope="core", relation="supports",
        claim_id="fake-claim", claim_text="fabricated claim",
        verification_result_id="fake-result-id", verifier_family="fake-family",
        verifier_version="9", verification_method_profile="deterministic",
        execution_id="fake-exec", target_revision=REV, root_fingerprints=("fake-root",),
    )


def test_fabricated_proposition_cannot_enter_via_verification_results():
    from argos_epistemic.algorithm import Budget, analyze_system

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": REV}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(
        system, goal, budget, verification_results=[_fabricated_proposition()]
    )
    assert report["proposition_count"] == 0
    assert report["coverage"] == 0.0
    assert report["complete"] is False


def test_two_fabricated_propositions_never_reach_complete_true():
    """The exact repro from the rejection: two fabricated Proposition objects
    with invented verification_result_id/families/roots/executions must not
    produce complete=True, coverage=1.0, residual_risk=0.0."""
    from argos_epistemic.algorithm import Budget, analyze_system

    fabricated = [_fabricated_proposition(), _fabricated_proposition()]
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": REV}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=fabricated)
    assert report["complete"] is False
    assert report["coverage"] == 0.0
    assert report["residual_risk"] == 1.0
    assert report["proposition_count"] == 0


def test_tampered_verification_result_cannot_enter_via_verification_results():
    """A genuine VerificationResult whose fields were altered after stamping
    (dataclasses.replace) no longer matches its own result_id and must be
    rejected by validate_verification_result -> refused admission."""
    import dataclasses

    from argos_epistemic.algorithm import Budget, analyze_system

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    genuine = _pep621(PYPROJECT_BASIC, target)
    assert genuine.outcome == SUPPORTS
    tampered = dataclasses.replace(genuine, confidence=0.99)  # result_id now stale

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": REV}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[tampered])
    assert report["proposition_count"] == 0
    assert report["complete"] is False


@pytest.mark.parametrize("garbage", [7, "not-a-result", object(), None, {"outcome": "supports"}])
def test_wrong_type_verification_results_never_raise_or_admit(garbage):
    from argos_epistemic.algorithm import Budget, analyze_system

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": REV}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[garbage])
    assert report["proposition_count"] == 0
    admission = report["verification_admission"]
    assert admission["verification_candidates_offered"] == 1
    assert admission["verification_propositions_admitted"] == 0
    assert admission["verification_candidates_rejected"] == 1
    assert "invalid_result" in admission["verification_rejection_reasons"]
    assert report["complete"] is False


def test_genuine_verification_result_still_admits_normally():
    """The fail-closed gate must not also fail-closed on VALID input."""
    from argos_epistemic.algorithm import Budget, analyze_system

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    r1 = _pep621(PYPROJECT_BASIC, target, execution_id="run-1")
    r2 = _pep508(REQUIREMENTS_BASIC, target, execution_id="run-2")
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": REV}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[r1, r2])
    assert report["proposition_count"] == 2
    admission = report["verification_admission"]
    assert admission["verification_candidates_offered"] == 2
    assert admission["verification_results_valid"] == 2
    assert admission["verification_propositions_admitted"] == 2
    assert admission["verification_candidates_rejected"] == 0
    assert report["complete"] is True


# --------------------------------------------------------------------------
# P1-2: dependency targets must be scoped to the goal's REAL aspects. An
# off-scope target must never execute and must never contaminate an
# unrelated, legitimately-satisfied aspect's completion.
# --------------------------------------------------------------------------


def test_off_scope_target_never_executes_and_never_contaminates_the_goal():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0", "requests>=2.0"], ["flask>=1.0", "requests>=2.0"])
        goal_without_offscope = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": [{"name": "flask", "specifier": ">=1.0", "scope": "core"}],
        }
        goal_with_offscope = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": [
                {"name": "flask", "specifier": ">=1.0", "scope": "core"},
                # off-scope AND contradictory: must not affect the flask goal at all.
                {"name": "requests", "specifier": ">=5.0", "scope": "core"},
            ],
        }
        without = analyze_path(root, goal=goal_without_offscope,
                               budget=Budget(tokens_remaining=10000, tool_remaining=50))
        withit = analyze_path(root, goal=goal_with_offscope,
                              budget=Budget(tokens_remaining=10000, tool_remaining=50))

    assert without["coverage"] == withit["coverage"]
    assert without["residual_risk"] == withit["residual_risk"]
    assert without["complete"] == withit["complete"] is True
    assert not any(c.get("conflicts") for c in [without, withit])
    assert withit["completion"]["reason_codes"] == []
    dep = withit["dependency_verification"]
    assert dep["accepted_targets"] == 1
    assert dep["rejected_targets"] == 1
    assert "dependency_target_outside_goal:requests" in dep["diagnostics"]
    # The off-scope target never ran: no pep508/pep621 result mentions "requests".
    assert all(r["aspect"] != "requests" for r in dep["results"])


def test_off_scope_target_produces_zero_verification_results():
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        ".", [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("flask",),
    )
    assert outcome.results == ()
    assert outcome.accepted_targets == 0
    assert outcome.rejected_targets == 1
    assert "dependency_target_outside_goal:requests" in outcome.diagnostics


# --------------------------------------------------------------------------
# P1-3: every token/tool charged against the budget must appear in the
# report, and complete=True must always imply termination_reason ==
# "thresholds_met" with no blocking reason codes - even when the verifier
# consumed the LAST unit of budget.
# --------------------------------------------------------------------------


def test_dependency_verification_cost_appears_in_the_report():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="flask", specifier=">=1.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "min_sources_per_aspect": 1,
            "dependency_targets": [target],
        }
        budget = Budget(tokens_remaining=200000, tool_remaining=2000)
        report = analyze_path(root, goal=goal, budget=budget)

    charged_tokens = 200000 - budget.tokens_remaining
    charged_tool = 2000 - budget.tool_remaining
    assert charged_tokens > 0 and charged_tool > 0
    assert report["cost"]["estimated_tokens"] >= charged_tokens
    assert report["cost"]["observed_tokens"] >= charged_tokens
    assert report["cost"]["phases"]["dependency_verification"]["tokens"] == charged_tokens
    assert report["cost"]["phases"]["dependency_verification"]["tools"] == charged_tool
    assert report["cost"]["phases"]["dependency_verification"]["manifests_inspected"] == [
        "pyproject.toml", "requirements.txt",
    ]
    assert report["cost"]["phases"]["dependency_verification"]["executions"] == 2


def test_budget_exhausted_by_last_verifier_still_reports_thresholds_met():
    """The loop must check thresholds BEFORE budget capacity: if the
    verification that consumed the final unit of budget already satisfied the
    goal, termination_reason must be thresholds_met, never budget_exhausted,
    and complete=True must never coexist with a blocking reason code."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="flask", specifier=">=1.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "min_sources_per_aspect": 1,
            "dependency_targets": [target],
        }
        # Probe the exact charge first, then construct a budget with exactly
        # that many tool units so it reaches zero precisely when verification
        # finishes and never earlier.
        probe_budget = Budget(tokens_remaining=200000, tool_remaining=2000)
        analyze_path(root, goal=dict(goal), budget=probe_budget)
        exact_tool = 2000 - probe_budget.tool_remaining

        budget = Budget(tokens_remaining=200000, tool_remaining=exact_tool)
        report = analyze_path(root, goal=goal, budget=budget)

    assert budget.tool_remaining == 0
    assert report["complete"] is True
    assert report["completion"]["termination_reason"] == "thresholds_met"
    assert report["completion"]["reason_codes"] == []


@pytest.mark.parametrize("tool_remaining,expect_complete", [(1, False), (0, False), (4, True)])
def test_complete_true_never_coexists_with_a_blocking_reason_code(tool_remaining, expect_complete):
    """Non-vacuous: each budget level asserts an EXPLICIT positive or negative
    control, not merely 'if complete, then...' (P2-2 correction - the prior
    version could pass without ever exercising the complete=True branch)."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="flask", specifier=">=1.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "min_sources_per_aspect": 1,
            "dependency_targets": [target],
        }
        report = analyze_path(
            root, goal=goal, budget=Budget(tokens_remaining=200000, tool_remaining=tool_remaining)
        )
    assert report["complete"] is expect_complete
    if report["complete"]:
        assert report["completion"]["termination_reason"] == "thresholds_met"
        assert report["completion"]["reason_codes"] == []
    else:
        assert report["completion"]["reason_codes"] != []


def test_budget_exhausted_by_last_verifier_with_default_min_sources():
    """The same invariant, but with the DEFAULT min_sources_per_aspect=2 and
    theta/rho defaults (not the relaxed min_sources=1 of the test above): two
    independently-written manifests supply the two required sources."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["requests>=2.0"], ["requests>=2.0"])
        goal = {
            "name": "g", "aspects": ["requests"], "target_revision": "rev-1",
            "dependency_targets": [target],
        }
        probe_budget = Budget(tokens_remaining=200000, tool_remaining=2000)
        analyze_path(root, goal=dict(goal), budget=probe_budget)
        exact_tool = 2000 - probe_budget.tool_remaining

        budget = Budget(tokens_remaining=200000, tool_remaining=exact_tool)
        report = analyze_path(root, goal=goal, budget=budget)

    assert budget.tool_remaining == 0
    assert report["complete"] is True
    assert report["completion"]["termination_reason"] == "thresholds_met"
    assert report["completion"]["reason_codes"] == []


# --------------------------------------------------------------------------
# P1-4: diagnostics and non-probative results must survive into a public,
# sanitized "dependency_verification" report section - even when zero
# Proposition was produced.
# --------------------------------------------------------------------------


def test_dependency_verification_section_present_even_with_zero_propositions():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    # A target that will not match anything: manifest present, but the
    # declared version differs, and the goal aspect matches so it DOES run
    # (in scope) yet produces no supporting proposition.
    target = DependencyTarget(name="flask", specifier=">=99.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": [target],
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))

    dep = report["dependency_verification"]
    assert dep["enabled"] is True
    assert dep["verification_result_count"] == 2  # two REFUTES results, still audited
    assert all(r["outcome"] == "refutes" for r in dep["results"])
    # refutes ARE propositions (just negative); the loop may ALSO derive its
    # own mentions-based propositions from discovering the fixture files, so
    # this only asserts on what the dependency-verification results produced.
    dep_result_ids = {r["result_id"] for r in dep["results"]}
    matching = [
        c for c in report["conclusions"]
        if c.get("relation") == "refutes" and c.get("aspect") == "flask"
    ]
    assert len(matching) >= 2
    assert dep_result_ids  # non-empty, sanity


def test_dependency_verification_section_present_with_zero_propositions_from_unknown(tmp_path):
    """P2-2 correction: the case above uses REFUTES, which ARE propositions.
    This is the real zero-proposition-from-verification case: a fully
    inspected manifest that simply never mentions the target -> UNKNOWN, which
    is non-probative and produces NO proposition (verified directly via
    verify_dependency_targets + proposition_from_verification, not inferred
    from the noisier full analyze_path report)."""
    from argos_epistemic.algorithm import proposition_from_verification
    from argos_epistemic.dependency_verifiers import (
        dependency_verification_report,
        verify_dependency_targets,
    )

    _write_fixture(tmp_path, ["flask>=1.0"], ["flask>=1.0"])
    target = DependencyTarget(name="nonexistent-pkg", scope="core")
    outcome = verify_dependency_targets(
        tmp_path, [target], "rev-1", None, goal_aspects=("nonexistent-pkg",),
    )
    assert outcome.results
    assert all(r.outcome == UNKNOWN for r in outcome.results)
    propositions = [proposition_from_verification(r, "g") for r in outcome.results]
    assert all(p is None for p in propositions)  # zero propositions from verification

    report = dependency_verification_report(outcome, "rev-1")
    assert report["enabled"] is True
    assert report["verification_result_count"] == len(outcome.results)
    assert all(entry["outcome"] == "unknown" for entry in report["results"])


def test_dependency_verification_section_disabled_when_not_requested():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    assert report["dependency_verification"] == {"enabled": False}


def test_dependency_verification_section_never_contains_manifest_content_or_urls():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    target = DependencyTarget(name="pkg", specifier=">=1.0", scope="core")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            '[project]\nname="x"\ndependencies=["pkg>=1.0"]\n', encoding="utf-8"
        )
        (root / "requirements.txt").write_text(
            f"pkg @ https://user:{SENTINEL_SECRET}@example.com/pkg.whl\n", encoding="utf-8"
        )
        goal = {
            "name": "g", "aspects": ["pkg"], "target_revision": "rev-1",
            "dependency_targets": [target],
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    dep = report["dependency_verification"]
    assert SENTINEL_SECRET not in repr(dep)
    assert "https://" not in repr(dep)


# --------------------------------------------------------------------------
# P1-6: opt-in is the PRESENCE of "dependency_targets" in the goal, not its
# truthiness - None/0/""/[] must all still classify explicitly, never be
# silently treated as "feature not requested".
# --------------------------------------------------------------------------


@pytest.mark.parametrize("falsy_value", [None, 0, "", False])
def test_falsy_but_present_dependency_targets_still_opts_in_with_diagnostic(falsy_value):
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": falsy_value,
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    dep = report["dependency_verification"]
    assert dep["enabled"] is True
    assert "invalid_dependency_targets_collection" in dep["diagnostics"]


def test_empty_list_dependency_targets_opts_in_with_no_diagnostic():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": [],
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    dep = report["dependency_verification"]
    assert dep["enabled"] is True
    assert dep["diagnostics"] == []
    assert dep["requested_targets"] == 0


# --------------------------------------------------------------------------
# P1-7: manifests are read via a bounded, symlink-rejecting read. A
# repository under analysis must never be able to use a symlink to pull an
# arbitrary file from outside (or missing from) the analyzed root.
# --------------------------------------------------------------------------


def test_symlink_pointing_outside_root_is_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "pyproject.toml").write_text(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
    )
    inside = tmp_path / "inside"
    inside.mkdir()
    (inside / "pyproject.toml").symlink_to(outside / "pyproject.toml")

    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        inside, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert "pyproject.toml" not in outcome.manifests_inspected
    assert "pyproject.toml:symlink_rejected" in outcome.diagnostics
    assert outcome.results == ()  # never read, never verified, never a claim


def test_symlink_pointing_inside_root_is_also_rejected(tmp_path):
    """Conservative choice: ANY symlink is rejected, not only external ones -
    never following a link silently is simpler and strictly safer than trying
    to prove containment for the internal case."""
    real = tmp_path / "requirements.txt"
    real.write_text("requests>=2.0\n", encoding="utf-8")
    link = tmp_path / "pyproject.toml"
    link.symlink_to(real)

    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert "pyproject.toml" not in outcome.manifests_inspected
    assert "pyproject.toml:symlink_rejected" in outcome.diagnostics


def test_broken_symlink_is_rejected_not_an_exception(tmp_path):
    broken = tmp_path / "pyproject.toml"
    broken.symlink_to(tmp_path / "does-not-exist.toml")

    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert "pyproject.toml:symlink_rejected" in outcome.diagnostics
    assert "pyproject.toml" not in outcome.manifests_inspected


def test_regular_file_manifest_is_read_normally(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
    )
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "specifier": ">=2.0", "scope": "core"}],
        "rev-1", None, goal_aspects=("requests",),
    )
    assert "pyproject.toml" in outcome.manifests_inspected
    assert any(r.outcome == SUPPORTS for r in outcome.results)


# --------------------------------------------------------------------------
# P2-1: budget is checked/consumed BEFORE the effective read, using a
# bounded read (not stat alone) as the source of truth for the size cap.
# --------------------------------------------------------------------------


def test_oversized_manifest_is_never_read_even_partially(tmp_path):
    from argos_epistemic.dependency_verifiers import (
        MAX_MANIFEST_BYTES,
        verify_dependency_targets,
    )

    huge = "x" * (MAX_MANIFEST_BYTES + 10)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname="x"\n# {huge}\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
    )
    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert "pyproject.toml" not in outcome.manifests_inspected
    assert "pyproject.toml:exceeds_size_limit" in outcome.diagnostics
    assert outcome.results == () or all(r.artifact_id != "pyproject.toml" for r in outcome.results)


def test_budget_too_small_for_manifest_read_never_charges_and_never_raises(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
    )
    from argos_epistemic.algorithm import Budget
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    budget = Budget(tokens_remaining=1, tool_remaining=1)
    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", budget, goal_aspects=("requests",),
    )
    assert budget.tokens_remaining >= 0
    assert budget.tool_remaining >= 0
    assert "pyproject.toml:budget_exhausted" in outcome.diagnostics


# --------------------------------------------------------------------------
# Adversarial round: types, permutation/idempotence, zero network/subprocess
# already covered above; the following close remaining gaps named in the
# rejection's mandatory adversarial list.
# --------------------------------------------------------------------------


def test_single_dict_target_not_wrapped_in_a_list_is_rejected_not_iterated():
    """A lone dict is truthy and iterable (over its keys) - `for spec in
    targets` over a bare dict would silently treat each KEY as a spec."""
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        ".", {"name": "requests", "scope": "core"}, "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.results == ()
    assert "invalid_dependency_targets_collection" in outcome.diagnostics


def test_verify_dependency_targets_result_is_permutation_invariant(tmp_path):
    _write_fixture(tmp_path, ["flask>=1.0", "requests>=2.0"], ["flask>=1.0", "requests>=2.0"])
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    a = {"name": "flask", "specifier": ">=1.0", "scope": "core"}
    b = {"name": "requests", "specifier": ">=2.0", "scope": "core"}
    forward = verify_dependency_targets(tmp_path, [a, b], "rev-1", None, goal_aspects=("flask", "requests"))
    backward = verify_dependency_targets(tmp_path, [b, a], "rev-1", None, goal_aspects=("flask", "requests"))
    assert {r.result_id for r in forward.results} == {r.result_id for r in backward.results}
    assert forward.accepted_targets == backward.accepted_targets == 2


def test_unknown_and_degraded_results_are_visible_but_never_probative(tmp_path):
    _write_fixture(tmp_path, ["flask>=1.0"], ["flask>=1.0"])
    from argos_epistemic.dependency_verifiers import (
        dependency_verification_report,
        verify_dependency_targets,
    )

    # nonexistent is in scope (goal aspect matches) but the manifest doesn't
    # declare it -> UNKNOWN, not SUPPORTS/REFUTES.
    outcome = verify_dependency_targets(
        tmp_path, [{"name": "nonexistent", "scope": "core"}], "rev-1", None,
        goal_aspects=("nonexistent",),
    )
    assert all(r.outcome == UNKNOWN for r in outcome.results)
    assert all(not r.is_probative for r in outcome.results)
    report = dependency_verification_report(outcome, "rev-1")
    assert report["verification_result_count"] == len(outcome.results)
    assert all(entry["outcome"] == "unknown" for entry in report["results"])


def test_verify_dependency_targets_never_touches_network_or_subprocess(tmp_path, monkeypatch):
    import socket
    import subprocess

    def _blocked(*a, **kw):
        raise RuntimeError("no network/subprocess access permitted")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)

    _write_fixture(tmp_path, ["requests>=2.0"], ["requests>=2.0"])
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "specifier": ">=2.0", "scope": "core"}],
        "rev-1", None, goal_aspects=("requests",),
    )
    assert any(r.outcome == SUPPORTS for r in outcome.results)


def test_non_empty_string_dependency_targets_is_rejected_not_iterated_as_chars():
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": "flask",
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    dep = report["dependency_verification"]
    assert dep["enabled"] is True
    assert "invalid_dependency_targets_collection" in dep["diagnostics"]
    assert dep["requested_targets"] == 0


def test_unreadable_encoding_manifest_is_diagnosed_not_an_exception(tmp_path):
    (tmp_path / "pyproject.toml").write_bytes(b"\xff\xfe\x00not valid utf-8 toml \xfa")

    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert "pyproject.toml" not in outcome.manifests_inspected
    assert any(d.startswith("pyproject.toml:") for d in outcome.diagnostics)
    assert outcome.results == () or all(r.artifact_id != "pyproject.toml" for r in outcome.results)


def test_absent_manifests_produce_no_diagnostic_just_no_work(tmp_path):
    """A repository with neither manifest is a normal, unremarkable case -
    "not_found" must not be reported as a diagnostic (it is not a problem)."""
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.manifests_inspected == ()
    assert outcome.results == ()
    assert not any("not_found" in d for d in outcome.diagnostics)


def test_dependency_target_budget_exhausted_mid_loop_is_diagnostic_not_exception(tmp_path):
    """Enough budget for the manifest reads but not for every per-target
    charge: remaining targets must be skipped with a diagnostic, never crash
    or silently claim support for the ones that never ran."""
    _write_fixture(tmp_path, ["flask>=1.0", "requests>=2.0"], ["flask>=1.0", "requests>=2.0"])
    from argos_epistemic.algorithm import Budget
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    # Enough for both manifest reads (2 tool units) but only 1 more tool unit -
    # not enough for both targets' per-target charge (2 more tool units).
    budget = Budget(tokens_remaining=100000, tool_remaining=3)
    outcome = verify_dependency_targets(
        tmp_path,
        [
            {"name": "flask", "specifier": ">=1.0", "scope": "core"},
            {"name": "requests", "specifier": ">=2.0", "scope": "core"},
        ],
        "rev-1", budget, goal_aspects=("flask", "requests"),
    )
    assert budget.tool_remaining >= 0
    assert any(d.startswith("dependency_target_budget_exhausted:") for d in outcome.diagnostics)


# ==========================================================================
# Second rejection round (v2 -> v3): P1-1 admission scoping, P1-2 counters,
# P1-3 cost-for-real-work, P1-4 race-free read, P1-5 hostile goal_aspects,
# P1-6 typed dependency_verification boundary, P2-1 initial conflicts.
# ==========================================================================


def _pep621_at(content, target, execution_id, revision, goal_aspects):
    reg = VerifierRegistration(
        "pep621-dependencies", "1", "deterministic", make_pep621_verifier(target), ""
    )
    payload = verification_input(
        "pyproject.toml", content, "pyproject.toml", revision, goal_aspects
    )
    return run_verifier(reg, payload, execution_id)[0]


# --------------------------------------------------------------------------
# P1-1: admission must filter by aspect membership AND target_revision, not
# only by structural identity.
# --------------------------------------------------------------------------


def test_admission_rejects_genuine_support_off_scope():
    from argos_epistemic.algorithm import Budget, analyze_system

    off_scope = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n',
        DependencyTarget(name="requests", specifier=">=2.0", scope="core"),
        "run-1", "rev-1", ("requests",),
    )
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[off_scope])
    assert report["proposition_count"] == 0
    admission = report["verification_admission"]
    assert admission["verification_candidates_rejected"] == 1
    assert "aspect_outside_goal" in admission["verification_rejection_reasons"]


def test_admission_rejects_genuine_refutes_off_scope():
    from argos_epistemic.algorithm import Budget, analyze_system

    off_scope_refutes = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=9.0"]\n',
        DependencyTarget(name="requests", specifier=">=2.0", scope="core"),
        "run-1", "rev-1", ("requests",),
    )
    assert off_scope_refutes.outcome == REFUTES
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[off_scope_refutes])
    assert report["proposition_count"] == 0
    admission = report["verification_admission"]
    assert "aspect_outside_goal" in admission["verification_rejection_reasons"]
    assert "negative_proposition" not in report["completion"]["reason_codes"]


def test_admission_rejects_genuine_support_stale_revision():
    from argos_epistemic.algorithm import Budget, analyze_system

    stale = _pep621_at(
        '[project]\nname="x"\ndependencies=["flask>=1.0"]\n',
        DependencyTarget(name="flask", specifier=">=1.0", scope="core"),
        "run-1", "rev-OLD", ("flask",),
    )
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-NEW"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[stale])
    assert report["proposition_count"] == 0
    admission = report["verification_admission"]
    assert "revision_mismatch" in admission["verification_rejection_reasons"]


def test_admission_rejects_genuine_refutes_stale_revision():
    from argos_epistemic.algorithm import Budget, analyze_system

    stale_refutes = _pep621_at(
        '[project]\nname="x"\ndependencies=["flask>=9.0"]\n',
        DependencyTarget(name="flask", specifier=">=1.0", scope="core"),
        "run-1", "rev-OLD", ("flask",),
    )
    assert stale_refutes.outcome == REFUTES
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-NEW"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=[stale_refutes])
    assert report["proposition_count"] == 0
    admission = report["verification_admission"]
    assert "revision_mismatch" in admission["verification_rejection_reasons"]
    assert "negative_proposition" not in report["completion"]["reason_codes"]


def test_admission_mixes_current_valid_with_stale_and_off_scope_without_contamination():
    """Combination case: two genuinely valid, in-scope, current-revision
    results reach complete=True; adding stale AND off-scope genuine results to
    the SAME call must not change coverage/risk/completion at all."""
    from argos_epistemic.algorithm import Budget, analyze_system

    flask_target = DependencyTarget(name="flask", specifier=">=1.0", scope="core")
    # Two DIFFERENT verifier families (pep621 + pep508) so they count as two
    # genuinely independent sources - two reads of IDENTICAL content would
    # collapse to one source via root_fingerprint, which is not what this
    # test is about.
    current_1 = _pep621_at(
        '[project]\nname="x"\ndependencies=["flask>=1.0"]\n', flask_target,
        "run-1", "rev-1", ("flask",),
    )
    current_2 = _pep508("flask>=1.0\n", flask_target, execution_id="run-2", revision="rev-1")
    stale = _pep621_at(
        '[project]\nname="x"\ndependencies=["flask>=1.0"]\n', flask_target,
        "run-3", "rev-OLD", ("flask",),
    )
    off_scope = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=9.0"]\n',
        DependencyTarget(name="requests", specifier=">=2.0", scope="core"),
        "run-4", "rev-1", ("requests",),
    )
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}

    clean = analyze_system(
        system, goal, Budget(tokens_remaining=1000, tool_remaining=10),
        verification_results=[current_1, current_2],
    )
    mixed = analyze_system(
        system, goal, Budget(tokens_remaining=1000, tool_remaining=10),
        verification_results=[current_1, current_2, stale, off_scope],
    )
    assert clean["coverage"] == mixed["coverage"]
    assert clean["residual_risk"] == mixed["residual_risk"]
    assert clean["complete"] == mixed["complete"] is True
    admission = mixed["verification_admission"]
    assert admission["verification_candidates_offered"] == 4
    assert admission["verification_propositions_admitted"] == 2
    assert admission["verification_candidates_rejected"] == 2
    assert set(admission["verification_rejection_reasons"]) == {
        "revision_mismatch", "aspect_outside_goal",
    }


def test_admission_boundary_enforced_end_to_end_through_analyze_path():
    """Not just verify_dependency_targets' own off-scope filter (which never
    executes the target at all) - analyze_system's admission gate is an
    independent, second line of defense reachable by ANY caller of the public
    API, not only the automatic dependency-verification path."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget, analyze_path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        goal = {
            "name": "g", "aspects": ["flask"], "target_revision": "rev-1",
            "dependency_targets": [{"name": "flask", "specifier": ">=1.0", "scope": "core"}],
        }
        report = analyze_path(root, goal=goal, budget=Budget(tokens_remaining=10000, tool_remaining=50))
    # Every admitted proposition attributable to the dependency verification
    # boundary must be for the "flask" aspect and at "rev-1" - the admission
    # gate inside analyze_system enforces this regardless of what the upstream
    # boundary already filtered.
    dep_result_ids = {r["result_id"] for r in report["dependency_verification"]["results"]}
    assert dep_result_ids
    for c in report["conclusions"]:
        if c.get("authority_class") == "direct_verification":
            assert c["aspect"] == "flask"


# --------------------------------------------------------------------------
# P1-3: cost is charged ONLY for real work - a nonexistent manifest, a
# rejected symlink or a target with zero available manifests costs zero.
# --------------------------------------------------------------------------


def test_cost_zero_manifests_present(tmp_path):
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.manifests_inspected == ()
    assert outcome.results == ()
    assert outcome.executions == 0
    assert outcome.charged_tokens == 0
    assert outcome.charged_tool == 0
    assert outcome.diagnostics == ()


def test_cost_only_pyproject_present(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', encoding="utf-8"
    )
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "specifier": ">=2.0", "scope": "core"}],
        "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.manifests_inspected == ("pyproject.toml",)
    assert outcome.executions == 1
    assert len(outcome.results) == 1
    assert outcome.results[0].artifact_id == "pyproject.toml"
    assert outcome.charged_tool == 2  # 1 manifest read + 1 resolution (1 manifest available)
    assert outcome.charged_tokens > 0


def test_cost_only_requirements_present(tmp_path):
    (tmp_path / "requirements.txt").write_text("requests>=2.0\n", encoding="utf-8")
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "specifier": ">=2.0", "scope": "core"}],
        "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.manifests_inspected == ("requirements.txt",)
    assert outcome.executions == 1
    assert len(outcome.results) == 1
    assert outcome.results[0].artifact_id == "requirements.txt"
    assert outcome.charged_tool == 2


def test_cost_both_manifests_present(tmp_path):
    _write_fixture(tmp_path, ["requests>=2.0"], ["requests>=2.0"])
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "specifier": ">=2.0", "scope": "core"}],
        "rev-1", None, goal_aspects=("requests",),
    )
    assert set(outcome.manifests_inspected) == {"pyproject.toml", "requirements.txt"}
    assert outcome.executions == 2
    assert len(outcome.results) == 2
    # 2 manifest reads + a per-target resolution charge of len(available)=2.
    assert outcome.charged_tool == 4
    assert outcome.charged_tokens > 0


def test_cost_manifests_rejected_by_symlink_size_encoding_cost_nothing(tmp_path):
    from argos_epistemic.dependency_verifiers import (
        MAX_MANIFEST_BYTES,
        verify_dependency_targets,
    )

    # symlink
    (tmp_path / "pyproject.toml").symlink_to(tmp_path / "does-not-exist.toml")
    # oversized
    huge = "x" * (MAX_MANIFEST_BYTES + 10)
    (tmp_path / "requirements.txt").write_text(f"# {huge}\nrequests>=2.0\n", encoding="utf-8")

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.manifests_inspected == ()
    assert outcome.results == ()
    assert outcome.executions == 0
    assert outcome.charged_tokens == 0
    assert outcome.charged_tool == 0
    assert "pyproject.toml:symlink_rejected" in outcome.diagnostics
    assert "requirements.txt:exceeds_size_limit" in outcome.diagnostics


def test_cost_target_with_zero_available_manifests_costs_nothing(tmp_path):
    """Directory exists but neither manifest does: the target has nothing to
    resolve against and must never be charged or executed."""
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.executions == 0
    assert outcome.charged_tokens == 0
    assert outcome.charged_tool == 0


def test_executions_tool_cost_and_results_are_reconstructible(tmp_path):
    """executions == len(results); charged_tool's per-target component ==
    executions (1 tool unit per resolution) plus 1 per manifest actually read."""
    _write_fixture(tmp_path, ["flask>=1.0", "requests>=2.0"], ["flask>=1.0", "requests>=2.0"])
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path,
        [
            {"name": "flask", "specifier": ">=1.0", "scope": "core"},
            {"name": "requests", "specifier": ">=2.0", "scope": "core"},
        ],
        "rev-1", None, goal_aspects=("flask", "requests"),
    )
    assert outcome.executions == len(outcome.results)
    manifest_read_tool = len(outcome.manifests_inspected)
    resolution_tool = outcome.accepted_targets * len(outcome.manifests_inspected)
    assert outcome.charged_tool == manifest_read_tool + resolution_tool
    assert outcome.executions == resolution_tool


# --------------------------------------------------------------------------
# P1-4: single fail-closed open (O_NOFOLLOW), no separate check-then-open.
# --------------------------------------------------------------------------


def test_symlink_replacement_between_would_be_check_and_open_cannot_slip_through(tmp_path):
    """A single os.open(..., O_NOFOLLOW) makes the symlink rejection part of
    the atomic open syscall - there is no separate is_symlink()-then-open()
    window for a concurrent replacement to exploit. We cannot literally win a
    race in a unit test, but we CAN prove the design has no such window: the
    manifest is a symlink AT THE MOMENT verify_dependency_targets touches it,
    and it must be rejected, exercising the exact code path a race would
    target."""
    real = tmp_path / "real.toml"
    real.write_text('[project]\nname="x"\ndependencies=["requests>=2.0"]\n', encoding="utf-8")
    link = tmp_path / "pyproject.toml"
    link.symlink_to(real)

    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        tmp_path, [{"name": "requests", "specifier": ">=2.0", "scope": "core"}],
        "rev-1", None, goal_aspects=("requests",),
    )
    assert outcome.results == ()
    assert outcome.charged_tokens == 0
    assert "pyproject.toml:symlink_rejected" in outcome.diagnostics


# --------------------------------------------------------------------------
# P1-5: goal_aspects is validated BEFORE being iterated - hostile input never
# raises and never reinterprets an iterable's elements/keys as aspect names.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile_goal_aspects",
    [7, object(), 3.5, {"requests": True}, {"requests"}, b"requests", None],
)
def test_hostile_goal_aspects_never_raises_and_never_admits(hostile_goal_aspects):
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        ".", [{"name": "requests", "scope": "core"}], "rev-1", None,
        goal_aspects=hostile_goal_aspects,
    )
    assert outcome.results == ()
    assert outcome.accepted_targets == 0
    assert outcome.charged_tokens == 0
    assert "invalid_goal_aspects" in outcome.diagnostics


def test_string_goal_aspects_is_rejected_not_iterated_as_characters():
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        ".", [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects="requests",
    )
    assert "invalid_goal_aspects" in outcome.diagnostics
    assert outcome.results == ()


def test_valid_goal_aspects_list_still_works():
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    outcome = verify_dependency_targets(
        ".", [{"name": "requests", "scope": "core"}], "rev-1", None, goal_aspects=["requests"],
    )
    assert outcome.accepted_targets == 1  # list (not just tuple) is accepted


def test_dependency_verification_diagnostic_reaches_the_public_report_for_hostile_goal_aspects():
    """The diagnostic must appear in report['dependency_verification'], never
    escape as an exception through analyze_path."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        # Call the boundary directly with hostile goal_aspects, then check that
        # analyze_system (as analyze_path would call it) surfaces the outcome
        # cleanly regardless.
        outcome = verify_dependency_targets(
            root, [{"name": "flask", "scope": "core"}], "rev-1", None, goal_aspects=7,
        )
        assert "invalid_goal_aspects" in outcome.diagnostics

        from argos_epistemic.algorithm import analyze_system

        goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
        report = analyze_system(
            {"name": "x", "artifacts": []}, goal, Budget(tokens_remaining=1000, tool_remaining=10),
            dependency_verification_outcome=outcome,
        )
    assert "invalid_goal_aspects" in report["dependency_verification"]["diagnostics"]


# --------------------------------------------------------------------------
# P1-6: dependency_verification_outcome must be a TYPED
# DependencyVerificationOutcome - a caller-supplied dict is never trusted,
# and cost/report are always derived from the SAME object.
# --------------------------------------------------------------------------


def test_hostile_dependency_verification_dict_never_raises_and_is_ignored():
    from argos_epistemic.algorithm import Budget, analyze_system

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(
        system, goal, budget,
        dependency_verification_outcome={"cost": {"tokens": object()}},
    )
    assert report["dependency_verification"]["enabled"] is False
    assert "invalid_dependency_verification_outcome" in report["dependency_verification"]["diagnostics"]
    assert report["cost"]["estimated_tokens"] == 0
    assert report["cost"]["observed_tokens"] == 0


@pytest.mark.parametrize("garbage", [7, "not-a-summary", object(), [1, 2, 3], 3.5])
def test_arbitrary_type_dependency_verification_outcome_never_raises(garbage):
    from argos_epistemic.algorithm import Budget, analyze_system

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(
        system, goal, budget, dependency_verification_outcome=garbage,
    )
    assert report["dependency_verification"]["enabled"] is False


def test_dependency_verification_outcome_with_negative_cost_is_clamped():
    from argos_epistemic.algorithm import Budget, analyze_system
    from argos_epistemic.dependency_verifiers import DependencyVerificationOutcome

    hostile_outcome = DependencyVerificationOutcome(
        results=(), diagnostics=(), manifests_inspected=(),
        requested_targets=0, accepted_targets=0, rejected_targets=0, executions=0,
        families_executed=(), charged_tokens=-999, charged_tool=-5,
    )
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(
        system, goal, budget, dependency_verification_outcome=hostile_outcome,
    )
    assert report["cost"]["estimated_tokens"] == 0
    assert report["cost"]["observed_tokens"] == 0
    assert "invalid_dependency_verification_cost" in report["dependency_verification"]["diagnostics"]


def test_verification_results_and_dependency_verification_outcome_are_independent():
    """Passing dependency_verification_outcome alone (without also passing its
    .results through verification_results) must NOT fabricate a proposition -
    the two parameters are separate by design (P1-6)."""
    import tempfile
    from pathlib import Path

    from argos_epistemic import Budget
    from argos_epistemic.algorithm import analyze_system
    from argos_epistemic.dependency_verifiers import verify_dependency_targets

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_fixture(root, ["flask>=1.0"], ["flask>=1.0"])
        outcome = verify_dependency_targets(
            root, [{"name": "flask", "specifier": ">=1.0", "scope": "core"}],
            "rev-1", None, goal_aspects=("flask",),
        )
    assert outcome.results  # sanity: real work happened
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    report = analyze_system(
        {"name": "x", "artifacts": []}, goal, Budget(tokens_remaining=1000, tool_remaining=10),
        dependency_verification_outcome=outcome,  # NOT also passed via verification_results
    )
    assert report["proposition_count"] == 0  # report section present, but no propositions
    assert report["dependency_verification"]["verification_result_count"] == len(outcome.results)


# --------------------------------------------------------------------------
# P2-1: conflicts from initially-admitted evidence are computed BEFORE the
# first threshold/capacity check, regardless of the starting budget.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tokens,tool", [(0, 0), (1000, 10)])
def test_initial_support_and_refutes_produce_a_conflict_before_the_loop_runs(tokens, tool):
    from argos_epistemic.algorithm import Budget, analyze_system

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    support = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', target,
        "run-1", "rev-1", ("requests",),
    )
    refutes = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=9.0"]\n', target,
        "run-2", "rev-1", ("requests",),
    )
    assert support.normalized_claim_id == refutes.normalized_claim_id
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=tokens, tool_remaining=tool)
    report = analyze_system(system, goal, budget, verification_results=[support, refutes])
    assert report["conflict_count"] == 1
    assert report["complete"] is False


def test_initial_conflict_set_is_identical_across_budget_levels():
    from argos_epistemic.algorithm import Budget, analyze_system

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    support = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', target,
        "run-1", "rev-1", ("requests",),
    )
    refutes = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=9.0"]\n', target,
        "run-2", "rev-1", ("requests",),
    )
    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": "rev-1"}
    zero = analyze_system(
        system, goal, Budget(tokens_remaining=0, tool_remaining=0),
        verification_results=[support, refutes],
    )
    positive = analyze_system(
        system, goal, Budget(tokens_remaining=1000, tool_remaining=10),
        verification_results=[support, refutes],
    )
    assert zero["conflicts"] and positive["conflicts"]
    assert {c["claim_id"] for c in zero["conflicts"]} == {c["claim_id"] for c in positive["conflicts"]}


# --------------------------------------------------------------------------
# Final adversarial round: garbage in verification_results (iterable and
# non-iterable), permutation/idempotence spot checks, invariants.
# --------------------------------------------------------------------------


def test_non_iterable_verification_results_never_raises():
    from argos_epistemic.algorithm import Budget, analyze_system

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["flask"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    try:
        analyze_system(system, goal, budget, verification_results=7)
    except TypeError:
        pytest.fail("analyze_system must not raise on a non-iterable verification_results")


def test_verification_results_generator_is_consumed_exactly_once():
    """A generator (not a list) must still be admitted correctly - the
    admission loop consumes it exactly once, never re-iterating."""
    from argos_epistemic.algorithm import Budget, analyze_system

    target = DependencyTarget(name="requests", specifier=">=2.0", scope="core")
    r1 = _pep621_at(
        '[project]\nname="x"\ndependencies=["requests>=2.0"]\n', target,
        "run-1", "rev-1", ("requests",),
    )
    r2 = _pep508(REQUIREMENTS_BASIC, target, execution_id="run-2", revision="rev-1")

    def gen():
        yield r1
        yield r2

    system = {"name": "x", "artifacts": []}
    goal = {"name": "g", "aspects": ["requests"], "target_revision": "rev-1"}
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    report = analyze_system(system, goal, budget, verification_results=gen())
    assert report["proposition_count"] == 2
