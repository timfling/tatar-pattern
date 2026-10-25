"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";
import { loadLibrary, type SavedPattern } from "@/lib/library";
import {
  addProject,
  deleteProjects,
  formatProjectDate,
  generationsLabel,
  loadProjects,
  renameProject,
  type SavedProject,
} from "@/lib/projects";

import { loadPreferences } from "@/lib/preferences";
import { apiMessage } from "@/lib/api";

type HistoryView = "tiles" | "rows";

export function AccountLibraryScreen() {
  const router = useRouter();
  const [items, setItems] = useState<SavedPattern[]>([]);
  const [projects, setProjects] = useState<SavedProject[]>([]);
  const [modeFilter, setModeFilter] = useState<"all" | "flat" | "ai">("all");
  const [view, setView] = useState<HistoryView>("tiles");
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [projectFilter, setProjectFilter] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      const [history, folders] = await Promise.all([loadLibrary(), loadProjects()]);
      setItems(history); setProjects(folders); setError("");
    } catch (e) { setError(apiMessage(e)); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    // Browser preference is applied together with asynchronously loaded history.
    Promise.all([loadLibrary(), loadProjects()]).then(([history, folders]) => {
      if (active) { setItems(history); setProjects(folders); setView(loadPreferences().libraryView); try { const saved = JSON.parse(sessionStorage.getItem("tp-library-view") ?? "{}"); if(saved.view === "tiles" || saved.view === "rows") setView(saved.view); if(saved.project) setProjectFilter(saved.project); if(["all","flat","ai"].includes(saved.mode)) setModeFilter(saved.mode); } catch {} }
    }).catch((e) => { if (active) setError(apiMessage(e)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => { if(!loading) sessionStorage.setItem("tp-library-view", JSON.stringify({view,project:projectFilter,mode:modeFilter})); }, [view,projectFilter,modeFilter,loading]);
  const history = items.filter((item) => (!projectFilter || item.projectId === projectFilter) && (modeFilter === "all" || item.mode === modeFilter));
  async function mutate(action: () => Promise<unknown>) {
    if (pending) return;
    setPending(true);
    try { await action(); await refresh(); }
    catch (e) { setError(apiMessage(e)); }
    finally { setPending(false); }
  }

  const projectNames = new Map(projects.map((project) => [project.id, project.name]));

  function openPattern(id: string) {
    router.push(`/constructor?pattern=${encodeURIComponent(id)}&from=library`);
  }

  function handleAdd() {
    void mutate(() => addProject());
    setEditing(false);
    setSelected(new Set());
  }

  function toggleEdit() {
    setEditing((current) => {
      if (current) setSelected(new Set());
      return !current;
    });
  }

  function toggleSelect(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleDelete() {
    if (selected.size === 0) return;
    void mutate(() => deleteProjects([...selected]));
    setSelected(new Set());
    setEditing(false);
  }

  function handleRename(id: string, name: string) {
    void mutate(() => renameProject(id, name));
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-tl-[24px] rounded-bl-[3px] bg-surface px-[58px] pt-[60px] max-md:rounded-none max-md:bg-transparent max-md:px-[27px] max-md:pt-[24px]">
      <div className="min-h-0 flex-1 overflow-y-auto pb-[12px]">
        {error ? <div role="alert" className="api-error">{error} <button onClick={refresh} className="underline">Повторить</button></div> : null}
        {loading || pending ? <p role="status" className="api-notice">{loading ? "Загружаем библиотеку…" : "Сохраняем изменения…"}</p> : null}
        <div className="flex flex-wrap items-center gap-x-[12px] gap-y-[8px]">
          <h1 className="font-display text-[36px] italic leading-none text-black max-md:text-[28px]">
            Ваши проекты
          </h1>
          <button
            type="button"
            disabled={pending || loading}
            aria-label="Новый проект"
            onClick={handleAdd}
            className="pressable-icon text-[#8B8B8B]"
          >
            <PlusGlyph />
          </button>
          <button
            type="button"
            aria-label="Редактировать проекты"
            aria-pressed={editing}
            onClick={toggleEdit}
            className={`pressable-icon ${editing ? "text-black" : "text-[#8B8B8B]"}`}
          >
            <PencilGlyph />
          </button>
          {editing ? (
            <button
              type="button"
              disabled={selected.size === 0 || pending}
              onClick={handleDelete}
              className="pressable rounded-[16px] bg-white px-[12px] py-[6px] text-[14px] font-semibold text-[#C45C5C] disabled:cursor-default disabled:opacity-30"
            >
              Удалить
            </button>
          ) : null}
        </div>

        <div className="mt-[40px] flex flex-wrap content-start gap-x-[18px] gap-y-[15px] max-md:mt-[23px] max-md:gap-x-[12px] max-md:gap-y-[10px]">
          {projects.map((project) => {
            const count = items.filter((item) => item.projectId === project.id).length;
            return (
              <ProjectCard
                key={project.id}
                project={project}
                count={count}
                editing={editing}
                selected={selected.has(project.id)}
                onSelect={() => toggleSelect(project.id)}
                onOpen={() => setProjectFilter((id) => id === project.id ? null : project.id)}
                active={projectFilter === project.id}
                onRename={(name) => handleRename(project.id, name)}
              />
            );
          })}
        </div>

        {!loading && !projects.length ? <p className="api-notice">Создайте проект, чтобы объединить результаты в коллекцию.</p> : null}
        {projectFilter ? <button className="mt-6 underline" onClick={() => setProjectFilter(null)}>Вся история</button> : null}
        <label className="mt-8 flex flex-wrap items-center gap-3 text-sm">Тип генерации<select aria-label="Тип генерации" className="rounded-xl bg-white px-3 py-2" value={modeFilter} onChange={(e) => setModeFilter(e.target.value as "all" | "flat" | "ai")}><option value="all">Все режимы</option><option value="flat">Flat-рисунки</option><option value="ai">ИИ-варианты</option></select></label>
        <div className="mt-[64px] flex items-center justify-between max-md:mt-[51px]">
          <h2 className="font-display text-[36px] italic leading-none text-black max-md:text-[28px]">
            История генераций
          </h2>
          <div className="flex items-center gap-[14px] max-md:gap-0">
            <button
              type="button"
              aria-label="Вид плитка"
              aria-pressed={view === "tiles"}
              onClick={() => setView("tiles")}
              className={`pressable-icon ${view === "tiles" ? "opacity-100" : "opacity-40"}`}
            >
              <Icon
                name="51c4d2d3"
                width={35}
                height={33}
                className="hidden md:block"
              />
              <Icon
                name="bb1801f5"
                width={24}
                height={23}
                className="md:hidden"
              />
            </button>
            <button
              type="button"
              aria-label="Вид строками"
              aria-pressed={view === "rows"}
              onClick={() => setView("rows")}
              className={`pressable-icon ${view === "rows" ? "opacity-100" : "opacity-40"}`}
            >
              <Icon name="4033b369" width={36} height={33} />
            </button>
          </div>
        </div>

        <div className="mt-[39px] max-md:mt-[23px]">
          {!loading && !history.length ? <p className="api-notice">{projectFilter ? "В проекте пока нет результатов." : "Здесь появятся ваши сохранённые генерации."}</p> : null}
          {view === "rows" ? (
            <div className="flex flex-col gap-[12px]">
              {history.map((item, index) => (
                <HistoryRow
                  key={item?.id ?? `empty-${index}`}
                  item={item}
                  projectName={
                    item?.projectId
                      ? (projectNames.get(item.projectId) ?? null)
                      : null
                  }
                  onOpen={item ? () => openPattern(item.id) : undefined}
                />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-[22px] max-md:grid-cols-2 max-md:gap-[12px]">
              {history.map((item, index) => (
                <HistoryTile
                  key={item?.id ?? `empty-${index}`}
                  item={item}
                  placeholderIndex={index}
                  projectName={
                    item?.projectId
                      ? (projectNames.get(item.projectId) ?? null)
                      : null
                  }
                  onOpen={item ? () => openPattern(item.id) : undefined}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      <p className="shrink-0 pb-[24px] pt-[12px] text-center text-[15px] font-semibold leading-[15px] text-ink-disclaimer max-md:text-[11px]">
        История хранится в вашем аккаунте
      </p>
    </section>
  );
}

function ProjectCard({
  project,
  count,
  editing,
  selected,
  onSelect,
  onRename,
  onOpen,
  active,
}: {
  onOpen: () => void;
  active: boolean;
  project: SavedProject;
  count: number;
  editing: boolean;
  selected: boolean;
  onSelect: () => void;
  onRename: (name: string) => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState(project.name);
  const inputRef = useRef<HTMLInputElement>(null);


  useEffect(() => {
    if (renaming) inputRef.current?.select();
  }, [renaming]);

  function commit() {
    const next = draft.trim() || "Новый проект";
    setDraft(next);
    onRename(next);
    setRenaming(false);
  }

  return (
    <article
      role={editing ? "checkbox" : "button"}
      aria-checked={editing ? selected : undefined}
      tabIndex={0}
      onKeyDown={(event) => { if (event.target === event.currentTarget && (event.key === "Enter" || event.key === " ")) { event.preventDefault(); if (editing) onSelect(); else onOpen(); } }}
      className={[
        "flex h-[160px] w-[min(100%,320px)] flex-col justify-center gap-[46px] rounded-[18px] bg-white px-[24px] py-[20px] max-md:h-[125px] max-md:w-[210px] max-md:gap-[32px] max-md:rounded-[13px] max-md:px-[17px] max-md:py-[14px]",
        "cursor-pointer",
        selected || active ? "outline outline-[2px] -outline-offset-[2px] outline-black" : "",
      ].join(" ")}
      onClick={editing ? onSelect : onOpen}
    >
      <h2 className="min-h-[54px] text-[22px] font-medium leading-tight text-black max-md:min-h-[40px] max-md:text-[18px]">
        {renaming ? (
          <input
            ref={inputRef}
            value={draft}
            aria-label="Имя проекта"
            onClick={(event) => event.stopPropagation()}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                commit();
              }
              if (event.key === "Escape") {
                setDraft(project.name);
                setRenaming(false);
              }
            }}
            className="w-full bg-transparent text-[22px] font-medium leading-tight text-black outline-none max-md:text-[18px]"
          />
        ) : (
          <button
            type="button"
            disabled={editing}
            onClick={(event) => {
              event.stopPropagation();
              if (!editing) onOpen();
            }}
            className="pressable-quiet w-full cursor-text text-left disabled:cursor-pointer"
            aria-label={`Открыть проект ${project.name}`}
          >
            {project.name}
          </button>
        )}
      </h2>
      <div className="flex items-center justify-between gap-[16px] text-[15px] font-semibold text-[#4E4E4E] max-md:text-[11px]">
        <button type="button" onClick={(e) => { e.stopPropagation(); onOpen(); }} className="underline" aria-label={`Открыть проект ${project.name}`}>{generationsLabel(count)}</button>
        <button aria-label={`Переименовать проект ${project.name}`} onClick={e => { e.stopPropagation(); setDraft(project.name); setRenaming(true); }} className="p-2">✎</button><span>{formatProjectDate(project.createdAt)}</span>
      </div>
    </article>
  );
}

function HistoryTile({
  item,
  placeholderIndex,
  projectName,
  onOpen,
}: {
  item: SavedPattern | null;
  placeholderIndex: number;
  projectName: string | null;
  onOpen?: () => void;
}) {
  const body = (
    <>
      {item?.imageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={item.imageUrl}
          alt={item.name}
          className="absolute inset-0 size-full object-contain"
        />
      ) : item ? (
        <p role="status" className="api-notice">{item.status === "queued" ? "В очереди" : item.status === "processing" ? "Обрабатывается" : item.status === "cancelled" ? "Отменено" : item.status === "failed" || item.status === "error" ? "Ошибка задания" : "Изображение недоступно"}</p>
      ) : null}

      {item ? (
        <div className="pointer-events-none absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-black/65 via-black/20 to-transparent px-[14px] py-[12px] opacity-0 max-md:opacity-100 transition-opacity duration-150 [@media(hover:hover)]:group-hover:opacity-100">
          <p className="truncate text-[16px] font-semibold leading-[20px] text-white">
            {item.name}
          </p>
          <p className="mt-[4px] text-[13px] font-medium leading-[16px] text-white/85">
            {item.mode === "ai" ? "ИИ-вариант" : "Flat-рисунок"} · {item.stamp}
          </p>
          {projectName ? (
            <p className="mt-[2px] truncate text-[13px] font-medium leading-[16px] text-white/75">
              {projectName}
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );

  const className = [
    "group relative aspect-square overflow-hidden rounded-[22px] bg-white max-md:rounded-[15px]",
    item ? "pressable" : "",
    !item && placeholderIndex >= 4 ? "max-md:hidden" : "",
  ].join(" ");

  if (item && onOpen) {
    return (
      <button type="button" onClick={onOpen} className={className} aria-label={item.name}>
        {body}
      </button>
    );
  }

  return <article className={className}>{body}</article>;
}

function HistoryRow({
  item,
  projectName,
  onOpen,
}: {
  item: SavedPattern | null;
  projectName: string | null;
  onOpen?: () => void;
}) {
  const inner = (
    <>
      <div className="relative size-[72px] shrink-0 overflow-hidden rounded-[14px] bg-white">
        {item?.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={item.imageUrl}
            alt=""
            className="absolute inset-0 size-full object-contain"
          />
        ) : item ? (
          <p role="status" className="api-notice">{item.status === "queued" ? "В очереди" : item.status === "processing" ? "Обрабатывается" : item.status === "cancelled" ? "Отменено" : item.status === "failed" || item.status === "error" ? "Ошибка задания" : "Изображение недоступно"}</p>
        ) : null}
      </div>
      {item ? (
        <div className="min-w-0 flex-1 text-left">
          <p className="truncate text-[18px] font-medium text-black">{item.name}</p>
          <p className="mt-[4px] text-[14px] font-semibold text-[#4E4E4E]">{item.mode === "ai" ? "ИИ-вариант" : "Flat-рисунок"} · {item.stamp}</p>
          {projectName ? (
            <p className="mt-[2px] truncate text-[13px] font-medium text-[#8B8B8B]">
              {projectName}
            </p>
          ) : null}
        </div>
      ) : null}
    </>
  );

  if (item && onOpen) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="pressable flex w-full items-center gap-[18px] rounded-[18px] bg-white px-[20px] py-[14px] text-left"
      >
        {inner}
      </button>
    );
  }

  return (
    <article className="flex items-center gap-[18px] rounded-[18px] bg-white px-[20px] py-[14px]">
      {inner}
    </article>
  );
}

function PlusGlyph() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden>
      <path
        d="M14 6v16M6 14h16"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function PencilGlyph() {
  return (
    <svg width="26" height="26" viewBox="0 0 26 26" fill="none" aria-hidden>
      <path
        d="M16.8 5.2l4 4L8.5 21.5H4.5v-4L16.8 5.2z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M14.7 7.3l4 4"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}
