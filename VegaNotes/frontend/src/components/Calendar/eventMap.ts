import type { Task } from "../../api/client";

export interface CalendarEvent {
  id: string;
  title: string;
  date: string;
  color: string;
}

/**
 * Map the `tasks` API payload to FullCalendar event objects.
 *
 * Behavior (per issue #160):
 *   - Skip items without an `eta`.
 *   - Skip ARs (`kind !== "task"`); ARs live under their parent task and
 *     would otherwise clutter the month grid.
 *   - Append the owner list to the title as `Title — @owner1, @owner2`.
 *     Unowned tasks render with no suffix.
 *   - Done tasks get a muted color so they don't draw the eye.
 */
export function tasksToCalendarEvents(tasks: Task[]): CalendarEvent[] {
  return tasks
    .filter((t) => !!t.eta && t.kind === "task")
    .map((t) => {
      const owners = (t.owners ?? []).filter((o) => !!o && o.trim().length > 0);
      const ownerSuffix = owners.length
        ? " — " + owners.map((o) => `@${o}`).join(", ")
        : "";
      return {
        id: String(t.id),
        title: `${t.title}${ownerSuffix}`,
        date: t.eta!,
        color: t.status === "done" ? "#9ca3af" : "#0284c7",
      };
    });
}
