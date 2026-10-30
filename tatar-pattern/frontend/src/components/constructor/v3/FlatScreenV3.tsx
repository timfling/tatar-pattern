"use client";
import "./v3.css";
import { useEffect, useMemo, useState } from "react";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { SendArrow } from "@/components/ui/SendArrow";
import { apiMessage } from "@/lib/api";
import { v3Api, v3Preview, V3_DEFAULTS, type V3Catalog, type V3Params } from "@/lib/v3";
import { V3Carousel, type CarouselItem } from "./V3Carousel";
import { FormatPicker, MotifsPicker, OptionGridPicker } from "./V3Pickers";
import { MeshCanvas } from "./MeshCanvas";

type Tile = "composition" | "motifs" | "density" | "palette" | "background" | "format";
const CORNERS = ["tl", "", "tr", "bl", "", "br"];
const MOBILE_CORNERS = ["tl", "tr", "", "", "bl", "br"];
const STORAGE = "tp-v3-params";
const REQUIRED: Tile[] = ["composition", "density", "palette", "background", "format"];
const TITLES: Record<Tile, string> = { composition: "композицию", motifs: "мотивы", density: "насыщенность", palette: "палитру", background: "фон", format: "формат" };

export function readSavedParams(): V3Params | null {
  try { const raw = sessionStorage.getItem(STORAGE); return raw ? { ...V3_DEFAULTS, ...JSON.parse(raw) } : null; } catch { return null; }
}

/**
 * Параметрический режим v3 (Figma «Конструктор (d/m), базовый экран»).
 * Пустое состояние: «Выберите». Кнопка генерации активна, только когда выбраны все обязательные опции
 * (всё, кроме «Мотивов»: без выбора мотивы подбираются автоматически).
 */
export function FlatScreenV3({ generating, onGenerate, initial }: { generating: boolean; onGenerate: (params: V3Params) => void; initial?: V3Params | null }) {
  const [catalog, setCatalog] = useState<V3Catalog | null>(null);
  const [error, setError] = useState("");
  const [params, setParams] = useState<V3Params>(initial ?? V3_DEFAULTS);
  const [touched, setTouched] = useState<Set<Tile>>(() => new Set(initial ? ["composition", "motifs", "density", "palette", "background", "format"] as Tile[] : []));
  const [open, setOpen] = useState<Tile | null>(null);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    v3Api.catalog(controller.signal).then(c => { setCatalog(c); setError(""); }).catch(e => { if (!controller.signal.aborted) setError(apiMessage(e)); });
    return () => controller.abort();
  }, [revision]);
  // Сохранённые в вкладке настройки читаются после гидрации (на сервере sessionStorage нет).
  useEffect(() => {
    if (initial) return;
    const saved = readSavedParams(); if (!saved) return;
    let active = true;
    queueMicrotask(() => { if (!active) return; setParams(saved); setTouched(new Set(["composition", "motifs", "density", "palette", "background", "format"])); });
    return () => { active = false; };
  }, [initial]);
  useEffect(() => { try { if (touched.size) sessionStorage.setItem(STORAGE, JSON.stringify(params)); else sessionStorage.removeItem(STORAGE); } catch { /* optional */ } }, [params, touched]);
  function apply(tile: Tile, patch: Partial<V3Params>) { setParams(p => ({ ...p, ...patch })); setTouched(t => new Set(t).add(tile)); }
  function reset() { setParams(V3_DEFAULTS); setTouched(new Set()); }

  const comp = catalog?.compositions.find(c => c.id === params.composition);
  const palette = catalog?.palettes.find(p => p.id === params.palette);
  const tiles: { key: Tile; label: string; value: string; quoted?: boolean; dots?: string[] }[] = [
    { key: "composition", label: "Композиция", value: comp?.title ?? "", quoted: true },
    { key: "motifs", label: "Мотивы", value: params.motifs.length ? `${params.motifs.length} ${params.motifs.length === 1 ? "мотив" : params.motifs.length < 5 ? "мотива" : "мотивов"}` : "Автоподбор" },
    { key: "density", label: "Насыщенность", value: catalog?.density.find(d => d.id === params.density)?.title ?? "", quoted: true },
    { key: "palette", label: "Палитра", value: palette?.title ?? "", quoted: true, dots: palette ? (palette.colors.length ? palette.colors : ORIGINAL_DOTS) : undefined },
    { key: "background", label: "Фон", value: catalog?.backgrounds.find(b => b.id === params.background)?.title ?? "" },
    { key: "format", label: "Формат", value: (catalog?.formats.find(f => f.id === params.format)?.title ?? "").replace(/\s[\d:]+$/, "") },
  ];
  const dirty = touched.size > 0;
  const missing = REQUIRED.filter(t => !touched.has(t));
  const complete = missing.length === 0;
  const missingText = `Чтобы сгенерировать узор, выберите ${missing.map(t => TITLES[t]).join(", ")}.`;

  const carousel = useMemo(() => {
    if (!catalog || !open || ["motifs", "format", "density", "palette"].includes(open)) return null;
    if (open === "composition") return { title: "Выберите композицию", description: "Композиция — это «скелет» орнамента из традиционных схем. Мотивы и цвета сохранятся при смене композиции.", chosen: "Выбранная композиция", choose: "Выбрать эту композицию", selected: params.composition,
      items: catalog.compositions.map(x => ({ id: x.id, title: x.title, description: x.note, image: v3Preview(x.preview, {}) })), set: (id: string) => apply("composition", { composition: id }) };
    const pal = catalog.palettes.find(p => p.id === params.palette);
    return { title: "Фон", description: "По умолчанию фон берётся из палитры. Можно задать свой цвет или прозрачный PNG.", chosen: "Выбранный фон", choose: "Выбрать этот фон", selected: params.background,
      items: catalog.backgrounds.map(x => ({ id: x.id, title: x.title, description: x.id === "palette" ? `Фон палитры «${pal?.title ?? ""}».` : x.id === "transparent" ? "PNG без фона — для наложения на свой макет. JPG сохранится со светлым фоном." : "Сплошной фон; цвета мотивов не меняются.",
        swatch: <span className="v3-swatch" data-transparent={x.id === "transparent"} style={{ background: x.id === "transparent" ? undefined : x.color ?? pal?.bg }} /> } as CarouselItem)), set: (id: string) => apply("background", { background: id }) };
  }, [catalog, open, params]);

  return <div className="ai-constructor-body flat-workspace v3-workspace">
    <h1>Соберите орнаментальный узор</h1>
    <div className="ai-parameter-grid v3-tiles" data-ready={Boolean(catalog)}>
      {tiles.map((t, i) => {
        // «Мотивы» необязательны: без выбора на плитке сразу виден автоподбор.
        const set = (t.key === "motifs" || touched.has(t.key)) && Boolean(t.value);
        return <button type="button" key={t.key} data-parameter-card={t.label} className={`v3-tile v3-c-${CORNERS[i]} v3-m-${MOBILE_CORNERS[i]}`} data-set={set} data-ghost={open === t.key}
          style={{ "--i": i } as React.CSSProperties} disabled={!catalog} onClick={() => setOpen(t.key)} aria-label={`${t.label}: ${set ? t.value : "выберите"}`}>
          <span className="v3-tile-label">{t.label}<svg viewBox="0 0 9 17" aria-hidden="true"><path d="M1.2 1.2 7.8 8.5 1.2 15.8" fill="none" stroke="#666" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg></span>
          <span key={set ? t.value : "empty"} className="v3-tile-value">
            {set ? <>{t.dots ? <span className="v3-dots v3-tile-dots">{t.dots.slice(0, 5).map((c, k) => <i key={k} style={{ background: c, "--k": k } as React.CSSProperties} />)}</span> : null}<span className="v3-tile-text" data-long={t.value.length + (t.dots ? 4 : 0) > 12}>{t.quoted ? `“${t.value}”` : t.value}</span></> : <span className="v3-tile-empty">Выберите</span>}
          </span>
        </button>;
      })}
    </div>
    <div className="ai-generate-area v3-generate-area">
      <button type="button" className="v3-reset" data-visible={dirty && !generating} aria-label="Сбросить настройки" title="Сбросить настройки" onClick={reset} tabIndex={dirty ? 0 : -1}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2 2l12 12M14 2 2 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
      </button>
      <button type="button" className="v3-generate" data-state={generating ? "busy" : complete ? "ready" : "idle"} disabled={!catalog || generating || !complete} onClick={() => { if (complete) onGenerate(params); }}
        title={!complete && catalog ? missingText : undefined} aria-describedby={!complete && catalog ? "v3-missing" : undefined} aria-live="polite">
        <span className="v3-generate-mesh" aria-hidden="true">{generating ? <MeshCanvas className="v3-mesh-canvas" /> : null}</span>
        <span className="v3-generate-label"><ModeIcon mode="flat" /><span>{generating ? "Генерируем…" : "Сгенерировать узор"}</span></span>
        <span className="ai-generate-arrow v3-generate-arrow"><SendArrow /></span>
        <span className="v3-loader" aria-hidden="true"><i /><i /><i /><i /></span>
      </button>
      {!complete && catalog && !generating ? <span id="v3-missing" className="sr-only">{missingText}</span> : null}
      <span className="v3-mobile-reset-row" data-visible={dirty && !generating}><button type="button" className="v3-reset-pill" onClick={reset} tabIndex={dirty ? 0 : -1}>Сбросить<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3 3 13" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" /></svg></button></span>
    </div>
    {error ? <p role="alert" className="api-error">{error} <button className="underline" onClick={() => setRevision(v => v + 1)}>Повторить</button></p> : null}
    {carousel ? <V3Carousel key={open} title={carousel.title} description={carousel.description} items={carousel.items} selected={touched.has(open!) ? carousel.selected : null}
      chooseLabel={carousel.choose} chosenLabel={carousel.chosen} onSelect={carousel.set} onClose={() => setOpen(null)} /> : null}
    {open === "motifs" && catalog ? <MotifsPicker catalog={catalog} value={params} onApply={p => apply("motifs", p)} onClose={() => setOpen(null)} /> : null}
    {open === "density" && catalog ? <OptionGridPicker label="Насыщенность" description="Сколько ярусов и деталей добавить в композицию. Каркас и мотивы при этом сохраняются."
      options={catalog.density.map(x => ({ id: String(x.id), title: x.title, hint: x.hint }))} value={String(params.density)}
      onApply={id => apply("density", { density: Number(id) })} onClose={() => setOpen(null)} /> : null}
    {open === "palette" && catalog ? <OptionGridPicker label="Палитра" description="«Исходные цвета» сохраняют цвета музейных мотивов. Остальные палитры перекрашивают все мотивы в единую гамму традиционной техники."
      options={catalog.palettes.map(x => ({ id: x.id, title: x.title, dots: x.colors.length ? x.colors : ORIGINAL_DOTS, image: v3Preview(catalog.previewPatterns.palette, { palette: x.id, composition: params.composition }) }))} value={params.palette}
      footer={id => catalog.palettes.find(p => p.id === id)?.hint ?? ""} onApply={id => apply("palette", { palette: id })} onClose={() => setOpen(null)} /> : null}
    {open === "format" && catalog ? <FormatPicker catalog={catalog} value={params} onApply={p => apply("format", p)} onClose={() => setOpen(null)} /> : null}
  </div>;
}
const ORIGINAL_DOTS = ["#8a5a2b", "#2f5b8f", "#b3302d"];
