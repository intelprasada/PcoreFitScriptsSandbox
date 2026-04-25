import { describe, it, expect } from "vitest";
import { compileClauses, parseClause, renderClause, DSLError } from "../src/store/dsl.ts";

describe("parseClause", () => {
  it.each([
    ["owner=alice",        { lhs: "owner",   op: "eq",  value: "alice", isAttr: false }],
    ["project!=internal",  { lhs: "project", op: "ne",  value: "internal", isAttr: false }],
    ["priority in P0,P1",  { lhs: "priority", op: "in", value: "P0,P1", isAttr: false }],
    ["priority not in P3", { lhs: "priority", op: "nin", value: "P3",   isAttr: false }],
    ["eta>=ww18",          { lhs: "eta",     op: "gte", value: "ww18",  isAttr: false }],
    ["@area=fit-val",      { lhs: "@area",   op: "eq",  value: "fit-val", isAttr: true }],
    ["@Risk = high",       { lhs: "@risk",   op: "eq",  value: "high",  isAttr: true }],
    ["status IN open,wip", { lhs: "status",  op: "in",  value: "open,wip", isAttr: false }],
    ["status=!done",       { lhs: "status",  op: "eq",  value: "!done", isAttr: false }],
  ] as const)("parses %s", (clause, expected) => {
    expect(parseClause(clause)).toEqual(expected);
  });

  it.each(["", "owner", "=alice", "owner=", "owner alice", "  "])(
    "rejects %p",
    (bad) => { expect(() => parseClause(bad)).toThrow(DSLError); },
  );
});

describe("compileClauses", () => {
  it("compiles fixed columns", () => {
    expect(compileClauses(["owner=alice", "status=wip"])).toEqual([
      ["owner", "alice"], ["status", "wip"],
    ]);
  });

  it("inverts fixed columns via not_*", () => {
    expect(compileClauses(["project!=internal"])).toEqual([["not_project", "internal"]]);
  });

  it("passes 'in' as csv to fixed columns", () => {
    expect(compileClauses(["priority in P0,P1"])).toEqual([["priority", "P0,P1"]]);
  });

  it("compiles arbitrary @attrs", () => {
    expect(compileClauses(["@area=fit-val", "@risk!=low"])).toEqual([
      ["attr", "area:eq:fit-val"],
      ["attr", "risk:ne:low"],
    ]);
  });

  it("routes eta range to dedicated date params", () => {
    expect(compileClauses(["eta>=2026-04-20", "eta<=2026-05-01"])).toEqual([
      ["eta_after", "2026-04-20"],
      ["eta_before", "2026-05-01"],
    ]);
  });

  it("routes eta equality through generic attr path", () => {
    expect(compileClauses(["eta=ww17"])).toEqual([["attr", "eta:eq:ww17"]]);
  });

  it("emits multiple attr params for repeated @key clauses", () => {
    const out = compileClauses(["@area=a", "@area=b", "@risk=high"]);
    expect(out.filter(([k]) => k === "attr")).toHaveLength(3);
  });

  it("rejects range op on non-date fixed column", () => {
    expect(() => compileClauses(["owner>=alice"])).toThrow(DSLError);
  });

  it("rejects unknown key without @ prefix", () => {
    expect(() => compileClauses(["area=fit-val"])).toThrow(DSLError);
  });

  it("skips empty clauses", () => {
    expect(compileClauses(["", "  ", "owner=x"])).toEqual([["owner", "x"]]);
  });
});

describe("renderClause round-trip", () => {
  it.each([
    "owner=alice",
    "project!=internal",
    "@area=fit-val",
    "eta>=ww18",
    "priority in P0,P1",
    "priority not in P3",
  ])("re-renders %s", (clause) => {
    const c = parseClause(clause);
    const round = renderClause(c);
    // Re-parse round-trip equals the parsed canonical form.
    expect(parseClause(round)).toEqual(c);
  });
});
