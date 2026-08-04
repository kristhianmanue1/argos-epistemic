"""Verificación estática degradada del contrato AN-KLA para entornos sin el CLI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

BEGIN = "<!-- an-kla:managed-begin "
END = '<!-- an-kla:managed-end {"id":"agent-context"} -->'
SUFFIX = " -->"
EXPECTED_SCHEMA = "an-kla/context-block/v1"
EXPECTED_VERSION = "0.1.0-beta.6"
EXPECTED_CONTRACT_SHA256 = "sha256:f19ca106533079e0154ac563a1ea432fb2dee331991c26d0ddf3c27e670364b1"


def digest(text: str) -> str:
    canonical = text.replace("\r\n", "\n").replace("\r", "\n")
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify(root: Path) -> dict[str, object]:
    agents = root / "AGENTS.md"
    contract = root / "AN-KLA.md"
    if agents.is_symlink() or contract.is_symlink():
        raise ValueError("context_symlink_forbidden")
    lines = agents.read_text(encoding="utf-8").splitlines(keepends=True)
    begins = [index for index, line in enumerate(lines) if line.startswith(BEGIN)]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
        raise ValueError("managed_block_structure_invalid")
    marker = lines[begins[0]].rstrip("\r\n")
    metadata = json.loads(marker[len(BEGIN) : -len(SUFFIX)])
    expected_keys = {"content_sha256", "id", "schema", "version"}
    if set(metadata) != expected_keys:
        raise ValueError("managed_block_structure_invalid")
    if metadata["id"] != "agent-context" or metadata["schema"] != EXPECTED_SCHEMA:
        raise ValueError("managed_block_structure_invalid")
    if metadata["version"] != EXPECTED_VERSION:
        raise ValueError("context_template_outdated")
    payload = "".join(lines[begins[0] + 1 : ends[0]])
    if digest(payload) != metadata["content_sha256"]:
        raise ValueError("managed_block_modified")
    contract_sha256 = digest(contract.read_text(encoding="utf-8"))
    if contract_sha256 != EXPECTED_CONTRACT_SHA256:
        raise ValueError("managed_contract_modified")
    return {
        "mode": "static-degraded",
        "ok": True,
        "schema": metadata["schema"],
        "template_version": metadata["version"],
        "contract_sha256": contract_sha256,
    }


if __name__ == "__main__":
    print(json.dumps(verify(Path.cwd()), ensure_ascii=False, sort_keys=True))
