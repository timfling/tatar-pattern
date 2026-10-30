"use client";
/* eslint-disable @next/next/no-img-element -- Generated data URLs / same-origin cookie-protected results. */
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { apiUrl } from "@/lib/api";
import type { V3Variant } from "@/lib/v3";
import { useShell } from "@/components/layout/shell-context";

/**
 * Экран результата (Figma «Конструктор (d/m), сгенерированный результат»):
 * 4 варианта-миниатюры, крупный просмотр, «Экспортировать», «🎲 Ещё варианты», справа — о композиции и мотивах.
 */
export function ResultV3({ variants, index, onIndex, onBack, onExport, onMore, exportBusy, moreBusy, notice, transparent = false }: {
  variants: V3Variant[]; index: number; onIndex: (i: number) => void; onBack: () => void; transparent?: boolean;
  onExport: () => void; onMore?: () => void; exportBusy: boolean; moreBusy: boolean; notice?: string;
}) {
  const { screenEl } = useShell();
  const [full, setFull] = useState(false);
  const current = variants[index] ?? variants[0];
  const info = current?.info;
  if (!current) return null;
  // Прозрачный фон показываем шахматкой, а не бежевой подложкой: иначе PNG выглядит как с фоном.
  return <div className="v3-result" data-transparent={transparent} key={variants.map(v => v.seed).join("-")}>
    <button type="button" className="v3-back" onClick={onBack}>
      <svg viewBox="0 0 11 20" aria-hidden="true"><path d="M9.5 1.5 1.5 10l8 8.5" fill="none" stroke="#666" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
      <span>Вернуться назад</span>
    </button>
    <div className="v3-result-body">
      <div className="v3-result-left">
        {variants.length > 1 ? <div className="v3-thumbs" role="tablist" aria-label="Варианты">
          {variants.map((v, i) => <button type="button" role="tab" key={v.seed} aria-selected={i === index} className="v3-thumb" style={{ "--i": i } as React.CSSProperties} onClick={() => onIndex(i)}>
            <img src={v.image} alt={`Вариант ${i + 1}`} draggable={false} />
          </button>)}
        </div> : null}
        <button type="button" className="v3-main" onClick={() => setFull(true)} aria-label="Открыть на весь экран">
          <img key={current.seed} src={current.image} alt={`${info?.composition ?? "Узор"}, вариант ${index + 1}`} draggable={false} />
        </button>
        <div className="v3-result-actions">
          <button type="button" className="v3-action" onClick={onExport} disabled={exportBusy}>
            <svg viewBox="0 0 18 21" aria-hidden="true"><path d="M9 13V2M5 5.5 9 1.5l4 4M4.5 8.5H3a1.5 1.5 0 0 0-1.5 1.5v8A1.5 1.5 0 0 0 3 19.5h12a1.5 1.5 0 0 0 1.5-1.5v-8A1.5 1.5 0 0 0 15 8.5h-1.5" fill="none" stroke="#1a1a1a" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <span>{exportBusy ? "Готовим файл…" : "Экспортировать"}</span>
          </button>
          {onMore ? <button type="button" className="v3-action" onClick={onMore} disabled={moreBusy}><span className="v3-dice" data-spin={moreBusy}>🎲</span><span>{moreBusy ? "Собираем…" : "Ещё варианты"}</span></button> : null}
        </div>
        {notice ? <p className="v3-notice">{notice}</p> : null}
      </div>
      <div className="v3-result-info" key={current.seed}>
        <h2>{info?.composition}</h2>
        <p className="v3-result-note">{info?.note}</p>
        {info?.traditionTitle ? <p className="v3-tradition">Техника-источник мотивов: <span className="v3-tradition-chip">{info.traditionTitle}</span></p> : null}
        {info?.used?.length ? <>
          <p className="v3-used-title">Использованные мотивы ({info.used.length}):</p>
          <ul className="v3-used">{info.used.map((u, i) => <li key={u.code} style={{ "--i": i } as React.CSSProperties}>
            <img src={apiUrl(`/api/v3/thumbs/${u.code}.png`)} alt="" loading="lazy" />
            <div><b>{u.name}</b><span>{u.code}{u.source ? ` · ${u.source}` : ""}{u.technique ? ` · ${u.technique}` : ""}</span></div>
          </li>)}</ul>
        </> : null}
      </div>
    </div>
    {full && screenEl ? createPortal(<Fullscreen image={current.image} onClose={() => setFull(false)} />, screenEl) : null}
  </div>;
}

function Fullscreen({ image, onClose }: { image: string; onClose: () => void }) {
  const [active, setActive] = useState(false);
  useEffect(() => {
    const f = requestAnimationFrame(() => setActive(true));
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", key);
    return () => { cancelAnimationFrame(f); window.removeEventListener("keydown", key); };
  });
  function close() { setActive(false); setTimeout(onClose, 260); }
  return <div className="v3-full" data-active={active} role="dialog" aria-modal="true" aria-label="Просмотр узора" onClick={close}>
    <img src={image} alt="Узор на весь экран" onClick={e => e.stopPropagation()} draggable={false} />
    <button type="button" className="v3-full-close" aria-label="Закрыть просмотр" onClick={close}>
      <svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
    </button>
  </div>;
}
