import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useUI } from "../../store/ui";

/**
 * Saved-view dropdown driven by `User.saved_views_json`. Each view is a
 * named `string[]` of DSL chips. Apply replaces the current chip set;
 * "★ Save" prompts for a name and persists the current chip set.
 */
export function SavedViews() {
  const where = useUI((s) => s.filters.where ?? []);
  const setChips = useUI((s) => s.setChips);
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);

  const { data: views } = useQuery({
    queryKey: ["me", "views"],
    queryFn: api.savedViews,
    staleTime: 30_000,
  });
  const named = views ?? {};
  const names = Object.keys(named).sort();

  async function save() {
    const name = window.prompt("Save current filter as view (name):");
    if (!name) return;
    setBusy(true);
    try {
      const next = { ...named, [name]: [...where] };
      await api.saveViews(next);
      qc.setQueryData(["me", "views"], next);
    } finally { setBusy(false); }
  }

  async function remove(name: string) {
    if (!window.confirm(`Delete saved view "${name}"?`)) return;
    setBusy(true);
    try {
      const next = { ...named };
      delete next[name];
      await api.saveViews(next);
      qc.setQueryData(["me", "views"], next);
    } finally { setBusy(false); }
  }

  return (
    <div className="flex items-center gap-1">
      <select
        className="rounded border px-2 py-1 text-sm"
        value=""
        disabled={busy}
        onChange={(e) => {
          const name = e.target.value;
          if (!name) return;
          const view = named[name];
          if (Array.isArray(view)) setChips(view);
          // Reset to placeholder so the same view can be re-applied.
          e.target.value = "";
        }}
      >
        <option value="">★ saved views…</option>
        {names.map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
      <button
        type="button"
        className="text-sm text-slate-500 hover:text-slate-900"
        onClick={save}
        disabled={busy || where.length === 0}
        title={where.length === 0 ? "add chips first" : "save current chips as a named view"}
      >save</button>
      {names.length > 0 && (
        <select
          className="rounded border px-2 py-1 text-sm text-red-500"
          value=""
          disabled={busy}
          onChange={(e) => { if (e.target.value) remove(e.target.value); e.target.value = ""; }}
          title="delete a saved view"
        >
          <option value="">×</option>
          {names.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      )}
    </div>
  );
}
