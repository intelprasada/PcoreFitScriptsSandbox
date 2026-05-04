import { describe, it, expect, beforeEach } from "vitest";
import { useEditorPrefs } from "../src/store/editorPrefs.ts";

beforeEach(() => {
  useEditorPrefs.setState({ flavor: "classic", vim: false });
  try {
    localStorage.removeItem("vega:editor:v1");
  } catch {
    /* jsdom may not expose localStorage */
  }
});

describe("useEditorPrefs", () => {
  it("defaults to classic with vim off", () => {
    expect(useEditorPrefs.getState().flavor).toBe("classic");
    expect(useEditorPrefs.getState().vim).toBe(false);
  });

  it("setFlavor updates the store", () => {
    useEditorPrefs.getState().setFlavor("cm6");
    expect(useEditorPrefs.getState().flavor).toBe("cm6");
    useEditorPrefs.getState().setFlavor("classic");
    expect(useEditorPrefs.getState().flavor).toBe("classic");
  });

  it("setVim toggles the vim flag", () => {
    useEditorPrefs.getState().setVim(true);
    expect(useEditorPrefs.getState().vim).toBe(true);
    useEditorPrefs.getState().setVim(false);
    expect(useEditorPrefs.getState().vim).toBe(false);
  });

  it("persists the selection to localStorage under vega:editor:v1", () => {
    useEditorPrefs.getState().setFlavor("cm6");
    useEditorPrefs.getState().setVim(true);
    const raw = localStorage.getItem("vega:editor:v1");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    // zustand persist v4 wraps state in { state, version }.
    expect(parsed.state.flavor).toBe("cm6");
    expect(parsed.state.vim).toBe(true);
  });

  it("falls back to classic if persisted flavor is unrecognised", () => {
    // Simulate an old build that wrote a now-removed flavor.
    localStorage.setItem(
      "vega:editor:v1",
      JSON.stringify({ state: { flavor: "lexical", vim: true }, version: 0 }),
    );
    useEditorPrefs.persist.rehydrate();
    expect(useEditorPrefs.getState().flavor).toBe("classic");
    // ...but vim flag survives because it's still a boolean.
    expect(useEditorPrefs.getState().vim).toBe(true);
  });

  it("coerces non-boolean persisted vim values to false", () => {
    localStorage.setItem(
      "vega:editor:v1",
      JSON.stringify({ state: { flavor: "cm6", vim: "yes" }, version: 0 }),
    );
    useEditorPrefs.persist.rehydrate();
    expect(useEditorPrefs.getState().vim).toBe(false);
  });
});
