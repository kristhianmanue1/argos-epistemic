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


def test_should_stop_when_thresholds_met():
    report = analyze_system(
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
        },
        budget=Budget(tokens_remaining=100000, tool_remaining=1000),
    )
    assert report["complete"] is True
    assert report["evidence_count"] >= 1


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
             "supports": [{"aspect": "f_X"}]},
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


def test_conflict_tolerates_rewording_but_flags_divergence():
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
    assert r_div["conflict_count"] >= 1


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
    assert "readme.md" in ids
    assert "pyproject.toml" in ids
    assert "argos_epistemic/algorithm.py" in ids
    levels = {a["level"] for a in system["artifacts"]}
    assert {0, 1, 2, 4}.issubset(levels)
    assert all(0.0 <= a["relevance"] <= 1.0 for a in system["artifacts"])


def test_extract_ignores_venv_and_cache():
    system = extract_system(".")
    ids = {a["id"] for a in system["artifacts"]}
    assert not any(part in ids for part in (".venv", "__pycache__", ".an-kla"))


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
    assert "history" in report["evidence_kinds"] or any(
        c["claim"].startswith("history@") for c in report["conclusions"]
    )
    hist = [c for c in report["conclusions"] if c["claim"].startswith("history@")]
    assert hist and hist[0]["confidence"] == 0.8 and hist[0]["status"] == "supported"


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
             "supports": [{"aspect": "f"}]},
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["f"], "theta_coverage": 2.0, "rho_risk": 0.0},
                            Budget(tokens_remaining=10000, tool_remaining=20))
    assert report["conflict_count"] == 1  # dedup: one conflict, not accumulated


def test_h7_conflict_is_aspect_based_not_location_based():
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
    assert report["conflict_count"] >= 1  # different locations, same aspect -> still a conflict


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
    dyn = [c for c in report["conclusions"] if c["claim"].startswith("test-run@")]
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
    for aid, lvl in [("readme.md", 0), ("pyproject.toml", 2),
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


def test_default_semantic_uses_dense_when_available_else_lexical():
    from argos_epistemic import default_semantic, dense_semantic_available, lexical_semantic
    from argos_epistemic.extractors import dense_semantic

    if dense_semantic_available():
        assert default_semantic() is dense_semantic
    else:
        assert default_semantic() is lexical_semantic


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
