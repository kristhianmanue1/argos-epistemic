import sys

import pytest

from argos_epistemic import (
    Budget,
    Cost,
    analyze_path,
    analyze_system,
    build_call_graph,
    extract_system,
    run,
)


def test_run_terminates_and_synthesizes():
    report = run()
    assert report["system"] == "argos"
    assert report["goal"] == "autoanalisis"
    assert report["evidence_count"] == 3
    assert report["belief_count"] == 3
    assert "coverage" in report
    assert "residual_risk" in report
    assert isinstance(report["levels_covered"], list)
    assert set(report["levels_covered"]).issubset({0, 2, 4})


def test_budget_bounds_loop():
    budget = Budget(tokens_remaining=120, tool_remaining=2)
    report = run(budget=budget)
    assert report["evidence_count"] <= 2
    assert budget.tokens_remaining >= 0
    assert budget.tool_remaining >= 0


def test_empty_system_terminates_without_error():
    report = analyze_system(
        system={"name": "vacio", "artifacts": []},
        goal={"name": "g", "aspects": ["a"], "theta_coverage": 0.9, "rho_risk": 0.1},
        budget=Budget(tokens_remaining=1000, tool_remaining=10),
    )
    assert report["evidence_count"] == 0
    assert report["belief_count"] == 0
    assert report["coverage"] == 0.0
    assert report["residual_risk"] == 1.0
    assert report["complete"] is False


def test_deterministic():
    r1 = run()
    r2 = run()
    assert r1 == r2


def _threshold_report(**goal_extra):
    return analyze_system(
        system={
            "name": "rico",
            "artifacts": [
                {"id": f"a{i}", "content": str(i), "level": i, "relevance": 1.0, "kind": "artifact",
                 "supports": [{"aspect": "x"}]}
                for i in range(5)
            ],
        },
        goal={
            "name": "cobertura",
            "aspects": ["x"],
            "theta_coverage": 0.5,
            "rho_risk": 0.1,
            **goal_extra,
        },
        budget=Budget(tokens_remaining=100000, tool_remaining=1000),
    )


def test_should_stop_when_thresholds_met():
    """Thresholds alone no longer complete: corroboration must also hold.

    These artifacts declare their own support and carry no verifier profile,
    execution or target revision, so they are undemonstrated sources. With the
    default ``min_sources_per_aspect=2`` the independence gate refuses
    completion no matter how high legacy coverage climbs; with a single source
    required, the thresholds do carry it through.
    """
    strict = _threshold_report()
    assert strict["coverage"] >= strict["completion"]["thresholds_met"]
    assert strict["complete"] is False
    assert "insufficient_sources" in strict["completion"]["reason_codes"]

    relaxed = _threshold_report(min_sources_per_aspect=1)
    assert relaxed["complete"] is True
    assert relaxed["evidence_count"] >= 1


def test_cost_dominance():
    small = Cost(tokens=10, tool=1)
    big = Cost(tokens=100, tool=5)
    assert small.dominates(big)
    assert not big.dominates(small)
    budget = Budget(tokens_remaining=50, tool_remaining=2)
    assert budget.can_afford(small)
    assert not budget.can_afford(big)


def test_detects_conflict_between_doc_and_code():
    system = {
        "name": "divergente",
        "artifacts": [
            {"id": "doc_f", "content": "feature on", "location": "f_X", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "f_X"}]},
            {"id": "code_f", "content": "feature off", "location": "f_X", "level": 4, "relevance": 1.0, "kind": "code",
             "refutes": [{"aspect": "f_X"}]},
        ],
    }
    goal = {"name": "g", "aspects": ["f_X"], "theta_coverage": 2.0, "rho_risk": 0.0}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=50))
    assert report["conflict_count"] >= 1
    conflict = report["conflicts"][0]
    assert conflict["scope"] == "f_X"
    assert conflict["evidence_for"]
    assert conflict["evidence_against"]
    assert conflict["resolution_status"] == "open"


def test_same_polarity_divergence_is_not_a_conflict():
    goal = {"name": "g", "aspects": ["auth"], "theta_coverage": 2.0, "rho_risk": 0.0}
    same = {
        "name": "s",
        "artifacts": [
            {"id": "a", "content": "Autenticacion requerida", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "auth"}]},
            {"id": "b", "content": "autenticacion  requerida!!!", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "auth"}]},
        ],
    }
    divergent = {
        "name": "s",
        "artifacts": [
            {"id": "a", "content": "autenticacion requerida", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "auth"}]},
            {"id": "b", "content": "sin autenticacion", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "auth"}]},
        ],
    }
    r_same = analyze_system(same, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    r_div = analyze_system(divergent, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    assert r_same["conflict_count"] == 0
    assert r_div["conflict_count"] == 0


def test_q_g_invariant_holds_under_compression_and_breaks_on_eviction():
    from argos_epistemic import Belief, BeliefStore, Evidence, EvidenceStore, q_g_invariant

    store = EvidenceStore()
    ev = Evidence(id="e1", content="important", kind="doc", source="disk", location="l", level=0)
    store.add(ev)
    for i in range(2, 12):
        store.add(Evidence(id=f"e{i}", content=f"filler {i}", kind="doc", source="disk", location=f"l{i}", level=0))
    beliefs = BeliefStore()
    beliefs._items.append(
        Belief(
            claim="c", confidence=0.9, status="supported",
            provenance="e1", dependencies=("e1",),
            scope="l", position=frozenset({"important"}),
        )
    )
    assert q_g_invariant(store, beliefs) is True

    store.compress(Budget(tokens_remaining=10000, tool_remaining=10), preserve_provenance=True, preserve_invariants=set())
    assert sum(1 for e in store if e.compressed) >= 1
    assert q_g_invariant(store, beliefs) is True  # digest -> traceability intact

    store._items.remove(ev)  # simulate a destructive compressor (eviction)
    assert q_g_invariant(store, beliefs) is False


def test_non_functional_extractors_add_evidence():
    system = {
        "name": "nf",
        "artifacts": [
            {"id": "a", "content": "config", "level": 2, "relevance": 1.0, "kind": "config", "nf": ["sec"]},
        ],
    }
    without_nf = analyze_system(
        system,
        {"name": "g", "aspects": ["a"], "non_functional": [], "theta_coverage": 2.0, "rho_risk": 0.0},
        Budget(tokens_remaining=10000, tool_remaining=50),
    )
    with_nf = analyze_system(
        system,
        {"name": "g", "aspects": ["a"], "non_functional": ["sec"], "theta_coverage": 2.0, "rho_risk": 0.0},
        Budget(tokens_remaining=10000, tool_remaining=50),
    )
    assert without_nf["evidence_count"] == 1
    assert with_nf["evidence_count"] == 2
    assert "nf:sec" in with_nf["evidence_kinds"]


def test_compression_summarizes_when_over_capacity():
    system = {
        "name": "grande",
        "artifacts": [
            {"id": f"f{i}", "content": f"v{i}", "level": i % 5, "relevance": 1.0, "kind": f"k{i % 3}"}
            for i in range(12)
        ],
    }
    goal = {"name": "compresion", "aspects": ["x"], "theta_coverage": 2.0, "rho_risk": 0.0}
    report = analyze_system(system, goal, Budget(tokens_remaining=8192, tool_remaining=1000))
    assert report["evidence_count"] == 12
    assert report["compressed_count"] >= 1
    assert report["evidence_kinds"]


def test_compression_capacity_is_budget_adaptive():
    from argos_epistemic import capacity_for_budget

    assert capacity_for_budget(Budget(tokens_remaining=4096, tool_remaining=10)) == 4
    assert capacity_for_budget(Budget(tokens_remaining=100_000, tool_remaining=10)) >= 90
    system = {
        "name": "grande",
        "artifacts": [
            {"id": f"f{i}", "content": f"v{i}", "level": 1, "relevance": 1.0, "kind": "k"}
            for i in range(12)
        ],
    }
    goal = {"name": "g", "aspects": ["x"], "theta_coverage": 2.0, "rho_risk": 0.0}
    loose = analyze_system(system, goal, Budget(tokens_remaining=100_000, tool_remaining=1000))
    tight = analyze_system(system, goal, Budget(tokens_remaining=4096, tool_remaining=1000))
    assert loose["compressed_count"] == 0
    assert tight["compressed_count"] >= 1


def test_extract_system_over_real_repo():
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    ids = {a["id"] for a in system["artifacts"]}
    assert "L1:topology" in ids
    assert "README.md" in ids
    assert "pyproject.toml" in ids
    assert "argos_epistemic/algorithm.py" in ids
    levels = {a["level"] for a in system["artifacts"]}
    assert {0, 1, 2, 4}.issubset(levels)
    assert all(0.0 <= a["relevance"] <= 1.0 for a in system["artifacts"])


def test_extract_ignores_venv_and_cache(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "hidden.py").write_text("secret = True", encoding="utf-8")
    (tmp_path / ".DS_Store").write_bytes(b"metadata")
    (tmp_path / "visible.py").write_text("visible = True", encoding="utf-8")

    system = extract_system(tmp_path)
    ids = {a["id"] for a in system["artifacts"]}
    topology = next(a["content"] for a in system["artifacts"] if a["id"] == "L1:topology")
    assert "visible.py" in ids
    assert ".venv" not in topology
    assert ".DS_Store" not in topology


def test_analyze_path_terminates_on_real_repo():
    report = analyze_path(
        ".",
        goal={"name": "seguridad", "aspects": ["algorithm", "config"], "theta_coverage": 0.9, "rho_risk": 0.1},
        budget=Budget(tokens_remaining=50000, tool_remaining=400),
    )
    assert report["system"] is not None
    assert report["evidence_count"] >= 1
    assert isinstance(report["levels_covered"], list)
    assert report["budget_remaining"]["tokens"] >= 0


def test_call_graph_detects_known_call():
    from pathlib import Path

    py = [Path("argos_epistemic/algorithm.py")]
    cg = build_call_graph(Path("."), py)
    caller = "argos_epistemic/algorithm.py::analyze_system"
    callee = "argos_epistemic/algorithm.py::execute_action"
    assert caller in cg.nodes
    assert callee in cg.nodes
    assert (caller, callee) in cg.edges
    impact = cg.impact()
    assert impact[caller] > 0.0


def test_extract_tags_impact_and_centrality():
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    assert any(a.get("impact", 0) > 0 for a in system["artifacts"])
    assert any(a.get("centrality", 0) > 0 for a in system["artifacts"])
    assert system["call_graph"]["nodes"] > 0
    assert system["call_graph"]["edges"] > 0
    assert any(a["id"] == "L3:callgraph" for a in system["artifacts"])


def test_relevance_blend_deterministic():
    s1 = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    s2 = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    m1 = {a["id"]: a["relevance"] for a in s1["artifacts"]}
    m2 = {a["id"]: a["relevance"] for a in s2["artifacts"]}
    assert m1 == m2


def test_s_semantic_is_pluggable_and_moves_relevance():
    default = extract_system(".", goal={"name": "x", "aspects": ["algorithm"]})
    custom = extract_system(
        ".",
        goal={"name": "x", "aspects": ["algorithm"]},
        semantic_fn=lambda art, goal: 1.0 if "extractors" in art.lower() else 0.0,
    )
    d = {a["id"]: a["relevance"] for a in default["artifacts"]}
    c = {a["id"]: a["relevance"] for a in custom["artifacts"]}
    assert "s_semantic" in next(a for a in custom["artifacts"] if a["id"] == "argos_epistemic/extractors.py")
    assert c["argos_epistemic/extractors.py"] >= d["argos_epistemic/extractors.py"]


def test_git_log_summary_on_this_repo():
    from argos_epistemic import git_log_summary

    summary = git_log_summary(".")
    assert summary is not None
    assert summary["commits"] >= 1
    assert summary["last_commit"] is not None
    assert summary["days_since_last_commit"] is not None


def test_historical_verification_confidence():
    from argos_epistemic import Budget, analyze_path

    report = analyze_path(
        ".",
        goal={"name": "historia", "aspects": ["algorithm"], "theta_coverage": 2.0, "rho_risk": 0.0,
              "aspect_linker": lambda c, a: 1.0},
        budget=Budget(tokens_remaining=500000, tool_remaining=5000),
        run_history=True,
    )
    assert "history" in report["evidence_kinds"]
    hist = [c for c in report["conclusions"] if c["method"] == "historical"]
    assert hist and hist[0]["confidence"] == 0.8 and hist[0]["status"] == "unknown"
    assert hist[0]["relation"] == "mentions"


def test_scrub_env_drops_credentials():
    from argos_epistemic import scrub_env

    env = {"PATH": "/bin", "GITHUB_TOKEN": "x", "DB_PASSWORD": "y", "API_KEY": "z", "SAFE_VAR": "1"}
    out = scrub_env(env)
    assert "GITHUB_TOKEN" not in out and "DB_PASSWORD" not in out and "API_KEY" not in out
    assert out["PATH"] == "/bin" and out["SAFE_VAR"] == "1"


def test_run_isolated_basic_and_timeout(tmp_path):
    from argos_epistemic import run_isolated

    ok = run_isolated(["true"], cwd=tmp_path, timeout=10)
    assert ok["returncode"] == 0 and ok["error"] is None
    slow = run_isolated(["sleep", "5"], cwd=tmp_path, timeout=1)
    assert slow["returncode"] is None and slow["error"] == "TimeoutExpired"


def test_embedding_semantic_better_than_lexical_on_morphology():
    from argos_epistemic import embedding_semantic, lexical_semantic

    art = "authentication module for the api"
    goal = "auth seguridad"
    assert embedding_semantic(art, goal) > lexical_semantic(art, goal)


def test_h4_loader_runs_only_when_selected():
    from argos_epistemic import analyze_system

    called = []

    def loader():
        called.append(True)
        return {"content": "deferred evidence payload", "run": {"status": "supported"}}

    system = {
        "name": "s",
        "artifacts": [
            {"id": "cheap", "content": "x", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "a"}]},
            {"id": "dyn", "content": "", "location": "(dynamic)", "level": 5, "relevance": 0.85,
             "kind": "test-run", "verification_method": "dynamic", "size": 100000,
             "supports": [{"aspect": "a"}], "loader": loader},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["a"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=500, tool_remaining=2))
    assert called == []  # 'dyn' too expensive (size 100000) -> never selected -> loader not run
    assert report["evidence_count"] == 1


def test_h4_loader_runs_when_affordable_and_cost_is_observed():
    from argos_epistemic import analyze_system

    called = []

    def loader():
        called.append(True)
        return {"content": "deferred evidence payload of some length", "run": {"status": "supported"}}

    system = {
        "name": "s",
        "artifacts": [
            {"id": "dyn", "content": "", "location": "(dynamic)", "level": 5, "relevance": 0.85,
             "kind": "test-run", "verification_method": "dynamic", "size": 100,
             "supports": [{"aspect": "a"}], "loader": loader},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["a"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=100000, tool_remaining=10))
    assert called == [True]
    assert any(c["method"] == "dynamic" for c in report["conclusions"])
    assert report["cost"]["observed_tokens"] > 0
    assert report["cost"]["estimated_tokens"] >= report["cost"]["observed_tokens"] / 25  # size hint was small


def test_h7_polarity_contradiction_on_same_aspect():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "doc", "content": "auth ok", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "auth"}]},
            {"id": "t", "content": "auth auth", "location": "(dynamic)", "level": 5, "relevance": 0.85,
             "kind": "test-run", "verification_method": "dynamic", "supports": [{"aspect": "auth"}],
             "run": {"runner": "x", "status": "contradicted", "returncode": 1,
                     "passed": 0, "failed": 1, "errors": 0}},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["auth"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=10000, tool_remaining=20))
    assert report["conflict_count"] >= 1
    conflict = report["conflicts"][0]
    assert conflict["scope"] == "auth"
    assert conflict["severity"] >= 0.9
    assert conflict["evidence_for"] and conflict["evidence_against"]


def test_h7_conflicts_deduplicated_across_iterations():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "a", "content": "feature on", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "f"}]},
            {"id": "b", "content": "feature off", "level": 0, "relevance": 1.0, "kind": "doc",
             "refutes": [{"aspect": "f"}]},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["f"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=10000, tool_remaining=20))
    assert report["conflict_count"] == 1  # dedup: one conflict, not accumulated


def test_h7_same_aspect_textual_diversity_is_not_a_conflict():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "doc_x", "content": "feature on", "location": "docs/file.md", "level": 0,
             "relevance": 1.0, "kind": "doc", "supports": [{"aspect": "f"}]},
            {"id": "code_y", "content": "feature off", "location": "src/file.py", "level": 4,
             "relevance": 1.0, "kind": "code", "supports": [{"aspect": "f"}]},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["f"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=10000, tool_remaining=20))
    assert report["conflict_count"] == 0


def test_h1_irrelevant_evidence_does_not_raise_coverage():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "irrel", "content": "completely unrelated content zzz", "level": 0, "relevance": 1.0, "kind": "doc"},
        ],
    }
    goal = {"name": "g", "aspects": ["target"], "theta_coverage": 2.0, "rho_risk": 0.0}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["evidence_count"] == 1
    assert report["proposition_count"] == 0
    assert report["coverage"] == 0.0
    assert report["aspect_scores"]["target"] == 0.0
    assert report["complete"] is False


def test_h1_coverage_requires_corroboration_and_is_weighted():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "a1", "content": "x", "level": 0, "relevance": 1.0, "kind": "doc", "supports": [{"aspect": "alpha"}]},
            {"id": "a2", "content": "y", "level": 0, "relevance": 1.0, "kind": "doc", "supports": [{"aspect": "alpha"}]},
            {"id": "a3", "content": "z", "level": 0, "relevance": 1.0, "kind": "doc", "supports": [{"aspect": "beta"}]},
        ],
    }
    goal = {
        "name": "g",
        "aspects": [{"name": "alpha", "weight": 0.75}, {"name": "beta", "weight": 0.25}],
        "theta_coverage": 2.0,
        "rho_risk": 0.0,
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    # alpha has 2 corroborating sources (mass 1.8 / 1.8 -> 1.0); beta has 1 (0.9/1.8 -> 0.5)
    assert abs(report["aspect_scores"]["alpha"] - 1.0) < 0.02
    assert abs(report["aspect_scores"]["beta"] - 0.5) < 0.02
    assert abs(report["coverage"] - 0.875) < 0.03  # 0.75*1.0 + 0.25*0.5


def test_h1_single_source_does_not_saturate_coverage():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "a1", "content": "x", "level": 0, "relevance": 1.0, "kind": "doc", "supports": [{"aspect": "alpha"}]},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["alpha"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=10000, tool_remaining=10))
    # one corroborating source -> 0.9/1.8 = 0.5, NOT saturated to 0.9
    assert abs(report["aspect_scores"]["alpha"] - 0.5) < 0.02


def test_h5_conclusions_carry_section_23_fields():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "d", "content": "auth doc", "level": 0, "relevance": 1.0, "kind": "doc",
             "supports": [{"aspect": "auth"}]},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["auth"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=10000, tool_remaining=10))
    concl = report["conclusions"][0]
    for field in ("claim", "aspect", "confidence", "status", "evidence", "method", "scope", "timestamp"):
        assert field in concl


def test_h2_negative_run_is_not_supported():
    system = {
        "name": "s",
        "artifacts": [
            {
                "id": "L5:x",
                "content": "runner=x rc=1 passed=0 failed=1",
                "location": "(dynamic)",
                "level": 5,
                "relevance": 0.85,
                "kind": "test-run",
                "verification_method": "dynamic",
                "run": {"runner": "x", "status": "contradicted", "returncode": 1,
                        "passed": 0, "failed": 1, "errors": 0},
            }
        ],
    }
    goal = {"name": "g", "aspects": ["x"], "theta_coverage": 2.0, "rho_risk": 0.0}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    concl = report["conclusions"][0]
    assert concl["status"] == "contradicted"
    assert concl["confidence"] <= 0.2
    assert report["complete"] is False


def test_h3_higher_relevance_same_cost_wins_utility():
    from argos_epistemic import BeliefStore, ConflictStore, EvidenceStore
    from argos_epistemic.algorithm import expected_utility, generate_candidate_actions

    system = {
        "artifacts": [
            {"id": "lo", "content": "same content", "level": 1, "relevance": 0.1, "kind": "x"},
            {"id": "hi", "content": "same content", "level": 1, "relevance": 1.0, "kind": "x"},
        ]
    }
    goal = {"name": "g", "aspects": ["x"]}
    actions = generate_candidate_actions(system, goal, EvidenceStore(), BeliefStore(), ConflictStore(), [])
    by_id = {a.target_id: a for a in actions}
    assert by_id["lo"].estimated_cost.tokens == by_id["hi"].estimated_cost.tokens
    budget = Budget(tokens_remaining=1000, tool_remaining=10)
    u_lo = expected_utility(by_id["lo"], goal, EvidenceStore(), BeliefStore(), budget)
    u_hi = expected_utility(by_id["hi"], goal, EvidenceStore(), BeliefStore(), budget)
    assert u_hi > u_lo


def test_h6_compression_digest_is_stable_sha256():
    import hashlib

    from argos_epistemic import Evidence

    e1 = Evidence(id="a", content="hello world", kind="x", source="d", location="l", level=0)
    e2 = Evidence(id="b", content="hello world", kind="x", source="d", location="l", level=0)
    e1.compress_in_place()
    e2.compress_in_place()
    expected = "phi:" + hashlib.sha256(b"hello world").hexdigest()[:16]
    assert e1.digest == expected
    assert e1.digest == e2.digest  # stable (not hash()-randomized)


def test_link_impact_prior_lifts_production_code_above_threshold():
    # Lever del item "linker sobre-enlaza docs": S_semantic sola favorece docs
    # cortos sobre codigo diluido. El prior de impact (link_impact_weight) levanta
    # el link efectivo del codigo productivo sin tocar a los docs (impact=0).
    from argos_epistemic.algorithm import link_aspects

    def low(content, aspect):  # sim baja uniforme (codigo y doc por igual)
        return 0.3

    code = {"id": "core.py", "content": "def run(): pass", "impact": 0.5}
    doc = {"id": "README.md", "content": "all about commands", "impact": 0.0}
    goal = {"aspects": ["command"], "link_threshold": 0.6}

    # sin prior: ninguno enlaza (0.3 < 0.6)
    assert link_aspects(code, ["command"], goal, low) == {}
    assert link_aspects(doc, ["command"], goal, low) == {}

    # con prior w=1.0: code 0.3+0.5=0.8 enlaza; doc 0.3+0=0.3 no
    goal_lift = {"aspects": ["command"], "link_threshold": 0.6, "link_impact_weight": 1.0}
    assert link_aspects(code, ["command"], goal_lift, low)["command"] >= 0.6
    assert link_aspects(doc, ["command"], goal_lift, low) == {}


def test_l5_logs_artifact(tmp_path):
    from argos_epistemic import logs_artifact

    (tmp_path / "app.log").write_text("2026-01-01 INFO ok\n2026-01-02 ERROR boom\ntraceback", encoding="utf-8")
    art = logs_artifact(tmp_path)
    assert art is not None
    assert art["run"]["error_signals"] >= 1
    assert art["run"]["status"] == "contradicted"
    assert art["kind"] == "logs"


def test_l5_coverage_artifact_parses_cobertura(tmp_path):
    from argos_epistemic import coverage_artifact, coverage_summary

    assert coverage_summary(tmp_path) is None  # sin coverage.xml -> None
    xml = (
        '<?xml version="1.0" ?>\n<coverage version="7.0" timestamp="0" line-rate="0.6">\n'
        "  <packages><package><classes>\n"
        '    <class filename="src/pkg/a.py" line-rate="0.9"><lines/></class>\n'
        '    <class filename="src/pkg/b.py" line-rate="0.2"><lines/></class>\n'
        "  </classes></package></packages>\n</coverage>\n"
    )
    (tmp_path / "coverage.xml").write_text(xml, encoding="utf-8")
    art = coverage_artifact(tmp_path)
    assert art is not None and art["kind"] == "coverage"
    assert art["verification_method"] == "historical"
    run = art["run"]
    assert run["line_rate"] == 0.6
    assert run["files"] == 2
    assert run["covered_files"] == 1  # sólo a.py >= 0.8
    assert run["status"] == "supported"  # total 0.6 >= 0.5
    assert "src/pkg/a.py" in run["per_file"]


def test_l5_profile_artifact_reads_cprofile_dump(tmp_path):
    import cProfile

    from argos_epistemic import profile_artifact, profile_summary

    assert profile_summary(tmp_path) is None  # sin *.prof -> None

    def workload():
        return sum(range(1000))

    prof = cProfile.Profile()
    prof.enable()
    workload()
    prof.disable()
    prof.dump_stats(str(tmp_path / "out.prof"))
    art = profile_artifact(tmp_path)
    assert art is not None and art["kind"] == "profile"
    assert art["verification_method"] == "historical"
    run = art["run"]
    assert run["total_tt"] is not None
    assert any("workload" in e["function"] for e in run["hotpaths"])


def test_l5_profile_hotpaths_are_sorted_and_profiles_are_combined(tmp_path):
    import cProfile

    from argos_epistemic import profile_summary

    def short_workload():
        return sum(range(10))

    def long_workload():
        return sum(range(500_000))

    short = cProfile.Profile()
    short.enable()
    short_workload()
    short.disable()
    short.dump_stats(str(tmp_path / "a-short.prof"))

    long = cProfile.Profile()
    long.enable()
    long_workload()
    long.disable()
    long.dump_stats(str(tmp_path / "b-long.prof"))

    summary = profile_summary(tmp_path)
    assert summary is not None
    assert summary["files"] == 2
    assert summary["profiles"] == ["a-short.prof", "b-long.prof"]
    assert any("short_workload" in entry["function"] for entry in summary["hotpaths"])
    assert any("long_workload" in entry["function"] for entry in summary["hotpaths"])
    cumulative = [entry["cumulative"] for entry in summary["hotpaths"]]
    assert cumulative == sorted(cumulative, reverse=True)


def test_l5_profile_ignores_invalid_dumps(tmp_path):
    import cProfile

    from argos_epistemic import profile_summary

    (tmp_path / "broken.prof").write_text("not pstats", encoding="utf-8")
    assert profile_summary(tmp_path) is None

    valid = cProfile.Profile()
    valid.enable()
    sum(range(100))
    valid.disable()
    valid.dump_stats(str(tmp_path / "valid.prof"))

    summary = profile_summary(tmp_path)
    assert summary is not None
    assert summary["files"] == 1
    assert summary["profiles"] == ["valid.prof"]


def test_l5_profile_limits_sources_deterministically(tmp_path):
    import cProfile

    from argos_epistemic import profile_summary

    for index in range(7):
        profile = cProfile.Profile()
        profile.enable()
        sum(range(index + 1))
        profile.disable()
        profile.dump_stats(str(tmp_path / f"{index}.prof"))

    summary = profile_summary(tmp_path)
    assert summary is not None
    assert summary["files"] == 5
    assert summary["profiles"] == [f"{index}.prof" for index in range(5)]


def test_l3_tree_sitter_javascript_when_available(tmp_path):
    import importlib

    from argos_epistemic import build_multi_call_graph
    from argos_epistemic.callgraph import L3_EXTRACTORS

    if importlib.util.find_spec("tree_sitter_javascript") is None:
        import pytest
        pytest.skip("tree-sitter-javascript not installed")
    (tmp_path / "mod.js").write_text(
        "function foo(){ bar(); }\nfunction bar(){ return 1; }\n", encoding="utf-8"
    )
    assert ".js" in L3_EXTRACTORS
    cg = build_multi_call_graph(tmp_path, [tmp_path / "mod.js"])
    ids = set(cg.nodes)
    assert "mod.js::foo" in ids and "mod.js::bar" in ids
    assert ("mod.js::foo", "mod.js::bar") in cg.edges


def test_detect_runner_by_manifest(tmp_path):
    from argos_epistemic import detect_runner

    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert detect_runner(tmp_path)[0] == "npm"
    (tmp_path / "package.json").unlink()
    (tmp_path / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
    assert detect_runner(tmp_path)[0] == "cargo"
    (tmp_path / "Cargo.toml").unlink()
    (tmp_path / "go.mod").write_text("module x\n", encoding="utf-8")
    assert detect_runner(tmp_path)[0] == "go"
    (tmp_path / "go.mod").unlink()
    assert detect_runner(tmp_path)[0] == "pytest"  # default


def test_l3_is_pluggable_per_language(tmp_path):
    from argos_epistemic import build_multi_call_graph, register_l3_extractor
    from argos_epistemic.callgraph import L3_EXTRACTORS, CallGraph

    (tmp_path / "mod.js").write_text("function foo(){ bar(); }\n", encoding="utf-8")

    def fake_js(root, files):
        cg = CallGraph()
        for f in files:
            cg.add_node(f"{f.relative_to(root)}::foo", str(f.relative_to(root)), "foo")
        return cg

    register_l3_extractor(".js", fake_js)
    try:
        cg = build_multi_call_graph(tmp_path, [tmp_path / "mod.js"])
        assert any(n == "mod.js::foo" for n in cg.nodes)
    finally:
        L3_EXTRACTORS.pop(".js", None)


def test_l3_unknown_language_is_graceful(tmp_path):
    from argos_epistemic import build_multi_call_graph

    (tmp_path / "mod.lua").write_text("function main() end\n", encoding="utf-8")
    cg = build_multi_call_graph(tmp_path, [tmp_path / "mod.lua"])
    assert len(cg.nodes) == 0  # no .lua extractor registered -> no L3, no crash


def test_impact_excludes_test_files():
    from pathlib import Path

    from argos_epistemic.callgraph import is_test_file

    cg = build_call_graph(
        Path("."),
        [Path("argos_epistemic/algorithm.py"), Path("tests/test_smoke.py")],
    )
    prod = cg.production_subgraph()
    assert all(not is_test_file(n.file) for n in prod.nodes.values())
    assert len(prod.nodes) < len(cg.nodes)
    imp = prod.impact()
    assert imp["argos_epistemic/algorithm.py::analyze_system"] > 0.0
    summary_top = extract_system(".", goal={"name": "x", "aspects": []})["call_graph"]["top_impact"]
    assert all("test" not in entry["id"].split("::")[0].lower() for entry in summary_top)


def test_run_pytest_yields_dynamic_evidence(tmp_path):
    from argos_epistemic import run_pytest

    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    result = run_pytest(tmp_path, timeout=60)
    assert result["status"] == "supported"
    assert result["passed"] >= 1
    assert result["failed"] == 0


def test_analyze_path_with_dynamic_includes_run(tmp_path):
    from argos_epistemic import Budget

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fix'\nversion = '0'\n", encoding="utf-8")
    (tmp_path / "pkg.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "test_pkg.py").write_text("from pkg import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    report = analyze_path(
        tmp_path,
        goal={"name": "refactor", "aspects": ["pkg"], "theta_coverage": 2.0, "rho_risk": 0.0,
              "aspect_linker": lambda c, a: 1.0},
        budget=Budget(tokens_remaining=500000, tool_remaining=5000),
        run_dynamic=True,
        dynamic_timeout=60,
    )
    kinds = report["evidence_kinds"]
    assert "test-run" in kinds
    dyn = [c for c in report["conclusions"] if c["method"] == "dynamic"]
    assert dyn and dyn[0]["status"] == "supported" and dyn[0]["confidence"] >= 0.9


def test_s10_confidence_propagation_clamps_to_weakest_dependency():
    from argos_epistemic import Belief, BeliefStore, propagate_confidence

    beliefs = BeliefStore()
    beliefs._items.append(Belief(claim="strong_root", confidence=0.95, status="supported",
                                 provenance="e1", dependencies=("e1",)))
    beliefs._items.append(Belief(claim="weak_root", confidence=0.30, status="weak",
                                 provenance="e2", dependencies=("e2",)))
    beliefs._items.append(Belief(claim="rests_on_strong", confidence=0.99, status="supported",
                                 provenance="x", dependencies=("strong_root",)))
    beliefs._items.append(Belief(claim="rests_on_weak", confidence=0.99, status="supported",
                                 provenance="x", dependencies=("weak_root",)))

    def resolver(dep_id):
        for b in beliefs:
            if b.claim == dep_id:
                return b.confidence
        return None

    propagate_confidence(beliefs, resolver)
    by_claim = {b.claim: b.confidence for b in beliefs}
    assert by_claim["rests_on_strong"] == 0.95  # clampeada por la raíz fuerte
    assert by_claim["rests_on_weak"] == 0.30    # clampeada por la raíz débil
    assert by_claim["strong_root"] == 0.95      # hoja sin cambios
    assert by_claim["weak_root"] == 0.30        # hoja sin cambios


def test_s10_propagation_is_noop_when_dependency_matches():
    from argos_epistemic import Belief, BeliefStore, propagate_confidence

    beliefs = BeliefStore()
    beliefs._items.append(Belief(claim="c", confidence=0.9, status="supported",
                                 provenance="e1", dependencies=("e1",)))
    propagate_confidence(beliefs, lambda d: 0.9 if d == "e1" else None)
    assert beliefs._items[0].confidence == 0.9  # no spurious clamp


def test_s10_chain_propagation_converges_transitively():
    from argos_epistemic import Belief, BeliefStore, propagate_confidence

    beliefs = BeliefStore()
    beliefs._items.append(Belief(claim="leaf", confidence=0.20, status="weak",
                                 provenance="e", dependencies=("e",)))
    beliefs._items.append(Belief(claim="mid", confidence=0.99, status="supported",
                                 provenance="e", dependencies=("leaf",)))
    beliefs._items.append(Belief(claim="top", confidence=0.99, status="supported",
                                 provenance="e", dependencies=("mid",)))

    def resolver(dep_id):
        for b in beliefs:
            if b.claim == dep_id:
                return b.confidence
        return None

    propagate_confidence(beliefs, resolver)
    by_claim = {b.claim: b.confidence for b in beliefs}
    assert by_claim["mid"] == 0.20   # clamp transitivo en 2 saltos
    assert by_claim["top"] == 0.20   # propagado hasta la cima


def test_s14_freshness_decays_with_age_and_is_neutral_without_timestamp():
    from argos_epistemic.extractors import freshness

    assert freshness(4, 0.0, 1_700_000_000.0) == 1.0  # sin t_x -> neutral
    assert freshness(4, 1_700_000_000.0, 0.0) == 1.0  # sin t_now -> neutral
    now = 1_700_000_000.0
    old = freshness(5, now - 86400 * 21, now)  # 21 días, L5
    recent = freshness(5, now - 86400, now)    # 1 día, L5
    assert 0.0 < old < recent < 1.0
    age = now - 86400 * 60
    assert freshness(0, age, now) > freshness(5, age, now)  # L0 más lento que L5


def test_s14_freshness_exposed_on_code_artifacts():
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    code = next(a for a in system["artifacts"] if a["id"] == "argos_epistemic/algorithm.py")
    assert "freshness" in code
    assert "timestamp" in code
    assert 0.0 <= code["freshness"] <= 1.0
    assert code["timestamp"] > 0


def test_s14_freshness_is_deterministic_within_run():
    s1 = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    s2 = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    f1 = {a["id"]: a.get("freshness") for a in s1["artifacts"] if "freshness" in a}
    f2 = {a["id"]: a.get("freshness") for a in s2["artifacts"] if "freshness" in a}
    assert f1 == f2  # granularidad por día -> estable dentro del mismo día


def test_s14_freshness_symmetric_across_levels():
    # §14 freshness debe ser transversal: todo artefacto lleva freshness+timestamp.
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    by_id = {a["id"]: a for a in system["artifacts"]}
    # agregados sintéticos (L1/L3): computed-now -> freshness 1.0
    assert by_id["L1:topology"]["freshness"] == 1.0
    assert by_id["L1:topology"]["timestamp"] > 0
    assert by_id["L3:callgraph"]["freshness"] == 1.0
    assert by_id["L3:callgraph"]["timestamp"] > 0
    # ficheros reales por nivel (L0 doc, L2 config, L4 code): freshness por mtime
    for aid, lvl in [("README.md", 0), ("pyproject.toml", 2),
                     ("argos_epistemic/algorithm.py", 4)]:
        art = by_id[aid]
        assert art["level"] == lvl, aid
        assert "freshness" in art and "timestamp" in art, aid
        assert 0.0 <= art["freshness"] <= 1.0, aid
        assert art["timestamp"] > 0, aid
        # el blend unificado expone s_semantic/impact/centrality en todos los niveles
        for fld in ("s_semantic", "impact", "centrality"):
            assert fld in art, (aid, fld)
    # ningún artefacto sin campo freshness
    missing = [a["id"] for a in system["artifacts"] if "freshness" not in a]
    assert missing == []


def test_l4_extracts_raises_asserts_mutations_and_skips_nested(tmp_path):
    from argos_epistemic import extract_behavior

    (tmp_path / "mod.py").write_text(
        "class C:\n"
        "    def mutates(self, x):\n        self.x = x\n"
        "    def validate(self, n):\n"
        "        if n < 0:\n            raise ValueError('neg')\n"
        "        return n\n"
        "    def invariant(self, a):\n"
        "        assert a > 0\n        return a\n"
        "    def raises_named(self):\n        raise KeyError('k')\n"
        "    def raises_call(self):\n        raise RuntimeError('r')\n"
        "    def nested(self):\n"
        "        def inner():\n            raise OSError\n"
        "        return inner\n"
        "    def reraise(self):\n        raise\n",
        encoding="utf-8",
    )
    b = {x.name: x for x in extract_behavior(tmp_path, [tmp_path / "mod.py"])}
    assert b["mutates"].mutates_self is True
    assert b["validate"].validates is True and b["validate"].raises == {"ValueError"}
    assert b["invariant"].asserts >= 1
    assert b["raises_named"].raises == {"KeyError"}
    assert b["raises_call"].raises == {"RuntimeError"}
    # el raise anidado pertenece a `inner`, no a `nested` (no doble conteo)
    assert b["nested"].raises == set()
    assert "inner" in b and b["inner"].raises == {"OSError"}
    # bare re-raise sin nombre de excepción
    assert b["reraise"].raises == set()


def test_l4_behavior_artifact_and_summary_in_extract_system():
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    art = next(a for a in system["artifacts"] if a["id"] == "L4:behavior")
    assert art["level"] == 4 and art["kind"] == "behavior"
    assert art["freshness"] == 1.0 and art["timestamp"] > 0
    s = system["behavior"]
    for fld in ("functions", "production_functions", "raising", "asserting", "mutating", "validating"):
        assert fld in s
    assert s["functions"] >= s["production_functions"] >= 0


def test_l4_known_signal_from_this_repo():
    from pathlib import Path

    from argos_epistemic import extract_behavior

    b = {
        x.id: x
        for x in extract_behavior(Path("."), [Path("argos_epistemic/extractors.py")])
    }
    es = b["argos_epistemic/extractors.py::extract_system"]
    assert "NotADirectoryError" in es.raises


def test_default_link_threshold_calibrated_per_linker():
    from argos_epistemic import default_link_threshold, embedding_semantic, lexical_semantic
    from argos_epistemic.extractors import dense_semantic

    # léxico (Jaccard, rango [0,1]): threshold bajo; denso y surrogate (rango
    # ~[0.5,0.65]): threshold alto o enlazan ruido; desconocido -> default bajo.
    assert default_link_threshold(lexical_semantic) == 0.05
    assert default_link_threshold(embedding_semantic) == 0.55
    assert default_link_threshold(dense_semantic) == 0.60
    assert default_link_threshold(lambda a, b: 0.5) == 0.05


def test_default_semantic_is_always_lexical_regardless_of_dense_availability():
    """The default path must be offline and deterministic, not host-dependent."""
    from argos_epistemic import default_semantic, lexical_semantic
    from argos_epistemic.extractors import dense_semantic

    assert default_semantic() is lexical_semantic
    assert default_semantic() is not dense_semantic


def test_default_extraction_path_never_touches_the_network(monkeypatch):
    """Fails if the default pipeline opens a socket (e.g. downloads a model)."""
    import socket

    class _NetworkAccessAttempted(RuntimeError):
        pass

    def _blocked(*args, **kwargs):
        raise _NetworkAccessAttempted("unit tests must not access the network")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    assert system["artifacts"]


def test_case_study_profiles_are_explicit_and_environment_independent():
    from argos_epistemic import lexical_semantic
    from examples.regenerate_case_studies import (
        SEMANTIC_PROFILES,
        THIRD_PARTY_CASES,
        configured_goal,
    )

    goal = configured_goal({"name": "g", "aspects": []}, "lexical-v1")
    assert goal["link_threshold"] == 0.10
    assert goal["aspect_linker"] is lexical_semantic
    assert set(SEMANTIC_PROFILES) == {"lexical-v1", "char-ngram-v1", "minilm-v1"}
    assert THIRD_PARTY_CASES["markupsafe"]["independence_class"] == "independent"
    assert THIRD_PARTY_CASES["an-kla-memory"]["independence_class"] == "operational_dependency"


def test_self_study_classifies_generated_documents_as_outputs(tmp_path):
    from examples.regenerate_case_studies import self_study_output_names

    examples = tmp_path / "examples"
    examples.mkdir()
    outputs = {
        "case-study-x.md",
        "reporte-tecnico-x.md",
        "plan-mejoras-x.md",
        "an-kla-memory-response-to-issue10.md",
    }
    for name in outputs | {"design-input.md"}:
        (examples / name).write_text(name, encoding="utf-8")
    assert self_study_output_names(tmp_path) == outputs


def test_git_identity_uses_full_revision_and_reports_dirty_state():
    from pathlib import Path

    from examples.regenerate_case_studies import git_identity

    identity = git_identity(Path("."))
    assert len(identity["revision"]) == 40
    assert isinstance(identity["dirty"], bool)


def test_third_party_cases_pin_an_exact_full_sha():
    import re

    from examples.regenerate_case_studies import THIRD_PARTY_CASES

    full_sha = re.compile(r"^[0-9a-f]{40}$")
    for slug, case in THIRD_PARTY_CASES.items():
        assert "pinned_revision" in case, f"{slug} must pin an exact revision"
        assert full_sha.match(case["pinned_revision"]), (
            f"{slug} pinned_revision must be a full 40-char SHA, not a branch/tag"
        )


def _local_origin(tmp_path):
    """A real but purely local git repo, so pin tests never touch the network."""
    import subprocess

    origin = tmp_path / "origin"
    origin.mkdir()
    run = lambda *a: subprocess.run(  # noqa: E731
        ["git", "-C", str(origin), *a], capture_output=True, text=True, check=True
    )
    subprocess.run(["git", "init", "-q", str(origin)], check=True, capture_output=True)
    run("config", "user.email", "t@example.invalid")
    run("config", "user.name", "t")
    (origin / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    run("add", "-A")
    run("commit", "-qm", "one")
    head = run("rev-parse", "HEAD").stdout.strip()
    return origin, head


def test_fetch_pinned_reports_error_on_unknown_revision(tmp_path):
    from examples.regenerate_case_studies import _fetch_pinned

    origin, _ = _local_origin(tmp_path)
    error = _fetch_pinned(str(origin), "0" * 40, tmp_path / "dest")
    assert error is not None


def test_fetch_pinned_checks_out_exactly_the_pinned_revision(tmp_path):
    from examples.regenerate_case_studies import _fetch_pinned, git_identity

    origin, head = _local_origin(tmp_path)
    dest = tmp_path / "dest"
    assert _fetch_pinned(str(origin), head, dest) is None
    identity = git_identity(dest)
    assert identity["revision"] == head
    assert identity["dirty"] is False


def test_pinned_revision_mismatch_is_rejected_not_rendered(tmp_path, monkeypatch):
    """A checkout that lands on a different revision must never be published."""
    from examples import regenerate_case_studies as mod

    origin, head = _local_origin(tmp_path)
    case = {
        "repo": str(origin),
        "pinned_revision": "1" * 40,
        "goal": {"name": "g", "aspects": ["x"], "theta_coverage": 0.8, "rho_risk": 0.25},
        "semantic_profile": "lexical-v1",
        "independence_class": "independent",
        "notes": [],
    }
    monkeypatch.setattr(mod, "_fetch_pinned", lambda repo, revision, dest: None)
    monkeypatch.setattr(mod, "git_identity", lambda root: {"revision": head, "dirty": False})
    md, error = mod._third_party_md("local", case)
    assert md is None
    assert error is not None
    assert "does not match" in error


def test_selected_targets_respects_check_target_argument():
    from examples.regenerate_case_studies import THIRD_PARTY_CASES, _selected_targets

    assert _selected_targets("argos") == ["argos"]
    assert _selected_targets("markupsafe") == ["markupsafe"]
    assert _selected_targets("an-kla-memory") == ["an-kla-memory"]
    all_targets = _selected_targets("all")
    assert all_targets[0] == "argos"
    assert set(all_targets[1:]) == set(THIRD_PARTY_CASES)


def test_failed_regeneration_preserves_previous_file_byte_for_byte(tmp_path, monkeypatch):
    from examples import regenerate_case_studies as mod

    examples = tmp_path / "examples"
    examples.mkdir()
    target = examples / "case-study-markupsafe.md"
    original = b"# previous content\n\ncoverage: 0.6333\n"
    target.write_bytes(original)

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(
        mod,
        "generate_case",
        lambda t, profile: (None, mod.STATUS_UNAVAILABLE, f"{t}: network down"),
    )
    monkeypatch.setattr(sys, "argv", ["prog", "--target", "markupsafe"])
    assert mod.main() == 1
    assert target.read_bytes() == original


def test_two_runs_with_identical_inputs_produce_identical_output(monkeypatch):
    """Determinism of the pipeline itself.

    ``_test_count`` shells out to ``pytest --collect-only``; it is pinned here so
    the assertion covers extraction, analysis and rendering rather than the cost
    and variability of re-collecting the suite twice.
    """
    from examples import regenerate_case_studies as mod

    monkeypatch.setattr(mod, "_test_count", lambda: 999)
    assert mod._argos_md("char-ngram-v1") == mod._argos_md("char-ngram-v1")


def test_check_target_all_reports_exactly_the_stale_case(monkeypatch, capsys):
    from examples import regenerate_case_studies as mod

    outcomes = {
        "argos": "case-study-argos.md is fresh",
        "markupsafe": "case-study-markupsafe.md is stale",
        "an-kla-memory": "case-study-an-kla-memory.md is fresh",
    }
    monkeypatch.setattr(
        mod,
        "check_case",
        lambda target, profile: (
            mod.STATUS_STALE if target == "markupsafe" else mod.STATUS_FRESH,
            outcomes[target],
        ),
    )
    monkeypatch.setattr(sys, "argv", ["prog", "--target", "all", "--check"])
    assert mod.main() == 1
    captured = capsys.readouterr()
    assert "case-study-markupsafe.md is stale" in captured.err
    assert "stale" not in captured.out
    assert "case-study-argos.md is fresh" in captured.out
    assert "case-study-an-kla-memory.md is fresh" in captured.out


def _an_kla_ref(requirement: str) -> str:
    return requirement.split("@")[-1].strip()


def test_an_kla_pin_does_not_drift_between_pyproject_and_requirements():
    """Regression: d31ba8b bumped requirements.txt and left pyproject.toml behind.

    The two declarations must name the same ref, otherwise `pip install -e .`
    and `pip install -r requirements.txt` provision different memory engines.
    """
    import tomllib
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    declared = [
        req
        for group in pyproject["project"].get("optional-dependencies", {}).values()
        for req in group
        if req.startswith("an-kla-memory")
    ]
    assert declared, "pyproject.toml must declare an-kla-memory"
    pinned = [
        line.strip()
        for line in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("an-kla-memory")
    ]
    assert pinned, "requirements.txt must declare an-kla-memory"
    assert {_an_kla_ref(r) for r in declared} == {_an_kla_ref(r) for r in pinned}


def test_unavailable_target_is_reported_not_silently_passed(monkeypatch):
    from examples import regenerate_case_studies as mod

    monkeypatch.setattr(
        mod,
        "evaluate_third_party",
        lambda slug, case, profile: (None, mod.STATUS_UNAVAILABLE, f"{slug}: network down"),
    )
    status, message = mod.check_case("markupsafe", None)
    assert status == mod.STATUS_UNAVAILABLE
    assert "network down" in message


def test_invalid_revision_is_distinguished_from_stale(monkeypatch):
    """The taxonomy must not collapse 'wrong revision' into 'needs regenerating'."""
    from examples import regenerate_case_studies as mod

    monkeypatch.setattr(
        mod,
        "evaluate_third_party",
        lambda slug, case, profile: (
            None,
            mod.STATUS_INVALID_REVISION,
            f"{slug}: checked-out revision deadbeef does not match pinned",
        ),
    )
    status, message = mod.check_case("markupsafe", None)
    assert status == mod.STATUS_INVALID_REVISION
    assert status != mod.STATUS_STALE
    assert "does not match" in message


def test_linker_threshold_mismatch_no_longer_overlinks_noise():
    # Repro del bug del caso an-kla-memory: el surrogate a threshold bajo enlazaba
    # ruido (.gitignore). Con default_link_threshold(embedding)=0.55, el suelo
    # ~0.5 del surrogate queda por debajo y NO enlaza.
    from argos_epistemic import embedding_semantic

    noise = "*.pyc\n__pycache__/\n.env\n"  # un .gitignore típico
    assert embedding_semantic(noise, "memory") < 0.55  # por debajo del threshold -> no enlace


def test_production_evidence_gate_blocks_overclaim_on_peripheral_only_support():
    # Repro del hallazgo click (validacion repos reales): el linker denso enlaza
    # docs/examples (impact=0) y satura coverage declarando complete=True con
    # recall 0. El gate exige apoyo productivo (impact>0) cuando hay datos L3.
    from argos_epistemic.algorithm import production_sources_met, system_has_production

    # Sistema CON datos L3: un artefacto periferico (doc, impact=0) soporta el
    # aspecto y un artefacto productivo (impact>0) existe pero NO soporta el aspecto.
    system_with_l3 = {
        "name": "click_like",
        "artifacts": [
            {"id": "doc", "content": "all about commands", "level": 0, "relevance": 0.9,
             "kind": "doc", "impact": 0.0, "supports": [{"aspect": "command"}]},
            {"id": "core.py", "content": "def run(): pass", "level": 4, "relevance": 0.5,
             "kind": "code", "impact": 0.7},
        ],
    }
    goal = {"name": "g", "aspects": ["command"], "theta_coverage": 0.3, "rho_risk": 0.5,
            "min_sources_per_aspect": 1}
    assert system_has_production(system_with_l3) is True
    report = analyze_system(system_with_l3, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    # coverage (0.5) y min_sources(1) se cumplen, pero complete debe ser False:
    # el aspecto no descansa sobre evidencia productiva (gate anti-overclaim).
    assert report["complete"] is False

    # Helper directo: soporte solo periferico -> False; con una proposicion
    # productiva (impact>0) -> True.
    from argos_epistemic.algorithm import Proposition, PropositionStore

    store = PropositionStore()
    store.add(Proposition("command", 1.0, "c", "doc", 0.9, "symbolic", "doc", impact=0.0))
    assert production_sources_met(store, [{"name": "command"}]) is False
    store.add(Proposition("command", 1.0, "c2", "core.py", 0.9, "deterministic", "core.py", impact=0.7))
    assert production_sources_met(store, [{"name": "command"}]) is True

    # Sistema SIN datos L3 (fixtures): el gate es vacuo (fallback al comportamiento previo).
    system_no_l3 = {
        "name": "fixture_like",
        "artifacts": [
            {"id": "doc", "content": "all about commands", "level": 0, "relevance": 0.9,
             "kind": "doc", "supports": [{"aspect": "command"}]},
        ],
    }
    assert system_has_production(system_no_l3) is False
    report2 = analyze_system(system_no_l3, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    # Sin gate de produccion, coverage puede llevar a complete=True (umbral bajo).
    assert report2["complete"] is True


def test_production_gate_can_be_disabled_via_goal():
    # El gate es opt-out via goal: util cuando se quiere el comportamiento previo
    # incluso con datos L3 (p.ej. analisis solo de intencion/docs).
    system = {
        "name": "s",
        "artifacts": [
            {"id": "doc", "content": "all about commands", "level": 0, "relevance": 0.9,
             "kind": "doc", "impact": 0.0, "supports": [{"aspect": "command"}]},
            {"id": "core.py", "content": "def run(): pass", "level": 4, "relevance": 0.5,
             "kind": "code", "impact": 0.7},
        ],
    }
    goal = {"name": "g", "aspects": ["command"], "theta_coverage": 0.3, "rho_risk": 0.5,
            "min_sources_per_aspect": 1,
            "require_production_evidence": False}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    assert report["complete"] is True


def _actions_for(system, goal, propositions=None):
    from argos_epistemic.algorithm import (
        BeliefStore,
        ConflictStore,
        EvidenceStore,
        generate_candidate_actions,
    )

    actions = generate_candidate_actions(
        system, goal, EvidenceStore(), BeliefStore(), ConflictStore(), [], propositions
    )
    return {a.target_id: a for a in actions}


def _calibrated(aspects=("write",)):
    """Goal using the explicitly-labelled illustrative calibration profile.

    The default profile promises zero, which would make the guards below pass
    vacuously; these tests must prove the guards hold when the numbers are NOT
    zero.
    """
    return {
        "name": "g",
        "aspects": list(aspects),
        "probative_calibration": "demo-linear-v0",
        "allow_non_empirical_calibration": True,
    }


def _support(confidence, evidence_id, aspect="write", claim=None):
    from argos_epistemic.algorithm import Proposition

    claim = claim or f"claim-{evidence_id}"
    return Proposition(
        aspect=aspect, polarity=1.0, claim=claim, evidence_id=evidence_id,
        confidence=confidence, method="symbolic", scope=aspect, relation="supports",
        claim_id=f"claim:{aspect}:{claim}",
    )


CAPABILITY_CASES = [
    # (artifact extras, expected capability) - hand-written oracle, not a
    # re-derivation of the implementation's own branching.
    ({}, "retrieval_only"),
    ({"supports": [{"aspect": "write"}]}, "probatory_static"),
    ({"refutes": [{"aspect": "write"}]}, "probatory_static"),
    ({"implements": [{"aspect": "write"}]}, "structural_relation"),
    ({"tests": [{"aspect": "write"}]}, "structural_relation"),
    ({"configures": [{"aspect": "write"}]}, "structural_relation"),
    ({"supports": [{"aspect": "telemetry"}]}, "retrieval_only"),
    ({"verification_method": "dynamic"}, "probatory_dynamic"),
]


@pytest.mark.parametrize("extras,expected", CAPABILITY_CASES)
def test_action_capability_matches_hand_written_oracle(extras, expected):
    artifact = {"id": "a", "content": "x", "level": 4, "relevance": 0.9, "kind": "code", **extras}
    system = {"name": "s", "artifacts": [artifact]}
    goal = {"name": "g", "aspects": ["write"]}
    assert _actions_for(system, goal)["a"].capability == expected


def test_retrieval_only_gets_no_coverage_and_no_risk_reduction():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "readme.md", "content": "explains the write path", "level": 0,
             "relevance": 0.9, "kind": "doc"},
        ],
    }
    action = _actions_for(system, {"name": "g", "aspects": ["write"]})["readme.md"]
    assert action.capability == "retrieval_only"
    assert action.expected_delta_coverage == 0.0
    assert action.expected_delta_risk_reduction <= 0.0
    assert action.expected_contradiction_discovery == 0.0
    # Retrieval is still worth something, under its own name.
    assert action.expected_retrieval_gain > 0.0


def test_structural_relations_get_no_probative_expectations():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "t.py", "content": "test", "level": 5, "relevance": 0.9, "kind": "test",
             "implements": [{"aspect": "write"}]},
        ],
    }
    action = _actions_for(system, {"name": "g", "aspects": ["write"]})["t.py"]
    assert action.capability == "structural_relation"
    assert action.expected_delta_coverage == 0.0
    assert action.expected_delta_risk_reduction <= 0.0


@pytest.mark.parametrize(
    "profile,diagnostic",
    [
        ("does-not-exist", "calibration_profile:unknown"),
        ({"coverage_gain": 9}, "calibration_profile:not_a_string"),
        (["x"], "calibration_profile:not_a_string"),
        (None, "calibration_profile:not_a_string"),
        (7, "calibration_profile:not_a_string"),
        ("demo-linear-v0", "calibration_profile:non_empirical_requires_opt_in"),
    ],
)
def test_invalid_or_unauthorized_calibration_reports_requested_and_effective(
    profile, diagnostic
):
    """No silent fallback under the requested name, and no accidental TypeError."""
    goal = {"name": "g", "aspects": ["write"], "probative_calibration": profile}
    action = _actions_for(_SUPPORTING_SYSTEM, goal)["core.py"]
    assert action.calibration_profile == "uncalibrated-v0"
    assert action.requested_calibration_profile != "uncalibrated-v0"
    assert diagnostic in action.declaration_diagnostics
    assert action.expected_delta_coverage == 0.0


def test_calibration_profile_metadata_is_internally_consistent():
    """`empirical` and `requires_opt_in` are separate axes; neither may lie."""
    from argos_epistemic.algorithm import PROBATIVE_CALIBRATION_PROFILES

    default = PROBATIVE_CALIBRATION_PROFILES["uncalibrated-v0"]
    # The default is a conservative zero bound, NOT an empirical calibration.
    assert default["empirical"] is False
    assert default["requires_opt_in"] is False
    assert default["status"] == "conservative_zero_bound"

    demo = PROBATIVE_CALIBRATION_PROFILES["demo-linear-v0"]
    assert demo["empirical"] is False
    assert demo["requires_opt_in"] is True
    assert demo["status"] == "illustrative_only"


def test_non_string_calibration_profile_is_reported_as_sanitised_marker():
    """The goal is caller-supplied; it must not be echoed back into the report."""
    secret = {"api_key": "s3cr3t"}
    action = _actions_for(
        _SUPPORTING_SYSTEM,
        {"name": "g", "aspects": ["write"], "probative_calibration": secret},
    )["core.py"]
    assert action.requested_calibration_profile == "<non-string:dict>"
    assert "s3cr3t" not in action.requested_calibration_profile


def test_non_empirical_profile_requires_explicit_opt_in():
    """demo-linear-v0 must never be mistaken for a production calibration."""
    from argos_epistemic.algorithm import PROBATIVE_CALIBRATION_PROFILES

    assert PROBATIVE_CALIBRATION_PROFILES["demo-linear-v0"]["requires_opt_in"] is True
    without = _actions_for(
        _SUPPORTING_SYSTEM,
        {"name": "g", "aspects": ["write"], "probative_calibration": "demo-linear-v0"},
    )["core.py"]
    assert without.calibration_profile == "uncalibrated-v0"
    with_opt_in = _actions_for(_SUPPORTING_SYSTEM, _calibrated())["core.py"]
    assert with_opt_in.calibration_profile == "demo-linear-v0"


def test_uncalibrated_default_promises_zero_probative_expectations():
    """No empirical calibration exists, so the honest prior is zero, not a guess."""
    system = {
        "name": "s",
        "artifacts": [
            {"id": "core.py", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
             "supports": [{"aspect": "write"}]},
        ],
    }
    action = _actions_for(system, {"name": "g", "aspects": ["write"]})["core.py"]
    assert action.capability == "probatory_static"
    assert action.calibration_profile == "uncalibrated-v0"
    assert action.expectation_uncertainty == "unbounded"
    assert action.expected_delta_coverage == 0.0
    assert action.expected_contradiction_discovery == 0.0
    assert action.expected_delta_risk_reduction == 0.0


def test_refutes_only_artifact_promises_no_coverage_and_no_risk_reduction():
    """A refutation cannot cover an aspect, and by the risk invariant cannot lower risk."""
    system = {
        "name": "s",
        "artifacts": [
            {"id": "neg.py", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
             "refutes": [{"aspect": "write"}]},
        ],
    }
    action = _actions_for(system, _calibrated())["neg.py"]
    assert action.capability == "probatory_static"
    assert action.expected_delta_coverage == 0.0
    assert action.expected_delta_risk_reduction <= 0.0
    # Its genuine value is discovering the contradiction, under a real profile.
    assert action.expected_contradiction_discovery > 0.0


def test_supports_and_refutes_on_same_claim_never_promises_risk_reduction():
    """Mandated regression: this combination previously promised 0.135 while the
    resulting residual_risk is 1.0."""
    system = {
        "name": "s",
        "artifacts": [
            {"id": "both.py", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
             "supports": [{"aspect": "write", "claim": "c", "scope": "s"}],
             "refutes": [{"aspect": "write", "claim": "c", "scope": "s"}]},
        ],
    }
    action = _actions_for(system, _calibrated())["both.py"]
    assert action.expected_delta_risk_reduction <= 0.0
    assert "self_contradictory_declaration" in action.declaration_diagnostics


_SUPPORTING_SYSTEM = {
    "name": "s",
    "artifacts": [
        {"id": "core.py", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
         "supports": [{"aspect": "write"}]},
    ],
}


def test_expected_coverage_tracks_headroom_not_a_binary_covered_flag():
    """Coverage is gradual via aspect_score, so partial support leaves headroom.

    Hand-computed oracle: aspect_score = clamp01(sum(conf) / 1.8). With one
    0.6 support the aspect sits at 0.3333, so a further support is still
    worth something; only once the score saturates does the delta vanish.
    """
    no_support = _actions_for(_SUPPORTING_SYSTEM, _calibrated())["core.py"]
    partial = _actions_for(
        _SUPPORTING_SYSTEM, _calibrated(), [_support(0.6, "e1")]
    )["core.py"]
    saturated = _actions_for(
        _SUPPORTING_SYSTEM, _calibrated(), [_support(0.9, "e1"), _support(0.9, "e2")]
    )["core.py"]

    assert no_support.expected_delta_coverage > 0.0
    assert partial.expected_delta_coverage > 0.0, "partial coverage must leave headroom"
    assert saturated.expected_delta_coverage == 0.0


def test_duplicate_support_does_not_inflate_expected_coverage():
    """Metamorphic: repeating the same claim must not raise the expected delta."""
    once = _actions_for(
        _SUPPORTING_SYSTEM, _calibrated(), [_support(0.6, "e1", claim="same")]
    )["core.py"]
    twice = _actions_for(
        _SUPPORTING_SYSTEM,
        _calibrated(),
        [_support(0.6, "e1", claim="same"), _support(0.6, "e1", claim="same")],
    )["core.py"]
    assert twice.expected_delta_coverage <= once.expected_delta_coverage + 1e-12


def test_legacy_known_unsound_coverage_counts_duplicate_claims_removal_target_pr_f():
    """LEGACY / KNOWN-UNSOUND compatibility contract. REMOVAL TARGET: PR F.

    This pins current behaviour that is **not correct** and must not be read as
    a specification. ``compute_residual_risk`` aggregates by claim identity, but
    ``compute_coverage``/``aspect_score`` still sum over propositions, so three
    readings of one claim treble the score.

    DESIRED behaviour, to be implemented in PR F: coverage is invariant under
    duplication of the same normalised claim and the same observed root, i.e.
    aggregated by claim and independence_group rather than by proposition
    volume.

    Until then, ``complete`` must never rest on this inflation: the independence
    gate (PR D) is what keeps duplicates from satisfying corroboration.
    """
    from argos_epistemic.algorithm import compute_coverage, compute_residual_risk

    aspects = [{"name": "write", "weight": 1.0}]
    duplicated = [_support(0.6, "e1", claim="same") for _ in range(3)]
    single = [_support(0.6, "e1", claim="same")]

    assert compute_coverage(single, aspects) == pytest.approx(0.3333, abs=1e-4)
    assert compute_coverage(duplicated, aspects) == pytest.approx(1.0, abs=1e-4)
    # Risk already ignores duplicates; coverage does not. That asymmetry is the defect.
    assert compute_residual_risk(duplicated, aspects, {}) == compute_residual_risk(
        single, aspects, {}
    )


def test_independent_additional_support_still_has_expected_coverage():
    independent = _actions_for(
        _SUPPORTING_SYSTEM, _calibrated(), [_support(0.6, "e1", claim="first")]
    )["core.py"]
    assert independent.expected_delta_coverage > 0.0


def test_expected_coverage_is_zero_without_calibration_even_with_headroom():
    """The headroom exists, but an uncalibrated profile promises nothing."""
    uncalibrated = _actions_for(
        _SUPPORTING_SYSTEM, {"name": "g", "aspects": ["write"]}, [_support(0.6, "e1")]
    )["core.py"]
    assert uncalibrated.expected_delta_coverage == 0.0


def test_off_goal_supports_earn_no_expected_coverage():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "off.py", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
             "supports": [{"aspect": "telemetry"}]},
        ],
    }
    action = _actions_for(system, {"name": "g", "aspects": ["write"]})["off.py"]
    assert action.capability == "retrieval_only"
    assert action.expected_delta_coverage == 0.0


METAMORPHIC_ARTIFACTS = [
    ("retrieval_only", {}),
    ("structural_relation", {"implements": [{"aspect": "write"}]}),
    ("probatory_static", {"supports": [{"aspect": "write"}]}),
    ("probatory_static", {"refutes": [{"aspect": "write"}]}),
    ("probatory_dynamic", {"verification_method": "dynamic"}),
]


@pytest.mark.parametrize("capability,extras", METAMORPHIC_ARTIFACTS)
def test_metamorphic_relevance_moves_only_retrieval_never_probative(capability, extras):
    """Metamorphic across every capability: relevance is a retrieval signal only."""
    def build(relevance):
        system = {
            "name": "s",
            "artifacts": [{"id": "a", "content": "x", "level": 4,
                           "relevance": relevance, "kind": "code", **extras}],
        }
        return _actions_for(system, _calibrated())["a"]

    low, high = build(0.1), build(0.9)
    assert low.capability == high.capability == capability
    assert high.expected_retrieval_gain > low.expected_retrieval_gain
    assert high.expected_delta_coverage == low.expected_delta_coverage
    assert high.expected_contradiction_discovery == low.expected_contradiction_discovery
    assert high.expected_delta_risk_reduction == low.expected_delta_risk_reduction


MALFORMED_DECLARATIONS = [
    {"supports": []},
    {"supports": "write"},
    {"supports": [{"no_aspect": "write"}]},
    {"supports": ["write"]},
    {"refutes": None},
    {"supports": [{"aspect": "write", "strength": None}]},
    {"supports": [{"aspect": "write", "strength": "bad"}]},
    {"supports": [{"aspect": "write", "strength": float("nan")}]},
    {"supports": [{"aspect": "write", "strength": float("inf")}]},
    {"supports": [{"aspect": "write", "strength": -0.5}]},
    {"supports": [{"aspect": "write", "strength": 1.5}]},
    {"supports": [{"aspect": "write", "claim": 42}]},
    {"supports": [{"aspect": "write", "scope": ["x"]}]},
    {"supports": [{"aspect": 7}]},
]


@pytest.mark.parametrize("relation", ["supports", "refutes"])
def test_zero_strength_never_produces_probative_evidence_end_to_end(relation):
    """A relation of strength exactly zero asserts that the relation does NOT hold.

    Admitting it produced a false completion: coverage 0.3333, residual_risk 0.0
    and complete=True from a declaration asserting nothing.
    """
    system = {
        "name": "s",
        "artifacts": [
            {"id": "a", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
             relation: [{"aspect": "write", "strength": 0.0}]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "min_sources_per_aspect": 1,
            "theta_coverage": 0.3, "rho_risk": 0.5}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))

    assert report["coverage"] == 0.0
    assert report["residual_risk"] == 1.0
    assert report["complete"] is False
    assert not {"supports", "refutes"} & {c["relation"] for c in report["conclusions"]}
    diagnostics = report["declaration_diagnostics"][0]["diagnostics"]
    assert f"{relation}:zero_strength_no_effect" in diagnostics


def test_positive_strength_below_one_remains_admissible():
    """Only exactly zero is rejected; (0, 1] stays usable."""
    system = {
        "name": "s",
        "artifacts": [
            {"id": "a", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
             "supports": [{"aspect": "write", "strength": 0.5}]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "min_sources_per_aspect": 1,
            "theta_coverage": 0.3, "rho_risk": 0.5}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["coverage"] > 0.0
    assert report["declaration_diagnostics"] == []


@pytest.mark.parametrize("extras", MALFORMED_DECLARATIONS)
def test_malformed_declarations_survive_analyze_system_end_to_end(extras):
    """End-to-end: the public entry point must not raise, must not treat junk as
    proof, must return finite metrics, and must surface the diagnostic."""
    import math as _math

    system = {
        "name": "s",
        "artifacts": [{"id": "a", "content": "x", "level": 4, "relevance": 0.9,
                       "kind": "code", **extras}],
    }
    goal = {"name": "g", "aspects": ["write"]}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))

    assert _math.isfinite(report["coverage"])
    assert _math.isfinite(report["residual_risk"])
    assert 0.0 <= report["coverage"] <= 1.0
    assert 0.0 <= report["residual_risk"] <= 1.0
    assert report["coverage"] == 0.0
    probative = {"supports", "refutes"}
    assert not probative & {c["relation"] for c in report["conclusions"]}
    assert "declaration_diagnostics" in report


@pytest.mark.parametrize(
    "extras",
    [
        {"supports": [{"aspect": "write", "strength": "bad"}]},
        {"supports": [{"aspect": "write", "strength": None}]},
        {"supports": [{"aspect": "write", "strength": float("nan")}]},
        {"refutes": "nonsense"},
        {"supports": [{"aspect": "write", "claim": 42}]},
    ],
)
def test_malformed_declarations_are_visible_in_the_public_report(extras):
    system = {
        "name": "s",
        "artifacts": [{"id": "a", "content": "x", "level": 4, "relevance": 0.9,
                       "kind": "code", **extras}],
    }
    report = analyze_system(
        system, {"name": "g", "aspects": ["write"]},
        Budget(tokens_remaining=10000, tool_remaining=10),
    )
    entries = report["declaration_diagnostics"]
    assert entries, f"diagnostic must reach the public report for {extras}"
    assert entries[0]["evidence_id"] == "a"
    assert entries[0]["diagnostics"]


@pytest.mark.parametrize("extras", MALFORMED_DECLARATIONS)
def test_adversarial_malformed_declarations_fail_closed(extras):
    """Malformed declarations must never be read as probative, and must not raise."""
    system = {
        "name": "s",
        "artifacts": [{"id": "a", "content": "x", "level": 4, "relevance": 0.9,
                       "kind": "code", **extras}],
    }
    action = _actions_for(system, _calibrated())["a"]
    assert action.capability == "retrieval_only", extras
    assert action.expected_delta_coverage == 0.0
    assert action.expected_delta_risk_reduction == 0.0


@pytest.mark.parametrize("relevance", [None, "high", float("nan"), float("inf"), -1.0, 2.0])
def test_adversarial_invalid_relevance_is_diagnosed_not_raised(relevance):
    system = {
        "name": "s",
        "artifacts": [{"id": "a", "content": "x", "level": 4, "relevance": relevance,
                       "kind": "code"}],
    }
    action = _actions_for(system, _calibrated())["a"]
    assert action.expected_retrieval_gain == 0.0
    assert "relevance:not_a_unit_interval_value" in action.declaration_diagnostics


def test_malformed_declarations_are_reported_as_structured_diagnostics():
    system = {
        "name": "s",
        "artifacts": [{"id": "a", "content": "x", "level": 4, "relevance": 0.9, "kind": "code",
                       "supports": [{"aspect": "write", "strength": float("nan")}],
                       "refutes": "nonsense"}],
    }
    action = _actions_for(system, _calibrated())["a"]
    assert "supports:strength_not_finite" in action.declaration_diagnostics
    assert "refutes:not_a_list" in action.declaration_diagnostics


def test_next_actions_carry_every_required_structured_field():
    system = {
        "name": "s",
        "inventory": {"degradations": ["content_truncated"]},
        "artifacts": [
            {"id": "readme.md", "content": "write stuff", "level": 0, "relevance": 0.9,
             "kind": "doc"},
        ],
    }
    goal = {
        "name": "g",
        "aspects": ["write"],
        "aspect_linker": lambda _content, _aspect: 1.0,
        "link_threshold": 0.5,
        "accepted_degradations": [],
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    completion = report["completion"]
    assert "content_truncated" in completion["reason_codes"]
    assert "threshold_not_met" in completion["reason_codes"]

    by_action = {a["action"]: a for a in completion["next_actions"]}
    # The action must exist: no optional branch may make this assertion vacuous.
    read_limit = by_action["increase_read_limit"]
    for field in (
        "addresses_reason_codes",
        "remaining_blockers",
        "expected_effect",
        "capability_required",
        "sufficient_if_successful",
        "authorization_required",
    ):
        assert field in read_limit, field
    assert read_limit["addresses_reason_codes"] == ["content_truncated"]
    assert "threshold_not_met" in read_limit["remaining_blockers"]
    assert "insufficient_sources" in read_limit["remaining_blockers"]
    assert read_limit["sufficient_if_successful"] is False
    assert read_limit["capability_required"] == "retrieval_only"


def test_sufficiency_requires_a_computed_target_not_just_an_empty_blocker_list():
    """"Raise the limit" with no target has no verifiable postcondition."""
    system = {
        "name": "s",
        "inventory": {"degradations": ["content_truncated"], "bytes_discovered": 4096},
        "artifacts": [
            {"id": "code.py", "content": "cas", "level": 4, "relevance": 1.0, "kind": "code",
             "supports": [{"aspect": "write", "claim": "c", "scope": "v1"}]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "theta_coverage": 0.1, "rho_risk": 1.0,
            "min_sources_per_aspect": 1}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    action = {a["action"]: a for a in report["completion"]["next_actions"]}["increase_read_limit"]
    assert action["remaining_blockers"] == []
    # A concrete target exists, so sufficiency is demonstrable here.
    assert action["parameter"] == "read_limit_bytes"
    assert action["target_value"] == 4096
    assert action["sufficient_if_successful"] is True


def test_sufficiency_is_false_when_no_target_can_be_computed():
    system = {
        "name": "s",
        "inventory": {"degradations": ["content_truncated"]},
        "artifacts": [
            {"id": "code.py", "content": "cas", "level": 4, "relevance": 1.0, "kind": "code",
             "supports": [{"aspect": "write", "claim": "c", "scope": "v1"}]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "theta_coverage": 0.1, "rho_risk": 1.0,
            "min_sources_per_aspect": 1}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    action = {a["action"]: a for a in report["completion"]["next_actions"]}["increase_read_limit"]
    assert action["remaining_blockers"] == []
    assert "target_value" not in action
    assert action["sufficient_if_successful"] is False


def test_increase_budget_never_claims_sufficiency():
    """No computable target exists for a budget bump."""
    report = run(budget=Budget(tokens_remaining=1, tool_remaining=1))
    action = {a["action"]: a for a in report["completion"]["next_actions"]}["increase_budget"]
    assert action["sufficient_if_successful"] is False


def test_missing_support_proposes_a_verifier_without_executing_anything():
    system = {
        "name": "s",
        "artifacts": [
            {"id": "readme.md", "content": "write stuff", "level": 0, "relevance": 0.9,
             "kind": "doc"},
        ],
    }
    goal = {
        "name": "g",
        "aspects": ["write"],
        "aspect_linker": lambda _content, _aspect: 1.0,
        "link_threshold": 0.5,
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    by_action = {a["action"]: a for a in report["completion"]["next_actions"]}
    proposal = by_action["enable_probative_verifier"]
    assert proposal["capability_required"] == "probatory_static"
    assert proposal["authorization_required"] is True
    assert "write" in proposal["aspects"]
    assert proposal["reason"] == "no_probative_evidence_available"
    assert proposal["aspects_without_support"] == ["write"]
    # Enabling a verifier cannot be shown to be sufficient in advance.
    assert proposal["sufficient_if_successful"] is False
    # Proposing is not running: no probative evidence appeared in this report.
    assert report["coverage"] == 0.0
    assert {c["relation"] for c in report["conclusions"]} == {"mentions"}


def test_verifier_proposal_distinguishes_under_corroboration_from_no_support():
    """With support present but min_sources unmet, the reason and targets must
    reflect corroboration, not 'no probative evidence', and must not be empty."""
    system = {
        "name": "s",
        "artifacts": [
            {"id": "code.py", "content": "cas", "level": 4, "relevance": 1.0, "kind": "code",
             "supports": [{"aspect": "write", "claim": "writes use cas", "scope": "v1"}]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "min_sources_per_aspect": 2,
            "theta_coverage": 0.9, "rho_risk": 0.1}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    completion = report["completion"]
    assert "insufficient_sources" in completion["reason_codes"]
    proposal = {a["action"]: a for a in completion["next_actions"]}["enable_probative_verifier"]
    assert proposal["reason"] == "insufficient_corroboration"
    assert proposal["aspects"] == ["write"]
    assert proposal["aspects"] != []
    assert proposal["aspects_under_corroborated"] == ["write"]
    assert proposal["aspects_without_support"] == []
    assert proposal["min_sources_per_aspect"] == 2
