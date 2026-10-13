"use client";

import { Icon } from "@/components/ui/Icon";
import { FitText } from "@/components/ui/FitText";

/**
 * Форма скругления зависит от места карточки.
 * Десктоп — сетка 3×2, внешние углы 32px.
 * Мобайл — сетка 2×3, внешние углы 26/24px, остальные 14px.
 */
const CORNER = {
  "top-left": "rounded-[16px] rounded-tl-[32px]",
  "top-right": "rounded-[16px] rounded-tr-[32px]",
  "bottom-left": "rounded-[16px] rounded-bl-[32px]",
  "bottom-right": "rounded-[16px] rounded-br-[32px]",
  none: "rounded-[16px]",
} as const;

const MOBILE_CORNER = {
  "top-left":
    "max-md:rounded-[14px] max-md:rounded-tl-[26px] max-md:rounded-tr-[14px] max-md:rounded-bl-[14px] max-md:rounded-br-[14px]",
  "top-right":
    "max-md:rounded-[14px] max-md:rounded-tl-[14px] max-md:rounded-tr-[24px] max-md:rounded-bl-[14px] max-md:rounded-br-[14px]",
  "bottom-left":
    "max-md:rounded-[14px] max-md:rounded-tl-[14px] max-md:rounded-tr-[14px] max-md:rounded-bl-[24px] max-md:rounded-br-[14px]",
  "bottom-right":
    "max-md:rounded-[14px] max-md:rounded-tl-[14px] max-md:rounded-tr-[14px] max-md:rounded-bl-[14px] max-md:rounded-br-[24px]",
  none: "max-md:rounded-[14px]",
} as const;

export type ParameterCardProps = {
  label: string;
  /** Текущее значение параметра либо приглашение к выбору. */
  value: string;
  /** Значение выбрано пользователем — меняет начертание подписи. */
  isSet?: boolean;
  /** В макете «По умолчанию» набрано чёрным, а счётчик мотивов — серым. */
  tone?: "subtle" | "strong";
  corner?: keyof typeof CORNER;
  mobileCorner?: keyof typeof MOBILE_CORNER;
  /** Открытая карточка в макете — пустой контур, поверх неё лежит окно. */
  ghost?: boolean;
  onClick?: () => void;
};

export function ParameterCard({
  label,
  value,
  isSet = false,
  tone = "subtle",
  corner = "none",
  mobileCorner = "none",
  ghost = false,
  onClick,
}: ParameterCardProps) {
  return (
    <button
      type="button"
      aria-label={`${label} ${value}`}
      data-parameter-card={label}
      onClick={onClick}
      className={[
        "relative flex h-full min-h-0 flex-col items-start justify-between overflow-hidden px-[29px] py-[clamp(16px,2.8vh,30px)] text-left",
        "max-md:items-center max-md:justify-center max-md:gap-[8px] max-md:px-[12px] max-md:py-0 max-md:text-center",
        CORNER[corner],
        MOBILE_CORNER[mobileCorner],
        ghost
          ? "cursor-default bg-transparent outline outline-[0.5px] -outline-offset-[0.5px] outline-[#C0C0C0] max-md:outline-hairline/30"
          : "pressable bg-card max-md:bg-card-dim",
      ].join(" ")}
    >
      {ghost ? null : (
        <>
          <span className="flex items-center justify-center gap-[8px]">
            <span className="font-ui text-[22px] leading-[22px] text-ink-subtle max-md:text-[14px] max-md:leading-[14px]">
              {label}
            </span>
            <Icon
              name="chevron-right"
              width={9}
              height={17}
              className="hidden md:block"
            />
            <Icon
              name="chevron-right-sm"
              width={7}
              height={12}
              className="md:hidden"
            />
          </span>

          <span
            className={[
              "min-w-0 self-stretch overflow-visible text-[32px] leading-[1.22] max-md:text-[20px] max-md:leading-[1.22]",
              isSet ? "font-display italic" : "font-extralight",
              tone === "strong" ? "text-black" : "text-ink-subtle",
            ].join(" ")}
          >
            <FitText wrapWords origin="left" className="max-md:origin-center">
              {value}
            </FitText>
          </span>
        </>
      )}
    </button>
  );
}
