"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { ParameterCard } from "./ParameterCard";
import { AiModal, AiOptionDialog, type AiOption } from "./AiOptionDialog";
import { SendArrow } from "@/components/ui/SendArrow";
import { ModeSelector, type ConstructorMode } from "./ModeSelector";
import { FlatScreen } from "./FlatScreen";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { GeneratingView } from "./GeneratingView";
import { ResultView } from "./ResultView";
import { FullscreenView } from "./FullscreenView";
import { ExportMenu } from "./ExportMenu";
import { DEFAULT_PATTERN_NAME, formatPatternStamp } from "./data";
import { emptySelections, PARAMETER_TILES } from "./parameters";
import { api, apiUrl, apiMessage, ApiError, type AiBaseCatalog, type GuestGeneration as Generation, type Element, type OrnamentStyle, type GuestRequest } from "@/lib/api";
import { aiRequest, ORNAMENT_STYLES, randomSeed, unavailableText } from "@/lib/ai-mvp";
import { startWork, rememberGeneration, blockWork, forgetWork, expiryText } from "@/lib/guest-work";
import { useShell } from "@/components/layout/shell-context";

type TileKey = "base" | "motifs" | "variant" | "palette" | "style" | "format";
type Stage = "form" | "generating" | "result";
const corners = ["top-left", "none", "top-right", "bottom-left", "none", "bottom-right"] as const;
const mobileCorners = ["top-left", "top-right", "none", "none", "bottom-left", "bottom-right"] as const;

export function ConstructorScreen({ initialPatternId, returnToLibrary = false, initialMode = "flat" }: { initialPatternId?: string; returnToLibrary?: boolean; initialMode?: ConstructorMode }) {
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
  useEffect(() => () => request.current?.abort(), []);

  const backToForm = useCallback(() => { request.current?.abort(); submitting.current=false; setConfirmStop(false); setFullscreen(false); setOpen(null); setStage("form"); }, []);
  const backFromResult = useCallback(() => { if(returnToLibrary) router.back(); else backToForm(); },[returnToLibrary,router,backToForm]);
  useEffect(() => { setConstructorClick(backToForm);setBackHandler(stage === "result" ? backFromResult : backToForm);return () => {setConstructorClick(null);setBackHandler(null);}; },[setConstructorClick,setBackHandler,stage,backFromResult,backToForm]);
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
        blockWork(e);setError(apiMessage(e));setStage("form");
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
  const selections = generation?.selections ?? emptySelections();
  const savedCodes = generation?.selections?.elementCodes;
  const infoSelections = savedCodes?.length ? {...selections,motifs:savedCodes} : selections;
  const infoTiles = PARAMETER_TILES.map(tile => tile.key === "motifs" && savedCodes?.length ? {...tile,options:savedCodes.map(code => ({value:code,label:`${code} · ${legacyElements.find(item => item.code === code)?.nameRu ?? "Элемент сохранённого рецепта"}`,description:code}))} : tile);
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
    {title:"Композиционная основа",value:savedBase?.titleRu ?? generation.ai.baseId},
    {title:"Стиль орнамента",value:ORNAMENT_STYLES[generation.ai.ornamentStyle]?.label ?? generation.ai.ornamentStyle},
    {title:"Палитра",value:"Исходная палитра основы; оттенки результата могут изменяться"},
    {title:"Профиль",value:generation.ai.profileVersion},
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
  const baseOptions: AiOption[] = (catalog?.bases ?? []).map(item => ({id:item.id,title:item.titleRu,previewUrl:item.previewUrl,description:`${item.familyTitleRu}. Мотивы: ${item.elementCodes.join(" / ")}.`,note:"Исходная композиционная основа. Это не результат AI-генерации."}));
  const styleOptions: AiOption[] = Object.entries(ORNAMENT_STYLES).map(([id,item]) => { const p=base?.styles.find(s => s.id === id);return {id,title:item.label,description:item.description,note:!base ? "Сначала выберите композиционную основу" : !p?.available ? unavailableText(p?.unavailableReasons) : "Доступно для выбранной основы"}; });
  const tileData: {key:TileKey;label:string;value:string;isSet:boolean}[] = [
    {key:"base",label:"Композиция",value:base?.titleRu ?? (baseId ? "Основа недоступна" : "Выберите"),isSet:Boolean(baseId)},
    {key:"motifs",label:"Мотивы",value:base ? `${base.elementCodes.length} в основе` : "От основы",isSet:Boolean(base)},
    {key:"variant",label:"Масштаб и ритм",value:"Новый вариант",isSet:true},
    {key:"palette",label:"Палитра",value:base ? "Исходная палитра" : "От основы",isSet:Boolean(base)},
    {key:"style",label:"Исполнение",value:style ? ORNAMENT_STYLES[style].label : "Выберите",isSet:Boolean(style)},
    {key:"format",label:"Применение",value:"PNG · 1024²",isSet:true},
  ];
  return <>
    <section className="ai-constructor-section flex min-h-0 flex-1 flex-col overflow-y-auto rounded-tl-[24px] rounded-bl-[3px] bg-surface max-md:rounded-none max-md:bg-transparent">
      {!ready ? <p role="status" className="api-notice">Открываем сохранённую работу…</p> : null}
      <div className="ai-constructor-form" hidden={!ready || stage !== "form"}>
        <ModeSelector mode={mode} onChange={setMode} />
        <div className="constructor-mode-form" hidden={mode !== "flat"}><FlatScreen onGenerate={submitGeneration} initialSelections={generation?.mode === "flat" ? generation.selections : null} /></div>
        <div className="constructor-mode-form" hidden={mode !== "ai"}>
        <div className="ai-constructor-body">
          <h1>Соберите орнаментальный узор</h1>
          <div className="ai-parameter-grid">{tileData.map((tile,i) => <ParameterCard key={tile.key} label={tile.label} value={tile.value} isSet={tile.isSet} corner={corners[i]} mobileCorner={mobileCorners[i]} compactValue={tile.key === "base" || tile.key === "style"} ghost={open === tile.key} onClick={() => setOpen(tile.key)} />)}</div>
          <div className="ai-generate-area">
            <button className="ai-generate" aria-disabled={!canSubmit} disabled={!canSubmit} onClick={startGeneration}><span><ModeIcon mode="ai" /> Сгенерировать узор</span><span className="ai-generate-arrow"><SendArrow /></span></button>
            {catalogError ? <p role="alert" className="api-error">{catalogError}<button onClick={loadCatalog}>Повторить загрузку каталога</button></p> : null}
          </div>
        </div>
        </div>{mode === "ai" ? <p className="ai-result-reminder">Всегда перепроверяйте результаты от ИИ</p> : null}
      </div>
      {ready && stage === "generating" ? <GeneratingView imageUrl={null} progress={typeof generation?.progress === "number" ? generation.progress : undefined} status={generation?.status} confirmStop={confirmStop} onBack={backToForm} onStop={() => {if(!confirmStop)setConfirmStop(true);else backToForm();}} /> : ready && stage === "result" && generation ? <div className="ai-result-stage flex min-h-0 flex-1 flex-col">
        <ResultView generation={generation} imageUrl={resultUrl ? apiUrl(resultUrl) : null} imageSize={repeat && repeatable && generation.repeat?.periodPx ? generation.repeat.periodPx : (Array.isArray(generation.recipe?.size) ? generation.recipe.size as number[] : generation.ai ? [1024,1024] : null)} stamp={formatPatternStamp(new Date(generation.createdAt))} name={DEFAULT_PATTERN_NAME} rating={null} selections={infoSelections} prompt="" tiles={infoTiles} infoDetails={details} editOpen={false} editLabel="К настройкам" onBack={backFromResult} onEdit={() => {if(resultAi){backToForm();newVariant();}else {setMode("flat");backToForm();}}} onCloseEdit={() => {}} onSubmitEdit={() => {}} onExpand={() => setFullscreen(true)} onExport={() => setExportOpen(true)} exportDisabled={imageError || !formats.length} repeatPreview={repeat && repeatable} onImageError={() => setImageError(true)} />
        {repeatable ? <button className="studio-button mx-auto" aria-pressed={repeat} onClick={() => {setRepeat(v => !v);}}>{repeat ? "Текущий результат" : "Модуль · повтор 3×3"}</button> : null}
        <p className="api-notice">Работа доступна до {expiryText(generation.expiresAt)}.</p>
      </div> : null}
      {error ? <div role="alert" className="api-error">{error}{generation && stage === "form" ? <button className="studio-button ml-3" onClick={reopenJob}>Открыть задание снова</button> : null}</div> : null}
      {imageError ? <p role="alert" className="api-error">Файл результата не загрузился. Скачивание недоступно. <button className="underline" onClick={() => window.location.reload()}>Повторить загрузку</button></p> : null}
    </section>
    {open === "base" ? <AiOptionDialog label="Выберите композиционную основу" options={baseOptions} selected={baseId} confirmLabel="Выбрать эту основу" onClose={() => setOpen(null)} onSelect={id => {setBaseId(id);setError("");}} /> : open === "style" ? <AiOptionDialog label="Стиль орнамента" options={styleOptions} selected={style} confirmLabel="Выбрать этот стиль" onClose={() => setOpen(null)} onSelect={id => {setStyle(id as OrnamentStyle);setError("");}} /> : open ? <AiModal label={tileData.find(t => t.key === open)?.label ?? "Параметры"} onClose={() => setOpen(null)} className="ai-details-modal"><div className="ai-picker-surface ai-details-surface"><h2>{tileData.find(t => t.key === open)?.label}</h2>
      {open === "palette" ? <><p>Исходная палитра выбранной основы</p>{base ? <><div className="ai-swatches">{(base.palette.swatches.length ? base.palette.swatches : [base.palette.background]).filter(color => /^#[0-9a-f]{6}$/i.test(color)).map((color,i) => <span key={i} style={{backgroundColor:color}} title={i === 0 ? `Фон основы ${color}` : color} />)}</div><p>{base.titleRu}. Цвета заданы основой. Оттенки AI-результата могут изменяться.</p></> : <p>Сначала выберите композиционную основу.</p>}</> : open === "motifs" ? <><p>Мотивы закреплены в выбранной композиции.</p><p>{base?.elementCodes.join(" · ") ?? "Сначала выберите основу"}</p></> : open === "variant" ? <><p>Новый вариант сохраняет основу и стиль. Расположение деталей может измениться.</p><button className="ai-confirm" onClick={newVariant}>Подготовить новый вариант</button><p role="status">Вариант {seed}</p></> : <><p>PNG с непрозрачным фоном, 1024 × 1024 px.</p><p>Исходный фон сохраняется во входной основе. Бесшовность AI-изображения не гарантируется.</p></>}
    </div></AiModal> : null}
    {exportOpen && generation ? <ExportMenu generation={generation} formats={formats} transparent={!resultAi && generation.selections?.transparentBackground} patternId={generation.id} onClose={() => setExportOpen(false)} /> : null}
    {fullscreen && screenEl ? createPortal(<FullscreenView imageUrl={generation?.imageUrl ? apiUrl(generation.imageUrl) : null} onClose={() => setFullscreen(false)} onEdit={() => {if(resultAi){backToForm();newVariant();}else {setMode("flat");backToForm();}}} />,screenEl) : null}
  </>;
}
