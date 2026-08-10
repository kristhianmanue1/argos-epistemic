import io
import tarfile
from pathlib import Path

import pytest

from scripts.normalize_sdist import SdistNormalizationError, normalize_sdist


def _archive(path: Path, *, member_name: str, mtime: int) -> None:
    payload = b"release-content"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = len(payload)
        member.mtime = mtime
        member.uid = 501
        member.gid = 20
        member.uname = "builder"
        member.gname = "staff"
        archive.addfile(member, io.BytesIO(payload))


def test_sdist_normalization_is_deterministic(tmp_path):
    first_source = tmp_path / "first.tar.gz"
    second_source = tmp_path / "second.tar.gz"
    first = tmp_path / "first-normalized.tar.gz"
    second = tmp_path / "second-normalized.tar.gz"
    _archive(first_source, member_name="package/file.txt", mtime=1)
    _archive(second_source, member_name="package/file.txt", mtime=999)

    normalize_sdist(first_source, first, 123456789)
    normalize_sdist(second_source, second, 123456789)

    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "safe/../../escape"])
def test_sdist_normalization_rejects_unsafe_paths(tmp_path, name):
    source = tmp_path / "source.tar.gz"
    destination = tmp_path / "normalized.tar.gz"
    _archive(source, member_name=name, mtime=1)

    with pytest.raises(SdistNormalizationError, match="unsafe_sdist_member"):
        normalize_sdist(source, destination, 1)


def test_sdist_normalization_rejects_in_place_rewrite(tmp_path):
    source = tmp_path / "source.tar.gz"
    _archive(source, member_name="package/file.txt", mtime=1)

    with pytest.raises(SdistNormalizationError, match="source_and_destination"):
        normalize_sdist(source, source, 1)
