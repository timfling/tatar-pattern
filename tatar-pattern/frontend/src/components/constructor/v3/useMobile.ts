"use client";
import { useSyncExternalStore } from "react";

const QUERY = "(max-width: 767px)";
function subscribe(update: () => void) {
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", update);
  return () => media.removeEventListener("change", update);
}
/** Тот же порог, что у Tailwind md и у --ui-scale в globals.css. */
export function useMobile() {
  return useSyncExternalStore(subscribe, () => window.matchMedia(QUERY).matches, () => false);
}

export function useReducedMotion() {
  return useSyncExternalStore(
    update => { const m = window.matchMedia("(prefers-reduced-motion: reduce)"); m.addEventListener("change", update); return () => m.removeEventListener("change", update); },
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}
