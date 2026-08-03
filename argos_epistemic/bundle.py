"""Contratos mínimos del bundle machine-first de Argos."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from .canonical import (
    CANONICALIZATION_PROFILE,
    canonical_clone,
    content_id,
    fingerprinted_document,
    sha256_fingerprint,
    verify_fingerprinted_document,
)

MANIFEST_SCHEMA = "argos/evaluation-manifest-v1"
ENVELOPE_SCHEMA = "argos/evaluation-envelope-v1"
RUN_SCHEMA = "argos/run-attestation-v1"
SUPPORTED_SCHEMAS = frozenset({MANIFEST_SCHEMA, ENVELOPE_SCHEMA, RUN_SCHEMA})
_STATUSES = frozenset({"pending", "running", "partial", "complete", "failed", "cancelled"})
_INDEPENDENCE_CLASSES = frozenset(
    {"independent", "operational_dependency", "self_study", "shared_authority", "unknown"}
)


class BundleContractError(ValueError):
    pass


def _require_mapping(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BundleContractError(f"{name} must be an object")
    return canonical_clone(value)


def _string_list(name: str, value: list[str] | None) -> list[str]:
    result = list(value or [])
    if not all(isinstance(item, str) for item in result):
        raise BundleContractError(f"{name} must contain only strings")
    return result


def _string_mapping(name: str, value: dict[str, str]) -> dict[str, str]:
    if not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise BundleContractError(f"{name} must contain only string keys and values")
    return dict(value)


def build_manifest(
    *,
    target: dict[str, Any],
    evaluator: dict[str, Any],
    goal: dict[str, Any],
    semantic_profile: dict[str, Any],
    discovery_profile: dict[str, Any],
    budget: dict[str, Any],
    independence_class: str,
    normalizations: list[str] | None = None,
    degradations: list[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(independence_class, str) or independence_class not in _INDEPENDENCE_CLASSES:
        raise BundleContractError(f"unsupported independence class: {independence_class}")
    configuration = {
        "semantic_profile": _require_mapping("semantic_profile", semantic_profile),
        "discovery_profile": _require_mapping("discovery_profile", discovery_profile),
        "budget": _require_mapping("budget", budget),
        "normalizations": _string_list("normalizations", normalizations),
    }
    document = {
        "schema": MANIFEST_SCHEMA,
        "canonicalization": CANONICALIZATION_PROFILE,
        "target": _require_mapping("target", target),
        "evaluator": _require_mapping("evaluator", evaluator),
        "goal": _require_mapping("goal", goal),
        "independence_class": independence_class,
        "configuration": configuration,
        "configuration_fingerprint": sha256_fingerprint(configuration),
        "degradations": _string_list("degradations", degradations),
    }
    return fingerprinted_document(document)


def verify_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema") != MANIFEST_SCHEMA:
        raise BundleContractError("unsupported manifest schema")
    for field in (
        "canonicalization",
        "target",
        "evaluator",
        "goal",
        "independence_class",
        "configuration",
        "configuration_fingerprint",
        "degradations",
        "fingerprint",
    ):
        if field not in manifest:
            raise BundleContractError(f"manifest missing field: {field}")
    if manifest["canonicalization"] != CANONICALIZATION_PROFILE:
        raise BundleContractError("unsupported canonicalization profile")
    if (
        not isinstance(manifest["independence_class"], str)
        or manifest["independence_class"] not in _INDEPENDENCE_CLASSES
    ):
        raise BundleContractError("unsupported independence class")
    for field in ("target", "evaluator", "goal", "configuration"):
        if not isinstance(manifest[field], dict):
            raise BundleContractError(f"invalid manifest field: {field}")
    if not isinstance(manifest["degradations"], list) or not all(
        isinstance(item, str) for item in manifest["degradations"]
    ):
        raise BundleContractError("invalid degradations")
    if manifest["configuration_fingerprint"] != sha256_fingerprint(manifest["configuration"]):
        raise BundleContractError("configuration fingerprint mismatch")
    if not verify_fingerprinted_document(manifest):
        raise BundleContractError("manifest fingerprint mismatch")


def build_envelope(
    *,
    manifest: dict[str, Any],
    status: str,
    procedure_complete: bool,
    reason_codes: list[str],
    links: dict[str, str],
    usage_ref: str | None = None,
) -> dict[str, Any]:
    verify_manifest(manifest)
    if not isinstance(status, str) or status not in _STATUSES:
        raise BundleContractError(f"unsupported evaluation status: {status}")
    manifest_fingerprint = manifest["fingerprint"]
    document = {
        "schema": ENVELOPE_SCHEMA,
        "canonicalization": CANONICALIZATION_PROFILE,
        "evaluation_id": content_id("eval", {"manifest_fingerprint": manifest_fingerprint}),
        "status": status,
        "manifest_fingerprint": manifest_fingerprint,
        "completion": {
            "procedure_complete": procedure_complete,
            "reason_codes": _string_list("reason_codes", reason_codes),
        },
        "links": _string_mapping("links", links),
    }
    if usage_ref is not None:
        if not isinstance(usage_ref, str):
            raise BundleContractError("usage_ref must be a string")
        document["usage_ref"] = usage_ref
    return fingerprinted_document(document)


def verify_envelope(envelope: dict[str, Any], manifest: dict[str, Any]) -> None:
    verify_manifest(manifest)
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        raise BundleContractError("unsupported envelope schema")
    if not isinstance(envelope.get("status"), str) or envelope["status"] not in _STATUSES:
        raise BundleContractError("unsupported evaluation status")
    completion = envelope.get("completion")
    if not isinstance(completion, dict):
        raise BundleContractError("envelope completion must be an object")
    if not isinstance(completion.get("procedure_complete"), bool):
        raise BundleContractError("invalid procedure_complete")
    if not isinstance(completion.get("reason_codes"), list):
        raise BundleContractError("invalid reason_codes")
    if not all(isinstance(item, str) for item in completion["reason_codes"]):
        raise BundleContractError("invalid reason_codes")
    links = envelope.get("links")
    if not isinstance(links, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in links.items()
    ):
        raise BundleContractError("invalid links")
    if envelope.get("manifest_fingerprint") != manifest["fingerprint"]:
        raise BundleContractError("envelope references a different manifest")
    expected_id = content_id("eval", {"manifest_fingerprint": manifest["fingerprint"]})
    if envelope.get("evaluation_id") != expected_id:
        raise BundleContractError("evaluation id mismatch")
    if not verify_fingerprinted_document(envelope):
        raise BundleContractError("envelope fingerprint mismatch")


def build_run_attestation(
    *,
    manifest_fingerprint: str,
    started_at: str,
    finished_at: str,
    usage: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        raise BundleContractError("run attestation timestamps must be strings")
    return fingerprinted_document(
        {
            "schema": RUN_SCHEMA,
            "canonicalization": CANONICALIZATION_PROFILE,
            "manifest_fingerprint": manifest_fingerprint,
            "started_at": started_at,
            "finished_at": finished_at,
            "usage": _require_mapping("usage", usage),
        }
    )


def verify_run_attestation(attestation: dict[str, Any], manifest: dict[str, Any]) -> None:
    verify_manifest(manifest)
    if attestation.get("schema") != RUN_SCHEMA:
        raise BundleContractError("unsupported run attestation schema")
    if attestation.get("canonicalization") != CANONICALIZATION_PROFILE:
        raise BundleContractError("unsupported canonicalization profile")
    for field in ("started_at", "finished_at"):
        if not isinstance(attestation.get(field), str):
            raise BundleContractError(f"invalid run attestation field: {field}")
    if not isinstance(attestation.get("usage"), dict):
        raise BundleContractError("invalid run attestation usage")
    if attestation.get("manifest_fingerprint") != manifest["fingerprint"]:
        raise BundleContractError("run attestation references a different manifest")
    if not verify_fingerprinted_document(attestation):
        raise BundleContractError("run attestation fingerprint mismatch")


def schema_names() -> tuple[str, ...]:
    return (
        "evaluation-envelope-v1.schema.json",
        "evaluation-manifest-v1.schema.json",
        "run-attestation-v1.schema.json",
    )


def load_schema(name: str) -> dict[str, Any]:
    if name not in schema_names():
        raise BundleContractError(f"unknown schema resource: {name}")
    resource = files("argos_epistemic.schemas").joinpath(name)
    return json.loads(resource.read_text(encoding="utf-8"))
