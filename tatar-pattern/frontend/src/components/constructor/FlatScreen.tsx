"use client";
import { useEffect, useRef, useState } from "react";
import { SendArrow } from "@/components/ui/SendArrow";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { ParameterCard } from "./ParameterCard";
import { AiModal } from "./AiOptionDialog";
import { api, type Capabilities, type Element, type SchemeCatalog, type GuestRequest, type Selections } from "@/lib/api";
import { flatSelections, FLAT_ACCEPTED_STATUS } from "@/lib/flat-request";
import { CompositionPicker } from "./CompositionPicker";
import { CatalogPicker } from "./CatalogPicker";
import { OutputSettings, DEFAULT_OUTPUT } from "./OutputSettings";
import { ParameterPanel } from "./ParameterPanel";
import { PARAMETER_TILES, type ParameterTile } from "./parameters";
import { PreflightError } from "./PreflightError";

const ACCEPTED = FLAT_ACCEPTED_STATUS;
export function FlatScreen({ onGenerate, initialSelections }: { onGenerate: (body: GuestRequest) => Promise<void>; initialSelections?: Selections | null }) {
  const [catalog,setCatalog] = useState<SchemeCatalog | null>(null);
  const [capabilities,setCapabilities] = useState<Capabilities | null>(null);
  const [items,setItems] = useState<Element[]>([]);
  const [touched, setTouched] = useState<string[]>([]);
  const touch = (key: string) => setTouched(v => v.includes(key) ? v : [...v,key]);
  const [schemeId,setSchemeId] = useState("");
  const [codes,setCodes] = useState<string[]>([]);
  const [primary,setPrimary] = useState("");
  const [rhythm,setRhythm] = useState("default");
  const [palette,setPalette] = useState("porcelain");
  const [output,setOutput] = useState(DEFAULT_OUTPUT);
  const [rapportOutput,setRapportOutput] = useState<"module" | "sample">("module");
  const [moduleSize,setModuleSize] = useState<[number,number] | null>(null);
  const [open,setOpen] = useState<"composition" | "motifs" | "parameters" | "palette" | "execution" | "usage" | null>(null);
  const [pending,setPending] = useState(false);
  const [error,setError] = useState<unknown>(null);
  const busy = useRef(false);
  const scheme = catalog?.schemes.find(s => s.id === schemeId);
  async function load() {
    try {
      const [next,caps,elements] = await Promise.all([api.compositionSchemes(),api.capabilities(),api.elements()]);
      setCatalog(next);setCapabilities(caps);setItems(elements.items);setError(null);
    } catch(e) {setError(e);}
  }
  useEffect(() => { queueMicrotask(() => {void load();}); },[]);
  useEffect(() => {
    if (!initialSelections) return;
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setSchemeId(initialSelections.schemeId ?? "");
      setCodes(initialSelections.elementCodes ?? []);
      setPrimary(initialSelections.primaryElementCode ?? "");
      setRhythm(initialSelections.parameters ?? "default");
      setPalette(initialSelections.palette ?? "porcelain");
      setOutput({ ...DEFAULT_OUTPUT, scale: initialSelections.scale ?? 1, transparentBackground: initialSelections.transparentBackground ?? false, backgroundColor: initialSelections.backgroundColor ?? null, outputSize: initialSelections.outputSize ?? null });
      setRapportOutput(initialSelections.rapportOutput ?? "module");
      setModuleSize(initialSelections.moduleSize ?? null);
      setTouched(["parameters", "palette", "execution", "usage"]);
    });
    return () => { active = false; };
  }, [initialSelections]);
  const ready = scheme?.available && scheme.reviewStatus === ACCEPTED && codes.length >= scheme.minimumSelected && codes.length <= scheme.maximumSelected && codes.every(c => scheme.availableElementCodes.includes(c) && scheme.allowedElementCodes.includes(c));
  async function generate() {
    if(!ready || busy.current || !scheme || !catalog) return;
    busy.current=true;setPending(true);setError(null);
    const seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483648;
    try {
      const selections = flatSelections(catalog,scheme,codes,{parameters:rhythm,palette,...output,...(primary && codes.includes(primary) ? {primaryElementCode:primary} : {}),rapportOutput,moduleSize});
      await onGenerate({mode:"flat",requestId:crypto.randomUUID(),selections,seed});
    } catch(e) {
      setError(e);
    } finally {busy.current=false;setPending(false);}
  }
  const tile = (open === "parameters" || open === "palette") && PARAMETER_TILES.find(t => t.key === open);
  const parameterTile: ParameterTile | null = tile ? {...tile,options:tile.options.filter(o => open === "parameters" ? capabilities?.parameters?.includes(o.value) : capabilities?.palettes?.includes(o.value))} : null;
  const tiles = [
    { key: "composition", label: "Композиция", value: scheme?.titleRu ?? "Выберите", set: Boolean(scheme) },
    { key: "motifs", label: "Мотивы", value: codes.length ? `${codes.length} выбрано` : "Выберите", set: Boolean(codes.length) },
    { key: "parameters", label: "Масштаб и ритм", value: `${output.scale.toFixed(1)}× · ${PARAMETER_TILES.find(t => t.key === "parameters")?.options.find(o => o.value === rhythm)?.label ?? "Обычный"}`, set: true },
    { key: "palette", label: "Палитра", value: PARAMETER_TILES.find(t => t.key === "palette")?.options.find(o => o.value === palette)?.label ?? "Выберите", set: true },
    { key: "execution", label: "Исполнение", value: "Исходные цвета", set: true },
    { key: "usage", label: "Применение", value: output.outputSize ? `${output.outputSize.join(" × ")} px` : "Настройте формат", set: Boolean(output.outputSize) },
  ] as const;
  const corners = ["top-left", "none", "top-right", "bottom-left", "none", "bottom-right"] as const;
  const mobileCorners = ["top-left", "top-right", "none", "none", "bottom-left", "bottom-right"] as const;
  return <div className="ai-constructor-body flat-workspace">
    <h1>Соберите орнаментальный узор</h1>
    <div className="ai-parameter-grid">{tiles.map((tile, i) => <ParameterCard key={tile.key} label={tile.label} value={tile.set && (tile.key === "composition" || tile.key === "motifs" || touched.includes(tile.key)) ? tile.value : "Выберите"} isSet={tile.set && (tile.key === "composition" || tile.key === "motifs" || touched.includes(tile.key))} corner={corners[i]} mobileCorner={mobileCorners[i]} compactValue ghost={open === tile.key} onClick={() => setOpen(tile.key)} />)}</div>
    {error ? <div className="constructor-form-error"><PreflightError error={error} /><button className="studio-button" onClick={load}>Повторить загрузку каталога</button></div> : null}
    <div className="ai-generate-area"><button className="ai-generate" disabled={!ready || pending} onClick={generate}><span><ModeIcon mode="flat" />{pending ? "Создаём узор…" : "Сгенерировать узор"}</span><span className="ai-generate-arrow"><SendArrow /></span></button></div>
    {open === "execution" ? <AiModal label="Исполнение" onClose={() => setOpen(null)}><div className="constructor-settings"><h2>Исходные цвета</h2><button className="studio-button" onClick={() => {touch("execution");setOpen(null);}}>Готово</button></div></AiModal> : null}
    {open === "usage" ? <AiModal label="Применение и формат" onClose={() => setOpen(null)}><div className="constructor-settings"><h2>Применение и формат</h2><OutputSettings capabilities={capabilities ? {...capabilities,scaleRange:undefined} : null} compositionRenderer value={output} usage="textile" onChange={v => {setOutput(v);touch("usage");}} />
    {scheme?.composition === "rapport" ? <div className="my-4 flex flex-col gap-3"><label>Экспорт раппорта<select className="ml-2 rounded-xl bg-white p-3" value={rapportOutput} onChange={e => setRapportOutput(e.target.value as "module" | "sample")}><option value="module">Модуль повтора</option><option value="sample">Образец заданного размера</option></select></label><label className="flex items-center gap-2"><input type="checkbox" checked={Boolean(moduleSize)} onChange={e => setModuleSize(e.target.checked ? [1024,1024] : null)} />Задать размер модуля</label>{moduleSize ? <div className="flex flex-wrap gap-3">{[0,1].map(i => <label key={i}>{i === 0 ? "Ширина" : "Высота"}<input className="ml-2 w-24 rounded-xl bg-white p-2" type="number" min={256} max={2048} value={moduleSize[i]} onChange={e => setModuleSize(i === 0 ? [Number(e.target.value),moduleSize[1]] : [moduleSize[0],Number(e.target.value)])} /></label>)}</div> : null}</div> : null}
    <button className="studio-button" onClick={() => setOpen(null)}>Готово</button></div></AiModal> : null}
    {open === "composition" ? <CompositionPicker acceptedOnly capabilities={capabilities} items={items} renderer="composition-v2" composition={scheme?.composition ?? null} borderLayout="registers" schemeCatalog={catalog} schemeId={schemeId} onScheme={s => {setSchemeId(s.id);setCodes(s.defaultElementCodes);setPrimary("");setOutput(v => ({...v,colorMode:"original"}));setOpen(null);setError(null);}} onSelect={() => {}} onClose={() => setOpen(null)} /> : open === "motifs" ? <CatalogPicker items={items.filter(item => scheme?.allowedElementCodes.includes(item.code))} value={codes} max={scheme?.maximumSelected ?? capabilities?.maxSelectedElements ?? 16} composition={scheme?.composition} scheme={scheme} roleLabels={catalog?.roleLabelsRu} onChange={setCodes} onClose={() => setOpen(null)} /> : parameterTile ? <ParameterPanel tile={parameterTile} value={open === "parameters" ? rhythm : palette} onConfirm={v => {if(typeof v === "string"){if(open === "parameters"){setRhythm(v);touch("parameters");}else {setPalette(v);touch("palette");}}}} onClose={() => setOpen(null)} >{open === "parameters" ? <div className="mb-5 grid gap-4">{capabilities?.scaleRange ? <label>Масштаб мотивов · {output.scale.toFixed(1)}×<input aria-label="Масштаб мотивов" className="block w-full mt-3" type="range" min={capabilities.scaleRange[0]} max={capabilities.scaleRange[1]} step="0.1" value={output.scale} onChange={e => {setOutput({...output,scale:Number(e.target.value)});touch("parameters");}} /></label> : null}{scheme?.centerCandidates.some(c => codes.includes(c)) ? <label>Главный мотив<select className="ml-3 rounded-xl bg-white p-3" value={primary} onChange={e => setPrimary(e.target.value)}><option value="">По схеме</option>{scheme.centerCandidates.filter(c => codes.includes(c)).map(c => <option key={c}>{c}</option>)}</select></label> : null}</div> : null}</ParameterPanel> : null}
  </div>;
}
