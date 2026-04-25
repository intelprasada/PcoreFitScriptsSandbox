import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../api/client";
import { useUI } from "../../store/ui";
import { DSLError, parseClause, renderClause } from "../../store/dsl";

/**
 * Free-form chip input for the FilterBar. Type a DSL clause and press
 * Enter to add a chip; Backspace at empty input removes the last chip;
 * `×` on a chip removes it. Typing `@` (or starting with one) opens an
 * autocomplete listing distinct TaskAttr keys with a couple of sample
 * values each — fed by `GET /api/attrs`.
 */
export function ChipBar() {
  const where = useUI((s) => s.filters.where ?? []);
  const addChip = useUI((s) => s.addChip);
  const removeChip = useUI((s) => s.removeChip);

  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const { data: attrs } = useQuery({
    queryKey: ["attrs"],
    queryFn: api.attrs,
    staleTime: 60_000,
  });

  // Autocomplete is only shown while the cursor is inside an `@` token.
  const ac = useMemo(() => deriveAutocomplete(input, attrs ?? []), [input, attrs]);

  function commit(text: string) {
    const t = text.trim();
    if (!t) return;
    try {
      const c = parseClause(t);
      addChip(renderClause(c));
      setInput("");
      setError(null);
    } catch (e) {
      setError(e instanceof DSLError ? e.message : String(e));
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      e.preventDefault();
      commit(input);
    } else if (e.key === "Backspace" && input === "" && where.length > 0) {
      removeChip(where.length - 1);
    } else if (e.key === "Escape") {
      setInput("");
      setError(null);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1 flex-1 min-w-[200px] relative">
      {where.map((clause, i) => (
        <span key={`${clause}-${i}`}
          className="inline-flex items-center gap-1 rounded bg-slate-100 px-2 py-0.5 text-xs">
          <code className="font-mono">{clause}</code>
          <button
            type="button"
            aria-label={`remove ${clause}`}
            className="text-slate-400 hover:text-slate-700"
            onClick={() => removeChip(i)}
          >×</button>
        </span>
      ))}
      <input
        ref={inputRef}
        className="rounded border px-2 py-1 text-sm flex-1 min-w-[160px]"
        placeholder='filter… e.g. @area=fit-val  or  eta>=ww18'
        value={input}
        onChange={(e) => { setInput(e.target.value); setError(null); }}
        onKeyDown={onKey}
        title={error ?? undefined}
        aria-invalid={error ? "true" : "false"}
      />
      {ac.suggestions.length > 0 && (
        <ul className="absolute z-20 left-0 top-full mt-1 max-h-60 w-72 overflow-auto rounded border bg-white shadow-lg text-xs">
          {ac.suggestions.map((s) => (
            <li key={s.key}>
              <button
                type="button"
                className="block w-full text-left px-2 py-1 hover:bg-slate-100"
                onClick={() => {
                  // Insert "@key=" into the input and refocus so the
                  // user can type the value.
                  setInput(ac.replacePrefix + "@" + s.key + "=");
                  inputRef.current?.focus();
                }}
              >
                <span className="font-mono">@{s.key}</span>
                <span className="ml-2 text-slate-400">
                  {s.sample_values.slice(0, 3).join(", ")}
                  {s.count > 3 ? `  (+${s.count - 3})` : ""}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </div>
  );
}

interface AcRow { key: string; count: number; sample_values: string[] }
interface AcResult { suggestions: AcRow[]; replacePrefix: string }

/**
 * Decide whether to show the autocomplete dropdown based on the cursor
 * position (we approximate "cursor at end" — good enough for v1).
 */
function deriveAutocomplete(input: string, attrs: AcRow[]): AcResult {
  const at = input.lastIndexOf("@");
  if (at < 0) return { suggestions: [], replacePrefix: "" };
  // Only suggest while the user is still typing the @key fragment
  // (no `=` / op after the @).
  const tail = input.slice(at + 1);
  if (/[=!<>\s]/.test(tail)) return { suggestions: [], replacePrefix: "" };
  const prefix = tail.toLowerCase();
  const matches = attrs
    .filter((a) => a.key.toLowerCase().startsWith(prefix))
    .slice(0, 8);
  return { suggestions: matches, replacePrefix: input.slice(0, at) };
}
