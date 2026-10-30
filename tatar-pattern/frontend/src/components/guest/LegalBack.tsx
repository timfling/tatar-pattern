"use client";

import { useRouter } from "next/navigation";

export function LegalBack() {
  const router = useRouter();
  return <button type="button" onClick={() => {
    if (window.history.length > 1) router.back();
    else router.replace("/");
  }}>← Назад</button>;
}
