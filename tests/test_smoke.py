from argos_model import Budget, Cost, analyze_system, run


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
