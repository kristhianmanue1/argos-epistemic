import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from argos_epistemic import __main__ as cli

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    python_path = os.pathsep.join(filter(None, (str(ROOT), os.environ.get("PYTHONPATH"))))
    return subprocess.run(
        [sys.executable, "-m", "argos_epistemic", *args],
        cwd=cwd,
        env={
            **os.environ,
            "ARGOS_SENTINEL_SECRET": "must-not-appear",
            "PYTHONPATH": python_path,
        },
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_module_help_is_informative_and_side_effect_free(tmp_path):
    result = _run("--help", cwd=tmp_path)

    assert result.returncode == 0
    assert "biblioteca Python" in result.stdout
    assert "no analiza repositorios" in result.stdout
    assert "analyze_path()" in result.stdout
    assert "must-not-appear" not in result.stdout + result.stderr
    assert list(tmp_path.iterdir()) == []


def test_module_without_arguments_prints_help(tmp_path):
    result = _run(cwd=tmp_path)

    assert result.returncode == 0
    assert result.stdout.startswith("usage: python -m argos_epistemic")
    assert result.stderr == ""


def test_module_version_uses_installed_distribution_metadata(tmp_path):
    result = _run("--version", cwd=tmp_path)

    assert result.returncode == 0
    assert result.stdout.strip() == f"python -m argos_epistemic {version('argos-epistemic')}"
    assert result.stderr == ""


def test_unknown_argument_fails_without_traceback(tmp_path):
    result = _run("--analyze", cwd=tmp_path)

    assert result.returncode == 2
    assert "unrecognized arguments: --analyze" in result.stderr
    assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []


def test_positional_target_is_rejected_instead_of_becoming_an_implicit_analysis(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    sentinel = target / "private.txt"
    sentinel.write_text("unchanged")

    result = _run(str(target), cwd=tmp_path)

    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr
    assert "Traceback" not in result.stderr
    assert sentinel.read_text() == "unchanged"


def test_uninstalled_checkout_reports_unknown_version_without_traceback(monkeypatch, capsys):
    def missing_distribution(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(cli, "version", missing_distribution)

    with pytest.raises(SystemExit) as stopped:
        cli.main(["--version"])

    assert stopped.value.code == 0
    assert "desconocida (checkout sin instalar)" in capsys.readouterr().out
