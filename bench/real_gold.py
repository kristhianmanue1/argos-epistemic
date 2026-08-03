"""Gold hand-labeled para la validacion sobre repos reales (item 1).

Tres repos pequenos de pallets (markupsafe, itsdangerous, click). El gold por
aspecto se etiqueto a mano leyendo el codigo fuente de cada repo (commit fijado
en ``bench/real_repos.py``). Cada aspecto mezcla intencionalmente:
* entradas token-obvias (el gold comparte tokens con el aspecto / id) que el
  linker lexico ya deberia recuperar; y
* entradas semanticas (sin overlap lexico, p.ej. ``injection``/``errors``) que
  aislan la senal densa: el lexico debe fallar y el denso recuperar.

ADVERTENCIA de honestidad: es etiquetado por una persona (el agente) sobre 3
repos; no es un corpus con annotation多重, ni ciego. Sirve para pasar de
micro-fixture a codigo real, pero NO es validacion estadistica amplia.
"""

from __future__ import annotations

MARKUPSAFE = {
    "name": "markupsafe",
    "goal": {
        "name": "audit_seguridad",
        "aspects": ["escape", "native", "markup", "format", "injection"],
        "theta_coverage": 0.8,
        "rho_risk": 0.25,
    },
    "gold": {
        "escape": {"src/markupsafe/__init__.py", "src/markupsafe/_native.py", "tests/test_escape.py"},
        "native": {"src/markupsafe/_native.py"},
        "markup": {"src/markupsafe/__init__.py"},
        "format": {"src/markupsafe/__init__.py"},
        "injection": {"src/markupsafe/__init__.py", "src/markupsafe/_native.py"},
    },
}

ITSDANGEROUS = {
    "name": "itsdangerous",
    "goal": {
        "name": "audit_firma",
        "aspects": ["signing", "serialization", "timestamp", "encoding", "security"],
        "theta_coverage": 0.8,
        "rho_risk": 0.25,
    },
    "gold": {
        "signing": {
            "src/itsdangerous/signer.py",
            "src/itsdangerous/__init__.py",
            "tests/test_itsdangerous/test_signer.py",
        },
        "serialization": {
            "src/itsdangerous/serializer.py",
            "src/itsdangerous/__init__.py",
            "tests/test_itsdangerous/test_serializer.py",
        },
        "timestamp": {
            "src/itsdangerous/timed.py",
            "src/itsdangerous/__init__.py",
            "tests/test_itsdangerous/test_timed.py",
        },
        "encoding": {
            "src/itsdangerous/encoding.py",
            "src/itsdangerous/url_safe.py",
            "tests/test_itsdangerous/test_encoding.py",
        },
        "security": {"src/itsdangerous/signer.py", "src/itsdangerous/timed.py", "src/itsdangerous/exc.py"},
    },
}

CLICK = {
    "name": "click",
    "goal": {
        "name": "audit_cli",
        "aspects": ["command", "types", "parsing", "formatting", "errors"],
        "theta_coverage": 0.8,
        "rho_risk": 0.25,
    },
    "gold": {
        "command": {"src/click/core.py", "src/click/decorators.py", "src/click/__init__.py"},
        "types": {"src/click/types.py", "src/click/__init__.py"},
        "parsing": {"src/click/parser.py", "src/click/core.py"},
        "formatting": {"src/click/formatting.py", "src/click/__init__.py"},
        "errors": {"src/click/exceptions.py"},
    },
}

REPOS = {
    "markupsafe": MARKUPSAFE,
    "itsdangerous": ITSDANGEROUS,
    "click": CLICK,
}
