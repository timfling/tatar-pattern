"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Icon } from "@/components/ui/Icon";
import { recipeLines } from "@/components/constructor/parameters";
import type { ParameterTile, ConstructorSelections } from "@/components/constructor/parameters";
import type { Evidence, GuestGeneration as Generation } from "@/lib/api";
function Sources({ evidence }: { evidence?: Evidence[] }) {
  return evidence?.length ? <ul className="mt-3 space-y-3 text-xs leading-relaxed">{evidence.map((source,index) => {
    const label = source.title_ru ?? source.title ?? source.id ?? "Основание";
    const url = source.url && /^https?:\/\//i.test(source.url) ? source.url : null;
    return <li key={index}>{source.author ? `${source.author}. ` : ""}{url ? <a className="underline" href={url} target="_blank" rel="noopener noreferrer">{label.replace(/TP-E-\d+/g,"Мотив")}</a> : label.replace(/TP-E-\d+/g,"Мотив")}{source.locator ? ` · ${source.locator}` : ""}{source.basis ? <p>{typeof source.basis === "string" ? source.basis : source.basis.context ?? source.basis.geometry}</p> : null}</li>;
  })}</ul> : null;
}
export function GenerationInfo({ selections, prompt, compact = false, tiles, details = [], generation }: {
  selections: ConstructorSelections; prompt: string; compact?: boolean; tiles?: ParameterTile[];
  details?: { title: string; value: string }[]; generation?: Generation | null;
}) {
  const [open, setOpen] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => { if(open) dialog.current?.showModal(); }, [open]);
  function close() { dialog.current?.close(); setOpen(false); const visibleTrigger = trigger.current?.getClientRects().length ? trigger.current : Array.from(document.querySelectorAll<HTMLButtonElement>('button[aria-label="О генерации"]')).find(button => button.getClientRects().length);
    visibleTrigger?.focus({preventScroll:true}); }
  const savedScheme = generation?.recipe?.schemeDefinition as { titleRu?: string; roleLabelsRu?: Record<string,string> } | undefined;
  const savedRoles = generation?.recipe?.roles as Record<string,string> | undefined;
  const motifOptions=tiles?.find(tile=>tile.key === "motifs")?.options ?? [];
  const motifName=(code:string)=>motifOptions.find(option=>option.value === code)?.label ?? "Мотив";
  const readable=(value:string)=>value.replace(/TP-E-\d+/g,motifName);
  const lines = [...(generation?.ai ? [] : recipeLines(selections,prompt,tiles)),...details];
  const requested = generation?.mode === "ai" || generation?.descriptionDetails?.basis === "requested_only";
  const note = requested ? null : generation?.culturalNote;
  const text = generation?.description ?? generation?.descriptionDetails?.text;
  return <div className="relative">
    <button ref={trigger} type="button" aria-label="О генерации" aria-haspopup="dialog" aria-expanded={open} onClick={() => setOpen(true)} className="pressable-icon"><Icon name={compact ? "info-sm" : "info"} width={compact ? 32 : 52} height={compact ? 32 : 52} /></button>
    {open ? createPortal(<dialog ref={dialog} aria-labelledby="generation-info-heading" className="studio-dialog generation-info" onCancel={e => {e.preventDefault();close();}} onClick={e => {if(e.target === e.currentTarget) close();}}>
      <header className="mb-5 flex items-start justify-between gap-4"><h2 id="generation-info-heading" className="text-2xl font-semibold">{requested ? "О задании для ИИ" : "О рисунке"}</h2><button autoFocus onClick={close} className="studio-button">Закрыть</button></header>
      <p className="text-base leading-relaxed">{(text ? readable(text) : null) || (requested ? "Сохранено задание для ИИ. Содержание итогового изображения не проверено; параметры доступны в рецепте ниже." : "Для этой работы серверное описание недоступно. Ниже показан сохранённый рецепт.")}</p>
      {requested ? <p className="mt-3 text-sm leading-relaxed text-ink-muted">Выбор мотивов и параметров не подтверждает их наличие, цвета или бесшовность итогового изображения.</p> : generation?.descriptionDetails?.basis === "legacy_recipe" ? <p className="mt-3 text-xs leading-relaxed text-ink-muted">Описание восстановлено сервером по старому рецепту; культурная справка отсутствует.</p> : null}
      {note?.text ? <section className="mt-5 border-t border-hairline/40 pt-4"><h3 className="font-semibold">{note.claimType === "single_object_visual_observation" ? "Контекст источника" : "Культурный контекст"}</h3><p className="mt-2 text-sm leading-relaxed">{note.text}</p><details className="mt-3 text-xs"><summary className="cursor-pointer">Основания и источники</summary><Sources evidence={note.evidence} /></details></section> : null}
      <p className="mt-4 text-xs leading-relaxed text-ink-muted">Совет по применению — ориентир для макета. Он не подтверждает права на материалы или пригодность для производства.</p>
      {generation?.compatibility?.reasons?.length ? <details className="mt-5 text-sm"><summary className="cursor-pointer font-semibold">Рекомендации и ограничения</summary><div className="mt-3 space-y-3">{generation.compatibility.reasons.map((reason,index) => <p key={index} className={`rounded-xl p-3 leading-relaxed ${reason.severity === "prohibition" ? "bg-red-50" : reason.severity === "recommendation" ? "bg-amber-50" : "bg-white/60"}`}><strong>{reason.severity === "prohibition" ? "Ограничение" : reason.severity === "recommendation" ? "Рекомендация" : "Нет подтверждённой рекомендации"}: </strong>{reason.message}</p>)}</div></details> : null}
      <h3 className="mb-4 mt-6 border-t border-hairline/40 pt-4 font-semibold">{requested ? "Параметры задания и выбранные мотивы" : "Рецепт и мотивы"}</h3>
      {savedScheme && !requested ? <section className="mb-4 text-sm leading-relaxed"><h4 className="font-semibold">Сохранённая схема: {savedScheme.titleRu ?? "Выбранная композиция"}</h4>{savedRoles ? Object.entries(savedRoles).map(([code,role]) => <p key={code}>{motifName(code)}: {savedScheme.roleLabelsRu?.[role] ?? ({center:"Центр",primary:"Главный мотив",support:"Вспомогательный мотив",branch:"Направленная ветвь",leaf:"Листовой акцент",frame:"Рамочный фрагмент",pendant:"Подвесная форма"} as Record<string,string>)[role] ?? role}</p>) : null}<p>Главный мотив: {generation?.recipe?.primaryElementCode ? motifName(String(generation.recipe.primaryElementCode)) : "не указан"}</p></section> : null}
      <dl className="flex flex-col gap-4">{lines.map(line => <div key={line.title}><dt className="text-sm text-ink-muted">{line.title}</dt><dd className="mt-1 whitespace-pre-line text-base leading-relaxed">{line.title === "Мотивы" && line.value !== "не выбраны" ? <ol className="list-decimal space-y-2 pl-5">{line.value.split("\n").map((name,index) => <li key={index}>{name}</li>)}</ol> : line.value}</dd></div>)}</dl>
      {generation ? <details className="mt-5 text-xs leading-relaxed"><summary className="cursor-pointer font-semibold">Основания и подробности</summary><p className="mt-3">Описание: {generation.descriptionDetails?.basis === "saved_recipe" ? "факты сохранённого рецепта" : requested ? "задание для ИИ" : "старый рецепт"} · {generation.descriptionDetails?.templateVersion ?? "версия не указана"}</p><Sources evidence={generation.descriptionDetails?.evidence} /><p className="mt-3">Выбрано: {generation.selections?.elementCodes?.map(motifName).join(", ") || generation.selections?.motifs?.join(", ") || (generation.ai ? "Мотивы закреплённой основы" : "не указано")}</p><p>Использовано: {requested ? "не подтверждено" : Array.isArray(generation.recipe?.usedElementCodes) ? generation.recipe.usedElementCodes.map(motifName).join(", ") : "см. сохранённые элементы рецепта"}</p>{Array.isArray(generation.recipe?.modernAdditions) && generation.recipe.modernAdditions.length ? <p className="mt-3">Современные композиционные добавления:</p> : null}{Array.isArray(generation.recipe?.modernAdditions) ? <ul className="mt-2 space-y-2">{generation.recipe.modernAdditions.map((addition: {kind?:string;purpose?:string},index:number) => <li key={index}>{addition.kind === "wave_guide" ? "Волнообразная направляющая ритма, не восстановленный стебель" : addition.kind === "horizontal_border_rules" ? "Тонкие линии обрамления" : "Направляющая композиции"}. Современное дизайнерское добавление.</li>)}</ul> : null}</details> : null}
    </dialog>, document.body) : null}
  </div>;
}
