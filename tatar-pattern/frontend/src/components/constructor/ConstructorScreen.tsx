"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createPortal } from "react-dom";
import { CatalogPicker } from "@/components/constructor/CatalogPicker";
import { OutputSettings, DEFAULT_OUTPUT, type OutputOptions } from "@/components/constructor/OutputSettings";
import { PromptBar } from "@/components/constructor/PromptBar";
import { ParameterCard } from "@/components/constructor/ParameterCard";
import { GeneratingView } from "@/components/constructor/GeneratingView";
import { ResultView } from "@/components/constructor/ResultView";
import { FullscreenView } from "@/components/constructor/FullscreenView";
import {
  DEFAULT_PATTERN_NAME,
  formatPatternStamp,
} from "@/components/constructor/data";
import {
  PARAMETER_TILES,
  cardFromSelection,
  emptySelections,
  selectionsReady,
  type ConstructorSelections,
  type ParameterKey,
  type ParameterSelection,
} from "@/components/constructor/parameters";
import { api, apiUrl, apiMessage, toApiSelections, type Generation, type Element, type Capabilities, type GenerationMode } from "@/lib/api";
import { ExportMenu } from "@/components/constructor/ExportMenu";
import { ProjectPicker } from "@/components/constructor/ProjectPicker";
import { ParameterPanel } from "@/components/constructor/ParameterPanel";
import { useShell } from "@/components/layout/shell-context";
import {
  updatePattern,
  type PatternRating,
} from "@/lib/library";

type Stage = "form" | "generating" | "result";

export function ConstructorScreen({
  initialPatternId, returnToLibrary = false,
}: {
  initialPatternId?: string; returnToLibrary?: boolean;
}) {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("form");
  const [prompt, setPrompt] = useState("");
  const [selections, setSelections] = useState<ConstructorSelections>(
    emptySelections(),
  );
  const [catalog, setCatalog] = useState<Element[] | null>(null);
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [mode, setMode] = useState<GenerationMode>("flat");
  const [elementCodes, setElementCodes] = useState<string[]>([]);
  const [output, setOutput] = useState<OutputOptions>(DEFAULT_OUTPUT);
  const [jobStatus, setJobStatus] = useState<Generation["status"] | null>(null);
  const [repeatPreview, setRepeatPreview] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [resultFormats, setResultFormats] = useState<("png" | "jpg")[]>([]);
  const [resultSize, setResultSize] = useState<number[] | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [openKey, setOpenKey] = useState<ParameterKey | null>(null);
  const [progress, setProgress] = useState<number | undefined>(undefined);
  const {
    screenEl,
    setConstructorClick,
    setBackHandler,
    setShowBack,
  } = useShell();
  const [confirmStop, setConfirmStop] = useState(false);
  const [stamp, setStamp] = useState("");
  // Protected URL from the server.
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [patternId, setPatternId] = useState<string | null>(null);
  const [patternName, setPatternName] = useState(DEFAULT_PATTERN_NAME);
  const [rating, setRating] = useState<PatternRating>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [hintOn, setHintOn] = useState(false);
  const [hintFlash, setHintFlash] = useState(0);
  const [patternReady, setPatternReady] = useState(!initialPatternId);
  const hintHide = useRef<number | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState<string[]>([]);
  const [exportOpen, setExportOpen] = useState(false);
  const [projectId, setProjectId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([api.elements(), api.capabilities()]).then(([{ items }, caps]) => {
      if (active) { setCatalog(items); setCapabilities(caps); }
    }).catch((e) => { if (active) setCatalogError(apiMessage(e)); });
    return () => { active = false; };
  }, []);
  const directElements = capabilities?.elementSelection === "elementCodes";
  const availableMotifs = new Set((catalog ?? []).map((item) => item.motifKey).filter((key): key is string => Boolean(key)));
  const tiles = PARAMETER_TILES.map((tile) => {
    if (tile.key === "style" && output.colorMode === "original" && capabilities?.colorModes?.includes("original")) return { ...tile, options: [{ value: "heritage", label: "Исходный PNG", description: "Сохраняются цвета и мягкие края исходного элемента. Для стилизации выберите «Силуэт» в настройках цвета ниже." }] };
    if (tile.key === "motifs") return { ...tile, options: [...availableMotifs].map((key) => ({ value: key, label: catalog?.find((item) => item.motifKey === key)?.motifClass ?? key, description: "Категория из каталога API. Генератор выбирает элементы этой категории." })), multiTotal: availableMotifs.size };
    const allowed = tile.key === "style" ? capabilities?.styles ? Object.keys(capabilities.styles) : undefined : tile.key === "composition" ? capabilities?.compositions : tile.key === "parameters" ? capabilities?.parameters : tile.key === "palette" ? capabilities?.palettes : tile.key === "usage" ? capabilities?.usageSizes ? Object.keys(capabilities.usageSizes) : undefined : undefined;
    return { ...tile, options: tile.options.filter((option) => !allowed || allowed.includes(option.value)).map((option) => ({ ...option, description: option.description })) };
  });

  function applyGeneration(g: Generation) {
    setMode(g.mode ?? "flat"); setJobStatus(g.status);
    setElementCodes(g.selections.elementCodes ?? []);
    setOutput({ scale: g.selections.scale ?? 1, transparentBackground: g.selections.transparentBackground ?? false, backgroundColor: g.selections.backgroundColor ?? null, outputSize: g.selections.outputSize ?? null, colorMode: g.selections.colorMode ?? "original" });
    setResultFormats(g.formats ?? capabilities?.formats ?? (g.mode === "ai" ? ["png"] : ["png", "jpg"]));
    setResultSize(Array.isArray(g.recipe?.size) ? g.recipe.size as number[] : null);
    setPatternId(g.id); setPatternName(g.title || DEFAULT_PATTERN_NAME); setStamp(formatPatternStamp(new Date(g.createdAt)));
    setImageUrl(g.imageUrl ? apiUrl(g.imageUrl) : null); setRating(g.rating);
    setPrompt(g.prompt ?? ""); setSelections(g.selections); setProjectId(g.projectId);
    setWarnings((g.warnings ?? []).filter(w => w.code !== "PROMPT_UNSUPPORTED").map((w) => w.message));
    if (g.recipe?.isFixture && !(g.warnings ?? []).some((w) => w.code === "TEST_FIXTURE")) setWarnings((w) => ["Тестовый результат: синтетические мотивы.", ...w]);
    setProgress(typeof g.progress === "number" && Number.isFinite(g.progress) ? Math.max(0, Math.min(100, g.progress)) : undefined);
  }
  async function waitForResult(first: Generation, controller: AbortController) {
    let g = first;
    while (!controller.signal.aborted) {
      if (controller.signal.aborted) return;
      applyGeneration(g);
      if (g.status === "done") {
        if (!g.imageUrl) throw new Error("Сервис завершил генерацию без изображения. Повторите запрос позже.");
        setStage("result");
        if (initialPatternId !== g.id) router.replace(`/constructor?pattern=${encodeURIComponent(g.id)}${returnToLibrary ? "&from=library" : ""}`);
        return;
      }
      if (g.status !== "queued" && g.status !== "processing") throw new Error(typeof g.error === "string" ? g.error : g.error?.message ?? "Генерация не завершилась. Попробуйте снова.");
      setPatternReady(true);
      setStage("generating");
      await new Promise<void>((resolve, reject) => {
        const stop = () => { clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); };
        const timer = setTimeout(() => { controller.signal.removeEventListener("abort", stop); resolve(); }, 1500);
        controller.signal.addEventListener("abort", stop, { once: true });
      });
      g = (await api.generation(g.id, controller.signal)).generation;
    }
  }
  useEffect(() => {
    if (!initialPatternId) return;
    const controller = new AbortController(); requestRef.current = controller;
    api.generation(initialPatternId, controller.signal).then(({ generation }) => waitForResult(generation, controller))
      .catch((e) => { if (!controller.signal.aborted) { setError(apiMessage(e)); setStage("form"); } })
      .finally(() => { if (!controller.signal.aborted) setPatternReady(true); });
    return () => controller.abort();
    // A new pattern id remounts this screen.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPatternId]);
  useEffect(() => () => requestRef.current?.abort(), []);

  async function startGeneration() {
    if (!canSubmit || (requestRef.current && !requestRef.current.signal.aborted && stage === "generating")) return;
    const controller = new AbortController(); requestRef.current = controller;
    setError(""); setWarnings([]); setProgress(undefined); setConfirmStop(false);
    setOpenKey(null); setEditOpen(false); setHintOn(false); setImageUrl(null); setJobStatus(null); setPatternId(null); setImageError(false); setRepeatPreview(false); setPatternReady(true); setStage("generating");
    try {
      const input = toApiSelections(directElements ? { ...selections, motifs: elementCodes } : selections);
      if (directElements) { input.motifs = []; input.elementCodes = elementCodes; input.scale = output.scale; input.transparentBackground = output.transparentBackground; input.backgroundColor = output.backgroundColor; input.colorMode = output.colorMode; input.outputSize = output.outputSize; }
      const { generation } = await api.generate(input, prompt, projectId ?? undefined, controller.signal, capabilities?.modes ? mode : undefined);
      if (!controller.signal.aborted) await waitForResult(generation, controller);
    } catch (e) {
      if (!controller.signal.aborted) { setError(apiMessage(e)); setStage("form"); }
    }
  }

  const backToForm = useCallback(() => {
    setConfirmStop(false);
    setWarnings([]);
    setImageError(false);
    requestRef.current?.abort();
    setFullscreen(false);
    setEditOpen(false);
    setHintOn(false);
    setOpenKey(null);
    setStage("form");
  }, []);

  const backFromResult = useCallback(() => { if(returnToLibrary) router.back(); else backToForm(); }, [returnToLibrary, router, backToForm]);

  function showBlockedHint() {
    setHintOn(true);
    setHintFlash((n) => n + 1);
    if (hintHide.current) window.clearTimeout(hintHide.current);
    hintHide.current = window.setTimeout(() => setHintOn(false), 4500);
  }

  useEffect(() => {
    return () => {
      if (hintHide.current) window.clearTimeout(hintHide.current);
    };
  }, []);

  useEffect(() => {
    setConstructorClick(backToForm);
    setBackHandler(stage === "result" ? backFromResult : backToForm);
    return () => {
      setConstructorClick(null);
      setBackHandler(null);
    };
  }, [setConstructorClick, setBackHandler, backToForm, backFromResult, stage]);

  useEffect(() => {
    setShowBack(stage !== "form");
    return () => setShowBack(false);
  }, [setShowBack, stage]);

  function handleStop() {
    if (!confirmStop) {
      setConfirmStop(true);
      return;
    }
    backToForm();
    setError("Ожидание прекращено. Работа на сервере могла продолжиться; проверьте библиотеку перед повторным запросом.");
  }

  function applySelection(key: ParameterKey, next: ParameterSelection) {
    setSelections((current) => ({ ...current, [key]: next }));
    const tile = PARAMETER_TILES.find((item) => item.key === key);
    if (!tile?.multi && key !== "style") setOpenKey(null);
  }

  async function handleRename(next: string) {
    if (!patternId) return;
    try { const g = await updatePattern(patternId, { name: next }); setPatternName(g.name); setError(""); }
    catch (e) { setError(apiMessage(e)); }
  }

  async function handleRate(next: PatternRating) {
    if (!patternId) return;
    try { const g = await updatePattern(patternId, { rating: next }); setRating(g.rating); setError(""); }
    catch (e) { setError(apiMessage(e)); }
  }

  const openTile = tiles.find((item) => item.key === openKey) ?? null;
  const aiReady = capabilities?.modes?.ai?.available === true && capabilities.modes.ai.verified === true;
  const canSubmit = selectionsReady(directElements ? { ...selections, motifs: elementCodes } : selections) && (directElements ? elementCodes.every((code) => catalog?.some((item) => item.code === code)) : (Array.isArray(selections.motifs) && selections.motifs.every((key) => availableMotifs.has(key)))) && Boolean(catalog?.length) && !catalogError && (mode === "flat" ? capabilities?.modes?.flat?.available !== false : aiReady);
  const infoTiles = tiles.map((tile) => tile.key === "motifs" && elementCodes.length ? { ...tile, options: elementCodes.map((code) => ({ value: code, label: catalog?.find((item) => item.code === code)?.nameRu ?? code, description: code })) } : tile);
  const infoSelections = elementCodes.length ? { ...selections, motifs: elementCodes } : selections;
  const repeatable = mode === "flat" && selections.composition === "rapport" && !imageError;

  const overlay =
    fullscreen && screenEl
      ? createPortal(
          <FullscreenView
            imageUrl={imageUrl}
            onClose={() => setFullscreen(false)}
            onEdit={() => {
              setFullscreen(false);
              backToForm();
            }}
          />,
          screenEl,
        )
      : null;

  return (
    <>
      <section className="flex min-h-0 flex-1 flex-col overflow-y-auto rounded-tl-[24px] rounded-bl-[3px] bg-surface max-md:rounded-none max-md:bg-transparent">
          {catalogError ? <p role="alert" className="api-error">Каталог: {catalogError} <button className="underline" onClick={() => window.location.reload()}>Повторить</button></p> : null}
          {directElements && elementCodes.some((code) => catalog && !catalog.some((item) => item.code === code)) && stage === "form" ? <p role="alert" className="api-error">Некоторые элементы сохранённого рецепта отсутствуют в текущем каталоге. Выберите доступные мотивы.</p> : null}
          {catalog?.length === 0 ? <p role="status" className="api-notice">Каталог элементов пока пуст. Генерация станет доступна после его наполнения.</p> : null}
          {error ? <p role="alert" className="api-error">{error}</p> : null}
          {!patternReady ? <p className="api-notice" role="status">Открываем сохранённый результат…</p> : stage === "form" ? (
            <div className="constructor-stage flex min-h-[720px] flex-1 flex-col max-md:min-h-[760px]">
              <div className="flex shrink-0 flex-col items-center gap-2 px-4 pt-4 text-sm">
                <div role="group" aria-label="Режим генерации" className="flex gap-2 rounded-full bg-white/50 p-1">
                  <button aria-pressed={mode === "flat"} onClick={() => setMode("flat")} className={`rounded-full px-5 py-2 ${mode === "flat" ? "bg-[#356052] text-white" : ""}`}>Плоский</button>
                  <button disabled={!aiReady} aria-pressed={mode === "ai"} onClick={() => setMode("ai")} className={`rounded-full px-5 py-2 disabled:opacity-40 ${mode === "ai" ? "bg-[#356052] text-white" : ""}`}>ИИ{!aiReady ? " · пока недоступен" : ""}</button>
                </div>

              </div>

              <div className="flex min-h-0 w-full flex-1 flex-col items-center justify-center gap-[clamp(16px,3.5vh,43px)] px-[24px] py-[16px] max-md:justify-between max-md:gap-[16px] max-md:px-[16px] max-md:py-[12px]">
                <h1 className="shrink-0 text-center font-display text-[clamp(28px,3.2vw,40px)] italic leading-none text-ink-heading max-md:max-w-[322px] max-md:text-[28px] max-md:leading-[28px]">
                  Соберите орнаментальный узор
                </h1>

                <div className="relative min-h-0 w-full max-w-[936px] max-h-[401px] flex-[1_1_auto] max-md:max-h-[372px] max-md:max-w-[327px]">
                  <div className="grid h-full grid-cols-3 grid-rows-2 gap-[15px] [grid-auto-rows:minmax(0,193px)] max-md:grid-cols-2 max-md:grid-rows-3 max-md:gap-x-[9px] max-md:gap-y-[6px] max-md:[grid-auto-rows:minmax(0,120px)]">
                    {tiles.map((tile) => (
                      <ParameterCard
                        key={tile.key}
                        {...cardFromSelection(tile, tile.key === "motifs" && directElements ? elementCodes : selections[tile.key])}
                        {...(tile.key === "motifs" ? { value: catalog === null ? "Загрузка каталога…" : directElements ? `${elementCodes.length} выбрано` : `${Array.isArray(selections.motifs) ? selections.motifs.length : 0} из ${availableMotifs.size}` } : {})}
                        ghost={openKey === tile.key}
                        onClick={() =>
                          setOpenKey((current) =>
                            current === tile.key ? null : tile.key,
                          )
                        }
                      />
                    ))}
                  </div>

                  {openKey === "motifs" && directElements ? <CatalogPicker items={catalog ?? []} value={elementCodes.filter((code) => catalog?.some((item) => item.code === code))} max={capabilities?.maxSelectedElements ?? 16} onChange={setElementCodes} onClose={() => setOpenKey(null)} /> : openTile ? (
                    <ParameterPanel
                      key={openTile.key}
                      tile={openTile}
                      value={selections[openTile.key]}
                      onConfirm={(next) => applySelection(openTile.key, next)}
                      onClose={() => setOpenKey(null)}
                    >{openKey === "style" ? <OutputSettings capabilities={capabilities} value={output} usage={typeof selections.usage === "string" ? selections.usage : null} onChange={next => { setOutput(next); if(next.colorMode === "original") setSelections(current => ({ ...current, style: "heritage" })); }} /> : null}</ParameterPanel>
                  ) : null}
                </div>

                <div className="flex w-full max-w-[703px] shrink-0 flex-col items-center gap-[10px] max-md:max-w-[369px]">
                  <div className="flex w-full flex-col items-center">
                    <PromptBar
                      noteOnly={mode === "flat"}
                      value={prompt}
                      onChange={setPrompt}
                      onSubmit={startGeneration}
                      canSubmit={canSubmit}
                      onBlockedSubmit={showBlockedHint}
                    />
                    <p
                      role="status"
                      className={[
                        "hint-msg max-w-[687px] text-center text-[13px] font-medium leading-[16px] max-md:max-w-[369px] max-md:text-[12px] max-md:leading-[15px]",
                        hintOn ? "hint-msg-on" : "",
                      ].join(" ")}
                    >
                      <span key={hintFlash} className={hintOn ? "hint-flash" : ""}>
                        {catalogError || catalog?.length === 0 ? "Генерация недоступна: каталог элементов не готов" : "Настройте все параметры генерации, чтобы продолжить"}
                      </span>
                    </p>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          {patternReady && stage === "generating" ? (
            <GeneratingView
              imageUrl={imageUrl}
              progress={progress}
              status={jobStatus}
              confirmStop={confirmStop}
              onBack={backToForm}
              onStop={handleStop}
            />
          ) : null}

          {patternReady && stage === "result" ? (
            <ResultView
              imageUrl={imageUrl}
              repeatPreview={repeatPreview && repeatable}
              onImageError={() => setImageError(true)}
              stamp={stamp}
              name={patternName}
              rating={rating}
              selections={infoSelections}
              prompt={prompt}
              editOpen={editOpen}
              onBack={backFromResult}
              onDelete={async () => { if(patternId) { await api.trashGeneration(patternId); router.push("/library"); } }}
              imageSize={resultSize}
              infoDetails={[{title:"Тип генерации",value:mode === "flat" ? "Плоский" : "ИИ"},{title:"Размер",value:resultSize ? `${resultSize.join(" × ")} px` : "По применению"},{title:"Цвет мотивов",value:output.colorMode === "original" ? "Исходные цвета" : "Силуэт"},{title:"Прозрачный фон PNG",value:output.transparentBackground ? "Да" : "Нет"}]}
              onEdit={backToForm}
              onExport={() => { if (!imageError && resultFormats.length) setExportOpen(true); }}
              exportDisabled={imageError || !resultFormats.length}
              tiles={infoTiles}
              onCloseEdit={() => setEditOpen(false)}
              onSubmitEdit={() => {}}
              onExpand={() => setFullscreen(true)}
              onRename={handleRename}
              onRate={handleRate}
            />
          ) : null}

          {stage === "result" ? <div className="flex shrink-0 flex-wrap items-center justify-center gap-3 text-xs">
            <span>{mode === "ai" ? "Новый ИИ-вариант · историческая достоверность не подтверждена" : "Плоская композиция из элементов каталога"}{resultSize ? ` · ${resultSize.join(" × ")} px` : ""}</span>
            {repeatable ? <button aria-pressed={repeatPreview} onClick={() => setRepeatPreview((value) => !value)} className="rounded-full bg-white px-4 py-2">{repeatPreview ? "Один раппорт" : "Повтор 3×3"}</button> : null}
          </div> : null}
          {imageError ? <p role="alert" className="api-error">Не удалось загрузить файл результата. <button className="underline" onClick={() => window.location.reload()}>Повторить загрузку</button></p> : null}
          {error && patternId && stage === "form" ? <button className="mx-auto shrink-0 rounded-full bg-white px-4 py-2 text-sm" onClick={() => { const controller = new AbortController(); requestRef.current = controller; setError(""); setPatternReady(true); setStage("generating"); api.generation(patternId, controller.signal).then(({ generation }) => waitForResult(generation, controller)).catch((e) => { if (!controller.signal.aborted) { setError(apiMessage(e)); setStage("form"); } }); }}>Открыть задание снова</button> : null}
          {stage === "result" && patternId ? <ProjectPicker patternId={patternId} value={projectId} onChange={setProjectId} onError={setError} /> : null}
          {warnings.map((w, i) => <p key={i} role="status" className="api-notice">{w}</p>)}

          {exportOpen && patternId ? <ExportMenu formats={resultFormats} transparent={output.transparentBackground} patternId={patternId} onClose={() => setExportOpen(false)} /> : null}

      </section>
      {overlay}
    </>
  );
}
