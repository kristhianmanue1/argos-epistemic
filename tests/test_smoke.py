from argos_model import Budget, Cost, analyze_path, analyze_system, build_call_graph, extract_system, run


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
                {"id": f"a{i}", "content": str(i), "level": i, "relevance": 1.0, "kind": "artifact"}
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
            {"id": "doc_f", "content": "feature on", "location": "f_X", "level": 0, "relevance": 1.0, "kind": "doc"},
            {"id": "code_f", "content": "feature off", "location": "f_X", "level": 4, "relevance": 1.0, "kind": "code"},
        ],
    }
    goal = {"name": "g", "aspects": ["f_X"], "theta_coverage": 0.95, "rho_risk": 0.05}
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
            {"id": "a", "content": "Autenticacion requerida", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc"},
            {"id": "b", "content": "autenticacion  requerida!!!", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc"},
        ],
    }
    divergent = {
        "name": "s",
        "artifacts": [
            {"id": "a", "content": "autenticacion requerida", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc"},
            {"id": "b", "content": "sin autenticacion", "location": "auth", "level": 0, "relevance": 1.0, "kind": "doc"},
        ],
    }
    r_same = analyze_system(same, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    r_div = analyze_system(divergent, goal, Budget(tokens_remaining=10000, tool_remaining=20))
    assert r_same["conflict_count"] == 0
    assert r_div["conflict_count"] >= 1


def test_q_g_invariant_holds_under_compression_and_breaks_on_eviction():
    from argos_model import Belief, BeliefStore, Evidence, EvidenceStore, q_g_invariant

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
    report = analyze_system(system, goal, Budget(tokens_remaining=100000, tool_remaining=1000))
    assert report["evidence_count"] == 12
    assert report["compressed_count"] >= 1
    assert report["evidence_kinds"]


def test_extract_system_over_real_repo():
    system = extract_system(".", goal={"name": "refactor", "aspects": ["algorithm"]})
    ids = {a["id"] for a in system["artifacts"]}
    assert "L1:topology" in ids
    assert "readme.md" in ids
    assert "pyproject.toml" in ids
    assert "argos_model/algorithm.py" in ids
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

    py = [Path("argos_model/algorithm.py")]
    cg = build_call_graph(Path("."), py)
    caller = "argos_model/algorithm.py::analyze_system"
    callee = "argos_model/algorithm.py::execute_action"
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
    assert "s_semantic" in next(a for a in custom["artifacts"] if a["id"] == "argos_model/extractors.py")
    assert c["argos_model/extractors.py"] >= d["argos_model/extractors.py"]


def test_git_log_summary_on_this_repo():
    from argos_model import git_log_summary

    summary = git_log_summary(".")
    assert summary is not None
    assert summary["commits"] >= 1
    assert summary["last_commit"] is not None
    assert summary["days_since_last_commit"] is not None


def test_historical_verification_confidence():
    from argos_model import analyze_path, Budget

    report = analyze_path(
        ".",
        goal={"name": "historia", "aspects": ["algorithm"], "theta_coverage": 2.0, "rho_risk": 0.0},
        budget=Budget(tokens_remaining=500000, tool_remaining=5000),
        run_history=True,
    )
    assert "history" in report["evidence_kinds"] or any(
        c["claim"].startswith("history@") for c in report["conclusions"]
    )
    hist = [c for c in report["conclusions"] if c["claim"].startswith("history@")]
    assert hist and hist[0]["confidence"] == 0.8 and hist[0]["status"] == "supported"


def test_impact_excludes_test_files():
    from pathlib import Path

    from argos_model.callgraph import is_test_file

    cg = build_call_graph(
        Path("."),
        [Path("argos_model/algorithm.py"), Path("tests/test_smoke.py")],
    )
    prod = cg.production_subgraph()
    assert all(not is_test_file(n.file) for n in prod.nodes.values())
    assert len(prod.nodes) < len(cg.nodes)
    imp = prod.impact()
    assert imp["argos_model/algorithm.py::analyze_system"] > 0.0
    summary_top = extract_system(".", goal={"name": "x", "aspects": []})["call_graph"]["top_impact"]
    assert all("test" not in entry["id"].split("::")[0].lower() for entry in summary_top)


def test_run_pytest_yields_dynamic_evidence(tmp_path):
    from argos_model import run_pytest

    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    result = run_pytest(tmp_path, timeout=60)
    assert result["status"] == "supported"
    assert result["passed"] >= 1
    assert result["failed"] == 0


def test_analyze_path_with_dynamic_includes_run(tmp_path):
    from argos_model import Budget

    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'fix'\nversion = '0'\n", encoding="utf-8")
    (tmp_path / "pkg.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "test_pkg.py").write_text("from pkg import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    report = analyze_path(
        tmp_path,
        goal={"name": "refactor", "aspects": ["pkg"], "theta_coverage": 2.0, "rho_risk": 0.0},
        budget=Budget(tokens_remaining=500000, tool_remaining=5000),
        run_dynamic=True,
        dynamic_timeout=60,
    )
    kinds = report["evidence_kinds"]
    assert "test-run" in kinds
    dyn = [c for c in report["conclusions"] if c["claim"].startswith("test-run@")]
    assert dyn and dyn[0]["status"] == "supported" and dyn[0]["confidence"] >= 0.9
