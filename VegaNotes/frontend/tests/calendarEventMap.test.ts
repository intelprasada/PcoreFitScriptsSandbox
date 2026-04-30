import { describe, it, expect } from "vitest";
import { tasksToCalendarEvents } from "../src/components/Calendar/eventMap.ts";
import type { Task } from "../src/api/client";

function mkTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 1,
    task_uuid: null,
    slug: "t-1",
    title: "Untitled",
    status: "wip",
    kind: "task",
    owners: [],
    projects: [],
    features: [],
    attrs: {},
    eta: "2026-05-01",
    priority_rank: 0,
    parent_task_id: null,
    note_id: 1,
    ...overrides,
  };
}

describe("tasksToCalendarEvents", () => {
  it("drops items without an eta", () => {
    const events = tasksToCalendarEvents([
      mkTask({ id: 1, title: "Has eta" }),
      mkTask({ id: 2, title: "No eta", eta: null }),
    ]);
    expect(events.map((e) => e.id)).toEqual(["1"]);
  });

  it("drops ARs (kind !== 'task')", () => {
    const events = tasksToCalendarEvents([
      mkTask({ id: 1, title: "Real task", kind: "task" }),
      mkTask({ id: 2, title: "Action item", kind: "ar" }),
      mkTask({ id: 3, title: "Other kind", kind: "note" }),
    ]);
    expect(events.map((e) => e.id)).toEqual(["1"]);
  });

  it("appends '— @owner' when there is exactly one owner", () => {
    const [event] = tasksToCalendarEvents([
      mkTask({ title: "Build pipeline", owners: ["alice"] }),
    ]);
    expect(event.title).toBe("Build pipeline — @alice");
  });

  it("joins multiple owners with comma+space", () => {
    const [event] = tasksToCalendarEvents([
      mkTask({ title: "Code review", owners: ["alice", "bob", "carol"] }),
    ]);
    expect(event.title).toBe("Code review — @alice, @bob, @carol");
  });

  it("omits the suffix entirely when there are no owners", () => {
    const [event] = tasksToCalendarEvents([
      mkTask({ title: "Solo task", owners: [] }),
    ]);
    expect(event.title).toBe("Solo task");
  });

  it("ignores empty / whitespace-only owner strings", () => {
    const [event] = tasksToCalendarEvents([
      mkTask({ title: "Padded", owners: ["", "  ", "alice"] }),
    ]);
    expect(event.title).toBe("Padded — @alice");
  });

  it("uses the muted color for done tasks and the active color otherwise", () => {
    const events = tasksToCalendarEvents([
      mkTask({ id: 1, status: "done" }),
      mkTask({ id: 2, status: "wip" }),
      mkTask({ id: 3, status: "todo" }),
    ]);
    expect(events[0].color).toBe("#9ca3af");
    expect(events[1].color).toBe("#0284c7");
    expect(events[2].color).toBe("#0284c7");
  });

  it("preserves task id and eta verbatim", () => {
    const [event] = tasksToCalendarEvents([
      mkTask({ id: 42, eta: "2026-06-15" }),
    ]);
    expect(event.id).toBe("42");
    expect(event.date).toBe("2026-06-15");
  });

  it("returns an empty array for empty input", () => {
    expect(tasksToCalendarEvents([])).toEqual([]);
  });

  it("handles owners being undefined defensively", () => {
    const [event] = tasksToCalendarEvents([
      mkTask({ title: "Defensive", owners: undefined as unknown as string[] }),
    ]);
    expect(event.title).toBe("Defensive");
  });
});
