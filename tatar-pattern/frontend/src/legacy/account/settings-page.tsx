"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { loadPreferences, savePreferences, DEFAULT_PREFERENCES } from "@/lib/preferences";
export default function Page() {
  const [value,setValue] = useState(DEFAULT_PREFERENCES);
  // Browser preferences are read only after hydration.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setValue(loadPreferences()), []);
  function update(next: typeof value) { setValue(next); savePreferences(next); }
  return <section className="studio-page"><div className="studio-article"><h1>Настройки конструктора</h1><p>Параметры интерфейса сохраняются в этом браузере.</p><section className="flex flex-col gap-6"><label className="flex gap-3"><input type="checkbox" checked={value.reducedMotion} onChange={e => update({ ...value, reducedMotion: e.target.checked })} />Уменьшить анимации</label><label className="flex flex-wrap gap-3">Вид библиотеки по умолчанию<select value={value.libraryView} onChange={e => update({ ...value, libraryView: e.target.value as "tiles" | "rows" })} className="rounded-xl bg-white p-2"><option value="tiles">Плитка</option><option value="rows">Строки</option></select></label></section><Link className="studio-button" href="/profile">Аккаунт ↗</Link></div></section>;
}
