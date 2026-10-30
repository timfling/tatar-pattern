"use client";
import { useEffect, useRef, useState } from "react";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { createPortal } from "react-dom";
function ModelLogo() { return (        <svg
          width="31"
          height="17"
          viewBox="0 0 31 17"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-hidden
          className="ai-model-logo"
        >
          <path
            d="M10.5596 0.762695L19.8408 0.762695C19.8855 0.76276 19.911 0.774279 19.9277 0.786133C19.948 0.800485 19.9681 0.824991 19.9814 0.857422C19.9947 0.889737 19.9975 0.920888 19.9932 0.945312C19.9896 0.965545 19.9799 0.991949 19.9482 1.02344L15.3076 5.62305C15.2482 5.68191 15.1522 5.68177 15.0928 5.62305L10.4521 1.02344C10.4203 0.99184 10.4108 0.965597 10.4072 0.945312C10.4029 0.920918 10.4048 0.889713 10.418 0.857422C10.4313 0.824991 10.4523 0.800485 10.4727 0.786133C10.4895 0.774323 10.515 0.762695 10.5596 0.762695Z"
            stroke="currentColor"
            strokeWidth="1.52534"
          />
          <path
            d="M1.18066 8.53271C1.12173 8.47326 1.12174 8.37733 1.18066 8.31787L6.69434 2.75439C6.75399 2.6942 6.85145 2.69424 6.91113 2.75439L12.4258 8.31787C12.4847 8.37731 12.4847 8.47326 12.4258 8.53271L6.91113 14.0972C6.85143 14.1571 6.75391 14.1573 6.69434 14.0972L1.18066 8.53271Z"
            stroke="currentColor"
            strokeWidth="1.52534"
          />
          <path
            d="M15.0928 11.1714C15.1522 11.1125 15.2482 11.1125 15.3076 11.1714L19.9482 15.77C19.9799 15.8015 19.9896 15.8279 19.9932 15.8481C19.9975 15.8726 19.9948 15.9046 19.9814 15.937C19.9681 15.9692 19.9479 15.993 19.9277 16.0073C19.911 16.0192 19.8855 16.0307 19.8408 16.0308H10.5596C10.5148 16.0308 10.4895 16.0192 10.4727 16.0073C10.4524 15.993 10.4313 15.9693 10.418 15.937C10.4046 15.9046 10.4029 15.8726 10.4072 15.8481C10.4108 15.8279 10.4204 15.8015 10.4521 15.77L15.0928 11.1714Z"
            stroke="currentColor"
            strokeWidth="1.52534"
          />
          <path
            d="M17.9746 8.47559C17.9157 8.41613 17.9157 8.3202 17.9746 8.26074L23.4883 2.69727C23.5479 2.63707 23.6454 2.63711 23.7051 2.69727L29.2197 8.26074C29.2786 8.32018 29.2786 8.41613 29.2197 8.47559L23.7051 14.04C23.6454 14.1 23.5479 14.1001 23.4883 14.04L17.9746 8.47559Z"
            stroke="currentColor"
            strokeWidth="1.52534"
          />
        </svg>); }
export function ModelBadge({ model = "Pattern Lab 01", modeTrigger = false, modeSelected = true, onActivate }: { model?: string; modeTrigger?: boolean; modeSelected?: boolean; onActivate?: () => void }) {
  const trigger = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [origin, setOrigin] = useState<{left:number;top:number;width:number;height:number} | null>(null);
  const [active, setActive] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if(!origin) return;
    const el = dialog.current; el?.showModal();
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => setActive(true)); });
    const resized = () => { setActive(false); setOrigin(null); };
    window.addEventListener("resize",resized);
    return () => { cancelAnimationFrame(first); cancelAnimationFrame(second); window.removeEventListener("resize",resized); el?.close(); };
  }, [origin]);
  useEffect(() => () => { if(timer.current) clearTimeout(timer.current); }, []);
  function close() {
    if(timer.current) return;
    setActive(false);
    timer.current = setTimeout(() => { setOrigin(null); timer.current = null; requestAnimationFrame(() => trigger.current?.focus({preventScroll:true})); }, 420);
  }
  return <>
    <button ref={trigger} className={`ai-model-badge ${modeTrigger ? "constructor-mode-ai-info" : ""}`} style={{visibility:origin ? "hidden" : "visible"}} aria-label={modeTrigger ? modeSelected ? "О режиме ИИ-генерация" : "ИИ-генерация" : "О модели Pattern Lab 01"} aria-pressed={modeTrigger ? modeSelected : undefined} aria-haspopup={modeSelected ? "dialog" : undefined} aria-expanded={Boolean(origin)} onClick={() => { if (modeTrigger && !modeSelected) { onActivate?.(); return; } const rect = trigger.current?.getBoundingClientRect(); if(rect) setOrigin({left:rect.left,top:rect.top,width:rect.width,height:rect.height}); }}>{modeTrigger ? <><ModeIcon mode="ai" /><strong><span className="mode-label-short">ИИ</span><span className="mode-label-long">ИИ-генерация</span></strong><ModeIcon mode="info" /></> : <><span>Модель:</span><ModelLogo /><strong>{model}</strong></>}</button>
    {origin ? createPortal(<dialog ref={dialog} className="ai-modal ai-model-modal" data-active={active} aria-label="О модели Pattern Lab 01" onCancel={e => {e.preventDefault();close();}} onClick={e => {if(e.target === e.currentTarget) close();}}>
      <div className="ai-model-morph" data-active={active} style={{"--origin-left":`${origin.left}px`, "--origin-top":`${origin.top}px`, "--origin-width":`${origin.width}px`, "--origin-height":`${origin.height}px`} as React.CSSProperties}>
        <button className="ai-model-expanded" onClick={close} aria-label="Свернуть информацию о модели"><span className="ai-model-name"><small>Модель:</small><span><ModelLogo /><strong>{model}</strong></span></span><p>Наша первая и актуальная ИИ модель для генерации национальных орнаментов. Базируется на SDXL Base 1.0.</p></button><div className="ai-model-collapsed" aria-hidden="true"><span>Модель:</span><ModelLogo /><strong>{model}</strong></div>
      </div>
    </dialog>,document.body) : null}
  </>;
}
