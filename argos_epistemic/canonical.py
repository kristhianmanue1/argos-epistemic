"""Canonicalización e identidad de contenido para contratos Argos."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

CANONICALIZATION_PROFILE = "argos/canonical-json-v1"
_ID_KIND = re.compile(r"^[a-z][a-z0-9-]*$")


class CanonicalizationError(ValueError):
    pass


def _validate_json(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        raise CanonicalizationError(
            f"floating-point number at {path}; use a decimal string or scaled integer"
        )
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"non-string object key at {path}")
            _validate_json(item, f"{path}.{key}")
        return
    raise CanonicalizationError(f"unsupported value at {path}: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    _validate_json(value)
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalizationError(str(exc)) from exc
    return encoded.encode("utf-8")


def canonical_clone(value: Any) -> Any:
    return json.loads(canonical_json_bytes(value))


def sha256_fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def content_id(kind: str, value: Any) -> str:
    if not _ID_KIND.fullmatch(kind):
        raise ValueError(f"invalid content id kind: {kind}")
    return f"{kind}:{sha256_fingerprint(value)}"


def fingerprinted_document(document: dict[str, Any]) -> dict[str, Any]:
    core = canonical_clone(document)
    core.pop("fingerprint", None)
    core["fingerprint"] = sha256_fingerprint(core)
    return core


def verify_fingerprinted_document(document: dict[str, Any]) -> bool:
    fingerprint = document.get("fingerprint")
    if not isinstance(fingerprint, str):
        return False
    core = canonical_clone(document)
    core.pop("fingerprint", None)
    return fingerprint == sha256_fingerprint(core)
