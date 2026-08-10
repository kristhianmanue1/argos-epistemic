"""Normalize a validated sdist tarball to deterministic ownership and timestamps."""

from __future__ import annotations

import argparse
import copy
import gzip
import tarfile
from pathlib import Path, PurePosixPath


class SdistNormalizationError(ValueError):
    pass


def _safe_member(member: tarfile.TarInfo) -> bool:
    path = PurePosixPath(member.name)
    return (
        bool(member.name)
        and not path.is_absolute()
        and ".." not in path.parts
        and (member.isfile() or member.isdir())
    )


def normalize_sdist(source: Path, destination: Path, epoch: int) -> None:
    if isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise SdistNormalizationError("invalid_source_date_epoch")
    if source.resolve() == destination.resolve():
        raise SdistNormalizationError("source_and_destination_must_differ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(source, "r:gz") as incoming:
        members = incoming.getmembers()
        if any(not _safe_member(member) for member in members):
            raise SdistNormalizationError("unsafe_sdist_member")
        with (
            destination.open("wb") as raw,
            gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed,
            tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as outgoing,
        ):
            for member in sorted(members, key=lambda item: item.name):
                normalized = copy.copy(member)
                normalized.uid = 0
                normalized.gid = 0
                normalized.uname = ""
                normalized.gname = ""
                normalized.mtime = epoch
                normalized.pax_headers = {}
                content = incoming.extractfile(member) if member.isfile() else None
                outgoing.addfile(normalized, content)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--epoch", required=True, type=int)
    args = parser.parse_args()
    normalize_sdist(args.source, args.destination, args.epoch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
