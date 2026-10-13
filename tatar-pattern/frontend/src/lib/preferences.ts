export type Preferences = { reducedMotion: boolean; libraryView: "tiles" | "rows" };
export const DEFAULT_PREFERENCES: Preferences = { reducedMotion: false, libraryView: "tiles" };
export function loadPreferences(): Preferences { try { return { ...DEFAULT_PREFERENCES, ...JSON.parse(localStorage.getItem("tp-preferences") ?? "{}") }; } catch { return DEFAULT_PREFERENCES; } }
export function savePreferences(value: Preferences) { localStorage.setItem("tp-preferences", JSON.stringify(value)); document.documentElement.dataset.reducedMotion = String(value.reducedMotion); window.dispatchEvent(new Event("tp-preferences-updated")); }
