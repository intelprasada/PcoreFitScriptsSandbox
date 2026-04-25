import { describe, it, expect, beforeEach } from "vitest";
import { useUI, filtersToParams } from "../src/store/ui.ts";

beforeEach(() => {
  useUI.setState({ filters: { hide_done: true, where: [] } });
});

describe("UI filter store", () => {
  it("addChip appends to where", () => {
    useUI.getState().addChip("@area=fit-val");
    useUI.getState().addChip("eta>=ww18");
    expect(useUI.getState().filters.where).toEqual(["@area=fit-val", "eta>=ww18"]);
  });

  it("removeChip drops by index", () => {
    useUI.getState().setChips(["a=1", "b=2", "c=3"]);
    useUI.getState().removeChip(1);
    expect(useUI.getState().filters.where).toEqual(["a=1", "c=3"]);
  });

  it("clearFilters resets where to []", () => {
    useUI.getState().setChips(["@a=1"]);
    useUI.getState().clearFilters();
    expect(useUI.getState().filters.where).toEqual([]);
    expect(useUI.getState().filters.hide_done).toBe(true);
  });
});

describe("filtersToParams", () => {
  it("passes fixed columns through unchanged", () => {
    const params = filtersToParams({
      owner: "alice", project: "qry", hide_done: true,
    });
    expect(params.owner).toBe("alice");
    expect(params.project).toBe("qry");
    expect(params.hide_done).toBe(true);
  });

  it("compiles where chips into wire params", () => {
    const params = filtersToParams({
      where: ["@area=fit-val", "eta>=ww18", "project!=internal"],
    });
    expect(params.attr).toBe("area:eq:fit-val");
    expect(params.eta_after).toBe("ww18");
    expect(params.not_project).toBe("internal");
  });

  it("collapses repeated attr params into an array for the api client", () => {
    const params = filtersToParams({
      where: ["@area=a", "@area=b", "@risk=high"],
    });
    expect(Array.isArray(params.attr)).toBe(true);
    expect(params.attr).toEqual(["area:eq:a", "area:eq:b", "risk:eq:high"]);
  });

  it("merges flag-set owner with chip-derived owner into an array", () => {
    const params = filtersToParams({
      owner: "alice",
      where: ["owner=bob"],
    });
    expect(params.owner).toEqual(["alice", "bob"]);
  });

  it("ignores empty chips", () => {
    const params = filtersToParams({ where: ["", "  ", "owner=x"] });
    expect(params.owner).toBe("x");
  });
});
