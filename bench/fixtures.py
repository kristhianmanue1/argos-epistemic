"""Fixtures planteados con gold conocido para el benchmark (P2).

ADVERTENCIA de honestidad: son sistemas sinteticos controlados con contenido
realista y un gold definido a mano (que archivos soportan cada aspecto). NO
llevan ``supports`` declarado, de modo que la inferencia de ligadura del modelo
se evalua contra el gold (no es circular). Son un micro-benchmark; la validacion
sobre repos reales con etiquetado amplio queda como trabajo futuro.

Dos familias:
* token-obvias (AUTH, MATH): el gold comparte tokens con el aspecto -> el linker
  léxico ya recupera todo; miden calibración y ablation L3.
* semánticas (COMMERCE, LIFECYCLE): el gold se relaciona con el aspecto sólo por
  SINÓNIMOS con cero overlap léxico (verificado: lexical Jaccard == 0 en todo
  par gold/distractor). Aislan la señal semántica: el linker léxico debe fallar
  (recall 0) y el denso recuperar (recall 1). Cierran el hallazgo dense de P2.
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

# Fixture semántico: el gold se relaciona con el aspecto sólo por SINÓNIMOS;
# cero overlap léxico (lexical Jaccard == 0 en todo par). El linker léxico no
# puede recuperar nada (recall 0); el denso sí. Verificado empíricamente con
# sentence-transformers (all-MiniLM-L6-v2): todo gold >= 0.60, distractor < 0.60.
COMMERCE = {
    "name": "semantic_commerce",
    "artifacts": [
        {"id": "ledger.py", "content": "issue bills and invoices for customer purchases handle checkout and money transactions", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "wallet.py", "content": "transfer funds dispurse payouts refunds and settle balances", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "faults.py", "content": "capture exceptions trace crashes and failures report defects and bugs", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "siren.py", "content": "log warnings raise alerts and monitor incidents and anomalies", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "velocity.py", "content": "measure latency and throughput tune performance avoid slow paths", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "turbo.py", "content": "keep the service fast and responsive optimize hot paths and quick replies", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "palette.py", "content": "red green blue palette for the interface widgets", "level": 4, "relevance": 0.2, "kind": "code"},
        {"id": "readme.md", "content": "service overview and contact information", "level": 0, "relevance": 0.3, "kind": "doc"},
    ],
    "goal": {"name": "audit_commerce", "aspects": ["payments", "errors", "speed"], "theta_coverage": 0.9, "rho_risk": 0.1, "link_threshold": 0.05},
    "gold": {"payments": {"ledger.py", "wallet.py"},
             "errors": {"faults.py", "siren.py"},
             "speed": {"velocity.py", "turbo.py"}},
}

LIFECYCLE = {
    "name": "semantic_lifecycle",
    "artifacts": [
        {"id": "accounts.py", "content": "register customers and clients manage member accounts and profiles", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "people.py", "content": "onboard subscribers and sign up new members and guests", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "ignition.py", "content": "start the system initialize services launch workers on boot", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "trigger.py", "content": "kick off commence and initiate the startup sequence spawn processes and open the pipeline", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "halt.py", "content": "stop workers terminate sessions end requests and complete shutdown", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "depart.py", "content": "close conclude and finalize sessions tear down resources complete the wrap up and log off", "level": 4, "relevance": 1.0, "kind": "code"},
        {"id": "format.py", "content": "format strings and dates misc utilities", "level": 4, "relevance": 0.2, "kind": "code"},
        {"id": "readme.md", "content": "project notes and architecture overview", "level": 0, "relevance": 0.3, "kind": "doc"},
    ],
    "goal": {"name": "audit_lifecycle", "aspects": ["users", "begin", "finish"], "theta_coverage": 0.9, "rho_risk": 0.1, "link_threshold": 0.05},
    "gold": {"users": {"accounts.py", "people.py"},
             "begin": {"ignition.py", "trigger.py"},
             "finish": {"halt.py", "depart.py"}},
}

FIXTURES = {
    "auth_project": AUTH,
    "math_lib": MATH,
    "semantic_commerce": COMMERCE,
    "semantic_lifecycle": LIFECYCLE,
}
