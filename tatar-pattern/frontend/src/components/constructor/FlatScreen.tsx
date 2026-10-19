"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "@/components/auth/RequireAuth";
import { api, ApiError, type Capabilities, type Element, type SchemeCatalog } from "@/lib/api";
import { flatSelections, FLAT_ACCEPTED_STATUS } from "@/lib/flat-request";
import { CompositionPicker } from "./CompositionPicker";
import { CatalogPicker } from "./CatalogPicker";
import { OutputSettings, DEFAULT_OUTPUT } from "./OutputSettings";
import { ParameterPanel } from "./ParameterPanel";
import { PARAMETER_TILES, type ParameterTile } from "./parameters";
import { PreflightError } from "./PreflightError";

const ACCEPTED = FLAT_ACCEPTED_STATUS;
export function FlatScreen() {
  const router = useRouter();
  const user = useSession();
  const pendingKey = `tp-flat-pending:${user?.id ?? "session"}`;
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
  const [open,setOpen] = useState<"composition" | "motifs" | "parameters" | "palette" | null>(null);
  const [pending,setPending] = useState(false);
  const [uncertain,setUncertain] = useState(false);
  const [error,setError] = useState<unknown>(null);
  const busy = useRef(false);
  const scheme = catalog?.schemes.find(s => s.id === schemeId);
  async function load() {
    try {
      const [next,caps,elements] = await Promise.all([api.compositionSchemes(),api.capabilities(),api.elements()]);
      setCatalog(next);setCapabilities(caps);setItems(elements.items);setError(null);
    } catch(e) {setError(e);}
  }
  useEffect(() => { queueMicrotask(() => {void load();setUncertain(sessionStorage.getItem(pendingKey) === "true");}); },[pendingKey]);
  const accepted = catalog?.schemes.filter(s => s.reviewStatus === ACCEPTED) ?? [];
  const ready = scheme?.available && scheme.reviewStatus === ACCEPTED && codes.length >= scheme.minimumSelected && codes.length <= scheme.maximumSelected && codes.every(c => scheme.availableElementCodes.includes(c) && scheme.allowedElementCodes.includes(c));
  async function generate() {
    if(!ready || busy.current || uncertain || !scheme || !catalog) return;
    busy.current=true;setPending(true);setError(null);
    const seed = crypto.getRandomValues(new Uint32Array(1))[0] % 2147483648;
    let submitted=false;
    let navigating=false;
    try {
      const selections = flatSelections(catalog,scheme,codes,{parameters:rhythm,palette,...output,...(primary && codes.includes(primary) ? {primaryElementCode:primary} : {}),rapportOutput,moduleSize});
      await api.preflight(selections,seed);
      // Flat has no backend idempotency key. Never automatically repeat an uncertain POST.
      sessionStorage.setItem(pendingKey,"true");submitted=true;
      const {generation}=await api.generate(selections,"",undefined,undefined,"flat",seed);
      sessionStorage.removeItem(pendingKey);
      navigating=true;
      router.push(`/constructor?pattern=${encodeURIComponent(generation.id)}`);
    } catch(e) {
      const ambiguous=submitted && (!(e instanceof ApiError) || !e.status || e.status >= 500);
      setUncertain(ambiguous);if(!ambiguous)sessionStorage.removeItem(pendingKey);setError(e);
    } finally {if(!navigating){busy.current=false;setPending(false);}}
  }
  const tile = open && PARAMETER_TILES.find(t => t.key === open);
  const parameterTile: ParameterTile | null = tile ? {...tile,options:tile.options.filter(o => open === "parameters" ? capabilities?.parameters?.includes(o.value) : capabilities?.palettes?.includes(o.value))} : null;
  return <section className="studio-page"><div className="studio-article flat-workspace">
    <h1>Параметрический рисунок</h1><p>Выберите схему и совместимые мотивы, настройте ритм, фон и размер. Flat размещает исходные мотивы по параметрам без GPU. Историческая атрибуция относится к мотивам; новая раскладка — современная дизайнерская композиция.</p>
    <p><Link href="/constructor" className="underline">AI-вариант выбранной основы ↗</Link></p>
    {catalog?.acceptedCoveredElementCount !== undefined ? <p>Принятые схемы поддерживают {catalog.acceptedCoveredElementCount} из {catalog.totalElements} мотивов реестра. Остальные мотивы пока не доступны в этом сценарии.</p> : null}
    <p role="status">{catalog ? `${accepted.length} принятых схем; ${(catalog.registeredSchemeCount ?? catalog.schemes.length)-accepted.length} ожидают оценки и недоступны для новой работы. Доступность исходных файлов проверяется отдельно.` : "Загружаем схемы…"}</p>
    <div className="my-6 grid gap-3 sm:grid-cols-2">
      <button className="studio-button" onClick={() => setOpen("composition")}>Схема: {scheme?.titleRu ?? "выберите"}</button>
      <button className="studio-button" disabled={!scheme} onClick={() => setOpen("motifs")}>Мотивы: {codes.length} выбрано</button>
      <button className="studio-button" onClick={() => setOpen("parameters")}>Ритм: {PARAMETER_TILES.find(t => t.key === "parameters")?.options.find(o => o.value === rhythm)?.label}</button>
      <button className="studio-button" onClick={() => setOpen("palette")}>Фон: {PARAMETER_TILES.find(t => t.key === "palette")?.options.find(o => o.value === palette)?.label}</button>
    </div>
    {scheme ? <><p>{scheme.descriptionRu}</p><p className="text-sm">Исходные цвета мотивов сохранены. Палитра меняет подложку. Принятие примера не гарантирует размещение любого ручного набора; сервер проверяет геометрию перед созданием.</p>
      {scheme.centerCandidates.some(c => codes.includes(c)) ? <label className="my-4 flex flex-col gap-2">Главный мотив<select className="rounded-xl bg-white p-3" value={primary} onChange={e => setPrimary(e.target.value)}><option value="">По схеме</option>{scheme.centerCandidates.filter(c => codes.includes(c)).map(c => <option key={c}>{c}</option>)}</select></label> : null}
    </> : null}
    <OutputSettings capabilities={capabilities} compositionRenderer value={output} usage="textile" onChange={setOutput} />
    {scheme?.composition === "rapport" ? <div className="my-4 flex flex-col gap-3"><label>Экспорт раппорта<select className="ml-2 rounded-xl bg-white p-3" value={rapportOutput} onChange={e => setRapportOutput(e.target.value as "module" | "sample")}><option value="module">Модуль повтора</option><option value="sample">Образец заданного размера</option></select></label><label className="flex items-center gap-2"><input type="checkbox" checked={Boolean(moduleSize)} onChange={e => setModuleSize(e.target.checked ? [1024,1024] : null)} />Задать размер модуля</label>{moduleSize ? <div className="flex flex-wrap gap-3">{[0,1].map(i => <label key={i}>{i === 0 ? "Ширина" : "Высота"}<input className="ml-2 w-24 rounded-xl bg-white p-2" type="number" min={256} max={2048} value={moduleSize[i]} onChange={e => setModuleSize(i === 0 ? [Number(e.target.value),moduleSize[1]] : [moduleSize[0],Number(e.target.value)])} /></label>)}</div> : null}<p className="text-sm">Модуль имеет свой фактический размер. Некратный ему образец не бесшовный. Стыки проверьте в просмотре повтора.</p></div> : null}
    {error ? <PreflightError error={error} /> : null}
    {uncertain ? <div role="alert" className="api-error">Ответ на создание не подтверждён. Новый запрос заблокирован, чтобы не создать вторую работу. <Link className="underline" href="/library">Проверьте историю</Link>.<button className="studio-button mt-3" onClick={() => {sessionStorage.removeItem(pendingKey);setUncertain(false);}}>История проверена — разрешить новую работу</button></div> : null}
    <div className="my-6 flex flex-wrap gap-3"><button className="studio-button" disabled={!ready || pending || uncertain} onClick={generate}>{pending ? "Проверяем и создаём…" : "Создать рисунок"}</button><button className="studio-button" disabled={pending} onClick={load}>Обновить каталог</button><Link className="studio-button" href="/library">История и скачивание ↗</Link></div>
    {open === "composition" ? <CompositionPicker acceptedOnly capabilities={capabilities} items={items} renderer="composition-v2" composition={scheme?.composition ?? null} borderLayout="registers" schemeCatalog={catalog} schemeId={schemeId} onScheme={s => {setSchemeId(s.id);setCodes(s.defaultElementCodes);setPrimary("");setOutput(v => ({...v,colorMode:"original"}));setOpen(null);setError(null);}} onSelect={() => {}} onClose={() => setOpen(null)} /> : open === "motifs" ? <CatalogPicker items={items.filter(item => scheme?.allowedElementCodes.includes(item.code))} value={codes} max={scheme?.maximumSelected ?? capabilities?.maxSelectedElements ?? 16} composition={scheme?.composition} scheme={scheme} roleLabels={catalog?.roleLabelsRu} onChange={setCodes} onClose={() => setOpen(null)} /> : parameterTile ? <ParameterPanel tile={parameterTile} value={open === "parameters" ? rhythm : palette} onConfirm={v => {if(typeof v === "string"){if(open === "parameters")setRhythm(v);else setPalette(v);}}} onClose={() => setOpen(null)} /> : null}
  </div></section>;
}
