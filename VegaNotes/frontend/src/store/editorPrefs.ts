import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ALL_FLAVORS, type EditorFlavor } from "../components/Editor/types";

interface EditorPrefsState {
  flavor: EditorFlavor;
  /** Vim keymap on top of CM6 (#168). Off by default; ignored by Classic. */
  vim: boolean;
  setFlavor: (f: EditorFlavor) => void;
  setVim: (v: boolean) => void;
}

function isFlavor(v: unknown): v is EditorFlavor {
  return typeof v === "string" && (ALL_FLAVORS as string[]).includes(v);
}

export const useEditorPrefs = create<EditorPrefsState>()(
  persist(
    (set) => ({
      flavor: "classic",
      vim: false,
      setFlavor: (flavor) => set({ flavor }),
      setVim: (vim) => set({ vim }),
    }),
    {
      name: "vega:editor:v1",
      // Defensive: if a future build removes a flavor, fall back to classic
      // instead of crashing the editor pane on first mount.  Same idea for
      // the vim flag — coerce non-boolean persisted values to false.
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        if (!isFlavor(state.flavor)) state.flavor = "classic";
        if (typeof state.vim !== "boolean") state.vim = false;
      },
    },
  ),
);
