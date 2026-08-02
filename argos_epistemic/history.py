"""Extractor L5 (historico): git log como evidencia de intencion y evolucion.

Lectura del historial del sistema (§4 L5: git log, blame, historial de
despliegues). Verificacion **historica** (§9.1): aporta evidencia sobre
intencionalidad, regresiones y decisiones previas. Es de solo lectura y barata,
pero requiere un repositorio git.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

_LOG_FMT = "%H%x1f%an%x1f%ad%x1f%s"
_DATE_FMT = "%Y-%m-%d"


def git_log_summary(root: Path | str, max_entries: int = 100) -> dict[str, Any] | None:
    root = Path(root)
    cmd = [
        "git",
        "-C",
        str(root),
        "log",
        "--no-merges",
        f"-n {max_entries}",
        f"--format={_LOG_FMT}",
        "--date=short",
    ]
    from .sandbox import run_isolated

    result = run_isolated(cmd, cwd=root, timeout=30, isolation="none")
    if result["error"] or result["returncode"] != 0:
        return None
    entries: list[dict[str, str]] = []
    for line in (result["stdout"] or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) < 4:
            continue
        entries.append({"hash": parts[0][:12], "author": parts[1], "date": parts[2], "subject": parts[3]})
    if not entries:
        return None
    authors = {e["author"] for e in entries}
    dates = []
    for e in entries:
        try:
            dates.append(datetime.strptime(e["date"], _DATE_FMT).date())
        except ValueError:
            continue
    today = date.today()
    recency = None
    first = None
    last = None
    if dates:
        recency = (today - max(dates)).days
        first = min(dates).isoformat()
        last = max(dates).isoformat()
    return {
        "status": "supported",
        "commits": len(entries),
        "authors": sorted(authors),
        "author_count": len(authors),
        "first_commit": first,
        "last_commit": last,
        "days_since_last_commit": recency,
        "recent": entries[:10],
    }


def history_artifact(root: Path | str, goal: dict[str, Any] | None = None) -> dict[str, Any] | None:
    summary = git_log_summary(root)
    if summary is None:
        return None
    lines = [
        f"git commits={summary['commits']} authors={summary['author_count']} "
        f"last={summary['last_commit']} days_since_last={summary['days_since_last_commit']}"
    ]
    lines.extend(f"{e['date']} {e['hash']} {e['subject']}" for e in summary["recent"][:8])
    return {
        "id": "L5:gitlog",
        "content": "\n".join(lines),
        "location": "(history)",
        "level": 5,
        "relevance": 0.7,
        "kind": "history",
        "verification_method": "historical",
        "run": summary,
    }
