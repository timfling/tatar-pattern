"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/Icon";

type FullscreenViewProps = {
  imageUrl: string | null;
  onClose: () => void;
  onEdit: () => void;
};

const DEFAULT_ZOOM = 45;
/** Потолок зума: окно растёт к краям экрана, без сильного пиксель-пинга. */
const MAX_ZOOM_SCALE = 1.36;

function visualScale(zoom: number) {
  if (zoom <= DEFAULT_ZOOM) {
    return 0.94 + (zoom / DEFAULT_ZOOM) * 0.06;
  }
  return 1 + ((zoom - DEFAULT_ZOOM) / (100 - DEFAULT_ZOOM)) * (MAX_ZOOM_SCALE - 1);
}

/**
 * Полноэкранный просмотр результата.
 * Десктоп: узор 4:3, справа закрыть / зум / редактировать / поделиться.
 * Мобайл: крупнее окно и крестик справа сверху. Ползунка на мобайле в макете нет.
 */
export function FullscreenView({
  imageUrl,
  onClose,
  onEdit,
}: FullscreenViewProps) {
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [zoomLive, setZoomLive] = useState(false);
  const scale = visualScale(zoom);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Просмотр узора"
      className="absolute inset-0 z-50 select-none"
    >
      <button
        type="button"
        aria-label="Закрыть просмотр"
        onClick={onClose}
        className="absolute inset-0 bg-[rgb(38_38_38/0.8)] max-md:bg-[rgb(39_39_39/0.8)]"
      />

      <div className="pointer-events-none relative z-10 hidden h-full w-full md:block">
        <div className="absolute inset-y-[70px] left-[211px] right-[132px] flex items-center justify-center [container-type:size]">
          <div
            className="pointer-events-auto flex items-stretch gap-[18px]"
            style={{
              height: "min(100cqh, calc((100cqw - 81px) * 3 / 4))",
              width: "min(100cqw, calc(100cqh * 4 / 3 + 81px))",
            }}
          >
            <div
              className={[
                "zoom-frame relative min-h-0 min-w-0 flex-1 origin-center overflow-hidden rounded-[8px] bg-[#252525] shadow-[0px_0px_86px_rgba(0,0,0,0.10)]",
                zoomLive ? "zoom-frame-live" : "",
              ].join(" ")}
              style={{ transform: `scale(${scale})` }}
            >
              <PatternImage imageUrl={imageUrl} />
            </div>
            <aside className="relative z-10 flex w-[63px] shrink-0 flex-col justify-between">
              <button
                type="button"
                aria-label="Закрыть"
                onClick={onClose}
                className="pressable-icon shrink-0"
              >
                <Icon name="overlay-close" width={63} height={63} />
              </button>

              <ZoomSlider
                value={zoom}
                onChange={setZoom}
                onLiveChange={setZoomLive}
              />

              <div className="flex flex-col gap-[16px]">
                <button
                  type="button"
                  aria-label="Изменить параметры"
                  onClick={onEdit}
                  className="pressable-icon"
                >
                  <Icon name="overlay-edit-ai" width={63} height={63} />
                </button>
                <button type="button" aria-label="Поделиться — скоро" disabled title="Публичные ссылки пока не поддерживаются" className="pressable-icon opacity-30">
                  <Icon name="overlay-share" width={63} height={63} />
                </button>
              </div>
            </aside>
          </div>
        </div>
      </div>

      <div className="pointer-events-none relative z-10 h-full w-full md:hidden">
        <button
          type="button"
          aria-label="Закрыть"
          onClick={onClose}
          className="pressable-icon pointer-events-auto absolute right-[22px] top-[max(10px,env(safe-area-inset-top))]"
        >
          <Icon name="overlay-close-sm" width={43} height={43} />
        </button>
        <div className="pointer-events-auto absolute top-[210px] right-[15px] left-[15px]">
          <div className="relative aspect-[4/3] w-full overflow-hidden rounded-[8px] bg-[#252525] shadow-[0px_0px_64px_rgba(0,0,0,0.10)]">
            <PatternImage imageUrl={imageUrl} />
          </div>
        </div>
      </div>
    </div>
  );
}

function PatternImage({ imageUrl }: { imageUrl: string | null }) {
  if (!imageUrl) {
    return <div className="absolute inset-0 bg-[#252525]" aria-hidden />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={imageUrl}
      alt="Сгенерированный узор"
      className="absolute inset-0 size-full object-contain"
    />
  );
}

const TRACK_H = 239;
const TRACK_PAD = 5;
const INNER_H = TRACK_H - TRACK_PAD * 2;

function clampZoom(value: number) {
  return Math.min(100, Math.max(0, Math.round(value)));
}

function ZoomSlider({
  value,
  onChange,
  onLiveChange,
}: {
  value: number;
  onChange: (value: number) => void;
  onLiveChange: (live: boolean) => void;
}) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(false);

  const setLive = useCallback(
    (live: boolean) => {
      setActive(live);
      onLiveChange(live);
    },
    [onLiveChange],
  );

  const setFromPointer = useCallback(
    (clientY: number) => {
      const track = trackRef.current;
      if (!track) return;
      const rect = track.getBoundingClientRect();
      const innerTop = rect.top + TRACK_PAD * (rect.height / TRACK_H);
      const innerBottom = rect.bottom - TRACK_PAD * (rect.height / TRACK_H);
      const t = (innerBottom - clientY) / (innerBottom - innerTop);
      onChange(clampZoom(t * 100));
    },
    [onChange],
  );

  const fillH = (INNER_H * value) / 100;

  return (
    <div className="relative h-[239px] w-[63px]">
      <div
        ref={trackRef}
        role="slider"
        aria-label="Масштаб"
        aria-orientation="vertical"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        tabIndex={0}
        className="absolute inset-0 cursor-ns-resize rounded-[75px] border-[0.5px] border-white/10 bg-white/5 opacity-80"
        onPointerDown={(event) => {
          event.preventDefault();
          event.currentTarget.setPointerCapture(event.pointerId);
          setLive(true);
          setFromPointer(event.clientY);
        }}
        onPointerMove={(event) => {
          if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
          setFromPointer(event.clientY);
        }}
        onPointerUp={() => setLive(false)}
        onPointerCancel={() => setLive(false)}
        onKeyDown={(event) => {
          if (event.key === "ArrowUp" || event.key === "ArrowRight") {
            event.preventDefault();
            onChange(clampZoom(value + 5));
          }
          if (event.key === "ArrowDown" || event.key === "ArrowLeft") {
            event.preventDefault();
            onChange(clampZoom(value - 5));
          }
        }}
      />

      <div
        aria-hidden
        className={
          active
            ? "zoom-fill zoom-fill-live pointer-events-none absolute left-[5px] w-[53px] rounded-[75px] border-[0.5px] border-white/25 opacity-80 shadow-[0px_0px_8px_rgba(255,255,255,0.15)]"
            : "zoom-fill pointer-events-none absolute left-[5px] w-[53px] rounded-[75px] border-[0.5px] border-white/25 opacity-80"
        }
        style={{
          bottom: TRACK_PAD,
          height: fillH,
          background: active
            ? "linear-gradient(180deg, rgba(255,255,255,0.40) 0%, rgba(255,255,255,0) 100%)"
            : "linear-gradient(180deg, rgba(255,255,255,0.25) 0%, rgba(255,255,255,0.13) 100%)",
        }}
      />

      <button
        type="button"
        aria-label="Увеличить"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => onChange(clampZoom(value + 5))}
        className="absolute left-0 right-0 top-[5px] z-10 font-ui text-[36px] font-medium leading-[36px] text-white opacity-50"
      >
        +
      </button>
      <button
        type="button"
        aria-label="Уменьшить"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => onChange(clampZoom(value - 5))}
        className="absolute bottom-[5px] left-0 right-0 z-10 font-ui text-[36px] font-medium leading-[36px] text-white opacity-50"
      >
        –
      </button>

      {active ? (
        <div className="pointer-events-none absolute top-1/2 left-[74px] flex -translate-y-1/2 items-center gap-[2px]">
          <Icon name="overlay-zoom-mark" width={12} height={12} />
          <span className="font-ui text-[15px] font-bold leading-[15px] text-white">
            {value}%
          </span>
        </div>
      ) : null}
    </div>
  );
}
