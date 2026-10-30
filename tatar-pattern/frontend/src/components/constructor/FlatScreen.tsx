"use client";
import { useEffect, useRef, useState } from "react";
import { SendArrow } from "@/components/ui/SendArrow";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { ParameterCard } from "./ParameterCard";
import { AiOptionDialog } from "./AiOptionDialog";
import { SettingsDialog } from "./SettingsDialog";
import { api, ApiError, type Capabilities, type Element, type SchemeCatalog, type GuestRequest, type Selections } from "@/lib/api";
import { flatSelections, FLAT_ACCEPTED_STATUS } from "@/lib/flat-request";
import { CompositionPicker } from "./CompositionPicker";
import { CatalogPicker } from "./CatalogPicker";
import { OutputSettings, DEFAULT_OUTPUT } from "./OutputSettings";
import { PARAMETER_TILES } from "./parameters";
import { PreflightError } from "./PreflightError";

type FlatOption = "composition" | "motifs" | "scale" | "rhythm" | "background" | "format";
const BACKGROUNDS = [
  { id: "porcelain", title: "Светлый", color: "#efe7d7", description: "Светлая подложка. Цвета самих мотивов сохраняются." },
  { id: "emerald", title: "Зелёный", color: "#123f34", description: "Тёмная зелёная подложка. Цвета самих мотивов сохраняются." },
  { id: "leather", title: "Коричневый", color: "#3b251a", description: "Тёплая коричневая подложка. Цвета самих мотивов сохраняются." },
];
export function FlatScreen({ onGenerate, initialSelections }: { onGenerate: (body: GuestRequest) => Promise<void>; initialSelections?: Selections | null }) {
  const [catalog,setCatalog] = useState<SchemeCatalog | null>(null);
  const [capabilities,setCapabilities] = useState<Capabilities | null>(null);
  const [items,setItems] = useState<Element[]>([]);
  const [schemeId,setSchemeId] = useState("");
  const [codes,setCodes] = useState<string[]>([]);
  const [primary,setPrimary] = useState("");
  const [rhythm,setRhythm] = useState("default");
  const [palette,setPalette] = useState("porcelain");
  const [output,setOutput] = useState(DEFAULT_OUTPUT);
  const [rapportOutput,setRapportOutput] = useState<"module" | "sample">("module");
  const [moduleSize,setModuleSize] = useState<[number,number] | null>(null);
  const [open,setOpen] = useState<FlatOption | null>(null);
  const [pending,setPending] = useState(false);
  const [checking,setChecking] = useState(true);
  const [error,setError] = useState<unknown>(null);
  const [catalogRevision,setCatalogRevision] = useState(0);
  const busy = useRef(false);
  const scheme = catalog?.schemes.find(s => s.id === schemeId);
  // A retry only refreshes read-only catalog data; selections and guest work are untouched.
  useEffect(() => {
    const controller = new AbortController();
    let retry: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    async function load() {
      try {
        const [next,caps,elements] = await Promise.all([api.compositionSchemes(controller.signal),api.capabilities(),api.elements(controller.signal)]);
        if(controller.signal.aborted) return;
        setCatalog(next);setCapabilities(caps);setItems(elements.items);setChecking(false);
      } catch {
        if(controller.signal.aborted) return;
        retry=setTimeout(load, Math.min(15000,1500 * 2 ** attempt++));
      }
    }
    void load();
    return () => {controller.abort();clearTimeout(retry);};
  },[catalogRevision]);
  useEffect(() => {
    const refresh=()=>{setChecking(true);setCatalogRevision(v=>v+1);};
    window.addEventListener("tp:catalog-refresh",refresh);
    return ()=>window.removeEventListener("tp:catalog-refresh",refresh);
  },[]);
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
    });
    return () => { active = false; };
  }, [initialSelections]);
  const ready = !checking && scheme?.available && scheme.reviewStatus === FLAT_ACCEPTED_STATUS && codes.length >= scheme.minimumSelected && codes.length <= scheme.maximumSelected && codes.every(c => scheme.availableElementCodes.includes(c) && scheme.allowedElementCodes.includes(c));
  async function generate() {
    if(!ready || busy.current || !scheme || !catalog) return;
    busy.current=true;setPending(true);setError(null);
    const seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483648;
    try {
      const selections = flatSelections(catalog,scheme,codes,{parameters:rhythm,palette,...output,...(primary && codes.includes(primary) ? {primaryElementCode:primary} : {}),rapportOutput,moduleSize});
      await onGenerate({mode:"flat",requestId:crypto.randomUUID(),selections,seed});
    } catch(e) {
      if(e instanceof ApiError && ["CATALOG_BUSY","SCHEME_REGISTRY_CHANGED"].includes(e.code)) {setChecking(true);setCatalogRevision(v=>v+1);} else setError(e);
    } finally {busy.current=false;setPending(false);}
  }
  const rhythms = PARAMETER_TILES.find(t=>t.key==="parameters")!.options.filter(o=>capabilities?.parameters?.includes(o.value));
  const tiles: {key:FlatOption;label:string;value:string;set:boolean}[] = [
    {key:"composition",label:"Композиция",value:scheme?.titleRu ?? "Выберите",set:Boolean(scheme)},
    {key:"motifs",label:"Мотивы",value:codes.length ? `${codes.length} выбрано` : "Выберите",set:Boolean(codes.length)},
    {key:"scale",label:"Масштаб",value:`${output.scale.toFixed(1)}×`,set:true},
    {key:"rhythm",label:"Ритм",value:rhythms.find(o=>o.value===rhythm)?.label ?? "По умолчанию",set:true},
    {key:"background",label:"Фон",value:output.transparentBackground ? "Прозрачный PNG" : output.backgroundColor ? "Свой цвет" : BACKGROUNDS.find(p=>p.id===palette)?.title ?? "Светлый",set:true},
    {key:"format",label:"Формат",value:output.outputSize ? `${output.outputSize.join(" × ")} px` : "1024 × 1024 px",set:true},
  ];
  const corners = ["top-left", "none", "top-right", "bottom-left", "none", "bottom-right"] as const;
  const mobileCorners = ["top-left", "top-right", "none", "none", "bottom-left", "bottom-right"] as const;
  const close=()=>setOpen(null);
  return <><div className="ai-constructor-body flat-workspace">
    <h1>Соберите орнаментальный узор</h1>
    <div className="ai-parameter-grid">{tiles.map((tile,i)=><ParameterCard key={tile.key} label={tile.label} value={tile.value} isSet={tile.set} corner={corners[i]} mobileCorner={mobileCorners[i]} compactValue ghost={open===tile.key} onClick={()=>setOpen(tile.key)} />)}</div>
    {error ? <div className="constructor-form-error"><PreflightError error={error} /></div> : null}
    <div className="ai-generate-area"><button className="ai-generate" disabled={!ready || pending} onClick={generate}><span><ModeIcon mode="flat" />{pending ? "Создаём узор…" : "Сгенерировать узор"}</span><span className="ai-generate-arrow"><SendArrow /></span></button></div>
    {open==="scale" ? <SettingsDialog title="Масштаб" description="Меняет размер мотивов относительно схемы. Начните с 1×. Слишком крупные мотивы могут не поместиться; в этом случае настройки сохранятся, и мы подскажем, что изменить." onClose={close}><label>Размер мотивов · {output.scale.toFixed(1)}×<input aria-label="Масштаб мотивов" type="range" min={capabilities?.scaleRange?.[0] ?? .5} max={capabilities?.scaleRange?.[1] ?? 2} step="0.1" value={output.scale} onChange={e=>setOutput({...output,scale:Number(e.target.value)})} /></label></SettingsDialog> : null}
    {open==="rhythm" ? <AiOptionDialog label="Ритм" options={rhythms.map(o=>({id:o.value,title:o.label,description:o.description}))} selected={rhythm} confirmLabel="Выбрать этот ритм" onSelect={setRhythm} onClose={close} /> : null}
    {open==="background" ? <SettingsDialog title="Фон" description="Меняет подложку узора. Цвета мотивов остаются родными. Прозрачность PNG выберите до создания: JPG всегда сохраняется с фоном." onClose={close}><div className="background-choices">{BACKGROUNDS.filter(p=>capabilities?.palettes?.includes(p.id)).map(p=><button className="studio-button" key={p.id} aria-pressed={!output.backgroundColor && palette===p.id} onClick={()=>{setPalette(p.id);setOutput({...output,backgroundColor:null});}}><i style={{background:p.color}} />{p.title}</button>)}</div><label>Свой цвет фона<input aria-label="Свой цвет фона" type="color" value={output.backgroundColor ?? BACKGROUNDS.find(p=>p.id===palette)?.color ?? "#efe7d7"} onChange={e=>setOutput({...output,backgroundColor:e.target.value})} /></label>{capabilities?.transparentPng ? <label className="settings-checkbox"><input type="checkbox" checked={output.transparentBackground} onChange={e=>setOutput({...output,transparentBackground:e.target.checked})} />Прозрачный фон PNG</label> : null}</SettingsDialog> : null}
    {open==="format" ? <SettingsDialog title="Формат" description="Выберите размеры и ориентацию изображения. Для повторяющегося узора модуль — одна плитка повтора, образец — фрагмент заданного размера. Проверьте стыки в просмотре 3×3." onClose={close}><OutputSettings capabilities={capabilities ? {...capabilities,scaleRange:undefined,transparentPng:false} : null} compositionRenderer value={output} usage="textile" onChange={setOutput} />{scheme?.composition==="rapport" ? <><label>Результат<select value={rapportOutput} onChange={e=>setRapportOutput(e.target.value as "module"|"sample")}><option value="module">Модуль повтора</option><option value="sample">Образец заданного размера</option></select></label><label className="settings-checkbox"><input type="checkbox" checked={Boolean(moduleSize)} onChange={e=>setModuleSize(e.target.checked ? [1024,1024] : null)} />Задать размер модуля</label>{moduleSize ? <div className="module-dimensions">{[0,1].map(i=><label key={i}>{i===0 ? "Ширина модуля" : "Высота модуля"}<input type="number" min={256} max={2048} value={moduleSize[i]} onChange={e=>setModuleSize(i===0 ? [Number(e.target.value),moduleSize[1]] : [moduleSize[0],Number(e.target.value)])} /></label>)}</div> : null}</> : null}</SettingsDialog> : null}
    {open==="composition" ? <CompositionPicker acceptedOnly capabilities={capabilities} items={items} renderer="composition-v2" composition={scheme?.composition ?? null} borderLayout="registers" schemeCatalog={catalog} schemeId={schemeId} onScheme={s=>{setSchemeId(s.id);setCodes(s.defaultElementCodes);setPrimary("");setOpen(null);setError(null);}} onSelect={()=>{}} onClose={close} /> : open==="motifs" ? <CatalogPicker items={items.filter(item=>scheme?.allowedElementCodes.includes(item.code))} value={codes} max={scheme?.maximumSelected ?? capabilities?.maxSelectedElements ?? 16} scheme={scheme} onChange={next=>{setCodes(next);if(!next.includes(primary))setPrimary("");}} onClose={close}>{scheme?.centerCandidates.some(c=>codes.includes(c)) ? <label className="primary-motif">Главный мотив<select value={primary} onChange={e=>setPrimary(e.target.value)}><option value="">По схеме</option>{scheme.centerCandidates.filter(c=>codes.includes(c)).map(c=><option key={c} value={c}>{items.find(item=>item.code===c)?.nameRu ?? "Мотив"}</option>)}</select></label> : null}</CatalogPicker> : null}
  </div>{checking ? <p className="ai-result-reminder catalog-checking" role="status">Идет проверка каталога. Если элементы не отображаются долго, попробуйте перезагрузить страницу</p> : null}</>;
}
