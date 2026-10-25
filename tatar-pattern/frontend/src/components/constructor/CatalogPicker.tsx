"use client";
/* eslint-disable @next/next/no-img-element -- Cookie-protected catalog previews. */
import { useEffect, useRef, useState } from "react";
import { apiUrl, type Element, type CompositionScheme, type PilotRecipe } from "@/lib/api";

export function CatalogPicker({ items, value, max, scheme, onChange, onClose }: {
  items: Element[]; value: string[]; max: number; composition?: string | null; pilotRecipe?: PilotRecipe;
  scheme?: CompositionScheme; roleLabels?: Record<string,string>;
  onChange: (value: string[]) => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  useEffect(() => { dialog.current?.showModal(); }, []);
  const categories = [...new Set(items.map(item => item.motifClass))];
  const visible = items.filter(item => (!category || item.motifClass === category) && `${item.nameRu} ${item.code}`.toLocaleLowerCase("ru").includes(search.toLocaleLowerCase("ru")));
  return <dialog ref={dialog} aria-labelledby="catalog-heading" onCancel={onClose} onClick={e => { if(e.target === e.currentTarget) onClose(); }} className="studio-dialog catalog-picker">
    <header className="picker-heading"><h2 id="catalog-heading">Мотивы из каталога</h2><button onClick={onClose} className="studio-button">Готово</button></header>
    <p className="picker-count" role="status">Выбрано {value.length} / {Math.min(max, scheme?.maximumSelected ?? max)}</p>
    <div className="catalog-filters"><label>Категория<select value={category} onChange={e => setCategory(e.target.value)}><option value="">Все категории</option>{categories.map(name => <option key={name}>{name}</option>)}</select></label><label>Поиск<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Название или код" /></label></div>
    <div className="catalog-items">{visible.map(item => {
      const selected = value.includes(item.code);
      const disabled = !selected && (value.length >= Math.min(max, scheme?.maximumSelected ?? max) || Boolean(scheme && (!scheme.allowedElementCodes.includes(item.code) || !scheme.availableElementCodes.includes(item.code))));
      return <button key={item.code} aria-pressed={selected} disabled={disabled} onClick={() => onChange(selected ? value.filter(code => code !== item.code) : [...value, item.code])} className="catalog-motif"><img src={apiUrl(item.imageUrl)} loading="lazy" alt="" /><span>{item.nameRu}</span><small>{item.code}</small></button>;
    })}</div>
    {!visible.length ? <p className="py-6 text-center">{items.length ? "По этому запросу элементов нет" : "Сначала выберите композицию"}</p> : null}
  </dialog>;
}
