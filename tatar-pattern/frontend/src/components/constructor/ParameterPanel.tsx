"use client";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import type { ParameterSelection, ParameterTile } from "@/components/constructor/parameters";
export function ParameterPanel({ tile, value, onConfirm, onClose, children }: { tile: ParameterTile; value: ParameterSelection; onConfirm: (value: ParameterSelection) => void; onClose: () => void; children?: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { dialog.current?.showModal(); }, []);
  return <dialog ref={dialog} onCancel={onClose} onClick={e => { if(e.target === e.currentTarget) onClose(); }} aria-labelledby="parameter-title" className="studio-dialog">
    <header className="mb-5 flex items-center justify-between gap-4"><h2 id="parameter-title" className="font-display text-2xl italic">{tile.pickerTitle}</h2><button className="studio-button" onClick={onClose}>Готово</button></header>
    {children}
    <div className="grid gap-3 sm:grid-cols-2">{tile.options.map(option => { const selected = Array.isArray(value) ? value.includes(option.value) : value === option.value; return <button key={option.value} aria-pressed={selected} onClick={() => onConfirm(tile.multi ? selected ? (value as string[]).filter(v => v !== option.value) : [...(Array.isArray(value) ? value : []),option.value] : option.value)} className={`parameter-choice rounded-2xl border p-4 text-left ${selected ? "border-[#356052] bg-[#356052]/10" : "border-hairline/40 bg-white/65"}`}><span className="block text-lg font-semibold">{option.label}{selected ? " ✓" : ""}</span><span className="mt-2 block text-sm leading-relaxed text-ink-muted">{["parameters","palette"].includes(tile.key) ? option.description.split(/(?<=[.!?])\s/)[0] : option.description}</span></button>; })}</div>
  </dialog>;
}
