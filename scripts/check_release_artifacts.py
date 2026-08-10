"""Validate release archives without extracting untrusted paths."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath


class ReleaseArtifactError(ValueError):
    pass


MAX_MEMBERS = 10_000
MAX_UNCOMPRESSED_BYTES = 100_000_000


def _safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def _metadata(text: str, *, version: str) -> None:
    parsed = Parser().parsestr(text)
    if parsed.get("Name") != "argos-epistemic":
        raise ReleaseArtifactError("unexpected_project_name")
    if parsed.get("Version") != version:
        raise ReleaseArtifactError("unexpected_project_version")
    if parsed.get("Requires-Python") != ">=3.12":
        raise ReleaseArtifactError("unexpected_python_requirement")
    if parsed.get("License-Expression") != "Apache-2.0":
        raise ReleaseArtifactError("unexpected_license_expression")
    requirements = parsed.get_all("Requires-Dist", [])
    if "packaging>=23.2" not in requirements:
        raise ReleaseArtifactError("missing_runtime_dependency")


def _wheel(path: Path, *, version: str) -> None:
    if path.name != f"argos_epistemic-{version}-py3-none-any.whl":
        raise ReleaseArtifactError("unexpected_wheel_filename")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise ReleaseArtifactError("wheel_member_limit_exceeded")
        if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
            raise ReleaseArtifactError("wheel_size_limit_exceeded")
        names = archive.namelist()
        if any(not _safe_name(name) for name in names):
            raise ReleaseArtifactError("unsafe_wheel_path")
        metadata = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata) != 1:
            raise ReleaseArtifactError("invalid_wheel_metadata_count")
        _metadata(archive.read(metadata[0]).decode("utf-8"), version=version)
        required = {
            "argos_epistemic/__init__.py",
            "argos_epistemic/__main__.py",
            "argos_epistemic/schemas/claim-record-v1.schema.json",
            "argos_epistemic/schemas/discovery-inventory-v1.schema.json",
            "argos_epistemic/schemas/evaluation-envelope-v1.schema.json",
            "argos_epistemic/schemas/evaluation-manifest-v1.schema.json",
            "argos_epistemic/schemas/run-attestation-v1.schema.json",
        }
        if missing := sorted(required - set(names)):
            raise ReleaseArtifactError(f"wheel_members_missing:{','.join(missing)}")
        wheel_metadata = [name for name in names if name.endswith(".dist-info/WHEEL")]
        records = [name for name in names if name.endswith(".dist-info/RECORD")]
        if len(wheel_metadata) != 1 or len(records) != 1:
            raise ReleaseArtifactError("invalid_wheel_control_file_count")
        wheel_headers = Parser().parsestr(archive.read(wheel_metadata[0]).decode("utf-8"))
        if wheel_headers.get("Root-Is-Purelib") != "true":
            raise ReleaseArtifactError("wheel_is_not_purelib")
        if "py3-none-any" not in wheel_headers.get_all("Tag", []):
            raise ReleaseArtifactError("unexpected_wheel_tag")
        rows = csv.reader(io.StringIO(archive.read(records[0]).decode("utf-8")))
        recorded = set()
        for row in rows:
            if len(row) != 3 or row[0] in recorded or row[0] not in names:
                raise ReleaseArtifactError("invalid_wheel_record")
            recorded.add(row[0])
            if row[0] == records[0]:
                if row[1] or row[2]:
                    raise ReleaseArtifactError("invalid_wheel_record_self_entry")
                continue
            data = archive.read(row[0])
            encoded = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            if row[1] != f"sha256={encoded}" or row[2] != str(len(data)):
                raise ReleaseArtifactError("wheel_record_mismatch")
        if recorded != set(names):
            raise ReleaseArtifactError("wheel_record_incomplete")


def _sdist(path: Path, *, version: str) -> None:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > MAX_MEMBERS:
            raise ReleaseArtifactError("sdist_member_limit_exceeded")
        if sum(member.size for member in members) > MAX_UNCOMPRESSED_BYTES:
            raise ReleaseArtifactError("sdist_size_limit_exceeded")
        if any(not _safe_name(member.name) for member in members):
            raise ReleaseArtifactError("unsafe_sdist_path")
        if any(not (member.isfile() or member.isdir()) for member in members):
            raise ReleaseArtifactError("unsafe_sdist_member_type")
        names = {member.name for member in members}
        prefix = f"argos_epistemic-{version}"
        metadata_name = f"{prefix}/PKG-INFO"
        metadata_member = archive.getmember(metadata_name)
        metadata_file = archive.extractfile(metadata_member)
        if metadata_file is None:
            raise ReleaseArtifactError("missing_sdist_metadata")
        _metadata(metadata_file.read().decode("utf-8"), version=version)
        required = {
            f"{prefix}/LICENSE",
            f"{prefix}/README.md",
            f"{prefix}/CHANGELOG.md",
            f"{prefix}/CONTRIBUTING.md",
            f"{prefix}/SECURITY.md",
            f"{prefix}/SUPPORT.md",
            f"{prefix}/pyproject.toml",
            f"{prefix}/docs/api.md",
            f"{prefix}/docs/release.md",
            f"{prefix}/argos_epistemic/__init__.py",
            f"{prefix}/argos_epistemic/__main__.py",
            f"{prefix}/scripts/check_release_artifacts.py",
            f"{prefix}/scripts/normalize_sdist.py",
        }
        if missing := sorted(required - names):
            raise ReleaseArtifactError(f"sdist_members_missing:{','.join(missing)}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_release(dist_dir: Path, version: str) -> dict[str, str]:
    wheels = sorted(dist_dir.glob(f"argos_epistemic-{version}-*.whl"))
    sdists = sorted(dist_dir.glob(f"argos_epistemic-{version}.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseArtifactError("expected_exactly_one_wheel_and_sdist")
    wheel, sdist = wheels[0], sdists[0]
    _wheel(wheel, version=version)
    _sdist(sdist, version=version)
    return {path.name: _sha256(path) for path in (wheel, sdist)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    args = parser.parse_args()
    print(json.dumps(inspect_release(args.dist_dir, args.version), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
