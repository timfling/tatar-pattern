export function ModeIcon({ mode }: { mode: "ai" | "flat" | "info" }) {
  return <span className={`mode-icon mode-icon-${mode}`} aria-hidden="true" />;
}
