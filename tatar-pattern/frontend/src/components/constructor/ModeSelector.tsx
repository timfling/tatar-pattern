"use client";
/* eslint-disable @next/next/no-img-element -- Original local SVG logo. */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { ModelBadge } from "./ModelBadge";
export type ConstructorMode = "flat" | "ai";
export function ModeSelector({ mode, onChange }: { mode: ConstructorMode; onChange: (mode: ConstructorMode) => void }) {
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [origin, setOrigin] = useState<DOMRect | null>(null);
  const [active, setActive] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!origin) return;
    const el = dialog.current; el?.showModal();
    let next = 0;
    const frame = requestAnimationFrame(() => { next = requestAnimationFrame(() => setActive(true)); });
    return () => { cancelAnimationFrame(frame); cancelAnimationFrame(next); el?.close(); };
  }, [origin]);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  function close(selected?: ConstructorMode) {
    if (timer.current) return;
    setActive(false);
    timer.current = setTimeout(() => { if (selected) onChange(selected); setOrigin(null); timer.current = null; requestAnimationFrame(() => trigger.current?.focus({ preventScroll: true })); }, 620);
  }
  return <div className="constructor-mode-selector">
    <div className="constructor-modes-desktop" data-mode={mode} role="group" aria-label="Режим конструктора">
      <span>Режим:</span><div className="constructor-mode-options">
        <button className="constructor-mode-flat" aria-pressed={mode === "flat"} aria-label="Параметрический режим" onClick={() => onChange("flat")}><ModeIcon mode="flat" /><span>Параметрический</span></button>
        <ModelBadge modeTrigger modeSelected={mode === "ai"} onActivate={() => onChange("ai")} />
      </div>
    </div>
    <button ref={trigger} className="constructor-mode-mobile" data-mode={mode} aria-haspopup="dialog" aria-expanded={Boolean(origin)} onClick={() => { const rect = trigger.current?.getBoundingClientRect(); if (rect) setOrigin(rect); }}><ModeIcon mode={mode} />{mode === "ai" ? "ИИ-генерация" : "Параметрический"}</button>
    {origin ? createPortal(<dialog ref={dialog} className="mode-dialog" data-active={active} onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }} aria-label="Выберите режим">
      <div className="mode-dialog-morph" style={{ "--mode-x": `${origin.left}px`, "--mode-y": `${origin.top}px`, "--mode-w": `${origin.width}px`, "--mode-h": `${origin.height}px` } as React.CSSProperties}>
        <div className="mode-dialog-choices"><h2>Выберите режим:</h2>
          <button className="mode-choice-flat" aria-pressed={mode === "flat"} onClick={() => close("flat")}><strong><ModeIcon mode="flat" />Параметрический</strong><span>Генерация орнаментов без<br />использования ИИ</span></button>
          <button className="mode-choice-ai" aria-pressed={mode === "ai"} onClick={() => close("ai")}><strong><img src="/home-v2/logo.svg" alt="" width="45" height="26" />Pattern Lab 01</strong><span>Наша первая и актуальная<br />ИИ модель для генерации<br />национальных орнаментов.<br />Базируется на SDXL Base 1.0.</span></button>
        </div>
      </div>
    </dialog>, document.body) : null}
  </div>;
}
