"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { ParameterCard } from "./ParameterCard";
import { AiModal, AiOptionDialog, type AiOption } from "./AiOptionDialog";
import { SendArrow } from "@/components/ui/SendArrow";
import { ModeSelector, type ConstructorMode } from "./ModeSelector";
import { FlatScreenV3 } from "./v3/FlatScreenV3";
import { ResultV3 } from "./v3/ResultV3";
import { v3Api, v3GuestRequest, randomSeeds, saveV3Session, updateV3Session, v3Session, type V3Params, type V3Variant, type V3Info } from "@/lib/v3";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { GeneratingView } from "./GeneratingView";
import { ResultView } from "./ResultView";
import { FullscreenView } from "./FullscreenView";
import { ExportMenu } from "./ExportMenu";
import { DEFAULT_PATTERN_NAME, formatPatternStamp } from "./data";
import { emptySelections, PARAMETER_TILES } from "./parameters";
import { api, apiUrl, apiMessage, ApiError, type AiBaseCatalog, type GuestGeneration as Generation, type Element, type OrnamentStyle, type GuestRequest } from "@/lib/api";
import { aiRequest, ORNAMENT_STYLES, randomSeed, unavailableText } from "@/lib/ai-mvp";
import { startWork, rememberGeneration, blockWork, forgetWork, forgetRecent, expiryText } from "@/lib/guest-work";
import { useShell } from "@/components/layout/shell-context";
import { CreateNotice } from "@/components/guest/CreateNotice";
import { AiUnavailable } from "./AiUnavailable";

type TileKey = "base" | "variant" | "style";
type Stage = "form" | "generating" | "result" | "v3";
const corners = ["top-left", "none", "top-right", "bottom-left", "none", "bottom-right"] as const;
const mobileCorners = ["top-left", "top-right", "none", "none", "bottom-left", "bottom-right"] as const;

export function ConstructorScreen({ initialPatternId, initialV3Session, returnToLibrary = false, initialMode = "flat" }: { initialPatternId?: string; initialV3Session?: string; returnToLibrary?: boolean; initialMode?: ConstructorMode }) {
  const router = useRouter();
  const [mode, setMode] = useState<ConstructorMode>(initialMode);
  const { screenEl, setConstructorClick, setBackHandler, setShowBack } = useShell();
  const [catalog, setCatalog] = useState<AiBaseCatalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [baseId, setBaseId] = useState<string | null>(null);
  const [style, setStyle] = useState<OrnamentStyle | null>(null);
  const [seed, setSeed] = useState(20261008);
  const [open, setOpen] = useState<TileKey | null>(null);
  const [stage, setStage] = useState<Stage>("form");
  const [generation, setGeneration] = useState<Generation | null>(null);
  const [legacyElements,setLegacyElements] = useState<Element[]>([]);
  const [ready, setReady] = useState(!initialPatternId);
  const [error, setError] = useState("");
  const [confirmStop, setConfirmStop] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [imageError, setImageError] = useState(false);
  const request = useRef<AbortController | null>(null);
  // Конструктор v3: варианты считаются быстро (превью), полный файл сохраняется только при экспорте.
  const [v3Variants,setV3Variants] = useState<V3Variant[]>([]);
  const [v3Index,setV3IndexState] = useState(0);
  const [v3Params,setV3Params] = useState<V3Params | null>(null);
  const [v3SessionId,setV3SessionId] = useState<string | null>(null);
  const [v3Missing,setV3Missing] = useState(false);
  const [v3Busy,setV3Busy] = useState(false);
  const [v3MoreBusy,setV3MoreBusy] = useState(false);
  const [v3ExportBusy,setV3ExportBusy] = useState(false);
  const [v3Notice,setV3Notice] = useState("");
  const v3Saved = useRef(new Map<string,Generation>());
  const setV3Index = (i: number) => { setV3IndexState(i); if (v3SessionId) updateV3Session(v3SessionId, { index: i }); };
  const v3Request = useRef<AbortController | null>(null);
  const submitting = useRef(false);
  const base = catalog?.bases.find(item => item.id === baseId);
  const profile = base?.styles.find(item => item.id === style);
  const canSubmit = Boolean(base && profile?.available && profile.profileVersion && !catalogError);


  async function loadCatalog() {
    try { const next = await api.aiBases(); setCatalog(next); setCatalogError(""); return next; }
    catch(e) { setCatalogError(apiMessage(e)); return null; }
  }
  useEffect(() => {
    const controller = new AbortController();
    api.aiBases(controller.signal).then(setCatalog).catch(e => { if(!controller.signal.aborted) setCatalogError(apiMessage(e)); });
    return () => controller.abort();
  }, []);

  function applyGeneration(g: Generation) {
    setGeneration(g); rememberGeneration(g); setImageError(false);
    if(g.ai) { setBaseId(g.ai.baseId); setStyle(g.ai.ornamentStyle); }
    if(typeof g.seed === "number") setSeed(g.seed);
    else if(typeof g.recipe?.seed === "number") setSeed(g.recipe.seed);
  }
  async function waitForResult(first: Generation, controller: AbortController) {
    let current = first;
    while(!controller.signal.aborted) {
      applyGeneration(current);
      if(current.status === "done") {
        if(!current.imageUrl) throw new Error("Сервис завершил задание без изображения. Результат недоступен.");
        setStage("result");
        if(initialPatternId !== current.id) router.replace(`/constructor?pattern=${encodeURIComponent(current.id)}${returnToLibrary ? "&from=library" : ""}`);
        return;
      }
      if(!["queued","processing"].includes(current.status)) { throw new Error(typeof current.error === "string" ? current.error : current.error?.message ?? "Задание не завершилось. Новая работа возможна только отдельным действием."); }
      setStage("generating");
      await new Promise<void>((resolve,reject) => {
        const stop = () => { clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); };
        const timer = setTimeout(() => { controller.signal.removeEventListener("abort",stop); resolve(); },1500);
        controller.signal.addEventListener("abort",stop,{once:true});
      });
      current = (await api.guestGeneration(current.id,controller.signal)).generation;
    }
  }
  useEffect(() => {
    if(!initialPatternId) return;
    const controller = new AbortController(); request.current = controller;
    api.guestGeneration(initialPatternId,controller.signal).then(({generation}) => {setReady(true);return waitForResult(generation,controller);})
      .catch(e => {if(!controller.signal.aborted) {blockWork(e);setError(apiMessage(e));setStage("form");}})
      .finally(() => {if(!controller.signal.aborted) setReady(true);});
    return () => controller.abort();
    // The page remounts for a different saved ID; catalog never controls reopening.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPatternId]);
  useEffect(() => {
    if(!generation?.selections?.elementCodes?.length) return;
    const controller = new AbortController();
    api.elements(controller.signal).then(({items}) => setLegacyElements(items)).catch(() => {});
    return () => controller.abort();
  },[generation?.id, generation?.selections?.elementCodes?.length]);
  useEffect(() => () => { request.current?.abort(); v3Request.current?.abort(); }, []);
  // Набор вариантов v3 из «Недавних генераций» открывается без нового запроса к серверу.
  // Читается после гидрации: на сервере памяти вкладки нет.
  useEffect(() => {
    if (!initialV3Session) return;
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      const s = v3Session(initialV3Session);
      if (!s) { setV3Missing(true); return; }
      for (const [seed, g] of Object.entries(s.saved)) v3Saved.current.set(JSON.stringify([s.params, Number(seed)]), g);
      setV3SessionId(s.id); setV3Params(s.params); setV3Variants(s.variants); setV3IndexState(s.index); setStage("v3");
    });
    return () => { active = false; };
  }, [initialV3Session]);

  async function v3Generate(params: V3Params, more = false) {
    if (v3Busy || v3MoreBusy) return;
    v3Request.current?.abort(); const controller = new AbortController(); v3Request.current = controller;
    setError(""); setV3Notice(""); if (more) setV3MoreBusy(true); else setV3Busy(true);
    const started = Date.now();
    try {
      const { results } = await v3Api.variants(params, randomSeeds(4), controller.signal);
      // Анимация «Генерируем…» должна успеть прочитаться, даже если сервер ответил мгновенно.
      const wait = Math.max(0, (more ? 400 : 1300) - (Date.now() - started));
      await new Promise(r => setTimeout(r, wait));
      if (controller.signal.aborted) return;
      // Каждый набор вариантов сразу попадает в «Недавние генерации» (раньше — только после экспорта).
      const session = saveV3Session(params, results);
      setV3SessionId(session.id); setV3Params(params); setV3Variants(results); setV3IndexState(0); setStage("v3");
    } catch (e) { if (!controller.signal.aborted) setError(apiMessage(e)); }
    finally { if (!controller.signal.aborted) { setV3Busy(false); setV3MoreBusy(false); } }
  }
  async function v3Export() {
    const variant = v3Variants[v3Index];
    if (!variant || !v3Params || v3ExportBusy) return;
    const key = JSON.stringify([v3Params, variant.seed]);
    const known = v3Saved.current.get(key);
    if (known && Date.parse(known.expiresAt) > Date.now()) { setGeneration(known); setExportOpen(true); return; }
    setV3ExportBusy(true); setV3Notice("");
    const controller = new AbortController();
    try {
      const saved = await startWork(v3GuestRequest(v3Params, variant.seed), controller.signal);
      // Экспорт сохраняет файл на сервере; в истории остаётся одна запись — набор вариантов.
      forgetRecent(saved.id); v3Saved.current.set(key, saved); setGeneration(saved); setExportOpen(true);
      if (v3SessionId) updateV3Session(v3SessionId, { saved: { ...v3Session(v3SessionId)?.saved, [variant.seed]: saved } });
    } catch (e) { blockWork(e); setV3Notice(apiMessage(e)); }
    finally { setV3ExportBusy(false); }
  }

  const backToForm = useCallback(() => { request.current?.abort(); v3Request.current?.abort(); setV3Busy(false); setV3MoreBusy(false); submitting.current=false; setConfirmStop(false); setFullscreen(false); setOpen(null); setStage("form"); }, []);
  const backFromResult = useCallback(() => { if(returnToLibrary) router.back(); else backToForm(); },[returnToLibrary,router,backToForm]);
  useEffect(() => { setConstructorClick(backToForm);setBackHandler(stage === "result" || stage === "v3" && returnToLibrary ? backFromResult : backToForm);return () => {setConstructorClick(null);setBackHandler(null);}; },[setConstructorClick,setBackHandler,stage,returnToLibrary,backFromResult,backToForm]);
  useEffect(() => {setShowBack(stage !== "form");return () => setShowBack(false);},[setShowBack,stage]);

  async function startGeneration() {
    if (!canSubmit || submitting.current) return;
    await submitGeneration(aiRequest(catalog,baseId,style,seed,crypto.randomUUID()));
  }
  async function submitGeneration(body: GuestRequest) {
    if (submitting.current) return;
    submitting.current=true;
    const controller = new AbortController(); request.current=controller;
    try {
      setError("");setGeneration(null);setImageError(false);setConfirmStop(false);setStage("generating");
      const generation = await startWork(body,controller.signal);
      if(!controller.signal.aborted) await waitForResult(generation,controller);
    } catch(e) {
      if(!controller.signal.aborted) {
        blockWork(e);setStage("form");
        if(e instanceof ApiError && e.code === "CATALOG_BUSY") {setError("");window.dispatchEvent(new Event("tp:catalog-refresh"));} else setError(apiMessage(e));
        if(e instanceof ApiError && e.code === "AI_PROFILE_CHANGED") await loadCatalog();
      }
    } finally { submitting.current=false; }
  }
  async function reopenJob() {
    if(!generation) return;
    request.current?.abort();const controller=new AbortController();request.current=controller;setError("");setStage("generating");
    try {await waitForResult((await api.guestGeneration(generation.id,controller.signal)).generation,controller);}catch(e){if(!controller.signal.aborted){blockWork(e);setError(apiMessage(e));setStage("form");}}
  }
  function newVariant() { forgetWork();setSeed(randomSeed());setOpen(null);setError(""); }
  const savedBase = generation?.recipe?.base as { titleRu?: string; elementCodes?: string[]; palette?: { background?: string } } | undefined;
  const resultAi = generation?.mode === "ai";
  const savedRecipe = generation?.recipe as ({ renderer?: string; v3?: V3Params; v3Info?: V3Info; seed?: number; size?: number[] } | undefined);
  const savedV3 = savedRecipe?.renderer === "composition-v3" ? savedRecipe.v3 ?? null : null;
  const v3Saved_: V3Variant | null = savedV3 && generation?.imageUrl && savedRecipe?.v3Info ? { seed: savedRecipe.seed ?? 0, image: apiUrl(generation.imageUrl), size: savedRecipe.size ?? [1, 1], info: savedRecipe.v3Info } : null;
  const selections = generation?.selections ?? emptySelections();
  const savedCodes = generation?.selections?.elementCodes;
  const infoSelections = savedCodes?.length ? {...selections,motifs:savedCodes} : selections;
  const infoTiles = PARAMETER_TILES.map(tile => tile.key === "motifs" && savedCodes?.length ? {...tile,options:savedCodes.map(code => ({value:code,label:legacyElements.find(item => item.code === code)?.nameRu ?? "Мотив",description:""}))} : tile);
  const repeatable = !resultAi && Boolean(generation?.moduleUrl || generation?.outputKind === "repeat_module" && generation.seamless) && !imageError;
  const [repeat, setRepeat] = useState(false);
  useEffect(() => {
    if (!generation) return;
    const check = () => {
      if (Date.parse(generation.expiresAt) <= Date.now()) {
        request.current?.abort();forgetWork();setGeneration(null);setStage("form");setFullscreen(false);setExportOpen(false);
        setError("Срок доступа к работе истёк. Сохранённый на устройстве файл остаётся у вас. Новое создание — отдельное действие.");
      }
    };
    check(); const timer = setInterval(check,1000);return () => clearInterval(timer);
  },[generation]);
  const resultUrl = repeat && repeatable && generation?.moduleUrl ? generation.moduleUrl : generation?.imageUrl;
  const formats = resultAi ? ["png" as const] : generation?.formats ?? ["png","jpg"] as ("png"|"jpg")[];
  const details = generation?.ai ? [
    {title:"Композиционная основа",value:savedBase?.titleRu ?? "Выбранная основа"},
    {title:"Стиль орнамента",value:ORNAMENT_STYLES[generation.ai.ornamentStyle]?.label ?? generation.ai.ornamentStyle},
    {title:"Палитра",value:"Исходная палитра основы; оттенки результата могут изменяться"},
    {title:"Вариант",value:String(generation.seed ?? generation.recipe?.seed ?? "не указан")},
    {title:"Экспорт",value:"PNG с фоном · бесшовность не гарантируется"},
  ] : [
    {title:"Тип генерации",value:resultAi ? "Сохранённая ИИ-работа прежней версии" : "Сохранённая графическая композиция"},
    ...(!resultAi && generation?.selections ? [
      {title:"Масштаб мотивов",value:`${generation.selections.scale ?? 1}×`},
      {title:"Фон PNG",value:generation.selections.transparentBackground ? "Прозрачный" : "Цветная подложка"},
      {title:"Размер результата",value:Array.isArray(generation.recipe?.size) ? `${generation.recipe.size.join(" × ")} px` : "См. исходный файл"},
      {title:"Стыки краёв",value:generation.seamless === true ? "Бесшовный повтор" : generation.seamless === false ? "Без бесшовного стыка" : "Не подтверждены"},
    ] : []),
  ];
  const baseOptions: AiOption[] = (catalog?.bases ?? []).map(item => ({id:item.id,title:item.titleRu,previewUrl:item.previewUrl,description:`${item.familyTitleRu}. Палитра и мотивы заданы основой; детали и оттенки результата могут измениться.`,note:"Исходная композиционная основа. Это не результат AI-генерации."}));
  const styleOptions: AiOption[] = Object.entries(ORNAMENT_STYLES).map(([id,item]) => { const p=base?.styles.find(s => s.id === id);return {id,title:item.label,description:item.description,note:!base ? "Сначала выберите композиционную основу" : !p?.available ? unavailableText(p?.unavailableReasons) : "Доступно для выбранной основы"}; });
  const tileData: {key:TileKey;label:string;value:string;isSet:boolean}[] = [
    {key:"base",label:"Композиция",value:base?.titleRu ?? (baseId ? "Основа недоступна" : "Выберите"),isSet:Boolean(baseId)},
    {key:"style",label:"Стиль",value:style ? ORNAMENT_STYLES[style].label : "Выберите",isSet:Boolean(style)},
    {key:"variant",label:"Вариант",value:"Настроить вариант",isSet:true},
  ];
  return <>
    <section className="ai-constructor-section flex min-h-0 flex-1 flex-col overflow-y-auto rounded-tl-[24px] rounded-bl-[3px] bg-surface max-md:rounded-none max-md:bg-transparent">
      {!ready ? <p role="status" className="api-notice">Открываем сохранённую работу…</p> : null}
      <div className="ai-constructor-form" hidden={!ready || stage !== "form"}>
        <ModeSelector mode={mode} onChange={setMode} />
        <div className="constructor-mode-form" hidden={mode !== "flat"}><FlatScreenV3 generating={v3Busy} onGenerate={params => void v3Generate(params)} initial={savedV3 ?? v3Params} /></div>
        <div className="constructor-mode-form" hidden={mode !== "ai"}>
        <div className="ai-constructor-body">
          <h1>Соберите орнаментальный узор</h1>
          <div className="ai-parameter-grid ai-real-options">{tileData.map((tile,i) => <ParameterCard key={tile.key} label={tile.label} value={tile.value} isSet={tile.isSet} corner={corners[i]} mobileCorner={mobileCorners[i]} compactValue={tile.key === "base" || tile.key === "style"} ghost={open === tile.key} onClick={() => setOpen(tile.key)} />)}</div>
          <div className={`ai-generate-area${catalog && !catalog.available ? " ai-generate-unavailable" : ""}`}>
            {catalog && !catalog.available ? <AiUnavailable /> : <button className="ai-generate" aria-disabled={!canSubmit} disabled={!canSubmit} onClick={startGeneration}><span><ModeIcon mode="ai" /> Сгенерировать узор</span><span className="ai-generate-arrow"><SendArrow /></span></button>}
            {catalogError ? <p role="alert" className="api-error">{catalogError}<button onClick={loadCatalog}>Повторить загрузку каталога</button></p> : null}
          </div>
        </div>
        </div>{mode === "ai" ? <p className="ai-result-reminder">Всегда перепроверяйте результаты от ИИ</p> : null}
      </div>
      {ready && stage === "v3" && v3Variants.length ? <ResultV3 variants={v3Variants} index={v3Index} onIndex={setV3Index} onBack={returnToLibrary ? backFromResult : backToForm} onExport={() => void v3Export()} onMore={v3Params ? () => void v3Generate(v3Params,true) : undefined} exportBusy={v3ExportBusy} moreBusy={v3MoreBusy} notice={v3Notice} transparent={v3Params?.background === "transparent"} /> : null}
      {ready && stage === "result" && generation && v3Saved_ ? <ResultV3 variants={[v3Saved_]} index={0} onIndex={() => {}} onBack={backFromResult} onExport={() => setExportOpen(true)} exportBusy={imageError} moreBusy={false} notice={`Работа доступна до ${expiryText(generation.expiresAt)}.`} transparent={savedV3?.background === "transparent"} /> : null}
      {ready && stage === "generating" ? <GeneratingView imageUrl={null} progress={typeof generation?.progress === "number" ? generation.progress : undefined} status={generation?.status} confirmStop={confirmStop} onBack={backToForm} onStop={() => {if(!confirmStop)setConfirmStop(true);else backToForm();}} /> : ready && stage === "result" && generation && !v3Saved_ ? <div className="ai-result-stage flex min-h-0 flex-1 flex-col">
        <ResultView generation={generation} imageUrl={resultUrl ? apiUrl(resultUrl) : null} imageSize={repeat && repeatable && generation.repeat?.periodPx ? generation.repeat.periodPx : (Array.isArray(generation.recipe?.size) ? generation.recipe.size as number[] : generation.ai ? [1024,1024] : null)} stamp={formatPatternStamp(new Date(generation.createdAt))} name={DEFAULT_PATTERN_NAME} rating={null} selections={infoSelections} prompt="" tiles={infoTiles} infoDetails={details} editOpen={false} editLabel="К настройкам" onBack={backFromResult} onEdit={() => {if(resultAi){backToForm();newVariant();}else {setMode("flat");backToForm();}}} onCloseEdit={() => {}} onSubmitEdit={() => {}} onExpand={() => setFullscreen(true)} onExport={() => setExportOpen(true)} exportDisabled={imageError || !formats.length} repeatPreview={repeat && repeatable} onImageError={() => setImageError(true)} />
        {repeatable ? <button className="studio-button mx-auto" aria-pressed={repeat} onClick={() => {setRepeat(v => !v);}}>{repeat ? "Текущий результат" : "Модуль · повтор 3×3"}</button> : null}
        <p className="api-notice">Работа доступна до {expiryText(generation.expiresAt)}.</p>
      </div> : null}
      {v3Missing && stage === "form" ? <p role="status" className="api-notice">Этот набор вариантов больше недоступен: «Недавние генерации» хранятся только до перезагрузки страницы. Соберите узор заново.</p> : null}
      {error ? <div role="alert" className="api-error">{error}{generation && stage === "form" ? <button className="studio-button ml-3" onClick={reopenJob}>Открыть задание снова</button> : null}</div> : null}
      {imageError ? <p role="alert" className="api-error">Файл результата не загрузился. Скачивание недоступно. <button className="underline" onClick={() => window.location.reload()}>Повторить загрузку</button></p> : null}
      {ready && stage === "form" ? <CreateNotice /> : null}
    </section>
    {open === "base" ? <AiOptionDialog label="Выберите композиционную основу" options={baseOptions} selected={baseId} confirmLabel="Выбрать эту основу" onClose={() => setOpen(null)} onSelect={id => {setBaseId(id);setError("");}} /> : open === "style" ? <AiOptionDialog label="Стиль орнамента" options={styleOptions} selected={style} confirmLabel="Выбрать этот стиль" onClose={() => setOpen(null)} onSelect={id => {setStyle(id as OrnamentStyle);setError("");}} /> : open ? <AiModal label={tileData.find(t => t.key === open)?.label ?? "Параметры"} onClose={() => setOpen(null)} className="ai-details-modal"><div className="ai-picker-surface ai-details-surface"><h2>{tileData.find(t => t.key === open)?.label}</h2>
      <p>Новый вариант сохраняет основу и стиль. Расположение деталей может измениться. Генерация начнётся после нажатия «Сгенерировать узор».</p><button className="ai-confirm" onClick={newVariant}>Подготовить новый вариант</button><p role="status">Текущий вариант: {seed}</p>
    </div></AiModal> : null}
    {exportOpen && generation ? <ExportMenu generation={generation} formats={formats} transparent={!resultAi && generation.selections?.transparentBackground} patternId={generation.id} onClose={() => setExportOpen(false)} /> : null}
    {fullscreen && screenEl ? createPortal(<FullscreenView imageUrl={generation?.imageUrl ? apiUrl(generation.imageUrl) : null} onClose={() => setFullscreen(false)} onEdit={() => {if(resultAi){backToForm();newVariant();}else {setMode("flat");backToForm();}}} />,screenEl) : null}
  </>;
}
