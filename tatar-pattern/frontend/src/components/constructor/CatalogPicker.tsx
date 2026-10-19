"use client";
/* eslint-disable @next/next/no-img-element -- Cookie-protected server files and local avatar data URLs use native images. */
import { useEffect, useRef, useState } from "react";
import { ROLE_LABELS } from "@/components/constructor/CompositionPicker";
import { motifPresets } from "@/lib/motif-presets";
import { apiUrl, type Element, type CompositionScheme, type PilotRecipe } from "@/lib/api";

export function CatalogPicker({ items, value, max, composition, pilotRecipe, scheme, roleLabels, onChange, onClose }: {
  items: Element[]; value: string[]; max: number; composition?: string | null; pilotRecipe?: PilotRecipe;
  scheme?: CompositionScheme; roleLabels?: Record<string,string>;
  onChange: (value: string[]) => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [expanded, setExpanded] = useState(true);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  const presets = motifPresets(items, max);
  const activePreset = presets.find(p => p.elements.length === value.length && p.elements.every(item => value.includes(item.code)));
  const categories = [...new Set(items.map((item) => item.motifClass))];
  const visible = items.filter((item) => (!category || item.motifClass === category) && `${item.nameRu} ${item.code}`.toLocaleLowerCase("ru").includes(search.toLocaleLowerCase("ru")));
  return <dialog ref={dialog} aria-labelledby="catalog-heading" onCancel={onClose} onClick={e => { if(e.target === e.currentTarget) onClose(); }} className="studio-dialog">
    <div className="flex items-center justify-between gap-3"><h2 id="catalog-heading" className="font-display text-3xl italic">Мотивы из каталога</h2><button onClick={onClose} className="rounded-full bg-white px-4 py-3">Готово</button></div>
    <p className="my-3 text-sm" role="status">Выбрано {value.length} из {max}. В каталоге {items.length} элементов. Категории и названия получены от сервера.</p>
    {pilotRecipe ? <div className="mb-4 rounded-2xl bg-white/70 p-4 text-sm leading-relaxed"><p>Текущая согласованная схема использует {pilotRecipe.codes.join(", ")}. Другие семейства — рекомендации ревизии; для произвольного набора выберите прежний генератор.</p><button className="studio-button mt-3" onClick={() => onChange(pilotRecipe.codes)}>Выбрать набор текущей схемы</button></div> : null}
    {scheme ? <div className="mb-4 rounded-2xl bg-white/70 p-4 text-sm"><p>{scheme.titleRu} · выберите от {scheme.minimumSelected} до {scheme.maximumSelected} элементов. Разрешённые коды не гарантируют размещение любого сочетания.</p><p className="mt-2">Предложенный набор: {scheme.defaultElementCodes.join(", ")}. Применить его и исходные цвета можно в выборе композиции.</p>{value.filter(c => !scheme.allowedElementCodes.includes(c)).map(c => <p key={c}>{c}: вне поддержки схемы; выбор сохранён, можно убрать вручную.</p>)}</div> : null}
    {!scheme ? <details className="mb-4"><summary className="mb-3 cursor-pointer text-sm font-semibold">Семейства из серверной ревизии · {presets.length}</summary>
    <div className="mb-4 grid max-h-64 gap-3 overflow-y-auto sm:grid-cols-3">{presets.map(preset => <button key={preset.id} aria-pressed={activePreset?.id === preset.id} onClick={() => onChange(preset.elements.map(item => item.code))} className={`parameter-choice rounded-2xl border p-4 text-left ${activePreset?.id === preset.id ? "border-[#356052] bg-[#356052]/10" : "border-hairline/40 bg-white"}`}><span className="block font-semibold">{preset.name}</span><span className="mt-2 block text-xs leading-relaxed">{preset.text}</span><span className="mt-3 flex gap-2">{preset.elements.map(item =>  <img key={item.code} src={apiUrl(item.imageUrl)} alt="" className="size-10 rounded-lg object-contain" />)}</span></button>)}</div>
    </details> : null}
    <p className="mb-3 text-sm">{activePreset ? `Набор: ${activePreset.name}` : value.length ? "Пользовательский набор" : "Выберите набор или соберите свой"}</p>
    <button className="studio-button mb-4" onClick={() => setExpanded(v => !v)} aria-expanded={expanded}>{expanded ? "Свернуть каталог" : `Все ${items.length} мотивов · собрать свой набор`}</button>
    {expanded ? <><div className="mb-4 flex flex-wrap gap-3"><label className="flex flex-col gap-1 text-sm">Категория<select className="rounded-xl bg-white p-3" value={category} onChange={(e) => setCategory(e.target.value)}><option value="">Все категории</option>{categories.map((name) => <option key={name}>{name}</option>)}</select></label>
      <label className="flex flex-1 flex-col gap-1 text-sm">Поиск<input className="min-w-0 rounded-xl bg-white p-3" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Название или код" /></label></div>
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">{visible.map((item) => {
      const selected = value.includes(item.code);
      return <button key={item.code} aria-pressed={selected} disabled={!selected && (value.length >= Math.min(max, scheme?.maximumSelected ?? max) || Boolean(scheme && (!scheme.allowedElementCodes.includes(item.code) || !scheme.availableElementCodes.includes(item.code))))} onClick={() => onChange(selected ? value.filter((code) => code !== item.code) : [...value, item.code])} className={`rounded-2xl border-2 bg-white p-3 text-left disabled:opacity-40 ${selected ? "border-[#356052]" : "border-transparent"}`}>
        {/* API file uses session cookies; direct img preserves them. */}
        {}
        <img src={apiUrl(item.imageUrl)} loading="lazy" alt="" className="mb-2 aspect-square w-full object-contain" />
        <span title={item.nameRu} className="block text-sm font-semibold">{item.nameRu}</span><span className="block text-xs">{item.motifClass} · {item.code}</span>
        <span className="mt-1 block text-xs text-[#666]">{item.isFixture ? "Тестовый элемент" : "Элемент каталога"}{item.artifactCode ? ` · Источник ${item.artifactCode}` : ""}</span>
        {scheme ? <span className="mt-2 block text-xs">{(scheme.roleOptions[item.code] ?? []).map(r => roleLabels?.[r] ?? r).join(" / ") || "Вне поддержки схемы"}</span> : null}
        {composition ? <span className="mt-2 block text-xs leading-relaxed">
          {pilotRecipe?.codes.includes(item.code) ? `Роль в схеме: ${ROLE_LABELS[pilotRecipe.roles[item.code]] ?? pilotRecipe.roles[item.code]}` : item.compositionMetadata?.usage[composition]?.state === "uncertain" || !item.compositionMetadata?.usage[composition] ? "Нет рекомендации для этой роли. Это не культурный запрет." : item.compositionMetadata.usage[composition].reason}
        </span> : null}
      </button>;
    })}</div>
    {!visible.length ? <p className="py-8 text-center">По этому запросу элементов нет.</p> : null}
    </> : null}
    {value.length ? <div className="my-4 rounded-2xl bg-white/70 p-4 text-sm leading-relaxed"><h3 className="font-semibold">Рекомендации для выбранных мотивов</h3>{value.map(code => { const item = items.find(item => item.code === code); const meta = item?.compositionMetadata; const usage = composition ? meta?.usage[composition] : undefined; return <div key={code} className="mt-3"><p>{code} · {usage?.state === "uncertain" || !usage ? "Нет подтверждённой рекомендации для роли. Это не культурный запрет. " : ""}{usage?.reason}</p>{meta?.readability?.recommended_min_long_side_px ? <p className="text-xs text-ink-muted">Ориентир детализации: длинная сторона от {meta.readability.recommended_min_long_side_px} px; проверьте конечный размер.</p> : null}{meta?.transforms?.rotation?.conditions?.length ? <details className="mt-1 text-xs"><summary>Преобразования</summary>{meta.transforms.rotation.conditions.map(condition => <p key={condition}>{condition}</p>)}<p>Отражение автоматически не применяется.</p></details> : null}</div>; })}</div> : null}
    <p className="mt-4 text-xs">Исходный мотив и его источник сохраняются в рецепте. Новый вариант ИИ не является подтверждённой исторической реконструкцией.</p>
  </dialog>;
}
