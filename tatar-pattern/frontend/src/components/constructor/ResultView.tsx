"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { BackButton } from "@/components/constructor/BackButton";
import { PatternCanvas } from "@/components/constructor/PatternCanvas";
import { LikeButton, DislikeButton } from "@/components/constructor/LikeButton";
import { GenerationInfo } from "@/components/constructor/GenerationInfo";
import type { ParameterTile, ConstructorSelections } from "@/components/constructor/parameters";
import type { GuestGeneration as Generation } from "@/lib/api";
import type { PatternRating } from "@/lib/library";

import {
  DEFAULT_PATTERN_NAME,
} from "@/components/constructor/data";

type ResultViewProps = {
  editLabel?: string;
  generation?: Generation | null;
  infoDetails?: { title: string; value: string }[];
  imageUrl: string | null; imageSize?: number[] | null; onDelete?: () => Promise<void>;
  repeatPreview?: boolean; onImageError?: () => void; exportDisabled?: boolean; tiles?: ParameterTile[];
  stamp: string;
  name: string;
  rating: PatternRating;
  selections: ConstructorSelections;
  prompt: string;
  editOpen: boolean;
  onBack: () => void;
  onEdit: () => void;
  onCloseEdit: () => void;
  onSubmitEdit: (text: string) => void;
  onExpand: () => void;
  onExport: () => void;
  onRename?: (name: string) => void;
  onRate?: (rating: PatternRating) => void;
};

export function ResultView({
  editLabel = "Редактировать", imageUrl, generation, infoDetails, imageSize, onDelete, repeatPreview, onImageError, exportDisabled, tiles,
  stamp,
  name,
  rating,
  selections,
  prompt,
  editOpen,
  onBack,
  onEdit,
  onCloseEdit,
  onSubmitEdit,
  onExpand,
  onExport,
  onRename,
  onRate,
}: ResultViewProps) {
  const [naturalRatio, setNaturalRatio] = useState(1);
  const aspect = imageSize?.[0] && imageSize?.[1] ? imageSize[0] / imageSize[1] : naturalRatio;
  return (
    <div className="constructor-stage flex min-h-0 flex-1 flex-col max-md:flex-none">
      <div className="relative hidden shrink-0 px-[25px] pt-[25px] md:block">
        <BackButton onClick={onBack} />
        <PatternMeta name={name} stamp={stamp} onRename={onRename} />
        <div className="absolute right-[25px] top-[25px] flex items-center gap-3">
          {onDelete ? <DeleteButton onDelete={onDelete} /> : null}<GenerationInfo generation={generation} details={infoDetails} tiles={tiles} selections={selections} prompt={prompt} />
        </div>
      </div>

      <div className="hidden min-h-0 flex-1 flex-col items-center px-[24px] py-[20px] md:flex">
        <div className="flex min-h-0 w-full flex-1 items-center justify-center [container-type:size]">
          <div className="flex max-h-full flex-col items-center">
            <button
              type="button"
              onClick={onExpand}
              aria-label="Открыть на весь экран"
              className="pressable cursor-zoom-in overflow-hidden rounded-[24px] bg-transparent p-0 shadow-[0px_0px_64px_rgba(0,0,0,0.05),0px_0px_30px_rgba(0,0,0,0.10)_inset]"
              style={{
                width: `min(100cqw, 966px, calc((100cqh - 70px) * ${aspect}), ${724 * aspect}px)`,
                aspectRatio: aspect,
              }}
            >
              <PatternCanvas repeatPreview={repeatPreview} onImageError={onImageError} onImageLoad={(w,h) => setNaturalRatio(w/h)} imageUrl={imageUrl} className="size-full" />
            </button>

            <div
              className={[
                "mt-[18px] hidden w-full max-w-[966px] shrink-0 items-center md:flex",
                editOpen || !onRate ? "justify-center" : "justify-between px-[12px] sm:px-[34px]",
              ].join(" ")}
            >
              {editOpen ? (
                <RefinePrompt onSubmit={onSubmitEdit} onClose={onCloseEdit} />
              ) : (
                <>
                  <div className="flex items-center gap-[12px]">
                    <button
                      type="button"
                      onClick={onEdit}
                      className="pressable flex items-center gap-[8px] overflow-hidden rounded-[24px] bg-surface-muted px-[26px] py-[12px] outline outline-[0.5px] -outline-offset-[0.5px] outline-hairline"
                    >
                      <Icon name="edit-sparkle" width={20} height={20} />
                      <span className="text-[20px] font-semibold leading-[20px] text-black opacity-90">
                        {editLabel}
                      </span>
                    </button>
                    <button
                      type="button"
                      disabled={exportDisabled} onClick={onExport}
                      className="pressable flex items-center gap-[10px] overflow-hidden rounded-[24px] bg-surface-muted px-[26px] py-[12px] outline outline-[0.5px] -outline-offset-[0.5px] outline-hairline"
                    >
                      <Icon name="export" width={18} height={21} />
                      <span className="text-[20px] font-semibold leading-[20px] text-black opacity-90">
                        Экспортировать
                      </span>
                    </button>
                  </div>

                  {onRate ? <RatingButtons rating={rating} onRate={onRate} size={45} /> : null}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-center px-[16px] py-[12px] md:hidden">
        <PatternMeta name={name} stamp={stamp} onRename={onRename} compact />

        <div className="mt-[14px] flex w-full max-w-[323px] flex-col items-center">
          <button
            type="button"
            onClick={onExpand}
            aria-label="Открыть на весь экран"
            style={{ aspectRatio: aspect, width: `min(100%, ${Math.min(323, 440*aspect)}px)` }}
            className="pressable w-full cursor-zoom-in overflow-hidden rounded-[14px] bg-transparent p-0 shadow-[0px_0px_32px_rgba(0,0,0,0.05),0px_0px_15px_rgba(0,0,0,0.05)_inset]"
          >
            <PatternCanvas repeatPreview={repeatPreview} onImageError={onImageError} onImageLoad={(w,h) => setNaturalRatio(w/h)} imageUrl={imageUrl} className="size-full" />
          </button>

          <div className="mt-[14px] flex w-full items-center justify-between px-[10px]">
            <div className="flex gap-3"><GenerationInfo generation={generation} details={infoDetails} tiles={tiles} selections={selections} prompt={prompt} compact />{onDelete ? <DeleteButton onDelete={onDelete} compact /> : null}</div>
            {onRate ? <RatingButtons rating={rating} onRate={onRate} size={32} /> : null}
          </div>

          <div className="mt-[30px] flex w-full flex-col items-center gap-[9px]">
            {editOpen ? (
              <RefinePrompt onSubmit={onSubmitEdit} onClose={onCloseEdit} compact />
            ) : (
              <>
                <ActionButton onClick={onEdit} icon="edit-sparkle" iconW={16} iconH={16}>
                  {editLabel}
                </ActionButton>
                <ActionButton disabled={exportDisabled} onClick={onExport} icon="export" iconW={14} iconH={16}>
                  Экспортировать
                </ActionButton>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PatternMeta({
  name,
  stamp,
  onRename,
  compact = false,
}: {
  name: string;
  stamp: string;
  onRename?: (name: string) => void;
  compact?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const inputRef = useRef<HTMLInputElement>(null);


  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function commit() {
    const next = draft.trim() || DEFAULT_PATTERN_NAME;
    setDraft(next);
    onRename?.(next);
    setEditing(false);
  }

  return (
    <div
      className={
        compact
          ? "flex flex-col items-center gap-[6px] px-[19px] py-[3px]"
          : "absolute left-1/2 top-[25px] flex -translate-x-1/2 flex-col items-center gap-[8px] px-[24px] py-[4px]"
      }
    >
      <div
        className={
          compact
            ? "rounded-[11px] px-[11px] py-[6px] outline outline-[0.4px] -outline-offset-[0.4px] outline-hairline"
            : "rounded-[14px] px-[14px] py-[8px] outline outline-[0.5px] -outline-offset-[0.5px] outline-hairline"
        }
      >
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            aria-label="Имя паттерна"
            onChange={(event) => setDraft(event.target.value)}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                commit();
              }
              if (event.key === "Escape") {
                setDraft(name);
                setEditing(false);
              }
            }}
            className={
              compact
                ? "w-[min(70vw,240px)] bg-transparent text-center text-[19px] font-semibold leading-[19px] text-ink-body outline-none"
                : "w-[280px] bg-transparent text-center text-[24px] font-semibold leading-[24px] text-ink-body outline-none"
            }
          />
        ) : (
          <button
            type="button"
            disabled={!onRename}
            onClick={() => { setDraft(name); setEditing(true); }}
            className="pressable-quiet cursor-text"
            aria-label={onRename ? "Переименовать паттерн" : undefined}
          >
            <p
              className={
                compact
                  ? "text-[19px] font-semibold leading-[19px] text-ink-body"
                  : "text-[24px] font-semibold leading-[24px] text-ink-body"
              }
            >
              {name}
            </p>
          </button>
        )}
      </div>
      <p
        className={
          compact
            ? "text-[16px] font-semibold leading-[16px] text-ink-body opacity-70"
            : "text-[20px] font-semibold leading-[20px] text-ink-body opacity-70"
        }
      >
        {stamp}
      </p>
    </div>
  );
}

function RatingButtons({
  rating,
  onRate,
  size,
}: {
  rating: PatternRating;
  onRate?: (rating: PatternRating) => void;
  size: 32 | 45;
}) {
  return (
    <div className="flex items-center gap-[12px]">
      <LikeButton
        pressed={rating === "like"}
        onToggle={() => onRate?.(rating === "like" ? null : "like")}
        size={size}
      />
      <DislikeButton
        pressed={rating === "dislike"}
        onToggle={() => onRate?.(rating === "dislike" ? null : "dislike")}
        size={size}
      />
    </div>
  );
}

function ActionButton({
  children,
  icon,
  iconW,
  iconH,
  onClick, disabled,
}: {
  disabled?: boolean;
  children: string;
  icon: string;
  iconW: number;
  iconH: number;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="pressable disabled:opacity-40 flex w-[187px] items-center justify-center gap-[6px] overflow-hidden rounded-[26px] bg-white/70 px-[20px] py-[13px] outline outline-[0.4px] -outline-offset-[0.4px] outline-hairline"
    >
      <Icon name={icon} width={iconW} height={iconH} />
      <span className="text-[15px] font-semibold leading-[15px] text-black opacity-90">
        {children}
      </span>
    </button>
  );
}

function RefinePrompt({
  onSubmit,
  onClose,
  compact = false,
}: {
  onSubmit: (text: string) => void;
  onClose: () => void;
  compact?: boolean;
}) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function submit() {
    const next = text.trim();
    if (!next) return;
    onSubmit(next);
  }

  return (
    <div
      className={[
        "edit-prompt-in flex items-center",
        compact ? "w-full max-w-[369px] gap-[8px]" : "gap-[6px]",
      ].join(" ")}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          submit();
        }}
        className={[
          "relative flex items-center overflow-hidden outline outline-[0.3px] -outline-offset-[0.3px] outline-hairline/60 [background-image:var(--gradient-prompt)]",
          compact
            ? "h-[44px] w-full rounded-[40px] p-[4px]"
            : "h-[50px] w-[601px] max-w-[601px] rounded-[60px] p-[5px]",
        ].join(" ")}
      >
        {!text ? (
          <div
            aria-hidden
            className={[
              "pointer-events-none absolute flex items-center gap-[8px] opacity-40",
              compact ? "left-[14px]" : "left-[22px]",
            ].join(" ")}
          >
            <Icon
              name="edit-sparkle"
              width={compact ? 16 : 20}
              height={compact ? 16 : 20}
            />
            <span
              className={
                compact
                  ? "text-[14px] font-medium leading-[14px] text-black"
                  : "text-[20px] font-medium leading-[20px] text-black"
              }
            >
              Опишите изменения…
            </span>
          </div>
        ) : null}
        <input
          ref={inputRef}
          value={text}
          aria-label="Опишите изменения"
          onChange={(event) => setText(event.target.value)}
          className={[
            "min-w-0 flex-1 bg-transparent font-medium text-ink-body outline-none",
            compact
              ? "px-[14px] text-[14px] leading-[14px]"
              : "px-[22px] text-[20px] leading-[20px]",
          ].join(" ")}
        />
        <button
          type="submit"
          aria-label="Отправить правку"
          className={[
            "pressable flex shrink-0 items-center justify-center outline outline-[1px] -outline-offset-[1px] outline-hairline/50",
            text.trim()
              ? "bg-[linear-gradient(165deg,#D9924C_0%,#E3B180_100%)]"
              : "bg-[linear-gradient(165deg,#CFC6C0_0%,#E7DDD7_100%)]",
            compact ? "size-[36px] rounded-[18px]" : "h-[40px] w-[68px] rounded-[20px]",
          ].join(" ")}
        >
          <SendUpArrow />
        </button>
      </form>
      <button
        type="button"
        aria-label="Закрыть окно правки"
        onClick={onClose}
        className="pressable-quiet shrink-0 p-[4px] opacity-50"
      >
        <CloseGlyph />
      </button>
    </div>
  );
}

function SendUpArrow() {
  return (
    <svg width="19" height="21" viewBox="0 0 19 21" fill="none" aria-hidden>
      <path
        d="M7.95508 19.25C7.95508 19.9404 8.51472 20.5 9.20508 20.5C9.89543 20.5 10.4551 19.9404 10.4551 19.25H9.20508H7.95508ZM10.089 0.366116C9.60081 -0.122038 8.80935 -0.122038 8.32119 0.366116L0.366243 8.32107C-0.121912 8.80922 -0.121912 9.60068 0.366243 10.0888C0.854399 10.577 1.64585 10.577 2.13401 10.0888L9.20508 3.01777L16.2761 10.0888C16.7643 10.577 17.5558 10.577 18.0439 10.0888C18.5321 9.60068 18.5321 8.80922 18.0439 8.32107L10.089 0.366116ZM9.20508 19.25H10.4551L10.4551 1.25H9.20508H7.95508L7.95508 19.25H9.20508Z"
        fill="white"
      />
    </svg>
  );
}

function CloseGlyph() {
  return (
    <svg width="15" height="15" viewBox="0 0 15 15" fill="none" aria-hidden>
      <path
        d="M7.44894 9.03503L1.89764 14.5863C1.68994 14.794 1.42559 14.8979 1.1046 14.8979C0.783602 14.8979 0.519254 14.794 0.311552 14.5863C0.103851 14.3786 0 14.1143 0 13.7933C0 13.4723 0.103851 13.208 0.311552 13.0002L5.86286 7.44894L0.311552 1.89764C0.103851 1.68994 0 1.42559 0 1.1046C0 0.783602 0.103851 0.519254 0.311552 0.311552C0.519254 0.103851 0.783602 0 1.1046 0C1.42559 0 1.68994 0.103851 1.89764 0.311552L7.44894 5.86286L13.0002 0.311552C13.208 0.103851 13.4723 0 13.7933 0C14.1143 0 14.3786 0.103851 14.5863 0.311552C14.794 0.519254 14.8979 0.783602 14.8979 1.1046C14.8979 1.42559 14.794 1.68994 14.5863 1.89764L9.03503 7.44894L14.5863 13.0002C14.794 13.208 14.8979 13.4723 14.8979 13.7933C14.8979 14.1143 14.794 14.3786 14.5863 14.5863C14.3786 14.794 14.1143 14.8979 13.7933 14.8979C13.4723 14.8979 13.208 14.794 13.0002 14.5863L7.44894 9.03503Z"
        fill="#666666"
      />
    </svg>
  );
}

function DeleteButton({ onDelete, compact = false }: { onDelete: () => Promise<void>; compact?: boolean }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [pending,setPending] = useState(false); const [error,setError] = useState("");
  async function remove() { if(pending) return; setPending(true); try { await onDelete(); dialog.current?.close(); } catch(e) { setError(e instanceof Error ? e.message : "Не удалось удалить работу"); } finally { setPending(false); } }
  return <><button aria-label="Переместить в корзину" onClick={() => dialog.current?.showModal()} className={`pressable-icon flex items-center justify-center rounded-full border border-hairline/60 ${compact ? "size-8" : "size-[52px]"}`}><svg width="22" height="24" viewBox="0 0 24 24" fill="none" aria-hidden><path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg></button><dialog ref={dialog} className="studio-dialog max-w-[460px]!" onClick={e => { if(e.target === e.currentTarget && !pending) dialog.current?.close(); }}><h2 className="font-display text-2xl italic">Переместить работу в корзину?</h2><p className="my-5 text-sm leading-relaxed">Работа исчезнет из библиотеки. Её можно будет восстановить в течение семи дней.</p><div className="flex flex-wrap gap-3"><button disabled={pending} onClick={() => dialog.current?.close()} className="studio-button">Оставить</button><button disabled={pending} onClick={() => void remove()} className="studio-button text-red-700">{pending ? "Перемещаем…" : "В корзину"}</button></div>{error ? <p role="alert" className="api-error">{error}</p> : null}</dialog></>;
}
