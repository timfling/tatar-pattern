"use client";
/* eslint-disable @next/next/no-img-element -- Same-origin catalogue thumbnails from the API. */
import { useRef, useState } from "react";
import { apiUrl } from "@/lib/api";
import type { V3Catalog, V3Params } from "@/lib/v3";
import { V3Dialog } from "./V3Dialog";

/** «Мотивы» — как в прототипе: техника-источник, вид мотива, сетка до 6 выбранных (первый — главный). */
export function MotifsPicker({ catalog, value, onApply, onClose }: { catalog: V3Catalog; value: V3Params; onApply: (patch: Partial<V3Params>) => void; onClose: () => void }) {
  const [tradition, setTradition] = useState(value.tradition);
  const [motifs, setMotifs] = useState(value.motifs);
  const [category, setCategory] = useState("all");
  const closer = useRef<() => void>(onClose);
  const list = catalog.motifs.filter(m => (category === "all" || m.categories.includes(category)) && (tradition === "auto" || m.traditions.includes(tradition)));
  const max = catalog.maxMotifs;
  function toggle(code: string) {
    setMotifs(prev => prev.includes(code) ? prev.filter(c => c !== code) : prev.length < max ? [...prev, code] : prev);
  }
  return <V3Dialog label="Мотивы" onClose={onClose} wide closeRef={fn => { closer.current = fn; }}>
    <div className="v3-grid-dialog">
      <header className="v3-dialog-head">
        <h2>Мотивы</h2>
        <p>Можно ничего не выбирать — мотивы подберутся автоматически по выбранной технике. Выберите до {max} мотивов: <b>первый</b> станет главным, остальные займут подходящие места.</p>
      </header>
      <div className="v3-grid-scroll">
        <p className="v3-section">Техника-источник</p>
        <div className="v3-chips">{catalog.traditions.map(t => <button type="button" key={t.id} className="v3-chip" aria-pressed={tradition === t.id} onClick={() => setTradition(t.id)}>{t.title}</button>)}</div>
        <p className="v3-section">Вид мотива</p>
        <div className="v3-chips">{[{ id: "all", title: `Все ${catalog.motifs.length}` }, ...catalog.categories].map(c => <button type="button" key={c.id} className="v3-chip" aria-pressed={category === c.id} onClick={() => setCategory(c.id)}>{c.title}</button>)}</div>
        <div key={`${tradition}-${category}`} className="v3-motif-grid">
          {list.length ? list.map((m, i) => {
            const at = motifs.indexOf(m.code);
            return <button type="button" key={m.code} className="v3-motif" aria-pressed={at >= 0} title={`${m.name}\n${m.source ?? ""}`} style={{ "--i": Math.min(i, 30) } as React.CSSProperties} onClick={() => toggle(m.code)}>
              {at >= 0 ? <i className="v3-motif-badge">{at === 0 ? "главный" : at + 1}</i> : null}
              <img src={apiUrl(m.thumb)} alt={m.name} loading="lazy" draggable={false} />
              <small>{m.code.slice(5)}</small>
            </button>;
          }) : <p className="v3-empty">В этой технике нет мотивов такого вида.</p>}
        </div>
      </div>
      <footer className="v3-grid-foot">
        <span>{motifs.length ? <>Выбрано {motifs.length} из {max} · <button type="button" className="v3-link" onClick={() => setMotifs([])}>сбросить (автоподбор)</button></> : "Автоподбор включён"}</span>
        <button type="button" className="v3-choose" onClick={() => { onApply({ tradition, motifs }); closer.current(); }}><span className="v3-choose-label">Готово</span></button>
      </footer>
    </div>
  </V3Dialog>;
}

/** «Формат» — как в прототипе: соотношение сторон и рамка. */
export function FormatPicker({ catalog, value, onApply, onClose }: { catalog: V3Catalog; value: V3Params; onApply: (patch: Partial<V3Params>) => void; onClose: () => void }) {
  const [format, setFormat] = useState(value.format);
  const [frame, setFrame] = useState(value.frame);
  const closer = useRef<() => void>(onClose);
  return <V3Dialog label="Формат и рамка" onClose={onClose} wide closeRef={fn => { closer.current = fn; }}>
    <div className="v3-grid-dialog">
      <header className="v3-dialog-head">
        <h2>Формат и рамка</h2>
        <p>Выберите, где будет использован узор. В вытянутых форматах композиция повторяется ритмом, как на полотенце.</p>
      </header>
      <div className="v3-grid-scroll">
        <p className="v3-section">Формат</p>
        <div className="v3-format-grid">{catalog.formats.map((f, i) => {
          const k = 64 / Math.max(f.w, f.h);
          return <button type="button" key={f.id} className="v3-format" aria-pressed={format === f.id} style={{ "--i": i } as React.CSSProperties} onClick={() => setFormat(f.id)}>
            <span className="v3-format-shape"><i style={{ width: f.w * k, height: f.h * k }} /></span>
            <b>{f.title}</b><small>{f.w}×{f.h} px</small>
          </button>;
        })}</div>
        <p className="v3-section">Рамка</p>
        <div className="v3-format-grid v3-frame-grid">{catalog.frames.map((f, i) => <button type="button" key={f.id} className="v3-format" aria-pressed={frame === f.id} style={{ "--i": i } as React.CSSProperties} onClick={() => setFrame(f.id)}>
          <span className={`v3-frame-shape v3-frame-${f.id}`}><i /></span><b>{f.title}</b>
        </button>)}</div>
        {value.composition === "pattern" ? <p className="v3-note">Для бесшовного узора рамка не используется; после генерации можно скачать отдельную плитку.</p> : null}
      </div>
      <footer className="v3-grid-foot">
        <span>{catalog.formats.find(f => f.id === format)?.title} · {catalog.frames.find(f => f.id === frame)?.title.toLowerCase()}</span>
        <button type="button" className="v3-choose" onClick={() => { onApply({ format, frame }); closer.current(); }}><span className="v3-choose-label">Готово</span></button>
      </footer>
    </div>
  </V3Dialog>;
}

export type GridOption = { id: string; title: string; hint?: string; image?: string; dots?: string[] };
/**
 * «Палитра» и «Насыщенность» — как в демо v3 (prototype-v3/web): сетка карточек 3 в ряд,
 * у палитры — превью и кружки цветов, у насыщенности — название и подсказка. Применяется по «Готово».
 */
export function OptionGridPicker({ label, description, options, value, footer, onApply, onClose }: {
  label: string; description: string; options: GridOption[]; value: string;
  footer?: (id: string) => string; onApply: (id: string) => void; onClose: () => void;
}) {
  const [picked, setPicked] = useState(value);
  const closer = useRef<() => void>(onClose);
  const withImages = options.some(o => o.image);
  return <V3Dialog label={label} onClose={onClose} wide closeRef={fn => { closer.current = fn; }}>
    <div className="v3-grid-dialog">
      <header className="v3-dialog-head"><h2>{label}</h2><p>{description}</p></header>
      <div className="v3-grid-scroll">
        <div className="v3-option-grid" data-images={withImages}>{options.map((o, i) => <button type="button" key={o.id} className="v3-option" aria-pressed={picked === o.id} style={{ "--i": i } as React.CSSProperties} onClick={() => setPicked(o.id)}>
          {o.image ? <span className="v3-option-media"><img src={o.image} alt="" loading="lazy" draggable={false} /></span> : null}
          <b>{o.title}</b>
          {o.dots?.length ? <span className="v3-dots v3-option-dots">{o.dots.map((c, k) => <i key={k} style={{ background: c }} />)}</span> : null}
          {o.hint ? <small>{o.hint}</small> : null}
        </button>)}</div>
      </div>
      <footer className="v3-grid-foot">
        <span>{footer?.(picked) ?? ""}</span>
        <button type="button" className="v3-choose" onClick={() => { onApply(picked); closer.current(); }}><span className="v3-choose-label">Готово</span></button>
      </footer>
    </div>
  </V3Dialog>;
}
