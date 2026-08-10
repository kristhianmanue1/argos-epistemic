import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0rc1"


def test_release_version_is_synchronized():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    citation = (ROOT / "CITATION.cff").read_text()
    readme = (ROOT / "README.md").read_text()
    changelog = (ROOT / "CHANGELOG.md").read_text()

    assert project["version"] == VERSION
    assert "Development Status :: 3 - Alpha" in project["classifiers"]
    assert re.search(rf'^version: "{re.escape(VERSION)}"$', citation, re.MULTILINE)
    assert f"`{VERSION}`" in readme
    assert f"## {VERSION} — 2026-08-10" in changelog


def test_release_tooling_is_declared_for_contributors():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    dev = project["optional-dependencies"]["dev"]

    assert any(requirement.startswith("build>=") for requirement in dev)
    assert any(requirement.startswith("twine>=") for requirement in dev)
