"use client";
import type { ReactNode } from "react";
import { AiModal } from "./AiOptionDialog";

export function SettingsDialog({ title, description, children, onClose }: { title: string; description: string; children: ReactNode; onClose: () => void }) {
  return <AiModal label={title} onClose={onClose} className="settings-modal"><div className="ai-picker-surface settings-surface">
    <div className="ai-option-description"><h2>{title}</h2><p>{description}</p><button className="ai-confirm ai-confirm-desktop" onClick={onClose}>Готово</button></div>
    <div className="ai-option-divider" /><div className="settings-controls">{children}</div>
  </div><button className="ai-confirm ai-confirm-mobile" onClick={onClose}>Готово</button></AiModal>;
}
