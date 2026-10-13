"use client";

import { useLayoutEffect, useRef } from "react";

type FitTextProps = {
  children: string;
  className?: string;
  /** Откуда сжимается строка. */
  origin?: "left" | "center";
  /**
   * Два и больше слова: если не влезают в одну строку —
   * перенос, а не сжатие всей фразы в линию.
   */
  wrapWords?: boolean;
  /**
   * Вписать перенесённый текст в высоту родителя.
   * Для ленты опций (окно 56px). На карточке не нужно:
   * там блок сам растёт на вторую строку.
   */
  fitToBox?: boolean;
};

function wordCount(text: string) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function resetFitStyles(el: HTMLSpanElement) {
  el.style.transform = "scale(1)";
  el.style.fontSize = "";
  el.style.lineHeight = "";
  el.style.width = "";
  el.style.maxWidth = "";
  el.style.whiteSpace = "";
  el.style.display = "";
  el.style.overflow = "";
  el.style.webkitLineClamp = "";
  el.style.webkitBoxOrient = "";
}

/**
 * Если подпись шире родителя — один раз сжимает её через scale.
 * Без цикла по font-size. Чтобы выключить: замените <FitText> на <span>.
 *
 * Исключение: wrapWords + не влезает — перенос. Тогда font-size
 * подбирается только чтобы две строки встали в коробку ленты.
 */
export function FitText({
  children,
  className = "",
  origin = "left",
  wrapWords = false,
  fitToBox = false,
}: FitTextProps) {
  const ref = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const parent = el.parentElement;
    if (!parent) return;

    const fit = () => {
      const availableW = parent.clientWidth;
      const availableH = parent.clientHeight;
      if (availableW <= 0) return;

      resetFitStyles(el);
      el.style.whiteSpace = "nowrap";
      el.style.width = "max-content";
      el.style.maxWidth = "none";

      const singleWidth = Math.ceil(el.scrollWidth);
      const inheritedSize = parseFloat(getComputedStyle(el).fontSize) || 32;
      const canWrap = wrapWords && wordCount(children) >= 2;
      const overflows = singleWidth > availableW;

      if (canWrap && overflows) {
        el.style.whiteSpace = "normal";
        el.style.width = "100%";
        el.style.maxWidth = "100%";
        el.style.lineHeight = "1.22";
        el.style.display = "-webkit-box";
        el.style.webkitBoxOrient = "vertical";
        el.style.webkitLineClamp = "2";
        el.style.overflow = "visible";

        if (fitToBox && availableH > 0) {
          el.style.fontSize = `${inheritedSize}px`;
          const scale = Math.min(
            1,
            availableW / Math.max(el.scrollWidth, 1),
            availableH / Math.max(el.scrollHeight, 1),
          );
          el.style.transform = `scale(${scale})`;
        } else {
          el.style.transform = "scale(1)";
        }
        return;
      }

      el.style.width = "";
      el.style.maxWidth = "";
      el.style.whiteSpace = "nowrap";
      const scale =
        availableW > 0 && singleWidth > availableW
          ? availableW / singleWidth
          : 1;
      el.style.transform = `scale(${scale})`;
    };

    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [children, wrapWords, fitToBox]);

  return (
    <span
      ref={ref}
      className={[
        "inline-block",
        wrapWords ? "max-w-full" : "whitespace-nowrap",
        origin === "center" ? "origin-center" : "origin-left",
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
