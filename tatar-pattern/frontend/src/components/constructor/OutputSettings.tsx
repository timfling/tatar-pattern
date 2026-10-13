"use client";
import type { Capabilities } from "@/lib/api";
export type OutputOptions = { scale: number; transparentBackground: boolean; backgroundColor: string | null; colorMode: "original" | "silhouette"; outputSize: [number,number] | null };
export const DEFAULT_OUTPUT: OutputOptions = { scale: 1, transparentBackground: false, backgroundColor: null, colorMode: "original", outputSize: null };
export function OutputSettings({ capabilities, value, usage, onChange }: { capabilities: Capabilities | null; value: OutputOptions; usage: string | null; onChange: (value: OutputOptions) => void }) {
  const size = value.outputSize ?? (usage ? capabilities?.usageSizes?.[usage] : undefined);
  const landscape = (value.outputSize?.[0] ?? 0) > (value.outputSize?.[1] ?? 1);
  const sizes = capabilities?.outputSizes ?? [];
  const ratios = ["1:1", "3:4", "2:3", "9:16"];
  const index = sizes.findIndex(([w,h]) => value.outputSize && Math.min(w,h) === Math.min(...value.outputSize) && Math.max(w,h) === Math.max(...value.outputSize));
  return <div className="mb-5 flex flex-col gap-4 rounded-2xl bg-white/55 p-4 text-sm">
    {capabilities?.colorModes ? <label className="flex flex-col gap-2">Цвет мотивов<select aria-label="Цвет мотивов" className="rounded-xl border border-hairline/40 bg-white p-3" value={value.colorMode} onChange={e => onChange({ ...value, colorMode: e.target.value as OutputOptions["colorMode"] })}><option value="original">Исходные цвета</option><option value="silhouette">Силуэт · цвета выбранной палитры</option></select></label> : null}
    {sizes.length ? <><label className="flex flex-col gap-2">Формат результата<select aria-label="Соотношение сторон" className="rounded-xl border border-hairline/40 bg-white p-3" value={index} onChange={e => { const selected = sizes[Number(e.target.value)]; onChange({ ...value, outputSize: selected ? landscape ? [selected[1],selected[0]] : selected : null }); }}><option value={-1}>По применению</option>{sizes.map(([w,h],i) => <option key={`${w}-${h}`} value={i}>{landscape ? ratios[i]?.split(":").reverse().join(":") : ratios[i]}</option>)}</select></label>{value.outputSize && value.outputSize[0] !== value.outputSize[1] ? <div role="group" aria-label="Ориентация" className="flex gap-2">{[false,true].map(horizontal => <button key={String(horizontal)} className="studio-button" aria-pressed={horizontal === landscape} onClick={() => { const [w,h] = value.outputSize!; onChange({ ...value, outputSize: horizontal ? [Math.max(w,h),Math.min(w,h)] : [Math.min(w,h),Math.max(w,h)] }); }}>{horizontal ? "Горизонтально" : "Вертикально"}</button>)}</div> : null}</> : null}
    <p>{size ? `${size.join(" × ")} px` : "Размер определяется выбранным применением."}</p>
    {capabilities?.transparentPng ? <label className="flex items-center gap-3"><input type="checkbox" checked={value.transparentBackground} onChange={e => onChange({ ...value, transparentBackground: e.target.checked })} />Прозрачный фон PNG</label> : null}
    <p className="text-xs text-ink-muted">Исходные цвета сохраняют рисунок элемента. Силуэт применяет графическое исполнение и палитру. Прозрачность доступна в PNG; JPG использует подложку выбранной палитры.</p>
  </div>;
}
