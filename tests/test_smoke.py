from argos_model import Budget, Cost, analyze_path, analyze_system, extract_system, run


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
