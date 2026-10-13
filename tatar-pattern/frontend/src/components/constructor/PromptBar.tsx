"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";

type PromptBarProps = {
  noteOnly?: boolean;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  /** Активна, когда выбраны все 6 параметров. Текст в поле не обязателен. */
  canSubmit?: boolean;
  /** Клик по ещё неактивной отправке — подсказка под полем. */
  onBlockedSubmit?: () => void;
};

const DESKTOP = { line: 20, textMax: 63, empty: 63, expanded: 109, icon: 53 };
const MOBILE = { line: 14, textMax: 76, empty: 56, expanded: 92, icon: 44 };

/**
 * Поле «дополните свой запрос».
 * Один и тот же textarea — иначе при смене input→textarea сбрасывается курсор.
 * Высота растёт только когда текст уже не помещается в одну строку.
 */
export function PromptBar({
  noteOnly = true,
  value,
  onChange,
  onSubmit,
  canSubmit = false,
  onBlockedSubmit,
}: PromptBarProps) {
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [compact, setCompact] = useState(false);
  const sizes = compact ? MOBILE : DESKTOP;

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");
    const apply = () => setCompact(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  // Textarea height depends on measured DOM scrollHeight.
  /* eslint-disable react-hooks/set-state-in-effect */
  useLayoutEffect(() => {
    const field = fieldRef.current;
    if (!field) return;

    if (!value) {
      setExpanded(false);
      field.style.height = `${sizes.line}px`;
      return;
    }

    field.style.height = `${sizes.line}px`;
    const needsMoreLines = field.scrollHeight > sizes.line + 2;
    setExpanded(needsMoreLines);
    field.style.height = `${Math.min(
      Math.max(field.scrollHeight, sizes.line),
      sizes.textMax,
    )}px`;
  }, [value, sizes.line, sizes.textMax]);
  /* eslint-enable react-hooks/set-state-in-effect */

  function trySubmit() {
    if (canSubmit) {
      onSubmit();
      return;
    }
    onBlockedSubmit?.();
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        trySubmit();
      }}
      className={[
        noteOnly ? "prompt-note" : "",
        "flex w-full items-center overflow-hidden outline outline-[0.3px] -outline-offset-[0.3px] outline-hairline/60 [background-image:var(--gradient-prompt)]",
        compact ? "rounded-[17px] p-[5px]" : "rounded-[24px] p-[5px]",
        expanded
          ? compact
            ? "min-h-[92px] max-w-[369px] gap-[18px]"
            : "min-h-[109px] max-w-[703px] gap-[12px]"
          : compact
            ? "h-[56px] max-w-[369px] gap-[8px]"
            : "h-[63px] max-w-[687px] gap-[8px]",
      ].join(" ")}
    >
      <textarea
        ref={fieldRef}
        aria-label={noteOnly ? "Заметка к узору" : "Запрос для ИИ"}
        maxLength={2000}
        rows={1}
        value={value}
        placeholder={noteOnly ? "Заметка к узору (не влияет на рисунок)" : "Опишите желаемый узор"}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            trySubmit();
          }
        }}
        className={[
          "min-w-0 flex-1 resize-none bg-transparent font-medium outline-none placeholder:text-black placeholder:opacity-30",
          compact
            ? "text-[14px] leading-[14px]"
            : "text-[20px] leading-[20px]",
          expanded
            ? compact
              ? "tracking-[0.14px] text-ink-body"
              : "tracking-[0.2px] text-ink-body"
            : "px-[16px] text-black max-md:px-[8px]",
        ].join(" ")}
      />
      <button
        type="submit"
        aria-label="Сгенерировать"
        aria-disabled={!canSubmit}
        onClick={(event) => {
          event.preventDefault();
          trySubmit();
        }}
        className={
          canSubmit
            ? "pressable-icon shrink-0"
            : "shrink-0 cursor-pointer opacity-70"
        }
      >
        <Icon
          name={canSubmit ? "send-active" : "send"}
          width={sizes.icon}
          height={sizes.icon}
          className="pointer-events-none"
        />
      </button>
    </form>
  );
}
