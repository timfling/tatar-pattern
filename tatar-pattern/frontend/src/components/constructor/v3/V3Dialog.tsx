"use client";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Окно выбора опции (Figma v3: «Frame 54» 1060×709 / мобайл 335×658).
 * Портал в body: backdrop-filter внутри масштабированного .app-screen рисуется со сдвигом.
 * Масштаб макета повторяется через zoom: var(--ui-scale). Блюр закрывает только окно генератора.
 */
export function V3Dialog({ label, onClose, children, wide = false, closeRef, closeButton = wide }: {
  label: string; onClose: () => void; children: ReactNode; wide?: boolean; closeButton?: boolean;
  /** Компонент-владелец получает функцию закрытия с анимацией. */
  closeRef?: (close: () => void) => void;
}) {
  const [active, setActive] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const surface = useRef<HTMLDivElement>(null);
  // onClose родителя меняется на каждом рендере; держим его в ref, чтобы не сбрасывать таймер закрытия.
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  const close = useCallback(() => {
    if (timer.current) return;
    setActive(false);
    timer.current = setTimeout(() => onCloseRef.current(), 280);
  }, []);
  useEffect(() => { closeRef?.(close); }, [close, closeRef]);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => { setActive(true); surface.current?.focus({ preventScroll: true }); }); });
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); close(); } };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(first); cancelAnimationFrame(second); window.removeEventListener("keydown", onKey);
      previous?.focus({ preventScroll: true });
    };
  }, [close]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  return createPortal(<div className="v3-overlay" data-active={active} onMouseDown={e => { if (e.target === e.currentTarget) close(); }}>
    <div ref={surface} tabIndex={-1} role="dialog" aria-modal="true" aria-label={label} className={`v3-dialog${wide ? " v3-dialog-wide" : ""}`}>
      {children}
      {closeButton ? <button type="button" className="v3-dialog-close" aria-label="Закрыть окно" onClick={close}>
        <svg viewBox="0 0 14 14" aria-hidden="true"><path d="M2 2l10 10M12 2 2 12" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
      </button> : null}
    </div>
  </div>, document.body);
}
