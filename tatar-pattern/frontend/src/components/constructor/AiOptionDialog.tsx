"use client";
/* eslint-disable @next/next/no-img-element -- Protected API previews are original input PNGs. */
import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { apiUrl } from "@/lib/api";

export function AiModal({ children, onClose, label, className = "" }: { children: ReactNode; onClose: () => void; label: string; className?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [active, setActive] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const close = useCallback(() => {
    if (timer.current) return;
    setActive(false);
    timer.current = setTimeout(onClose, 260);
  }, [onClose]);
  useEffect(() => {
    const el = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    el?.showModal();
    const first = requestAnimationFrame(() => { frame = requestAnimationFrame(() => setActive(true)); });
    let frame = 0;
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(frame); if (timer.current) clearTimeout(timer.current); el?.close(); requestAnimationFrame(() => previous?.focus({preventScroll:true})); };
  }, []);
  return createPortal(<dialog ref={dialog} className={`ai-modal ${className}`} data-active={active} aria-label={label} onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
    <div className="ai-modal-position"><div className="ai-modal-content">{children}<button className="ai-modal-close" aria-label="Закрыть окно" onClick={close}>×</button></div></div>
  </dialog>, document.body);
}
export type AiOption = { id: string; title: string; description: string; previewUrl?: string; note?: string; colors?: string[] };
export function AiOptionDialog({ label, options, selected, confirmLabel, onSelect, onClose }: {
  label: string; options: AiOption[]; selected: string | null; confirmLabel: string; onSelect: (id: string) => void; onClose: () => void;
}) {
  const [currentId, setCurrentId] = useState(selected ?? options[0]?.id ?? "");
  const items = options;
  const found = items.findIndex(item => item.id === currentId);
  const index = found < 0 ? 0 : found;
  const current = items[index];
  const id = useId();
  const pointerY = useRef<number | null>(null);
  const lastWheel = useRef(0);
  function move(delta: number) { const next = items[Math.max(0, Math.min(items.length - 1, index + delta))]; if (next) setCurrentId(next.id); }
  return <AiModal label={label} onClose={onClose} className="ai-picker-modal">
    <div className="ai-picker-surface">
      <div key={current?.id} className="ai-option-description" aria-live="polite">
        {current?.previewUrl ? <img key={current.id} src={apiUrl(current.previewUrl)} alt={`Исходная основа: ${current.title}`} className="ai-base-preview" /> : null}
        <p>{current?.description ?? "По запросу ничего не найдено"}</p>
        {current?.colors?.length ? <div className="ai-swatches">{current.colors.map((color,i) => <span key={`${color}-${i}`} style={{ backgroundColor: color }} title={color} />)}</div> : null}
        {current?.note ? <p className="ai-option-note">{current.note}</p> : null}
        <button className="ai-confirm ai-confirm-desktop" data-selected={current?.id === selected} disabled={!current} onClick={() => current && onSelect(current.id)}>{current?.id === selected ? "Выбрано ✓" : confirmLabel}</button>
      </div>
      <div className="ai-option-divider" />
      <div className="ai-options-column">
        <h2 className="sr-only">{label}</h2>
        <div className="ai-carousel" role="listbox" tabIndex={0} aria-label={label} aria-activedescendant={current ? `${id}-${current.id}` : undefined}
          onKeyDown={e => { if (["ArrowUp","ArrowDown","Home","End"].includes(e.key)) { e.preventDefault(); if(e.key === "Home") setCurrentId(items[0]?.id ?? ""); else if(e.key === "End") setCurrentId(items.at(-1)?.id ?? ""); else move(e.key === "ArrowUp" ? -1 : 1); } if(e.key === "Enter" && current) { e.preventDefault(); onSelect(current.id); } }}
          onWheel={e => { if(Math.abs(e.deltaY) > 8 && Date.now() - lastWheel.current > 170) { lastWheel.current = Date.now(); move(e.deltaY > 0 ? 1 : -1); } }}
          onPointerDown={e => { pointerY.current = e.clientY; }} onPointerUp={e => { if(pointerY.current !== null && Math.abs(pointerY.current-e.clientY) > 30) move(pointerY.current > e.clientY ? 1 : -1); pointerY.current = null; }}>
          <div className="ai-carousel-track" style={{ transform: `translateY(calc((1 - ${index}) * var(--ai-option-height)))` }}>
            {items.map((item, i) => <div key={item.id} id={`${id}-${item.id}`} role="option" aria-selected={item.id === current?.id} className="ai-carousel-option" data-current={i === index} data-near={Math.abs(i-index) === 1} onClick={() => setCurrentId(item.id)}>{item.title}</div>)}
          </div>
        </div>
        {items.length > 3 ? <div className="ai-carousel-navigation"><span>{items.length ? index+1 : 0} / {items.length}</span></div> : null}
      </div>
    </div>
    <button className="ai-confirm ai-confirm-mobile" data-selected={current?.id === selected} disabled={!current} onClick={() => current && onSelect(current.id)}>{current?.id === selected ? "Выбрано ✓" : confirmLabel}</button>
  </AiModal>;
}
