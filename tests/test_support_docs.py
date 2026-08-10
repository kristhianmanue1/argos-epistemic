from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/kristhianmanue1/argos-epistemic"


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_readme_exposes_actionable_support_routes():
    readme = _read("README.md")

    assert f"{REPOSITORY}/issues/new?template=bug.yml" in readme
    assert f"{REPOSITORY}/issues/new?template=feature.yml" in readme
    assert f"{REPOSITORY}/issues/new?template=question.yml" in readme
    assert "[Seguir el procedimiento de seguridad vigente](SECURITY.md)" in readme
    assert "gh release download v0.2.0rc2" in readme


def test_support_routes_remain_available_when_blank_issues_are_disabled():
    support = _read("SUPPORT.md")
    config = _read(".github/ISSUE_TEMPLATE/config.yml")

    assert "blank_issues_enabled: false" in config
    for template in ("bug.yml", "feature.yml", "question.yml"):
        assert (ROOT / ".github" / "ISSUE_TEMPLATE" / template).is_file()
        assert f"issues/new?template={template}" in support


def test_issue_forms_request_no_real_secrets():
    bug = _read(".github/ISSUE_TEMPLATE/bug.yml")
    question = _read(".github/ISSUE_TEMPLATE/question.yml")

    assert "No incluyas secretos" in bug
    assert "No incluyas secretos" in question
    assert "Python y sistema operativo" in bug
    assert "Método de instalación" in bug


def test_security_route_is_private_and_direct():
    security = _read("SECURITY.md")
    config = _read(".github/ISSUE_TEMPLATE/config.yml")
    question_route = f"{REPOSITORY}/issues/new?template=question.yml"
    policy_route = f"{REPOSITORY}/blob/main/SECURITY.md"

    assert question_route in security
    assert policy_route in config
    assert "No publiques detalles de una vulnerabilidad" in security
    assert "security/advisories/new" not in config
