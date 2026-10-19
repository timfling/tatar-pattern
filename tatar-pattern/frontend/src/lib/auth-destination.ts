"use client";
import { useEffect, useState } from "react";
export function authDestination() {
  const value = new URLSearchParams(window.location.search).get("next") ?? "/constructor";
  return /^\/(?:flat|constructor|library|profile|settings|help|trash|about-pattern|rules)(?:\?|$)/.test(value) ? value : "/constructor";
}
export function useAuthDestination() {
  const [destination,setDestination] = useState("/constructor");
  useEffect(() => {queueMicrotask(() => setDestination(authDestination()));},[]);
  return {destination,authQuery:`?next=${encodeURIComponent(destination)}`};
}
