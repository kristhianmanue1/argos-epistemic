import copy
import subprocess
import sys
import zipfile

import pytest

from argos_epistemic import (
    BundleContractError,
    CanonicalizationError,
    build_envelope,
    build_manifest,
    build_run_attestation,
    canonical_json_bytes,
    content_id,
    load_schema,
    schema_names,
    sha256_fingerprint,
    verify_envelope,
    verify_manifest,
    verify_run_attestation,
)


def manifest_fixture() -> dict:
    return build_manifest(
        target={"type": "git", "revision": "a" * 40, "dirty": False},
        evaluator={"name": "argos-epistemic", "version": "0.2.0.dev0"},
        goal={"name": "audit", "aspects": ["write", "test"]},
        semantic_profile={"name": "char-ngram-v1", "threshold": "0.55"},
        discovery_profile={"name": "legacy-v1", "max_code_artifacts": 400},
        budget={"tokens": 10000, "tools": 50},
        independence_class="operational_dependency",
        normalizations=["freshness-fixed-v1"],
    )


def test_canonical_json_is_utf8_sorted_compact_and_rejects_nonfinite():
    assert canonical_json_bytes({"z": 1, "á": "🧠"}) == '{"z":1,"á":"🧠"}'.encode()
    assert sha256_fingerprint({"b": 2, "a": 1}) == sha256_fingerprint({"a": 1, "b": 2})
    with pytest.raises(CanonicalizationError, match="floating-point number"):
        canonical_json_bytes({"threshold": 0.55})
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes({"unsupported": {1, 2}})
    with pytest.raises(CanonicalizationError, match="non-string object key"):
        canonical_json_bytes({1: "ambiguous"})


def test_content_ids_are_typed_and_version_sensitive():
    value = {"canonicalization": "argos/canonical-json-v1", "claim": "x"}
    assert content_id("claim", value).startswith("claim:sha256:")
    assert content_id("claim", value) != content_id("evidence", value)
    with pytest.raises(ValueError):
        content_id("Invalid Kind", value)


def test_manifest_is_deterministic_and_has_golden_fingerprint():
    first = manifest_fixture()
    second = manifest_fixture()
    assert first == second
    assert first["fingerprint"] == "sha256:5e30222273c313f3a449a90c2af48aefc98bf97835778e27d003d54d041d0933"
    verify_manifest(first)


def test_manifest_changes_when_configuration_changes_and_rejects_tampering():
    original = manifest_fixture()
    changed = build_manifest(
        target=original["target"],
        evaluator=original["evaluator"],
        goal=original["goal"],
        semantic_profile={"name": "char-ngram-v1", "threshold": "0.60"},
        discovery_profile=original["configuration"]["discovery_profile"],
        budget=original["configuration"]["budget"],
        independence_class=original["independence_class"],
        normalizations=original["configuration"]["normalizations"],
    )
    assert original["fingerprint"] != changed["fingerprint"]
    tampered = copy.deepcopy(original)
    tampered["goal"]["name"] = "different"
    with pytest.raises(BundleContractError, match="manifest fingerprint mismatch"):
        verify_manifest(tampered)
    unsupported = copy.deepcopy(original)
    unsupported["schema"] = "argos/evaluation-manifest-v2"
    with pytest.raises(BundleContractError, match="unsupported manifest schema"):
        verify_manifest(unsupported)


def test_envelope_is_bound_to_manifest_and_detects_tampering():
    manifest = manifest_fixture()
    envelope = build_envelope(
        manifest=manifest,
        status="partial",
        procedure_complete=False,
        reason_codes=["budget_exhausted"],
        links={"claims": "claims.jsonl"},
        usage_ref="attestations/usage.json",
    )
    verify_envelope(envelope, manifest)
    assert envelope["evaluation_id"].startswith("eval:sha256:")
    tampered = copy.deepcopy(envelope)
    tampered["status"] = "complete"
    with pytest.raises(BundleContractError, match="envelope fingerprint mismatch"):
        verify_envelope(tampered, manifest)


def test_run_attestation_does_not_change_reproducible_identity():
    manifest = manifest_fixture()
    envelope = build_envelope(
        manifest=manifest,
        status="complete",
        procedure_complete=True,
        reason_codes=[],
        links={},
    )
    first = build_run_attestation(
        manifest_fingerprint=manifest["fingerprint"],
        started_at="2026-08-03T10:00:00Z",
        finished_at="2026-08-03T10:00:01Z",
        usage={"wall_milliseconds": 1000},
    )
    second = build_run_attestation(
        manifest_fingerprint=manifest["fingerprint"],
        started_at="2026-08-03T11:00:00Z",
        finished_at="2026-08-03T11:00:03Z",
        usage={"wall_milliseconds": 3000},
    )
    verify_run_attestation(first, manifest)
    verify_run_attestation(second, manifest)
    assert first["fingerprint"] != second["fingerprint"]
    assert envelope == build_envelope(
        manifest=manifest,
        status="complete",
        procedure_complete=True,
        reason_codes=[],
        links={},
    )


def test_normative_schemas_are_loadable():
    expected = {
        "evaluation-envelope-v1.schema.json": "argos/evaluation-envelope-v1",
        "evaluation-manifest-v1.schema.json": "argos/evaluation-manifest-v1",
        "run-attestation-v1.schema.json": "argos/run-attestation-v1",
    }
    assert set(schema_names()) == set(expected)
    for name, schema_id in expected.items():
        schema = load_schema(name)
        assert schema["$id"] == schema_id
        assert schema["additionalProperties"] is False


def test_wheel_contains_normative_schemas(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("argos_epistemic-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    for schema_name in schema_names():
        assert f"argos_epistemic/schemas/{schema_name}" in names
