"use client";
/* eslint-disable @next/next/no-img-element -- Local, proven renderer examples; no image optimization needed. */
import { useState } from "react";
import { AiModal } from "./AiOptionDialog";
import { apiUrl, type SchemeCatalog, type CompositionScheme, type Renderer, type Capabilities, type Element, type PilotRecipe } from "@/lib/api";
export const ROLE_LABELS: Record<string,string> = { center: "Небольшой центр", outer_axial_accent: "Направленные пальметты", lower_framing_pair: "Нижняя парная опора", primary_flower: "Крупный цветок", horizontal_connector_accent: "Завитковый блок", small_accent: "Малый цветок", framing_band: "Рамочная полоса", small_secondary_module: "Вспомогательный ромб", large_primary_module: "Главный ромб" };
export const COMPOSITION_LABELS: Record<string,string> = { medallion: "Венок", border: "Бордюр", rapport: "Раппорт" };
export function CompositionPicker({ acceptedOnly = false, capabilities, items, renderer, composition, borderLayout, schemeCatalog, schemeId, onScheme, onSelect, onClose }: {
  acceptedOnly?: boolean; capabilities: Capabilities | null; items: Element[]; renderer: string; composition: string | null; borderLayout: string;
  schemeCatalog: SchemeCatalog | null; schemeId: string | null; onScheme: (scheme: CompositionScheme) => void;
  onSelect: (renderer: Renderer, composition: string, recipe?: PilotRecipe, borderLayout?: "registers" | "interwoven") => void; onClose: () => void;
}) {
  const current = schemeCatalog?.schemes.find(s => s.id === schemeId);
  const [kind, setKind] = useState(composition ?? "medallion");
  const [family, setFamily] = useState(current?.familyId ?? "");
  const pilot = capabilities?.renderers?.["composition-v1"];
  return <AiModal label="Выберите композицию" onClose={onClose} className="flat-picker-modal"><div className="studio-picker-surface">
    <header className="mb-4 flex items-center justify-between gap-3"><h2 id="composition-heading" className="font-display text-3xl italic">Выберите композицию</h2><button className="studio-button" onClick={onClose}>Готово</button></header>
    <p className="option-explanation">Схема задаёт расположение мотивов. При выборе применяется её готовый набор, который можно изменить в «Мотивах».</p>
    {schemeCatalog ? <>
      <div className="mb-4 flex flex-wrap gap-2">{["medallion","border","rapport"].map(k => <button key={k} className="studio-button" aria-pressed={kind === k} onClick={() => setKind(k)}>{k === "medallion" ? "Медальон / поле" : COMPOSITION_LABELS[k]}</button>)}</div>
      <label className="mb-4 flex flex-col gap-2 text-sm">Семейство · {schemeCatalog.totalFamilies}<select className="w-full rounded-xl bg-white p-3" value={family} onChange={e => setFamily(e.target.value)}><option value="">Все семейства</option>{schemeCatalog.families.map(f => <option key={f.id} value={f.id}>{f.titleRu}</option>)}</select></label>
      {!schemeCatalog.schemes.some(s => s.composition === kind && (!family || s.familyId === family)) ? <p className="mb-4 text-sm">В этом семействе нет схем выбранного типа. Выберите другой тип композиции или семейство.</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">{schemeCatalog.schemes.filter(s => s.composition === kind && (!family || s.familyId === family)).map(s => <article key={s.id} className="rounded-2xl border border-hairline/40 bg-white/65 p-4">
        {s.available && s.previewUrl ? <img loading="lazy" src={apiUrl(s.previewUrl)} alt={`Пример предложенного набора: ${s.titleRu}`} className="mb-3 h-40 w-full rounded-xl object-contain" /> : null}
        <h4 className="font-semibold">{s.titleRu}</h4>
        <button disabled={!s.available || acceptedOnly && s.reviewStatus !== "owner_accepted_2026_10_13"} aria-pressed={renderer === "composition-v2" && s.id === schemeId} className="studio-button mt-3 disabled:opacity-40" onClick={() => onScheme(s)}>{acceptedOnly && s.reviewStatus !== "owner_accepted_2026_10_13" ? "Ожидает оценки — недоступно" : !s.available ? "Набор недоступен" : renderer === "composition-v2" && s.id === schemeId ? "Выбрано ✓" : "Выбрать композицию"}</button>
      </article>)}</div>
    </> : <div aria-busy="true" aria-label="Загрузка композиций" className="grid grid-cols-2 gap-3">{[0,1].map(i => <div key={i} className="h-40 rounded-2xl bg-white/60" />)}</div>}
    {!acceptedOnly ? <><h3 className="mb-3 mt-6 font-semibold">Принятый пилот · v1</h3>
    {pilot ? <><p className="mb-4 text-sm leading-relaxed">Согласованные схемы с закреплёнными ролями. Выбор схемы применит указанный набор мотивов и исходные цвета. Изображения ниже — примеры работы генератора, ваш результат появится после генерации.</p>
    <div className="grid gap-4 sm:grid-cols-2">{pilot.pilotRecipes.flatMap(recipe => recipe.composition === "border" ? (pilot.borderLayouts ?? ["registers"]).map(layout => ({recipe, layout})) : [{ recipe, layout: "registers" }]).map(({recipe,layout}) => {
      const selected = renderer === "composition-v1" && composition === recipe.composition && (recipe.composition !== "border" || borderLayout === layout);
      const example = recipe.composition === "border" ? layout : recipe.composition;
      return <button key={recipe.id+layout} aria-pressed={selected} disabled={!recipe.codes.every(code => items.some(item => item.code === code))} className={`parameter-choice rounded-2xl border p-4 text-left disabled:opacity-40 ${selected ? "border-[#356052] bg-[#356052]/10" : "border-hairline/40 bg-white/65"}`} onClick={() => onSelect("composition-v1",recipe.composition,recipe,layout as "registers" | "interwoven")}>
        <img src={`/composition-examples/${example}.png`} alt={`Пример схемы ${COMPOSITION_LABELS[recipe.composition]}`} className="mb-3 h-40 w-full rounded-xl object-contain" />
        <span className="block text-lg font-semibold">{COMPOSITION_LABELS[recipe.composition]}{recipe.composition === "border" ? layout === "interwoven" ? " · Чередование весов" : " · Ярусы" : ""}{selected ? " ✓" : ""}</span>
        <span className="my-2 block text-xs text-ink-muted">Пример схемы · {recipe.codes.join(" / ")} · {recipe.composition === "border" && layout === "interwoven" ? "плотный ритм" : "обычный ритм"}</span>
        <span className="block text-sm leading-relaxed">{recipe.codes.map(code => `${code}: ${ROLE_LABELS[recipe.roles[code]] ?? recipe.roles[code]}`).join("; ")}</span>
        <span className="mt-2 block text-xs leading-relaxed">Современная декоративная композиция. {recipe.composition === "border" ? "Направляющие добавлены дизайнером." : recipe.composition === "medallion" ? "Открытая направляющая добавлена дизайнером." : "Дискретный модуль повтора."}</span>
      </button>;
    })}</div></> : <p className="mb-4 text-sm">Согласованные схемы пока недоступны в этом API.</p>}
    <h3 className="mb-3 mt-6 font-semibold">Свободное размещение · прежний генератор</h3>
    <p className="mb-3 text-sm">Сохраняет ваш набор. Роли и культурная совместимость новой расстановки не проверены.</p>
    <div className="flex flex-wrap gap-3">{(capabilities?.compositions ?? []).map(value => <button key={value} className="studio-button" aria-pressed={renderer === "legacy" && value === composition} onClick={() => onSelect("legacy",value)}>{COMPOSITION_LABELS[value] ?? value}</button>)}</div>
    </> : null}
  </div></AiModal>;
}
