"use client";

import { useEffect, useRef, useState } from "react";

type RatingKind = "like" | "dislike";

type RatingButtonProps = {
  pressed: boolean;
  onToggle: () => void;
  size: 32 | 45;
};

const PALETTE = {
  like: { flash: "#A8D5A2", icon: "#5B9A4A" },
  /* Парный кадр к лайку: в макете залитого дизлайка нет. */
  dislike: { flash: "#E5B0B0", icon: "#C45C5C" },
} as const;

/**
 * После нажатия: 1 с — цветная заливка и белая иконка,
 * затем заливка сходит, контур снова тёмный, иконка остаётся цветной.
 */
function RatingButton({
  kind,
  pressed,
  onToggle,
  size,
  label,
}: RatingButtonProps & { kind: RatingKind; label: string }) {
  const [flash, setFlash] = useState(false);
  const timer = useRef<number>(0);

  useEffect(() => {
    return () => window.clearTimeout(timer.current);
  }, []);


  function handleClick() {
    window.clearTimeout(timer.current);
    if (pressed) {
      setFlash(false);
      onToggle();
      return;
    }
    setFlash(true);
    onToggle();
    timer.current = window.setTimeout(() => setFlash(false), 1000);
  }

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      onClick={handleClick}
      className="pressable-icon rounded-full"
    >
      <RatingMark
        kind={kind}
        size={size}
        pressed={pressed}
        flashing={flash && pressed}
      />
    </button>
  );
}

function RatingMark({
  kind,
  size,
  pressed,
  flashing,
}: {
  kind: RatingKind;
  size: 32 | 45;
  pressed: boolean;
  flashing: boolean;
}) {
  const colors = PALETTE[kind];
  const fill = flashing ? colors.flash : "none";
  const ring = flashing ? "#FFFFFF" : "#666666";
  const icon = flashing ? "#FFFFFF" : pressed ? colors.icon : "#666666";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 45 45"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <rect
        x="0.5"
        y="0.5"
        width="44"
        height="44"
        rx="22"
        fill={fill}
        stroke={ring}
        className="transition-[fill,stroke] duration-300 ease-out"
      />
      <g
        transform={
          kind === "dislike"
            ? "rotate(180 22.5 22.5) translate(10.5 10.5)"
            : "translate(10.5 10.5)"
        }
        fill="none"
        stroke={icon}
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="transition-[stroke] duration-300 ease-out"
      >
        <path d="M7 10v12" />
        <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
      </g>
    </svg>
  );
}

export function LikeButton(props: RatingButtonProps) {
  return <RatingButton kind="like" label="Нравится" {...props} />;
}

export function DislikeButton(props: RatingButtonProps) {
  return <RatingButton kind="dislike" label="Не нравится" {...props} />;
}
