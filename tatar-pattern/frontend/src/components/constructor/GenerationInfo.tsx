"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";
import { recipeLines } from "@/components/constructor/parameters";
import type { ParameterTile, ConstructorSelections } from "@/components/constructor/parameters";

type GenerationInfoProps = {
  selections: ConstructorSelections;
  prompt: string;
  details?: { title: string; value: string }[];
  compact?: boolean; tiles?: ParameterTile[];
};

/**
 * Кнопка «i» и окно «О генерации».
 * Кадр: 313×514, стекло 70%, Raleway 500/600, «Нет» — Instrument Sans italic.
 */
export function GenerationInfo({
  selections,
  prompt,
  compact = false, tiles, details = [],
}: GenerationInfoProps) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const lines = [...recipeLines(selections, prompt, tiles), ...details];

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-label="О генерации"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="pressable-icon"
      >
        {compact ? (
          <Icon name="info-sm" width={32} height={32} />
        ) : (
          <Icon name="info" width={52} height={52} />
        )}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="О генерации"
          className={[
            "popover-enter absolute z-30 overflow-y-auto rounded-[24px] bg-white/70 px-[25px] pb-[28px] pt-[26px] shadow-[0px_8px_32px_rgba(0,0,0,0.10)] outline outline-[0.5px] -outline-offset-[0.5px] outline-[rgba(102,102,102,0.5)] backdrop-blur-[20px]",
            compact
              ? "bottom-[calc(100%+8px)] left-0 max-h-[min(514px,55dvh)] w-[min(313px,calc(100vw-32px))]"
              : "right-0 top-[60px] max-h-[min(514px,80vh)] w-[313px]",
          ].join(" ")}
        >
          <p className="text-[24px] font-semibold leading-[24px] text-[#292929]">
            О генерации
          </p>
          <dl className="mt-[24px] flex flex-col gap-[24px]">
            {lines.map((line) => {
              const empty = line.value === "Нет";
              return (
                <div key={line.title} className="flex flex-col gap-[6px]">
                  <dt className="text-[16px] font-medium leading-[16px] text-black">
                    {line.title}
                  </dt>
                  <dd
                    className={
                      empty
                        ? "font-ui text-[16px] font-normal italic leading-[16px] text-black opacity-95"
                        : "text-[18px] font-semibold leading-[18px] text-black opacity-90"
                    }
                  >
                    {line.title === "Мотивы" && line.value !== "не выбраны" ? <ol className="list-decimal space-y-2 pl-5">{line.value.split("\n").map((name,index) => <li key={index}>{name}</li>)}</ol> : line.value}
                  </dd>
                </div>
              );
            })}
          </dl>
        </div>
      ) : null}
    </div>
  );
}
