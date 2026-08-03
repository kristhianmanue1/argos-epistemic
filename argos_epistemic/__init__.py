from . import ts_extractors as _ts_extractors  # noqa: F401 (registers optional L3 extractors)
from .algorithm import (
    Action,
    Belief,
    BeliefStore,
    Budget,
    Conflict,
    ConflictStore,
    Cost,
    Evidence,
    EvidenceStore,
    Verification,
    analyze_system,
    capacity_for_budget,
    propagate_confidence,
    q_g_invariant,
    run,
)
from .behavior import FuncBehavior, behavior_summary, extract_behavior
from .callgraph import CallGraph, build_call_graph, build_multi_call_graph, register_l3_extractor
from .coverage import coverage_artifact, coverage_summary
from .dynamic import detect_runner, dynamic_artifact, run_pytest, run_tests
from .extractors import (
    analyze_path,
    default_link_threshold,
    default_semantic,
    embedding_semantic,
    extract_system,
    lexical_semantic,
)
from .history import git_log_summary, history_artifact
from .logs import logs_artifact
from .profile import profile_artifact, profile_summary
from .sandbox import run_isolated, scrub_env

try:
    from .dense_semantic import dense_semantic, dense_semantic_available
except Exception:  # pragma: no cover - optional heavy dep absent at import time
    dense_semantic = None  # type: ignore[assignment]

    def dense_semantic_available() -> bool:
        return False

__all__ = [
    "Action",
    "Belief",
    "BeliefStore",
    "Budget",
    "CallGraph",
    "Conflict",
    "ConflictStore",
    "Cost",
    "Evidence",
    "EvidenceStore",
    "FuncBehavior",
    "Verification",
    "analyze_path",
    "analyze_system",
    "behavior_summary",
    "build_call_graph",
    "build_multi_call_graph",
    "capacity_for_budget",
    "coverage_artifact",
    "coverage_summary",
    "default_link_threshold",
    "default_semantic",
    "dense_semantic",
    "dense_semantic_available",
    "detect_runner",
    "dynamic_artifact",
    "embedding_semantic",
    "extract_behavior",
    "extract_system",
    "git_log_summary",
    "history_artifact",
    "lexical_semantic",
    "logs_artifact",
    "profile_artifact",
    "profile_summary",
    "propagate_confidence",
    "q_g_invariant",
    "register_l3_extractor",
    "run",
    "run_isolated",
    "run_pytest",
    "run_tests",
    "scrub_env",
]
