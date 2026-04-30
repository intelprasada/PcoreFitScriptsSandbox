import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { tasksToCalendarEvents } from "./eventMap";

export function CalendarView() {
  const { data } = useQuery({ queryKey: ["tasks", "all"], queryFn: () => api.tasks({}) });
  const events = tasksToCalendarEvents(data?.tasks ?? []);
  return (
    <div className="p-4">
      <FullCalendar plugins={[dayGridPlugin]} initialView="dayGridMonth" events={events} height="80vh" />
    </div>
  );
}
