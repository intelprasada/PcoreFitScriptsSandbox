/**
 * Inline "+ New task" composer used by the Kanban board (per-column) and
 * by My Tasks (per-group).  See issue #63.
 *
 * UX:
 *   - Single-line title input, autofocused.
 *   - Optional row with priority + ETA + project (shown when no project
 *     filter is active).
 *   - Enter = Create, Esc = Cancel, Shift+Enter = newline.
 *   - After successful create, title is cleared but the composer stays open
 *     so the user can keep typing.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

interface Props {
  /** Status to assign to the created task (column / group context). */
  defaultStatus?: string;
  /** Project (folder) name; if unset, the composer shows a project picker. */
  defaultProject?: string;
  /** Priority to prefill (used when launched from a "by priority" group). */
  defaultPriority?: string;
  /** Closing the composer (Esc, click-away, Cancel button). */
  onClose: () => void;
  /** Compact mode for use inside narrow columns. */
  compact?: boolean;
}

export function NewTaskComposer({
  defaultStatus = "todo",
  defaultProject,
  defaultPriority,
  onClose,
  compact = false,
}: Props) {
  const qc = useQueryClient();
  const [title, setTitle]       = useState("");
  const [priority, setPriority] = useState(defaultPriority ?? "");
  const [eta, setEta]           = useState("");
  const [project, setProject]   = useState(defaultProject ?? "");
  const [error, setError]       = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Project list — only loaded when the user needs to pick one.
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.projects(),
    enabled: !defaultProject,
  });

  useEffect(() => { inputRef.current?.focus(); }, []);

  const createMut = useMutation({
    mutationFn: () =>
      api.createTask({
        title: title.trim(),
        status: defaultStatus,
        project: project || undefined,
        priority: priority || undefined,
        eta: eta || undefined,
      }),
    onSuccess: () => {
      // Refresh every list that might surface the new card.
      qc.invalidateQueries({ queryKey: ["tasks"] });
      qc.invalidateQueries({ queryKey: ["my-tasks"] });
      qc.invalidateQueries({ queryKey: ["agenda"] });
      qc.invalidateQueries({ queryKey: ["note"] });
      qc.invalidateQueries({ queryKey: ["tree"] });
      // Stay open with title cleared for fast batch capture.
      setTitle("");
      setError(null);
      inputRef.current?.focus();
    },
    onError: (e: any) => {
      setError(e?.message ?? "create failed");
    },
  });

  const submit = () => {
    setError(null);
    if (!title.trim()) return;
    if (!defaultProject && !project) {
      setError("pick a project (or open a project to create here)");
      return;
    }
    createMut.mutate();
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    } else if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div
      className={`rounded-md border border-sky-300 bg-white shadow-sm ${compact ? "p-2" : "p-3"} space-y-1.5`}
      onClick={(e) => e.stopPropagation()}
    >
      <input
        ref={inputRef}
        type="text"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        onKeyDown={handleKey}
        placeholder="New task title…"
        className="w-full text-sm px-2 py-1 border border-slate-200 rounded focus:outline-none focus:border-sky-400"
        disabled={createMut.isPending}
      />

      <div className="flex flex-wrap items-center gap-1.5">
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          className="text-[11px] px-1.5 py-0.5 border border-slate-200 rounded bg-white"
          title="Priority"
        >
          <option value="">priority…</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
        </select>
        <input
          type="text"
          value={eta}
          onChange={(e) => setEta(e.target.value)}
          onKeyDown={handleKey}
          placeholder="eta (e.g. ww18 or 2026-05-01)"
          className="text-[11px] px-1.5 py-0.5 border border-slate-200 rounded flex-1 min-w-[140px]"
        />
        {!defaultProject && (
          <select
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className="text-[11px] px-1.5 py-0.5 border border-slate-200 rounded bg-white"
            title="Destination project"
          >
            <option value="">project…</option>
            {(projects ?? []).map((p) => (
              <option key={p.name} value={p.name}>{p.name}</option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <div className="text-[11px] text-rose-600">{error}</div>
      )}

      <div className="flex items-center gap-2 pt-0.5">
        <button
          onClick={submit}
          disabled={createMut.isPending || !title.trim()}
          className="text-xs px-2 py-0.5 bg-sky-600 text-white rounded hover:bg-sky-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {createMut.isPending ? "Creating…" : "Create"}
        </button>
        <button
          onClick={onClose}
          className="text-xs px-2 py-0.5 text-slate-500 hover:text-slate-700"
        >
          Cancel
        </button>
        <span className="ml-auto text-[10px] text-slate-400">⏎ create · Esc close</span>
      </div>
    </div>
  );
}
