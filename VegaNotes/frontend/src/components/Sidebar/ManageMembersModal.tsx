import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type ProjectMember } from "../../api/client";

interface Props {
  project: string;
  onClose: () => void;
}

/**
 * Modal for managers/admins to view/add/remove project members.
 * Lists current members with role toggles + remove, plus an "add" form
 * backed by the user-list autocomplete.
 */
export function ManageMembersModal({ project, onClose }: Props) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [role, setRole] = useState<"member" | "manager">("member");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const { data: members = [], isLoading } = useQuery<ProjectMember[]>({
    queryKey: ["projectMembers", project],
    queryFn: () => api.projectMembers(project),
  });

  const { data: allUsers = [] } = useQuery<string[]>({
    queryKey: ["users"],
    queryFn: () => api.users(),
  });

  const onSuccess = () => {
    qc.invalidateQueries({ queryKey: ["projectMembers", project] });
    qc.invalidateQueries({ queryKey: ["tree"] });
    qc.invalidateQueries({ queryKey: ["projects"] });
  };

  const onError = (e: any) => {
    if (e instanceof ApiError) setErr(`${e.status}: ${e.detail}`);
    else setErr(String(e?.message ?? e));
  };

  const addOrUpdate = useMutation({
    mutationFn: (vars: { user_name: string; role: "member" | "manager" }) =>
      api.putProjectMember(project, vars.user_name, vars.role),
    onSuccess: () => {
      setName("");
      setRole("member");
      setErr(null);
      onSuccess();
    },
    onError,
  });

  const remove = useMutation({
    mutationFn: (user_name: string) => api.removeProjectMember(project, user_name),
    onSuccess,
    onError,
  });

  const memberNames = new Set(members.map((m) => m.user_name));
  const candidates = allUsers.filter((u) => !memberNames.has(u));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-[28rem] max-h-[80vh] overflow-y-auto rounded-lg bg-white p-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold">
            Manage members &middot; <span className="text-sky-700">{project}</span>
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 text-lg leading-none"
            title="Close (Esc)"
          >
            ×
          </button>
        </div>

        {err && (
          <div className="mb-3 rounded border border-rose-200 bg-rose-50 px-2 py-1 text-xs text-rose-700">
            {err}
          </div>
        )}

        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-slate-500 mb-1">
            Current members ({members.length})
          </h3>
          {isLoading ? (
            <div className="text-xs text-slate-400">Loading…</div>
          ) : members.length === 0 ? (
            <div className="text-xs italic text-slate-400">
              No members yet. Add one below.
            </div>
          ) : (
            <ul className="divide-y rounded border">
              {members.map((m) => (
                <li
                  key={m.user_name}
                  className="flex items-center justify-between gap-2 px-2 py-1.5 text-xs"
                >
                  <span className="font-mono text-slate-700">{m.user_name}</span>
                  <div className="flex items-center gap-2">
                    <select
                      value={m.role}
                      onChange={(e) =>
                        addOrUpdate.mutate({
                          user_name: m.user_name,
                          role: e.target.value as "member" | "manager",
                        })
                      }
                      disabled={addOrUpdate.isPending}
                      className="rounded border px-1 py-0.5 text-xs"
                    >
                      <option value="member">member</option>
                      <option value="manager">manager</option>
                    </select>
                    <button
                      onClick={() => {
                        if (window.confirm(`Remove ${m.user_name} from ${project}?`))
                          remove.mutate(m.user_name);
                      }}
                      disabled={remove.isPending}
                      className="text-rose-600 hover:text-rose-800"
                      title="Remove member"
                    >
                      remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <form
          className="space-y-2"
          onSubmit={(e) => {
            e.preventDefault();
            const n = name.trim();
            if (!n) return;
            addOrUpdate.mutate({ user_name: n, role });
          }}
        >
          <h3 className="text-xs uppercase tracking-wide text-slate-500">Add member</h3>
          <div className="flex gap-2">
            <input
              list="vn-member-candidates"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="username (case-sensitive)"
              className="flex-1 rounded border px-2 py-1 text-xs"
            />
            <datalist id="vn-member-candidates">
              {candidates.map((u) => (
                <option key={u} value={u} />
              ))}
            </datalist>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as "member" | "manager")}
              className="rounded border px-1 py-1 text-xs"
            >
              <option value="member">member</option>
              <option value="manager">manager</option>
            </select>
            <button
              type="submit"
              disabled={addOrUpdate.isPending || !name.trim()}
              className="rounded bg-sky-600 text-white px-3 text-xs disabled:opacity-50"
            >
              add
            </button>
          </div>
          <p className="text-[11px] text-slate-500">
            Tip: existing usernames autocomplete. Names are case-sensitive — use the same
            casing as <code>@mentions</code> in your notes.
          </p>
        </form>
      </div>
    </div>
  );
}
