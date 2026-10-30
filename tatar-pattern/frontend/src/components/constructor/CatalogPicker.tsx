"use client";
/* eslint-disable @next/next/no-img-element -- Cookie-protected catalog previews. */
import { useState, type ReactNode } from "react";
import { AiModal } from "./AiOptionDialog";
import { apiUrl, type Element, type CompositionScheme, type PilotRecipe } from "@/lib/api";

export function CatalogPicker({ items, value, max, scheme, onChange, onClose, children }: {
  children?: ReactNode; items: Element[]; value: string[]; max: number; composition?: string | null; pilotRecipe?: PilotRecipe;
  scheme?: CompositionScheme; roleLabels?: Record<string,string>;
  onChange: (value: string[]) => void; onClose: () => void;
}) {
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const categories = [...new Set(items.map(item => item.motifClass))];
  const visible = items.filter(item => (!category || item.motifClass === category) && item.nameRu.toLocaleLowerCase("ru").includes(search.toLocaleLowerCase("ru")));
  return <AiModal label="Мотивы из каталога" onClose={onClose} className="flat-picker-modal"><div className="studio-picker-surface">
    <header className="picker-heading"><h2 id="catalog-heading">Мотивы из каталога</h2><button onClick={onClose} className="studio-button">Готово</button></header>
    <p className="option-explanation">Выберите мотивы для этой схемы. Готовый набор уже выбран; его можно изменить в пределах совместимости.</p>
    <p className="picker-count" role="status">Выбрано {value.length} / {Math.min(max, scheme?.maximumSelected ?? max)}</p>
    <div className="catalog-filters"><label>Категория<select value={category} onChange={e => setCategory(e.target.value)}><option value="">Все категории</option>{categories.map(name => <option key={name}>{name}</option>)}</select></label><label>Поиск<input value={search} onChange={e => setSearch(e.target.value)} placeholder="Название мотива" /></label></div>
    {children}
    <div className="catalog-items">{visible.map(item => {
      const selected = value.includes(item.code);
      const disabled = !selected && (value.length >= Math.min(max, scheme?.maximumSelected ?? max) || Boolean(scheme && (!scheme.allowedElementCodes.includes(item.code) || !scheme.availableElementCodes.includes(item.code))));
      return <button key={item.code} aria-pressed={selected} disabled={disabled} onClick={() => onChange(selected ? value.filter(code => code !== item.code) : [...value, item.code])} className="catalog-motif"><img src={apiUrl(item.imageUrl)} loading="lazy" alt="" /><span>{item.nameRu}</span></button>;
    })}</div>
    {!visible.length ? <p className="py-6 text-center">{items.length ? "По этому запросу элементов нет" : "Сначала выберите композицию"}</p> : null}
  </div></AiModal>;
}
