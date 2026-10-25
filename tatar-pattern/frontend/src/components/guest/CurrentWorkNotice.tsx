"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiMessage } from "@/lib/api";
import { createWork, expiryText, forgetWork, readWork, type CurrentWork } from "@/lib/guest-work";
export function CurrentWorkNotice({ onChange }: { onChange?: (exists: boolean) => void }) {
  const router = useRouter();
  const [work,setWork] = useState<CurrentWork | null>(null);
  const [pending,setPending] = useState(false);
  const [error,setError] = useState("");
  useEffect(() => {
    const update = () => { const current = readWork(); setWork(current); onChange?.(Boolean(current)); };
    update(); window.addEventListener("tp-guest-work",update);
    const timer = setInterval(update,1000);
    return () => {window.removeEventListener("tp-guest-work",update);clearInterval(timer);};
  },[onChange]);
  async function resume() {
    if(pending) return;setPending(true);setError("");
    try { const g = await createWork(); router.push(`/constructor?pattern=${encodeURIComponent(g.id)}`); }
    catch(e) {setError(apiMessage(e));} finally {setPending(false);}
  }
  if (!work && !error) return null;
  return <div className="my-3 text-center text-sm">
    {work ? <><p>Только текущая работа. Доступ до {expiryText(work.expiresAt)}.</p><p>{work.blocked ? "Доступ утрачен. Повторная отправка заблокирована." : work.id ? "Можно открыть текущий результат без нового создания." : "Сохранена попытка. Проверка повторит тот же запрос; новая задача с другим UUID автоматически не создаётся."}</p><div className="my-2 flex flex-wrap justify-center gap-3"><button className="studio-button" disabled={pending || work.blocked} onClick={resume}>{pending ? "Проверяем…" : "Открыть текущую попытку"}</button><button className="studio-button" disabled={pending} onClick={() => {forgetWork();setError("");}}>Подготовить новую работу</button></div><p>Новая работа заменит текущую в этой вкладке. Это не отменяет уже отправленное вычисление.</p></> : null}
    {error ? <p role="alert">{error}</p> : null}
  </div>;
}
