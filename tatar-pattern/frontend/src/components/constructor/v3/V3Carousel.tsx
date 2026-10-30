"use client";
/* eslint-disable @next/next/no-img-element -- Same-origin generated previews (API), no optimization needed. */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { V3Dialog } from "./V3Dialog";
import { useMobile } from "./useMobile";

export type CarouselItem = { id: string; title: string; description: string; image?: string; swatch?: ReactNode; dots?: string[] };

/**
 * Окно «Выберите …» (Figma v3, «открытая опция»): центральная карточка с описанием и превью,
 * соседние — уменьшенные. Карточки морфятся (размер, позиция, прозрачность) при перелистывании.
 * Десктоп — горизонтальная лента, мобайл — вертикальная.
 */
export function V3Carousel({ title, description, items, selected, chooseLabel, chosenLabel, onSelect, onClose }: {
  title: string; description: string; items: CarouselItem[]; selected: string | null;
  chooseLabel: string; chosenLabel: string; onSelect: (id: string) => void; onClose: () => void;
}) {
  const mobile = useMobile();
  const start = Math.max(0, items.findIndex(i => i.id === selected));
  const [index, setIndex] = useState(start);
  const [justChosen, setJustChosen] = useState(false);
  const closer = useRef<() => void>(onClose);
  const wheel = useRef(0);
  const pointer = useRef<{ x: number; y: number } | null>(null);
  const current = items[index];
  const isChosen = current?.id === selected;
  const move = useCallback((delta: number) => setIndex(i => items.length > 2 ? (i + delta + items.length) % items.length : Math.max(0, Math.min(items.length - 1, i + delta))), [items.length]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (["ArrowLeft", "ArrowUp"].includes(e.key)) { e.preventDefault(); move(-1); }
      if (["ArrowRight", "ArrowDown"].includes(e.key)) { e.preventDefault(); move(1); }
      if (e.key === "Enter" && current) { e.preventDefault(); choose(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  function choose() {
    if (!current) return;
    onSelect(current.id); setJustChosen(true);
    // Короткая пауза, чтобы увидеть «Выбрано ✓», затем окно плавно закрывается.
    setTimeout(() => closer.current(), 650);
  }
  return <V3Dialog label={title} onClose={onClose} closeRef={fn => { closer.current = fn; }}>
    <div className="v3-carousel-dialog">
      <header className="v3-dialog-head">
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      <div className="v3-carousel" data-axis={mobile ? "y" : "x"} role="listbox" aria-label={title} aria-activedescendant={current ? `v3-opt-${current.id}` : undefined}
        onWheel={e => { const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY; if (Math.abs(d) > 10 && Date.now() - wheel.current > 260) { wheel.current = Date.now(); move(d > 0 ? 1 : -1); } }}
        onPointerDown={e => { pointer.current = { x: e.clientX, y: e.clientY }; }}
        onPointerUp={e => { const p = pointer.current; pointer.current = null; if (!p) return; const d = mobile ? p.y - e.clientY : p.x - e.clientX; if (Math.abs(d) > 36) move(d > 0 ? 1 : -1); }}>
        {items.map((item, i) => {
          // Кольцевая лента: у крайних карточек тоже есть соседи (как в макете).
          const n = items.length;
          let offset = i - index;
          if (n > 2) { if (offset > n / 2) offset -= n; if (offset < -n / 2) offset += n; }
          const state = offset === 0 ? "center" : Math.abs(offset) === 1 ? "side" : "hidden";
          return <div key={item.id} id={`v3-opt-${item.id}`} role="option" aria-selected={offset === 0}
            className="v3-card" data-state={state} data-chosen={item.id === selected}
            style={{ "--offset": Math.max(-2, Math.min(2, offset)) } as React.CSSProperties}
            onClick={() => { if (offset !== 0) setIndex(i); }}>
            <div className="v3-card-text">
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              {item.dots?.length ? <span className="v3-dots">{item.dots.map((c, k) => <i key={k} style={{ background: c }} />)}</span> : null}
            </div>
            <span className="v3-card-side-title">{item.title}</span>
            <div className="v3-card-media">{item.image ? <img src={item.image} alt="" draggable={false} loading="lazy" /> : item.swatch}</div>
          </div>;
        })}
      </div>
      <div className="v3-choose-row">
        <button type="button" className="v3-choose" data-chosen={isChosen} onClick={() => isChosen ? closer.current() : choose()}>
          <span key={isChosen ? "on" : "off"} className="v3-choose-label">{isChosen ? chosenLabel : chooseLabel}</span>
          <svg viewBox="0 0 22 17" aria-hidden="true" className="v3-check" data-pop={justChosen}><path d="M1.5 9l6 6L20.5 2" fill="none" stroke="#137d06" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
    </div>
  </V3Dialog>;
}
