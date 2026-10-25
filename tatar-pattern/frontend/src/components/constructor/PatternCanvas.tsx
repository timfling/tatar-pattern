"use client";
import { MeshGradient } from "@/components/constructor/MeshGradient";

type PatternCanvasProps = {
  /** Адрес картинки от модели. Пока null — заглушка: цвет или радуга при генерации. */
  imageUrl: string | null;
  generating?: boolean;
  repeatPreview?: boolean;
  onImageLoad?: (width: number, height: number) => void;
  onImageError?: () => void;
  progress?: number;
  className?: string;
};

/**
 * Окно узора. Одно и то же и во время генерации, и в результате:
 * когда облако отдаст файл, достаточно передать imageUrl.
 * Соотношение сторон задаёт родитель (4:3 / 966×724).
 */
export function PatternCanvas({
  imageUrl,
  generating = false,
  progress,
  repeatPreview = false,
  onImageError, onImageLoad,
  className = "",
}: PatternCanvasProps) {
  return (
    <div className={`relative bg-[conic-gradient(#eee_25%,white_0_50%,#eee_0_75%,white_0)] bg-[length:20px_20px] overflow-hidden rounded-[inherit] ${className}`}>
      {imageUrl && repeatPreview ? <div className="absolute inset-0 grid grid-cols-3 grid-rows-3" aria-label="Повтор раппорта 3 на 3">{Array.from({ length: 9 }, (_, index) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={index} src={imageUrl} alt="" onError={onImageError} className="size-full object-contain" />
      ))}</div> : imageUrl ? (
        // Обычный img: URL с облака ещё неизвестен, next/image потребовал бы белый список доменов.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          onLoad={event => onImageLoad?.(event.currentTarget.naturalWidth,event.currentTarget.naturalHeight)}
          onError={onImageError}
          src={imageUrl}
          alt={generating ? "" : "Сгенерированный узор"}
          className="absolute inset-0 size-full object-contain"
        />
      ) : generating ? (
        <MeshGradient />
      ) : (
        <div className="absolute inset-0 bg-pattern-preview" aria-hidden />
      )}

      {generating ? (
        <>
          {imageUrl ? (
            <div className="absolute inset-0 bg-black/30" aria-hidden />
          ) : null}
          <p className="pointer-events-none absolute inset-0 flex items-center justify-center text-center font-display text-[clamp(28px,4vw,48px)] italic leading-none text-surface [text-shadow:0px_0px_64px_rgba(0,0,0,0.50)] max-md:text-[28px] max-md:leading-[28px] max-md:[text-shadow:0px_0px_21px_rgba(0,0,0,0.50)]">
            Генерируем узор…
          </p>
          <div className="pointer-events-none absolute inset-x-0 bottom-[clamp(24px,6%,48px)] flex flex-col items-center gap-[21px] px-[24px] py-[16px] max-md:bottom-[16px] max-md:gap-[12px] max-md:py-[9px]">
            {progress !== undefined ? <span className="text-[24px] font-medium italic leading-[24px] text-white opacity-90 max-md:text-[13px] max-md:leading-[13px]">
              {`${Math.round(progress ?? 0)}%`}
            </span> : null}
            <div className="relative h-[6px] w-[200px] overflow-hidden rounded-full bg-white/60 max-md:h-[3px] max-md:w-[112px]">
              <div
                className={`absolute inset-y-0 left-0 rounded-full bg-white ${progress === undefined ? "api-wait" : ""}`}
                style={{ width: progress === undefined ? "40%" : `${progress}%` }}
              />
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
