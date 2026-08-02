"""Fixtures planteados con gold conocido para el benchmark (P2).

ADVERTENCIA de honestidad: son sistemas sinteticos controlados con contenido
realista y un gold definido a mano (que archivos soportan cada aspecto). NO
llevan ``supports`` declarado, de modo que la inferencia de ligadura del modelo
se evalua contra el gold (no es circular). Son un micro-benchmark; la validacion
sobre repos reales con etiquetado amplio queda como trabajo futuro.
"""

from __future__ import annotations

AUTH = {
    "name": "auth_project",
    "artifacts": [
        {"id": "login.py", "content": "def login(user, password): verify credentials and issue token", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "auth.py", "content": "def authenticate(token): check user authentication session", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "session.py", "content": "def logout(): destroy session and revoke token", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "util.py", "content": "def format_date(d): return formatted string", "level": 4, "relevance": 0.3, "kind": "code"},
        {"id": "colors.py", "content": "RED = 1 GREEN = 2 palette of colors for the ui", "level": 4, "relevance": 0.2, "kind": "code"},
        {"id": "readme.md", "content": "authentication library for login and session token management", "level": 0, "relevance": 0.8, "kind": "doc"},
        {"id": "config.toml", "content": "[auth] token_expiry = 3600", "level": 2, "relevance": 0.6, "kind": "config"},
        {"id": "tests/test_login.py", "content": "def test_login(): assert authenticate returns valid token", "level": 5, "relevance": 0.7, "kind": "test"},
    ],
    "goal": {"name": "audit_auth", "aspects": ["auth", "login", "token"], "theta_coverage": 0.9, "rho_risk": 0.1, "link_threshold": 0.05},
    "gold": {"auth": {"login.py", "auth.py", "session.py", "readme.md", "config.toml", "tests/test_login.py"},
             "login": {"login.py", "tests/test_login.py", "readme.md"},
             "token": {"login.py", "auth.py", "session.py", "config.toml", "readme.md"}},
}

MATH = {
    "name": "math_lib",
    "artifacts": [
        {"id": "vector.py", "content": "def add(v1, v2): vector addition element-wise", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "matrix.py", "content": "def multiply(m1, m2): matrix multiplication", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "stats.py", "content": "def mean(xs): arithmetic mean statistics", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "parser.py", "content": "def parse(s): parse string into tokens", "level": 4, "relevance": 0.3, "kind": "code"},
        {"id": "noise.py", "content": "const FOO = 42 unrelated filler content here", "level": 4, "relevance": 0.2, "kind": "code"},
        {"id": "readme.md", "content": "math library for vector matrix and statistics operations", "level": 0, "relevance": 0.8, "kind": "doc"},
    ],
    "goal": {"name": "audit_math", "aspects": ["vector", "matrix", "statistics"], "theta_coverage": 0.9, "rho_risk": 0.1, "link_threshold": 0.05},
    "gold": {"vector": {"vector.py", "readme.md"},
             "matrix": {"matrix.py", "readme.md"},
             "statistics": {"stats.py", "readme.md"}},
}

FIXTURES = {"auth_project": AUTH, "math_lib": MATH}
