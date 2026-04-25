"""Mini-DSL for ``vn list --where``.

Each ``--where`` clause is a single string ``key OP value``; clauses are
combined with implicit AND. Examples::

    owner=alice
    project!=internal
    priority in P0,P1
    eta>=2026-W18
    @area=fit-val           # arbitrary TaskAttr key
    status=!done            # legacy backend "everything but done" convention

The compiler translates clauses into the wire parameters that
``GET /api/tasks`` already understands (issue #38 follow-up):

* Known fixed columns (``owner``, ``project``, ``feature``, ``priority``,
  ``status``) compile to ``?key=v`` (or ``?not_key=v`` for ``!=``).
  Range operators on these are rejected — they don't index a sortable
  domain.  ``in`` becomes a comma-separated string, which the backend
  ``_split`` helper already accepts.
* ``eta`` compiles to ``?eta_before=`` / ``?eta_after=`` for range ops
  (date-typed) and to ``attr=eta:eq:bucket`` for equality (so ``ww17``
  buckets work).
* ``@key`` compiles to ``attr=key:op:value`` (repeatable).
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# Public surface --------------------------------------------------------------

__all__ = ["DSLError", "compile_clauses", "parse_clause"]


class DSLError(ValueError):
    """Raised for any malformed DSL clause."""


# Operator table. Order matters — longer prefixes first.
_OP_TOKENS: list[tuple[str, str]] = [
    (">=", "gte"),
    ("<=", "lte"),
    ("!=", "ne"),
    ("=",  "eq"),
    (">",  "gt"),
    ("<",  "lt"),
]

# Word operators (whitespace-bounded). Longest first so ``not in`` is
# tried before ``in``.
_WORD_OPS: list[tuple[str, str]] = [
    ("not in", "nin"),
    ("in",     "in"),
    ("like",   "like"),
]

# Fixed columns whose backend params we map to directly.  Anything not
# in this set must be addressed via the ``@key`` form.
_FIXED_COLUMNS: frozenset[str] = frozenset({
    "owner", "project", "feature", "priority", "status",
})

# Operators allowed on each fixed column.  Range ops only make sense on
# numeric / date domains; the backend has no "owner > x" semantics.
_FIXED_OPS: frozenset[str] = frozenset({"eq", "ne", "in"})


def parse_clause(clause: str) -> tuple[str, str, str]:
    """Split a clause into ``(lhs, op_code, value)``.

    ``op_code`` is the canonical short form (``eq``, ``ne``, ``gte``,
    ``lte``, ``gt``, ``lt``, ``in``, ``nin``, ``like``).
    """
    s = clause.strip()
    if not s:
        raise DSLError("empty clause")

    # Try word operators first (they need whitespace on both sides so we
    # don't accidentally split ``project=index``).  Match against the
    # original string with case-insensitive flag so ``IN`` / ``In`` work.
    for word, code in _WORD_OPS:
        m = re.match(
            rf"^(.+?)\s+{re.escape(word)}\s+(.+)$",
            s,
            flags=re.IGNORECASE,
        )
        if m:
            lhs = m.group(1).strip()
            rhs = m.group(2).strip()
            if not lhs or not rhs:
                raise DSLError(f"malformed clause: {clause!r}")
            return _normalize_lhs(lhs), code, rhs

    # Symbolic operators.
    for token, code in _OP_TOKENS:
        idx = s.find(token)
        if idx <= 0:
            continue
        lhs = s[:idx].strip()
        rhs = s[idx + len(token):].strip()
        if not lhs:
            raise DSLError(f"missing key in {clause!r}")
        if not rhs:
            raise DSLError(f"missing value in {clause!r}")
        return _normalize_lhs(lhs), code, rhs

    raise DSLError(
        f"no operator found in {clause!r}; "
        "expected one of =, !=, >=, <=, >, <, 'in', 'not in'"
    )


def _normalize_lhs(lhs: str) -> str:
    """Canonical-case key, preserving the leading ``@`` marker."""
    lhs = lhs.strip()
    if lhs.startswith("@"):
        return "@" + lhs[1:].strip().lower()
    return lhs.lower()


def compile_clauses(clauses: Iterable[str]) -> list[tuple[str, Any]]:
    """Compile DSL clauses into ``(param_name, value)`` pairs.

    Returns a list of pairs (rather than a dict) because some
    parameters may legitimately appear more than once — most notably
    ``attr`` (one entry per arbitrary-attr filter).  The CLI hands the
    list off to ``Client.request`` which knows how to encode repeats.
    """
    out: list[tuple[str, Any]] = []
    for raw in clauses:
        if raw is None or not str(raw).strip():
            continue
        lhs, op, value = parse_clause(str(raw))
        out.extend(_compile_one(lhs, op, value, raw))
    return out


# Per-clause compilation -----------------------------------------------------

def _compile_one(lhs: str, op: str, value: str, raw: str) -> list[tuple[str, Any]]:
    if lhs.startswith("@"):
        key = lhs[1:]
        if not key:
            raise DSLError(f"empty attr key in {raw!r}")
        return [("attr", f"{key}:{op}:{value}")]

    if lhs == "q":
        if op != "eq":
            raise DSLError(f"q only supports '=' (got {op!r})")
        return [("q", value)]

    if lhs == "kind":
        if op != "eq":
            raise DSLError(f"kind only supports '=' (got {op!r})")
        return [("kind", value)]

    if lhs == "eta":
        return _compile_eta(op, value, raw)

    if lhs in _FIXED_COLUMNS:
        if op not in _FIXED_OPS:
            raise DSLError(
                f"operator {op!r} not supported on {lhs!r}; "
                f"use one of =, !=, in (or address it as @{lhs} for richer ops)"
            )
        if op == "ne":
            return [(f"not_{lhs}", value)]
        # eq + in both produce a single comma-joined string — the backend
        # `_split` helper already turns that into an OR-list.
        return [(lhs, value)]

    raise DSLError(
        f"unknown key {lhs!r}; prefix arbitrary attrs with '@' (e.g. @{lhs}=…)"
    )


def _compile_eta(op: str, value: str, raw: str) -> list[tuple[str, Any]]:
    # Range ops — defer to the dedicated date-typed params so the
    # server can compare against real dates rather than the raw string.
    if op == "gte":
        return [("eta_after", value)]
    if op == "lte":
        return [("eta_before", value)]
    if op == "gt":
        # `eta_after` is inclusive; bump-by-day is server-side work, so
        # for now route strict `>` through the generic attr path which
        # uses lexicographic comparison on `value_norm`.
        return [("attr", f"eta:gt:{value}")]
    if op == "lt":
        return [("attr", f"eta:lt:{value}")]
    if op in ("eq", "ne", "in", "nin", "like"):
        return [("attr", f"eta:{op}:{value}")]
    raise DSLError(f"unsupported operator on eta: {op!r} (clause {raw!r})")
