"use client";
import { useEffect } from "react";
import { readWork } from "@/lib/guest-work";
export function GuestCleanup() {
  useEffect(() => {
    try {
    for (const storage of [localStorage, sessionStorage]) {
      for (const key of Object.keys(storage)) {
        if (/^tp-(ai-attempt:|flat-pending:|library-view$|session$)/.test(key) || key === "tp-preferences") storage.removeItem(key);
      }
    }
    readWork();
    } catch { /* Creating work will explain unavailable tab storage before POST. */ }
    // HttpOnly tp_session is expired by the real backend, not by document.cookie.
  }, []);
  return null;
}
