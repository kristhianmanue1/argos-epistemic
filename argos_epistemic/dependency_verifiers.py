"""Static dependency-declaration verifiers: PEP 621 and PEP 508 (plan §5.5, PR E).

Two narrow, deterministic verifiers over the D protocol (`argos_epistemic.verifiers`):

- ``make_pep621_verifier``: checks ``pyproject.toml`` for a PEP 621 dependency
  declaration, using :mod:`tomllib` from the standard library.
- ``make_pep508_verifier``: checks a ``requirements.txt``-style file for a
  PEP 508 requirement, using :class:`packaging.requirements.Requirement`.

Neither verifier is implemented from a hand-rolled grammar; both delegate
parsing to the standard library or to ``packaging``, the normative
implementation of these PEPs.

**The claim is deliberately narrow**: *"the repository declares dependency X
under constraint Y for scope Z at revision R."* Neither verifier ever asserts
that a dependency is installed, importable, resolvable, compatible with the
running environment, executable, functional, or present in a production
deployment - declaration is a static, syntactic fact; everything else is a
runtime property no static check can observe.

Both verifiers are parameterised by an expected target (name, specifier,
marker, scope) rather than scanning the whole file and reporting everything
they find: the plan calls for narrow, falsifiable claims, and "the manifest
declares X" is falsifiable only when X is stated in advance. Absence of the
queried dependency never produces ``refutes`` - only a *mismatched* declaration
for the same name and scope does. An unresolved include (``-r``/``-c``) or a
statically-absent-but-``dynamic`` PEP 621 field can hide the true declaration
elsewhere, so both degrade to ``unknown`` rather than asserting non-existence.
"""

from __future__ import annotations

import errno
import os
import re
import stat as stat_module
import tomllib
from dataclasses import dataclass, replace
from typing import Any

from packaging.markers import Marker
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import InvalidName, canonicalize_name

from .verifiers import (
    DEGRADED,
    REFUTES,
    SUPPORTS,
    UNKNOWN,
    VerificationInput,
    VerifierClaim,
    validate_verification_result,
)

PEP621_PROFILE = "pep621-dependencies"
PEP508_PROFILE = "pep508-requirements"
VERIFIER_VERSION = "1"

_PIP_INCLUDE_FLAGS = ("-r", "--requirement", "-c", "--constraint")
_PIP_OTHER_DIRECTIVE_PREFIXES = (
    "-e", "--editable",
    "-i", "--index-url", "--extra-index-url",
    "-f", "--find-links",
    "--no-index", "--pre", "--trusted-host",
    "--no-binary", "--only-binary", "--prefer-binary",
    "--hash",
)


def _canonical_specifier(text: str) -> str:
    if not text or not text.strip():
        return ""
    try:
        return str(SpecifierSet(text))
    except InvalidSpecifier:
        return text.strip()


def _canonical_marker(text: str) -> str:
    if not text or not text.strip():
        return ""
    try:
        return str(Marker(text))
    except Exception:
        return text.strip()


class InvalidDependencyTarget(ValueError):
    """A dependency target failed strict validation at the trusted boundary.

    Raised for configuration errors (a human or the goal builder supplying a
    malformed target), never for anything observed in an analyzed artifact. A
    target arriving through the automatic goal-driven path is validated by the
    caller and converted into a non-probative diagnostic on failure - it must
    never reach a verifier and must never widen into "any version" or
    "unconditional" just because a field was missing or the wrong type.
    """


def _require_target_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise InvalidDependencyTarget("name must be a non-empty string")
    try:
        canonicalize_name(name, validate=True)
    except InvalidName as exc:
        raise InvalidDependencyTarget(f"invalid dependency name: {name!r}") from exc
    return name


def _require_specifier_text(specifier: object) -> str:
    """No ``str()``, no truthiness: ``0``, ``False``, ``[]``, ``{}`` must not be
    silently read as "no specifier" - accepting them widened the claim to "any
    version" for a caller that almost certainly meant to supply something
    specific."""
    if not isinstance(specifier, str):
        raise InvalidDependencyTarget(f"specifier must be a string, got {type(specifier).__name__}")
    if specifier.strip():
        try:
            SpecifierSet(specifier)
        except InvalidSpecifier as exc:
            raise InvalidDependencyTarget(f"invalid specifier: {specifier!r}") from exc
    return specifier


def _require_marker_text(marker: object) -> str:
    if not isinstance(marker, str):
        raise InvalidDependencyTarget(f"marker must be a string, got {type(marker).__name__}")
    if marker.strip():
        try:
            Marker(marker)
        except Exception as exc:
            raise InvalidDependencyTarget(f"invalid marker: {marker!r}") from exc
    return marker


def _require_scope(scope: object) -> str:
    if not isinstance(scope, str) or not scope.strip():
        raise InvalidDependencyTarget(f"scope must be a non-empty string, got {scope!r}")
    return scope


def _require_extras(extras: object) -> tuple[str, ...]:
    if extras is None or isinstance(extras, str | bytes) or not isinstance(extras, tuple | list):
        raise InvalidDependencyTarget(f"extras must be a flat tuple of strings, got {extras!r}")
    result = []
    for item in extras:
        if not isinstance(item, str) or not item.strip():
            raise InvalidDependencyTarget(f"invalid extra name: {item!r}")
        try:
            canonicalize_name(item, validate=True)
        except InvalidName as exc:
            raise InvalidDependencyTarget(f"invalid extra name: {item!r}") from exc
        result.append(item)
    return tuple(result)


def _canonical_name(name: str) -> str:
    try:
        return canonicalize_name(name)
    except InvalidName:
        return name.strip().lower()


@dataclass(frozen=True)
class DependencyTarget:
    """The single, narrow claim a dependency verifier is asked to check.

    ``scope`` distinguishes core dependencies (``"core"``) from an optional
    group (``f"extra:{name}"``): an optional dependency must never corroborate
    a claim about the core dependency set, and vice versa.

    Validated strictly on construction (``__post_init__``): a non-string or
    syntactically invalid field raises ``InvalidDependencyTarget`` rather than
    being coerced or read as "no constraint". A malformed target is a
    configuration error at the boundary, not evidence to interpret charitably.
    """

    name: str
    specifier: str = ""
    marker: str = ""
    scope: str = "core"
    extras: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_target_name(self.name))
        object.__setattr__(self, "specifier", _require_specifier_text(self.specifier))
        object.__setattr__(self, "marker", _require_marker_text(self.marker))
        object.__setattr__(self, "scope", _require_scope(self.scope))
        object.__setattr__(self, "extras", _require_extras(self.extras))

    @property
    def canonical_name(self) -> str:
        return _canonical_name(self.name)

    @property
    def canonical_specifier(self) -> str:
        return _canonical_specifier(self.specifier)

    @property
    def canonical_marker(self) -> str:
        return _canonical_marker(self.marker)

    @property
    def canonical_extras(self) -> tuple[str, ...]:
        return tuple(sorted({_canonical_name(e) for e in self.extras}))

    def claim_text(self) -> str:
        extras = f"[{','.join(self.canonical_extras)}]" if self.canonical_extras else ""
        spec = self.canonical_specifier or "(any version)"
        marker = self.canonical_marker or "(unconditional)"
        return (
            f"the repository declares dependency {self.canonical_name}{extras} "
            f"under constraint {spec} with marker {marker} for scope {self.scope}"
        )


@dataclass(frozen=True)
class DeclaredDependency:
    """One dependency declaration found while parsing a manifest."""

    name: str
    specifier: str
    marker: str
    scope: str
    extras: tuple[str, ...] = ()

    @property
    def canonical_name(self) -> str:
        return _canonical_name(self.name)

    def matches_identity(self, target: DependencyTarget) -> bool:
        return self.canonical_name == target.canonical_name and self.scope == target.scope

    def matches_exactly(self, target: DependencyTarget) -> bool:
        return (
            self.matches_identity(target)
            and _canonical_specifier(self.specifier) == target.canonical_specifier
            and _canonical_marker(self.marker) == target.canonical_marker
            and tuple(sorted({_canonical_name(e) for e in self.extras})) == target.canonical_extras
        )


@dataclass(frozen=True)
class ParseOutcome:
    """Result of parsing a manifest: entries found plus honest degradations.

    ``fully_inspected`` is False whenever the file could hide declarations this
    parse did not see (an unresolved ``-r``/``-c`` include, or a PEP 621
    ``dynamic`` field), which is exactly the condition under which absence must
    never be read as refutation.

    ``direct_reference_count`` counts PEP 508 direct references (``pkg @ url``)
    encountered while parsing. A direct reference is visible - it does not make
    the file incompletely inspected - but it carries no name/specifier identity
    our target model recognises, so it never participates in matching and is
    never returned as ``supports`` or ``refutes`` for any target. The URL
    itself is never retained anywhere: a query string or URL fragment can carry
    a live secret exactly as userinfo can (``?token=...``, ``#token``), so the
    only conservative representation is a count plus the
    ``direct_reference_not_supported`` diagnostic - never the string.
    """

    entries: tuple[DeclaredDependency, ...] = ()
    fully_inspected: bool = True
    structurally_valid: bool = True
    diagnostics: tuple[str, ...] = ()
    direct_reference_count: int = 0


def parse_pyproject_dependencies(content: str) -> ParseOutcome:
    """Parse PEP 621 ``project.dependencies`` and ``project.optional-dependencies``.

    Deliberately ignores ``build-system.requires`` and every ``tool.*`` table:
    neither describes a runtime dependency of the project under PEP 621, and
    treating them as such would manufacture claims the standard does not make.
    A field declared both statically and as ``dynamic`` is a PEP 621 violation
    and is reported via ``dynamic_and_static_conflict`` rather than parsed.
    """
    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return ParseOutcome(fully_inspected=False, structurally_valid=False,
                            diagnostics=("toml_parse_error",))
    project = data.get("project")
    if not isinstance(project, dict):
        return ParseOutcome(fully_inspected=False, structurally_valid=False,
                            diagnostics=("missing_project_table",))

    diagnostics: list[str] = []
    direct_reference_count = 0
    dynamic = project.get("dynamic")
    if dynamic is not None and (
        not isinstance(dynamic, list)
        or any(not isinstance(field, str) for field in dynamic)
    ):
        return ParseOutcome(
            fully_inspected=False,
            structurally_valid=False,
            diagnostics=("invalid_dynamic_type",),
        )
    dynamic_fields = set(dynamic) if isinstance(dynamic, list) else set()
    core_dynamic = "dependencies" in dynamic_fields
    optional_dynamic = "optional-dependencies" in dynamic_fields

    entries: list[DeclaredDependency] = []
    raw_core = project.get("dependencies")
    if core_dynamic and raw_core is not None:
        diagnostics.append("dynamic_and_static_conflict")
    elif not core_dynamic:
        for line, is_direct_reference, problem in _parse_pep621_entries(raw_core, scope="core"):
            if is_direct_reference:
                direct_reference_count += 1
            if problem:
                diagnostics.append(problem)
            if line is not None:
                entries.append(line)

    raw_optional = project.get("optional-dependencies")
    if optional_dynamic and raw_optional is not None:
        diagnostics.append("dynamic_and_static_conflict")
    elif isinstance(raw_optional, dict):
        for extra_name, group in raw_optional.items():
            scope = f"extra:{_canonical_name(str(extra_name))}"
            for line, is_direct_reference, problem in _parse_pep621_entries(group, scope=scope):
                if is_direct_reference:
                    direct_reference_count += 1
                if problem:
                    diagnostics.append(problem)
                if line is not None:
                    entries.append(line)
    elif raw_optional is not None:
        diagnostics.append("invalid_optional_dependencies_type")

    fully_inspected = not (core_dynamic or optional_dynamic)
    if core_dynamic:
        diagnostics.append("dependencies_declared_dynamic")
    if optional_dynamic:
        diagnostics.append("optional_dependencies_declared_dynamic")
    return ParseOutcome(
        entries=tuple(entries),
        fully_inspected=fully_inspected,
        structurally_valid=True,
        diagnostics=tuple(sorted(set(diagnostics))),
        direct_reference_count=direct_reference_count,
    )


def _parse_pep621_entries(raw: object, scope: str):
    """Yield ``(entry | None, is_direct_reference, problem | None)`` per item.

    A direct reference (``pkg @ url``) carries no name/specifier identity our
    target model matches against: it is visible (does not hide anything) but
    never becomes an identity-bearing entry. The URL itself is NEVER retained -
    userinfo, query and fragment can all carry a live secret, so only the count
    and diagnostic survive.
    """
    if raw is None:
        return
    if not isinstance(raw, list):
        yield None, False, "invalid_dependencies_type"
        return
    for item in raw:
        if not isinstance(item, str):
            yield None, False, "invalid_dependency_entry_type"
            continue
        try:
            req = Requirement(item)
        except InvalidRequirement:
            yield None, False, "invalid_pep508_line"
            continue
        if req.url:
            yield None, True, "direct_reference_not_supported"
            continue
        yield (
            DeclaredDependency(
                name=req.name,
                specifier=str(req.specifier),
                marker=str(req.marker) if req.marker else "",
                scope=scope,
                extras=tuple(sorted(req.extras)),
            ),
            False,
            None,
        )


def parse_requirements_txt(content: str) -> ParseOutcome:
    """Parse a ``requirements.txt``-style file, distinguishing PEP 508
    requirement lines from pip-only directives, comments and blanks.

    Only ``-r``/``--requirement`` and ``-c``/``--constraint`` mark the file as
    not fully inspected: they can pull declarations from files this parse never
    reads. Editable installs, local paths and index options are visible right
    here - they simply are not PEP 508 requirements, so they contribute no
    evidence for or against any target, but they do not hide anything either.

    A full-line comment (optionally indented) is stripped; an INLINE trailing
    comment (``requests>=2 # note``) is deliberately NOT parsed as one, to avoid
    ambiguity with ``#`` appearing inside a URL fragment or an environment
    marker string. Such a line falls through to the PEP 508 parser and is
    reported as ``invalid_pep508_line`` - a documented, tested boundary, not a
    silent gap.
    """
    entries: list[DeclaredDependency] = []
    diagnostics: list[str] = []
    direct_reference_count = 0
    fully_inspected = True
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        first_token = line.split(None, 1)[0]
        if first_token in _PIP_INCLUDE_FLAGS or any(
            line.startswith(flag) for flag in _PIP_INCLUDE_FLAGS
        ):
            fully_inspected = False
            diagnostics.append("unresolved_include")
            continue
        if first_token in _PIP_OTHER_DIRECTIVE_PREFIXES or any(
            line.startswith(flag) for flag in _PIP_OTHER_DIRECTIVE_PREFIXES
        ):
            diagnostics.append("unsupported_pip_directive")
            continue
        if line.startswith("-"):
            diagnostics.append("unsupported_pip_directive")
            continue
        try:
            req = Requirement(line)
        except InvalidRequirement:
            diagnostics.append("invalid_pep508_line")
            continue
        if req.url:
            direct_reference_count += 1
            diagnostics.append("direct_reference_not_supported")
            continue
        entries.append(
            DeclaredDependency(
                name=req.name,
                specifier=str(req.specifier),
                marker=str(req.marker) if req.marker else "",
                scope="core",
                extras=tuple(sorted(req.extras)),
            )
        )
    return ParseOutcome(
        entries=tuple(entries),
        fully_inspected=fully_inspected,
        structurally_valid=True,
        diagnostics=tuple(sorted(set(diagnostics))),
        direct_reference_count=direct_reference_count,
    )


_PIP_COMPILE_HEADER = re.compile(
    r"^\s*#.*\b(pip-compile|autogenerated)\b.*$", re.IGNORECASE | re.MULTILINE
)


def looks_pip_compile_generated_from(content: str, source_filename: str) -> bool:
    """Conservative heuristic: does this file declare itself generated FROM another?

    Used by callers to decide whether to stamp ``derived_from`` when wiring two
    verifier results together. Per D's linkage rule, ``derived_from`` must
    reference the PARENT VerificationResult's ``result_id`` (passed as
    ``derived_from=(parent_result.result_id,)`` to ``run_verifier`` for the
    child), not a root fingerprint - a root links by content, derivation links
    by producing result. Two independently authored files are the intended
    positive case for independence; this only fires on an explicit, visible
    generation header naming the source file, never on mere name similarity or
    content overlap.
    """
    if not _PIP_COMPILE_HEADER.search(content):
        return False
    return source_filename in content


def _resolve(
    target: DependencyTarget, parsed: ParseOutcome
) -> tuple[str, tuple[str, ...]]:
    """Decide the outcome for one target against one parsed manifest.

    Precedence (BLOQUEO 2): an exact match found is always SUPPORTS - direct,
    positive, observed evidence outranks everything else. Absent an exact
    match, an unresolved include means the true declaration could exist
    somewhere this parse never read, so a same-identity MISMATCH must not be
    read as confident contradiction: only once the file is fully inspected can
    a mismatch become REFUTES. Getting this order backwards is exactly what let
    ``requests`` + an unresolved ``-c constraints.txt`` produce a false
    REFUTES against a target this parse never actually ruled out. A same-
    identity, fully-inspected mismatch means the name+scope IS declared here
    under a different constraint, which directly contradicts the expected claim.
    """
    if not parsed.structurally_valid:
        return DEGRADED, parsed.diagnostics
    same_identity = [e for e in parsed.entries if e.matches_identity(target)]
    for entry in same_identity:
        if entry.matches_exactly(target):
            return SUPPORTS, ()
    if not parsed.fully_inspected:
        return UNKNOWN, tuple(
            sorted(set(parsed.diagnostics) | {"unresolved_includes_may_hide_declaration"})
        )
    if same_identity:
        return REFUTES, ()
    return UNKNOWN, (*parsed.diagnostics, "not_declared_in_inspected_scope")


def _claim_for_parsed(target: DependencyTarget, parsed: ParseOutcome) -> VerifierClaim:
    """Resolve one target against an ALREADY-parsed manifest.

    Shared by the two public single-target verifier factories (which each
    parse their own payload) and by the automatic boundary below, which parses
    a manifest exactly once and resolves every requested target against that
    one ``ParseOutcome`` (PR E, P2-1) instead of re-parsing per target. The
    claim's aspect is the target's canonical name: if the goal does not
    declare it among its aspects, D's own gate degrades this to
    ``aspect_outside_goal``, which is correct and not routed around.
    """
    outcome, limitations = _resolve(target, parsed)
    return VerifierClaim(
        outcome=outcome,
        aspect=target.canonical_name,
        claim_text=target.claim_text(),
        scope=target.scope,
        confidence=0.9 if outcome in (SUPPORTS, REFUTES) else 0.0,
        limitations=limitations,
    )


def make_pep621_verifier(target: DependencyTarget):
    """Build a verifier checking ONE dependency target against ``pyproject.toml``."""

    def verify(payload: VerificationInput) -> list[VerifierClaim]:
        parsed = parse_pyproject_dependencies(payload.content)
        return [_claim_for_parsed(target, parsed)]

    return verify


def make_pep508_verifier(target: DependencyTarget):
    """Build a verifier checking ONE dependency target against a requirements file."""

    def verify(payload: VerificationInput) -> list[VerifierClaim]:
        parsed = parse_requirements_txt(payload.content)
        return [_claim_for_parsed(target, parsed)]

    return verify


def _verifier_from_parsed(target: DependencyTarget, parsed: ParseOutcome):
    """Verifier closure over an already-parsed manifest - no re-parse per target."""

    def verify(_payload: VerificationInput) -> list[VerifierClaim]:
        return [_claim_for_parsed(target, parsed)]

    return verify


# ---------------------------------------------------------------------------
# Automatic boundary: analyze_path -> discover manifests -> run_verifier ->
# proposition_from_verification -> aggregation (BLOQUEO 1, plan §5.5)
# ---------------------------------------------------------------------------

MAX_MANIFEST_BYTES = 4_000_000
"""Hard cap on manifest size. A file exceeding this is never partially read:
either the whole file is inspected, or it is not inspected at all."""

MAX_DEPENDENCY_TARGETS = 200
"""Hard cap on distinct targets accepted per call (P2-1). Bounds work: every
accepted target is charged its own cost below, so without a cap an unbounded
target list would still be an unbounded-cost list. Targets beyond the cap are
never silently dropped - they are counted and reported via
``dependency_targets_capped``."""

PYPROJECT_FILENAME = "pyproject.toml"
REQUIREMENTS_FILENAME = "requirements.txt"

_PER_TARGET_COST_TOKENS = 5
"""Fixed charge per (accepted target x inspected manifest): resolving a target
against an already-parsed manifest, stamping a VerificationResult and hashing
its identity is real, non-zero work. Without a per-target charge, a manifest
parsed once could still be "resolved" against an unbounded number of targets
for free, defeating the budget regardless of the manifest-read charge."""


def deterministic_execution_id(target_revision: str, artifact_id: str) -> str:
    """Stable execution id for one (revision, manifest) pair.

    Deterministic so the SAME analysis of the SAME revision always produces
    the same execution id (reproducibility, per D's identity contract), while
    still being distinct per manifest so pep621 and pep508 results never
    collide on execution id.
    """
    from .canonical import content_id

    return content_id(
        "dependency-verification-execution",
        {"target_revision": target_revision, "artifact_id": artifact_id},
    )


@dataclass(frozen=True)
class ManifestRead:
    """Outcome of opening and (attempting to) read a manifest file.

    ``problem`` (when set) is one of: ``not_found``, ``exceeds_size_limit``,
    ``encoding_error``, ``unreadable``, ``symlink_rejected``,
    ``symlink_protection_unavailable``, ``nonblocking_open_unavailable``,
    ``not_a_regular_file``, ``budget_exhausted``.
    """

    content: str | None
    problem: str | None
    size: int = 0
    """Observed bytes for diagnostics. It is cost-bearing only when ``charged``
    is true; ``manifest_bytes_read`` never records an uncharged value."""
    charged: bool = False


def _open_manifest_fd(path: Any) -> tuple[int | None, str | None]:
    """A SINGLE fail-closed open: ``O_NOFOLLOW`` makes symlink-rejection part
    of the atomic ``open()`` syscall itself (P1-4), closing the check-then-open
    race a separate ``path.is_symlink()`` before ``path.open()`` cannot close -
    a concurrent replacement between the check and the open could still slip a
    symlink through a two-step sequence; it cannot slip through one syscall.
    """
    if not hasattr(os, "O_NOFOLLOW"):
        return None, "symlink_protection_unavailable"
    if not hasattr(os, "O_NONBLOCK"):
        return None, "nonblocking_open_unavailable"
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        return os.open(str(path), flags), None
    except FileNotFoundError:
        return None, "not_found"
    except NotADirectoryError:
        return None, "not_found"
    except OSError as exc:
        if getattr(exc, "errno", None) == errno.ELOOP:
            return None, "symlink_rejected"
        return None, "unreadable"


def _read_manifest_bounded(
    path: Any,
    charge: Any,
    max_affordable_bytes: int | None = None,
) -> ManifestRead:
    """Read a manifest file's FULL bytes, or refuse outright - via ONE opened
    file descriptor, never a separate check-path then open-path sequence.

    ``fstat()`` on the already-open descriptor performs a conservative early
    cap check, but the charge uses the bytes actually read through that same
    descriptor. Reads continue until EOF or ``MAX_MANIFEST_BYTES + 1`` so a
    short read is never mistaken for EOF and growth after ``fstat()`` cannot
    be accepted or undercharged. A file that does not exist, is a symlink, is
    not regular or exceeds the cap is never charged.

    Never returns a truncated prefix: a file over the size cap is reported as
    unreadable-for-this-purpose rather than partially inspected, because a
    verifier result built from a partial read cannot honestly claim
    ``fully_inspected`` and must not be presented as if it could. The read
    itself is bounded to ``MAX_MANIFEST_BYTES + 1`` regardless of what
    ``fstat`` reported, so a file that grows between ``fstat`` and ``read`` on
    the SAME descriptor still cannot buy an unbounded read.
    """
    fd, problem = _open_manifest_fd(path)
    if fd is None:
        return ManifestRead(None, problem)
    try:
        try:
            st = os.fstat(fd)
        except OSError:
            return ManifestRead(None, "unreadable")
        if stat_module.S_ISLNK(st.st_mode):
            return ManifestRead(None, "symlink_rejected")
        if not stat_module.S_ISREG(st.st_mode):
            return ManifestRead(None, "not_a_regular_file")
        if st.st_size > MAX_MANIFEST_BYTES:
            return ManifestRead(None, "exceeds_size_limit")
        read_cap = MAX_MANIFEST_BYTES
        if max_affordable_bytes is not None:
            if max_affordable_bytes < 0:
                return ManifestRead(None, "budget_exhausted")
            read_cap = min(MAX_MANIFEST_BYTES, max_affordable_bytes)
            if st.st_size > read_cap:
                return ManifestRead(None, "budget_exhausted", size=st.st_size)
        chunks: list[bytes] = []
        total = 0
        while total <= read_cap:
            try:
                chunk = os.read(fd, read_cap + 1 - total)
            except OSError:
                return ManifestRead(None, "unreadable")
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    if len(raw) > MAX_MANIFEST_BYTES:
        return ManifestRead(None, "exceeds_size_limit", size=len(raw))
    if max_affordable_bytes is not None and len(raw) > max_affordable_bytes:
        return ManifestRead(None, "budget_exhausted", size=len(raw))
    if not charge(len(raw)):
        return ManifestRead(None, "budget_exhausted", size=len(raw))
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ManifestRead(None, "encoding_error", size=len(raw), charged=True)
    return ManifestRead(content, None, size=len(raw), charged=True)


def _coerce_target(spec: object) -> tuple[DependencyTarget | None, str | None]:
    """A target from the goal may be a DependencyTarget or a plain dict.

    Constructed defensively: a malformed spec from the goal-driven automatic
    path becomes a non-probative diagnostic, never an exception that aborts
    the whole analysis and never a support.
    """
    if isinstance(spec, DependencyTarget):
        return spec, None
    if isinstance(spec, dict):
        try:
            return DependencyTarget(**spec), None
        except (InvalidDependencyTarget, TypeError) as exc:
            return None, f"invalid_dependency_target:{type(exc).__name__}"
    return None, f"invalid_dependency_target:{type(spec).__name__}"


def _require_goal_aspects(value: object) -> tuple[tuple[str, ...], str | None]:
    """Strict validation, no iteration before the type is known (P1-5).

    ``goal_aspects=7``/``object()`` previously reached a bare ``for a in
    value`` and raised ``TypeError``; ``goal_aspects="requests"`` silently
    iterated CHARACTERS as individual aspect names; ``goal_aspects={"requests":
    True}`` silently accepted the dict's KEYS. Only a flat ``list``/``tuple`` of
    non-empty strings is accepted - no truthiness, no coercion, no iterating a
    container whose element type has not first been confirmed to be a string.
    """
    if not isinstance(value, list | tuple):
        return (), "invalid_goal_aspects"
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            return (), "invalid_goal_aspects"
        names.append(item)
    return tuple(sorted(set(names))), None


def _target_identity(target: DependencyTarget) -> tuple[str, str, str, str, tuple[str, ...]]:
    """Canonical identity for deduplication - two targets differing only in
    surface spelling (whitespace, case, specifier ordering) collapse to one."""
    return (
        target.canonical_name,
        target.scope,
        target.canonical_specifier,
        target.canonical_marker,
        target.canonical_extras,
    )


@dataclass(frozen=True)
class DependencyVerificationOutcome:
    """Everything the automatic boundary produced, for transparency and audit.

    Deliberately carries NO ``propositions`` field (P1-1): this boundary
    transports ``VerificationResult`` only. A ``Proposition`` is manufactured
    exclusively inside ``analyze_system``, via ``proposition_from_verification``
    after ``validate_verification_result`` - never here, and never by any
    other path, so a caller cannot bypass that single conversion by reading
    ``.propositions`` off this object.
    """

    results: tuple[Any, ...]
    diagnostics: tuple[str, ...]
    manifests_inspected: tuple[str, ...]
    manifest_bytes_read: tuple[tuple[str, int], ...]
    requested_targets: int
    accepted_targets: int
    rejected_targets: int
    executions: int
    families_executed: tuple[str, ...]
    charged_tokens: int
    charged_tool: int
    budget_charge_id: str = ""


def _dependency_outcome_charge_id(outcome: DependencyVerificationOutcome) -> str:
    from .canonical import content_id

    return content_id(
        "dependency-verification-charge",
        {
            "results": [result.result_id for result in outcome.results],
            "diagnostics": list(outcome.diagnostics),
            "manifests_inspected": list(outcome.manifests_inspected),
            "manifest_bytes_read": [list(item) for item in outcome.manifest_bytes_read],
            "requested_targets": outcome.requested_targets,
            "accepted_targets": outcome.accepted_targets,
            "rejected_targets": outcome.rejected_targets,
            "executions": outcome.executions,
            "families_executed": list(outcome.families_executed),
            "charged_tokens": outcome.charged_tokens,
            "charged_tool": outcome.charged_tool,
        },
    )


def _finalize_dependency_outcome(
    outcome: DependencyVerificationOutcome,
    budget: Any,
    receipts: tuple[object, ...] = (),
) -> DependencyVerificationOutcome:
    charge_id = _dependency_outcome_charge_id(outcome)
    finalized = replace(outcome, budget_charge_id=charge_id)
    recorder = getattr(budget, "_record_consumed_charge", None)
    if callable(recorder):
        from .algorithm import Cost

        recorded = recorder(
            charge_id,
            Cost(tokens=outcome.charged_tokens, tool=outcome.charged_tool),
            receipts,
        )
        if not recorded:
            raise RuntimeError("dependency_charge_receipt_mismatch")
    return finalized


def validate_dependency_verification_outcome(outcome: Any) -> tuple[str, ...]:
    if not isinstance(outcome, DependencyVerificationOutcome):
        return ("invalid_dependency_verification_outcome",)
    problems: list[str] = []
    if not isinstance(outcome.results, tuple) or any(
        validate_verification_result(result) for result in outcome.results
    ):
        problems.append("invalid_results")
    for name, textual_value in (
        ("diagnostics", outcome.diagnostics),
        ("manifests_inspected", outcome.manifests_inspected),
        ("families_executed", outcome.families_executed),
    ):
        if not isinstance(textual_value, tuple) or not all(
            isinstance(item, str) for item in textual_value
        ):
            problems.append(f"invalid_{name}")
    if not isinstance(outcome.manifest_bytes_read, tuple) or not all(
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        and not isinstance(item[1], bool)
        and isinstance(item[1], int)
        and 0 <= item[1] <= MAX_MANIFEST_BYTES
        for item in outcome.manifest_bytes_read
    ):
        problems.append("invalid_manifest_bytes_read")
    for name, numeric_value in (
        ("requested_targets", outcome.requested_targets),
        ("accepted_targets", outcome.accepted_targets),
        ("rejected_targets", outcome.rejected_targets),
        ("executions", outcome.executions),
        ("charged_tokens", outcome.charged_tokens),
        ("charged_tool", outcome.charged_tool),
    ):
        if (
            isinstance(numeric_value, bool)
            or not isinstance(numeric_value, int)
            or numeric_value < 0
        ):
            problems.append(f"invalid_{name}")
    if not isinstance(outcome.budget_charge_id, str) or not outcome.budget_charge_id:
        problems.append("invalid_budget_charge_id")
    if problems:
        return tuple(sorted(set(problems)))
    if outcome.accepted_targets + outcome.rejected_targets != outcome.requested_targets:
        problems.append("inconsistent_target_counts")
    if outcome.executions != len(outcome.results):
        problems.append("inconsistent_execution_count")
    expected_families = tuple(sorted({result.verifier_family for result in outcome.results}))
    if outcome.families_executed != expected_families:
        problems.append("inconsistent_families_executed")
    allowed_manifests = (PYPROJECT_FILENAME, REQUIREMENTS_FILENAME)
    expected_manifests = tuple(name for name in allowed_manifests if name in outcome.manifests_inspected)
    if outcome.manifests_inspected != expected_manifests:
        problems.append("invalid_manifests_inspected")
    charged_manifest_names = tuple(item[0] for item in outcome.manifest_bytes_read)
    expected_charged_names = tuple(name for name in allowed_manifests if name in charged_manifest_names)
    if charged_manifest_names != expected_charged_names:
        problems.append("invalid_manifest_bytes_read")
    if any(name not in charged_manifest_names for name in outcome.manifests_inspected):
        problems.append("manifest_charge_mismatch")
    if any(result.artifact_id not in outcome.manifests_inspected for result in outcome.results):
        problems.append("result_manifest_mismatch")
    expected_tool = len(outcome.manifest_bytes_read) + outcome.executions
    if outcome.charged_tool != expected_tool:
        problems.append("inconsistent_tool_cost")
    expected_tokens = sum(
        max(10, size // 4) for _, size in outcome.manifest_bytes_read
    ) + (_PER_TARGET_COST_TOKENS * outcome.executions)
    if outcome.charged_tokens != expected_tokens:
        problems.append("inconsistent_token_cost")
    if not problems and outcome.budget_charge_id != _dependency_outcome_charge_id(outcome):
        problems.append("budget_charge_id_mismatch")
    return tuple(sorted(set(problems)))


def verify_dependency_targets(
    root: Any,
    targets: Any,
    target_revision: object,
    budget: Any = None,
    goal_aspects: Any = (),
) -> DependencyVerificationOutcome:
    """THE single automatic boundary: goal-declared targets -> stamped
    ``VerificationResult`` (via ``run_verifier``). Conversion to ``Proposition``
    is intentionally NOT done here (P1-1) - only ``analyze_system`` performs it,
    exclusively via ``proposition_from_verification``.

    Opt-in is the presence of ``targets`` as a caller-supplied argument at all;
    the caller (``analyze_path``) decides presence from the goal, this function
    only classifies what it is given: a missing/empty valid collection produces
    no work and no diagnostic, an invalid type produces a diagnostic and no
    work (P1-6).

    ``goal_aspects`` are the REAL required aspects of the goal under analysis,
    never the target's own name (P1-2): a target whose canonical name is not
    among them is out of scope for this goal and is never executed - it
    produces ``dependency_target_outside_goal`` and contributes no
    ``VerificationResult``, so it can never surface as a probative proposition
    for a goal that never asked about it, and it can never contaminate that
    goal's coverage/risk/completion.

    Manifest cost is charged from the complete bounded byte count actually read;
    target-resolution cost is admitted against ``budget`` before the target
    runs. A manifest whose charge the budget cannot afford is unavailable for
    this call, never a confident absence. A nonexistent file, rejected symlink,
    over-cap file or target with zero parsed manifests costs nothing. Targets
    are deduplicated by canonical identity and capped at
    ``MAX_DEPENDENCY_TARGETS``.

    ``targets`` is guarded explicitly: a non-iterable value (``targets=7``) or
    a bare string would otherwise raise from iteration or silently iterate
    characters as individual specs; both are rejected as the caller error they
    almost certainly are. Each accepted target is resolved against the set of
    manifests actually available, in fixed order (pep621 before pep508) so
    ``derived_from`` linkage is well-defined; a target with zero available
    manifests has nothing to resolve against and is never charged, executed or
    diagnosed. Resolution is all-or-nothing per target (P1-3): the target is
    charged and executed against EVERY available manifest, or NONE of them -
    never a partial subset that would look complete while silently omitting a
    manifest the target should have been checked against.
    """
    from pathlib import Path

    from .verifiers import VerifierRegistration, run_verifier, verification_input

    def _empty(diag: tuple[str, ...] = ()) -> DependencyVerificationOutcome:
        return _finalize_dependency_outcome(
            DependencyVerificationOutcome((), diag, (), (), 0, 0, 0, 0, (), 0, 0),
            budget,
        )

    if budget is not None:
        from .algorithm import Budget

        if not isinstance(budget, Budget):
            return _finalize_dependency_outcome(
                DependencyVerificationOutcome(
                    (), ("invalid_budget",), (), (), 0, 0, 0, 0, (), 0, 0
                ),
                None,
            )

    if not isinstance(target_revision, str) or not target_revision.strip():
        return _empty(("missing_target_revision",))
    if not isinstance(targets, list | tuple):
        return _empty(("invalid_dependency_targets_collection",))

    goal_aspect_names, goal_aspects_problem = _require_goal_aspects(goal_aspects)
    if goal_aspects_problem is not None:
        return _empty((goal_aspects_problem,))

    if not targets:
        return _empty()

    diagnostics: list[str] = []
    requested_targets = len(targets)
    coerced: list[DependencyTarget] = []
    for spec in targets:
        target, problem = _coerce_target(spec)
        if problem:
            diagnostics.append(problem)
        elif target is not None:
            coerced.append(target)

    seen_identities: dict[tuple, DependencyTarget] = {}
    for target in coerced:
        seen_identities.setdefault(_target_identity(target), target)
    deduped = [seen_identities[key] for key in sorted(seen_identities)]

    in_scope: list[DependencyTarget] = []
    for target in deduped:
        if target.canonical_name not in goal_aspect_names:
            diagnostics.append(f"dependency_target_outside_goal:{target.canonical_name}")
            continue
        in_scope.append(target)

    if len(in_scope) > MAX_DEPENDENCY_TARGETS:
        diagnostics.append(
            f"dependency_targets_capped:{len(in_scope) - MAX_DEPENDENCY_TARGETS}"
        )
        in_scope = in_scope[:MAX_DEPENDENCY_TARGETS]

    accepted_targets = len(in_scope)
    rejected_targets = requested_targets - accepted_targets
    if not in_scope:
        return _finalize_dependency_outcome(
            DependencyVerificationOutcome(
                (), tuple(diagnostics), (), (), requested_targets, 0, rejected_targets, 0, (), 0, 0
            ),
            budget,
        )

    root_path = Path(root)
    charged_tokens = 0
    charged_tool = 0
    charge_receipts: list[object] = []

    def _charge(cost_tokens: int, cost_tool: int) -> bool:
        nonlocal charged_tokens, charged_tool
        if budget is None:
            charged_tokens += cost_tokens
            charged_tool += cost_tool
            return True
        from .algorithm import Cost

        cost = Cost(tokens=cost_tokens, tool=cost_tool)
        receipt = budget._consume_with_receipt(cost)
        if receipt is None:
            return False
        charge_receipts.append(receipt)
        charged_tokens += cost_tokens
        charged_tool += cost_tool
        return True

    def _load_manifest(filename: str) -> str | None:
        """Read one manifest via the bounded, symlink-rejecting reader.

        ``charge`` receives the complete bounded byte count read from the opened
        descriptor, never a stale path or ``fstat()`` estimate.
        """
        path = root_path / filename
        max_affordable_bytes = None
        if budget is not None:
            max_affordable_bytes = (
                min(MAX_MANIFEST_BYTES, budget.tokens_remaining * 4 + 3)
                if budget.tool_remaining >= 1 and budget.tokens_remaining >= 10
                else -1
            )
        read = _read_manifest_bounded(
            path,
            lambda size: _charge(max(10, size // 4), 1),
            max_affordable_bytes=max_affordable_bytes,
        )
        if read.problem is not None and read.problem != "not_found":
            diagnostics.append(f"{filename}:{read.problem}")
        if read.charged:
            manifest_bytes_read.append((filename, read.size))
        if read.content is not None:
            manifests_inspected.append(filename)
        return read.content

    manifests_inspected: list[str] = []
    manifest_bytes_read: list[tuple[str, int]] = []
    pyproject_content = _load_manifest(PYPROJECT_FILENAME)
    requirements_content = _load_manifest(REQUIREMENTS_FILENAME)

    pyproject_parsed = (
        parse_pyproject_dependencies(pyproject_content) if pyproject_content is not None else None
    )
    requirements_parsed = (
        parse_requirements_txt(requirements_content) if requirements_content is not None else None
    )

    requirements_derived_from_pyproject = bool(
        pyproject_content is not None
        and requirements_content is not None
        and looks_pip_compile_generated_from(requirements_content, PYPROJECT_FILENAME)
    )

    available: list[tuple[str, str, str, ParseOutcome]] = []
    if pyproject_parsed is not None:
        assert pyproject_content is not None
        available.append((PEP621_PROFILE, PYPROJECT_FILENAME, pyproject_content, pyproject_parsed))
    if requirements_parsed is not None:
        assert requirements_content is not None
        available.append((PEP508_PROFILE, REQUIREMENTS_FILENAME, requirements_content, requirements_parsed))

    results = []
    families_executed: set[str] = set()
    executions = 0
    for target in in_scope:
        if not available:
            continue
        resolution_cost = _PER_TARGET_COST_TOKENS * len(available)
        if not _charge(resolution_cost, len(available)):
            diagnostics.append(f"dependency_target_budget_exhausted:{target.canonical_name}")
            continue

        pep621_result = None
        for family, filename, content, parsed in available:
            payload = verification_input(
                filename, content, filename, target_revision, goal_aspect_names,
            )
            derived_from = (
                (pep621_result.result_id,)
                if family == PEP508_PROFILE
                and requirements_derived_from_pyproject
                and pep621_result is not None
                else ()
            )
            registration = VerifierRegistration(
                family, VERIFIER_VERSION, "deterministic",
                _verifier_from_parsed(target, parsed), "",
            )
            exec_id = deterministic_execution_id(target_revision, filename)
            result = run_verifier(registration, payload, exec_id, derived_from=derived_from)[0]
            results.append(result)
            families_executed.add(family)
            executions += 1
            if family == PEP621_PROFILE:
                pep621_result = result

    return _finalize_dependency_outcome(
        DependencyVerificationOutcome(
            tuple(results),
            tuple(diagnostics),
            tuple(manifests_inspected),
            tuple(manifest_bytes_read),
            requested_targets,
            accepted_targets,
            rejected_targets,
            executions,
            tuple(sorted(families_executed)),
            charged_tokens,
            charged_tool,
        ),
        budget,
        tuple(charge_receipts),
    )


def dependency_verification_report(
    outcome: DependencyVerificationOutcome, target_revision: str
) -> dict[str, Any]:
    """The sanitized, PUBLIC summary of one ``verify_dependency_targets`` call
    (P1-4). Never includes manifest content or any URL - only structural,
    already-non-secret fields: result identity, outcome, aspect, limitations,
    degradations and diagnostics. Included in the report even when zero
    ``VerificationResult`` turned into a proposition, so a target rejected as
    invalid, out-of-scope, oversized, unreadable or budget-exhausted remains
    visible rather than silently vanishing.
    """
    if validate_dependency_verification_outcome(outcome):
        return {
            "enabled": False,
            "diagnostics": ["invalid_dependency_verification_outcome"],
        }
    return {
        "enabled": True,
        "evaluated_target_revision": target_revision,
        "requested_targets": outcome.requested_targets,
        "accepted_targets": outcome.accepted_targets,
        "rejected_targets": outcome.rejected_targets,
        "families_executed": list(outcome.families_executed),
        "manifests_inspected": list(outcome.manifests_inspected),
        "manifest_bytes_read": [
            {"manifest": name, "bytes": size}
            for name, size in outcome.manifest_bytes_read
        ],
        "verification_result_count": len(outcome.results),
        "results": [
            {
                "result_id": r.result_id,
                "outcome": r.outcome,
                "aspect": r.aspect,
                "limitations": list(r.limitations),
                "degradations": list(r.degradations),
            }
            for r in outcome.results
        ],
        "diagnostics": list(outcome.diagnostics),
        "cost": {"tokens": outcome.charged_tokens, "tool": outcome.charged_tool},
    }
