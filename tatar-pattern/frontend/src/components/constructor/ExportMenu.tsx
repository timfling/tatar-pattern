"use client";
import { useEffect, useRef } from "react";
import { apiUrl, exportUrl, type Generation } from "@/lib/api";
export function ExportMenu({ patternId, formats, transparent, generation, onClose }: { generation?: Generation | null; patternId: string; formats: ("png" | "jpg")[]; transparent?: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} aria-labelledby="export-heading" onCancel={onClose} className="m-auto w-[min(90vw,380px)] rounded-3xl bg-[#f1eff0] p-7 backdrop:bg-black/40">
    <h2 id="export-heading" className="font-display text-2xl italic">Экспорт изображения</h2>
    <p className="my-4 text-sm">Скачать сохранённый результат в исходном размере.</p>
    <p className="my-3 text-sm">{generation?.outputKind === "repeat_module" ? "Модуль повтора" : generation?.outputKind === "pattern_sample" ? "Образец узора" : "Изображение"}{generation?.seamless === true ? " · бесшовный" : generation?.seamless === false ? " · без бесшовного стыка краёв" : " · бесшовность не подтверждена"}</p>
    {generation?.moduleUrl ? <a className="studio-button mb-4 inline-block" download href={apiUrl(generation.moduleUrl + (generation.moduleUrl.includes("?") ? "&" : "?") + "download=true")}>Скачать модуль PNG{generation.repeat?.periodPx ? ` · ${generation.repeat.periodPx.join(" × ")} px` : ""}</a> : null}
    {transparent ? <p className="my-3 text-sm">PNG — прозрачный фон. JPG — с цветной подложкой.</p> : null}
    <div className="flex gap-3">{formats.map((format) => <a key={format} href={exportUrl(patternId, format)} download className="pressable rounded-full bg-white px-7 py-3 font-semibold">{format.toUpperCase()}</a>)}</div>
    <button onClick={onClose} className="mt-5 p-2 text-sm underline">Закрыть</button>
  </dialog>;
}
