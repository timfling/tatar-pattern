"use client";

import { useEffect, useState } from "react";
import { loadUser } from "@/lib/auth";

export function useStudioHref() {
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    let active = true;
    loadUser().then((user) => { if (active) setAuthed(Boolean(user)); }).catch(() => {});
    return () => { active = false; };
  }, []);

  return {
    authed,
    href: authed ? "/constructor" : "/login",
  };
}
