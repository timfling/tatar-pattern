"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import { hasCreatedInTab } from "@/lib/guest-work";

function subscribe(update: () => void) {
  window.addEventListener("tp-created-in-tab", update);
  return () => window.removeEventListener("tp-created-in-tab", update);
}

export function CreateNotice() {
  const created = useSyncExternalStore(subscribe, hasCreatedInTab, () => true);
  if (created) return null;
  return <div className="api-notice mt-auto">
    <p>Нажимая кнопку создания, вы принимаете <Link className="underline" href="/legal/terms">правила использования</Link>. Результаты — только для личного некоммерческого использования.</p>
    <Link className="underline" href="/legal/privacy">Политика обработки персональных данных</Link>
  </div>;
}
