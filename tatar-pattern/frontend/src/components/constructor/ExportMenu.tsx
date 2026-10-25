"use client";
import { useEffect, useRef, useState } from "react";
import { apiUrl, exportUrl, ApiError, apiMessage, type GuestGeneration as Generation } from "@/lib/api";
import { blockWork } from "@/lib/guest-work";
export function ExportMenu({ patternId, formats, generation, onClose }: { generation?: Generation | null; patternId: string; formats: ("png" | "jpg")[]; transparent?: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const busy = useRef(false);
  const [pending,setPending] = useState(false);
  const [error,setError] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  async function download(format: "png" | "jpg", module = false) {
    if(busy.current) return;busy.current=true;setPending(true);setError("");
    try {
      if(!generation || Date.parse(generation.expiresAt) <= Date.now()) throw new ApiError("GUEST_ACCESS_EXPIRED","Срок доступа истёк.");
      const url = module ? apiUrl(`/api/guest/generations/${encodeURIComponent(patternId)}/file?format=png&artifact=module&download=true`) : exportUrl(patternId,format);
      const response = await fetch(url,{credentials:"include",cache:"no-store",referrerPolicy:"no-referrer"});
      if(!response.ok) {const data=await response.json().catch(() => null);throw new ApiError(data?.error?.code ?? "FILE_UNAVAILABLE",data?.error?.message ?? "Файл недоступен.",response.status);}
      const blob = await response.blob();const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");anchor.href=objectUrl;anchor.download=`tatar-pattern-${patternId}${module ? "-module" : ""}.${format}`;
      document.body.append(anchor);anchor.click();anchor.remove();setTimeout(() => URL.revokeObjectURL(objectUrl),1000);
    } catch(e) {blockWork(e);setError(apiMessage(e));} finally {busy.current=false;setPending(false);}
  }
  return <dialog ref={dialog} aria-labelledby="export-heading" onCancel={onClose} className="m-auto w-[min(90vw,380px)] rounded-3xl bg-[#f1eff0] p-7 backdrop:bg-black/40">
    <h2 id="export-heading" className="font-display text-2xl italic">Экспорт изображения</h2>
    {generation?.moduleUrl ? <button disabled={pending} className="studio-button mb-4" onClick={() => download("png",true)}>Скачать модуль PNG{generation.repeat?.periodPx ? ` · ${generation.repeat.periodPx.join(" × ")} px` : ""}</button> : null}
    <div className="flex gap-3">{formats.map(format => <button key={format} disabled={pending} onClick={() => download(format)} className="pressable rounded-full bg-white px-7 py-3 font-semibold">{format.toUpperCase()}</button>)}</div>
    {error ? <p role="alert" className="api-error">{error}</p> : null}
    <button onClick={onClose} className="mt-5 p-2 text-sm underline">Закрыть</button>
  </dialog>;
}
