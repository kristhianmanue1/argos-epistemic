from argos_epistemic import (
    Budget,
    analyze_system,
    extract_system,
    lexical_semantic,
    run,
    verify_inventory,
)


def test_inventory_reports_artifact_cap_and_excluded_candidates(tmp_path):
    for index in range(401):
        (tmp_path / f"module_{index:03}.py").write_text(
            f"def function_{index}():\n    return {index}\n", encoding="utf-8"
        )
    system = extract_system(
        tmp_path,
        goal={"name": "inventory", "aspects": ["module"]},
        semantic_fn=lexical_semantic,
    )
    inventory = system["inventory"]
    verify_inventory(inventory)
    assert inventory["files_discovered"] == 401
    assert inventory["files_eligible"] == 401
    assert inventory["files_selected"] == 400
    assert inventory["files_omitted_by_cap"] == 1
    assert inventory["degradations"] == ["artifact_cap_reached"]
    assert inventory["exclusions"] == [
        {"id": "module_400.py", "reason": "artifact_cap", "estimated_bytes": 35}
    ]


def test_inventory_reports_content_truncation_and_bytes(tmp_path):
    content = "x" * 9000
    (tmp_path / "readme.md").write_text(content, encoding="utf-8")
    system = extract_system(
        tmp_path,
        goal={"name": "docs", "aspects": ["readme"]},
        semantic_fn=lexical_semantic,
    )
    inventory = system["inventory"]
    artifact = next(item for item in system["artifacts"] if item["id"] == "readme.md")
    assert inventory["read_truncations"] == 1
    assert inventory["bytes_discovered"] == 9000
    assert inventory["bytes_read"] == 8192
    assert inventory["degradations"] == ["content_truncated"]
    assert artifact["content_truncated"] is True
    assert artifact["observed_bytes"] == 8192


def test_blocking_inventory_degradation_prevents_complete():
    system = {
        "name": "partial",
        "inventory": {
            "degradations": ["artifact_cap_reached"],
            "exclusions": [{"id": "omitted.py", "estimated_bytes": 400}],
            "files_discovered": 12,
        },
        "artifacts": [
            {
                "id": "observed.py",
                "content": "feature",
                "level": 4,
                "relevance": 1.0,
                "kind": "code",
                "supports": [{"aspect": "feature"}],
            }
        ],
    }
    goal = {
        "name": "g",
        "aspects": ["feature"],
        "theta_coverage": 0.1,
        "rho_risk": 1.0,
        "min_sources_per_aspect": 1,
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["complete"] is False
    assert report["completion"]["procedure_complete"] is False
    assert "artifact_cap_reached" in report["completion"]["reason_codes"]
    assert report["completion"]["next_actions"] == [
        {
            "action": "increase_artifact_cap",
            "reason": "artifact_cap_reached",
            "estimated_tokens": 100,
            "authorization_required": True,
            "addresses_reason_codes": ["artifact_cap_reached"],
            "remaining_blockers": [],
            "expected_effect": (
                "widen the observed corpus; surfaces more candidate evidence but "
                "creates no probative mass by itself"
            ),
            "capability_required": "retrieval_only",
            "parameter": "artifact_cap",
            "target_value": 12,
            "sufficient_if_successful": True,
        }
    ]


def test_no_affordable_action_is_explained():
    report = run(budget=Budget(tokens_remaining=1, tool_remaining=1))
    completion = report["completion"]
    assert completion["termination_reason"] == "no_affordable_actions"
    assert "no_affordable_actions" in completion["reason_codes"]
    by_action = {a["action"]: a for a in completion["next_actions"]}
    budget_action = by_action["increase_budget"]
    assert budget_action["addresses_reason_codes"] == ["no_affordable_actions"]
    assert budget_action["remaining_blockers"] == ["insufficient_sources", "threshold_not_met"]
    assert budget_action["sufficient_if_successful"] is False
    assert budget_action["capability_required"] == "retrieval_only"
    # Budget alone cannot manufacture proof, so a verifier proposal accompanies it.
    verifier = by_action["enable_probative_verifier"]
    assert verifier["capability_required"] == "probatory_static"
    assert verifier["addresses_reason_codes"] == ["insufficient_sources", "threshold_not_met"]
    assert verifier["authorization_required"] is True


def test_goal_can_explicitly_accept_a_known_degradation():
    system = {
        "name": "sampled",
        "inventory": {"degradations": ["content_truncated"]},
        "artifacts": [
            {
                "id": "doc",
                "content": "feature",
                "level": 0,
                "relevance": 1.0,
                "kind": "doc",
                "supports": [{"aspect": "feature"}],
            }
        ],
    }
    goal = {
        "name": "g",
        "aspects": ["feature"],
        "theta_coverage": 0.1,
        "rho_risk": 1.0,
        "min_sources_per_aspect": 1,
        "accepted_degradations": ["content_truncated"],
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["complete"] is True
    assert report["completion"]["degradations"] == ["content_truncated"]
    assert report["completion"]["blocking_degradations"] == []


def test_cost_exposes_discovery_extraction_and_analysis_phases(tmp_path):
    (tmp_path / "readme.md").write_text("goal documentation", encoding="utf-8")
    system = extract_system(
        tmp_path,
        goal={"name": "goal", "aspects": ["documentation"]},
        semantic_fn=lexical_semantic,
    )
    report = analyze_system(
        system,
        {"name": "goal", "aspects": ["documentation"]},
        Budget(tokens_remaining=10000, tool_remaining=10),
    )
    phases = report["cost"]["phases"]
    assert phases["discovery"] == {"files": 1, "bytes": 18}
    assert phases["extraction"] == {"files": 1, "bytes": 18}
    assert phases["analysis"]["observed_tokens"] == report["cost"]["observed_tokens"]
