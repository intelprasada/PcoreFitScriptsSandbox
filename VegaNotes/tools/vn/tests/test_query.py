"""Unit tests for the vn DSL parser/compiler (`vn/query.py`)."""

from __future__ import annotations

import pytest

from vn.query import DSLError, compile_clauses, parse_clause


# ---------- parse_clause ---------------------------------------------------

@pytest.mark.parametrize("clause,expected", [
    ("owner=alice",         ("owner", "eq", "alice")),
    ("project!=internal",   ("project", "ne", "internal")),
    ("priority in P0,P1",   ("priority", "in", "P0,P1")),
    ("priority not in P3",  ("priority", "nin", "P3")),
    ("eta>=ww18",           ("eta", "gte", "ww18")),
    ("eta<=2026-W20",       ("eta", "lte", "2026-W20")),
    ("eta>ww17",            ("eta", "gt", "ww17")),
    ("eta<ww22",            ("eta", "lt", "ww22")),
    ("@area=fit-val",       ("@area", "eq", "fit-val")),
    ("@Risk = high",        ("@risk", "eq", "high")),
    # Word op is case-insensitive on the operator but preserves value.
    ("status IN open,wip",  ("status", "in", "open,wip")),
    # Status legacy "!done" sentinel — the leading `!` is part of the value,
    # not the operator, because `=` matches before `!=` only when present.
    ("status=!done",        ("status", "eq", "!done")),
    # Owners with dots/dashes survive.
    ("owner=foo.bar-baz",   ("owner", "eq", "foo.bar-baz")),
])
def test_parse_clause(clause, expected):
    assert parse_clause(clause) == expected


@pytest.mark.parametrize("bad", [
    "",
    "owner",
    "=alice",
    "owner=",
    "owner alice",          # no operator, no `in`
    "  ",
])
def test_parse_clause_errors(bad):
    with pytest.raises(DSLError):
        parse_clause(bad)


# ---------- compile_clauses ------------------------------------------------

def test_compile_simple_fixed():
    pairs = compile_clauses(["owner=alice", "status=wip"])
    assert ("owner", "alice") in pairs
    assert ("status", "wip") in pairs


def test_compile_fixed_negation():
    pairs = compile_clauses(["project!=internal"])
    assert pairs == [("not_project", "internal")]


def test_compile_fixed_in_passthrough():
    # The backend `_split` helper splits comma values, so we pass the
    # raw csv string straight through as a single param.
    pairs = compile_clauses(["priority in P0,P1"])
    assert pairs == [("priority", "P0,P1")]


def test_compile_arbitrary_attr():
    pairs = compile_clauses(["@area=fit-val", "@risk!=low"])
    assert pairs == [
        ("attr", "area:eq:fit-val"),
        ("attr", "risk:ne:low"),
    ]


def test_compile_attr_in_keeps_csv():
    pairs = compile_clauses(["@area in fit-val,infra"])
    assert pairs == [("attr", "area:in:fit-val,infra")]


def test_compile_eta_range_uses_dedicated_params():
    pairs = compile_clauses(["eta>=2026-04-20", "eta<=2026-05-01"])
    assert ("eta_after", "2026-04-20") in pairs
    assert ("eta_before", "2026-05-01") in pairs


def test_compile_eta_eq_routes_through_attr():
    # `eta=ww17` is a bucket query — the date-typed eta_before/after
    # params can't express it, so it must take the generic attr path.
    pairs = compile_clauses(["eta=ww17"])
    assert pairs == [("attr", "eta:eq:ww17")]


def test_compile_eta_strict_gt_lt_uses_attr():
    pairs = compile_clauses(["eta>ww17", "eta<ww22"])
    assert ("attr", "eta:gt:ww17") in pairs
    assert ("attr", "eta:lt:ww22") in pairs


def test_compile_q_and_kind_passthrough():
    pairs = compile_clauses(["q=hello world", "kind=ar"])
    assert ("q", "hello world") in pairs
    assert ("kind", "ar") in pairs


def test_compile_multiple_attrs_preserved_as_repeats():
    # Multiple `attr` params must come through as separate pairs so the
    # urlencoder sends them as repeats.
    pairs = compile_clauses(["@area=a", "@area=b", "@risk=high"])
    keys = [k for k, _ in pairs]
    assert keys.count("attr") == 3


def test_compile_skips_empty():
    assert compile_clauses(["", None, "  ", "owner=x"]) == [("owner", "x")]


def test_compile_rejects_range_op_on_owner():
    with pytest.raises(DSLError):
        compile_clauses(["owner>=alice"])


def test_compile_rejects_unknown_lhs_without_at():
    with pytest.raises(DSLError):
        compile_clauses(["area=fit-val"])
