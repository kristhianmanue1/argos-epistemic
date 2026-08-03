import pytest

from argos_epistemic import Budget, BundleContractError, analyze_system, verify_claim_record


def _always_related(_content: str, _aspect: str) -> float:
    return 1.0


def test_semantic_similarity_produces_mentions_not_support():
    system = {
        "name": "semantic",
        "artifacts": [
            {"id": "readme", "content": "write memory", "level": 0, "relevance": 1.0, "kind": "doc"}
        ],
    }
    goal = {
        "name": "g",
        "aspects": ["write"],
        "aspect_linker": _always_related,
        "link_threshold": 0.5,
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["coverage"] == 0.0
    assert report["claims"][0]["schema"] == "argos/claim-record-v1"
    assert report["claims"][0]["fingerprint"].startswith("sha256:")
    verify_claim_record(report["claims"][0])
    assert report["conclusions"][0]["relation"] == "mentions"
    assert report["conclusions"][0]["status"] == "unknown"
    assert report["conclusions"][0]["authority_class"] == "semantic_relevance"


def test_explicit_supports_create_visible_stable_claims():
    claim = {"aspect": "write", "claim": "writes use compare-and-swap", "scope": "write-v1"}
    system = {
        "name": "explicit",
        "artifacts": [
            {"id": "code", "content": "cas", "level": 4, "relevance": 1.0, "kind": "code", "supports": [claim]},
            {"id": "test", "content": "cas test", "level": 5, "relevance": 1.0, "kind": "test", "supports": [claim]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "theta_coverage": 2.0, "rho_risk": 0.0}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    conclusions = report["conclusions"]
    assert {item["relation"] for item in conclusions} == {"supports"}
    assert len({item["claim_id"] for item in conclusions}) == 1
    assert conclusions[0]["claim_id"].startswith("claim:sha256:")
    assert conclusions[0]["claim_text"] == "writes use compare-and-swap"
    assert report["coverage"] > 0.0
    assert {item["authority_class"] for item in conclusions} == {"explicit_artifact_claim"}


def test_structural_relations_are_typed_but_not_probatory():
    system = {
        "name": "typed",
        "artifacts": [
            {
                "id": "implementation",
                "content": "writer",
                "level": 4,
                "relevance": 1.0,
                "kind": "code",
                "implements": [
                    {"aspect": "write", "claim": "writer implements CAS", "scope": "write-v1"}
                ],
            }
        ],
    }
    goal = {"name": "g", "aspects": ["write"]}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["conclusions"][0]["relation"] == "implements"
    assert report["coverage"] == 0.0
    assert report["conflict_count"] == 0


def test_claim_record_rejects_tampering():
    system = {
        "name": "tamper",
        "artifacts": [
            {
                "id": "doc",
                "content": "claim",
                "level": 0,
                "relevance": 1.0,
                "kind": "doc",
                "supports": [{"aspect": "write", "claim": "writes are atomic"}],
            }
        ],
    }
    report = analyze_system(system, {"name": "g", "aspects": ["write"]}, Budget(10000, 10))
    record = dict(report["claims"][0])
    record["relation"] = "refutes"
    with pytest.raises(BundleContractError, match="fingerprint mismatch"):
        verify_claim_record(record)


def test_opposed_relations_conflict_only_for_same_claim_and_scope():
    support = {
        "aspect": "write",
        "claim": "writes use compare-and-swap",
        "scope": "write-v1",
    }
    refute = dict(support)
    system = {
        "name": "conflict",
        "artifacts": [
            {"id": "code", "content": "cas", "level": 4, "relevance": 1.0, "kind": "code", "supports": [support]},
            {"id": "test", "content": "no cas", "level": 5, "relevance": 1.0, "kind": "test", "refutes": [refute]},
        ],
    }
    goal = {"name": "g", "aspects": ["write"], "theta_coverage": 2.0, "rho_risk": 0.0}
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["conflict_count"] == 1
    assert report["conflicts"][0]["kind"] == "contradiction"
    assert report["conflicts"][0]["claim_id"].startswith("claim:sha256:")

    system["artifacts"][1]["refutes"][0]["scope"] = "write-v2"
    separated = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert separated["conflict_count"] == 0


def test_thematically_related_an_kla_artifacts_do_not_create_conflict():
    system = {
        "name": "an-kla-like",
        "artifacts": [
            {"id": "an_kla/__init__.py", "content": "memory public api", "level": 4, "relevance": 1.0, "kind": "code"},
            {"id": "benchmarks/README.md", "content": "memory benchmark retrieval", "level": 0, "relevance": 1.0, "kind": "doc"},
        ],
    }
    goal = {
        "name": "audit",
        "aspects": ["memory"],
        "aspect_linker": _always_related,
        "link_threshold": 0.5,
        "theta_coverage": 2.0,
        "rho_risk": 0.0,
    }
    report = analyze_system(system, goal, Budget(tokens_remaining=10000, tool_remaining=10))
    assert report["proposition_count"] == 2
    assert {item["relation"] for item in report["conclusions"]} == {"mentions"}
    assert report["conflict_count"] == 0
