"use client";
import type { Generation } from "@/lib/api";
import { Icon } from "@/components/ui/Icon";
import { BackButton } from "@/components/constructor/BackButton";
import { PatternCanvas } from "@/components/constructor/PatternCanvas";

type GeneratingViewProps = {
  imageUrl: string | null;
  progress?: number; status?: Generation["status"] | null;
  confirmStop: boolean;
  onBack: () => void;
  onStop: () => void;
};

export function GeneratingView({
  imageUrl,
  progress,
  confirmStop,
  onBack,
  onStop,
}: GeneratingViewProps) {
  return (
    <div className="constructor-stage flex min-h-0 flex-1 flex-col">
      <div className="hidden shrink-0 px-[25px] pt-[25px] md:block">
        <BackButton onClick={onBack} />
      </div>

      <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-[24px] py-[20px] max-md:px-[16px]">
        <div className="flex min-h-0 w-full flex-1 items-center justify-center [container-type:size]">
          <div
            className="overflow-hidden rounded-[128px] shadow-[0px_0px_64px_rgba(0,0,0,0.15)] outline outline-[0.6px] outline-white/60 max-md:rounded-[56px] max-md:shadow-[0px_0px_21px_rgba(0,0,0,0.15)]"
            style={{
              width: "min(100cqw, 966px, calc(100cqh * 4 / 3))",
              height: "min(100cqh, 724px, calc(100cqw * 3 / 4))",
            }}
          >
            <PatternCanvas
              imageUrl={imageUrl}
              generating
              progress={progress}
              className="size-full"
            />
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-center pt-[20px] max-md:pt-[16px]">
          {confirmStop ? (
            <div className="flex w-[326px] flex-col items-center gap-[12px] max-md:w-[214px]">
              <button
                type="button"
                onClick={onStop}
                className="pressable flex w-full items-center justify-center gap-[12px] rounded-[28px] bg-danger px-[20px] py-[14px] opacity-70 max-md:gap-[8px] max-md:rounded-[20px] max-md:px-[14px] max-md:py-[10px]"
              >
                <Icon name="stop-inverse" width={24} height={24} className="hidden md:block" />
                <Icon name="stop-inverse" width={17} height={17} className="md:hidden" />
                <span className="font-ui text-[22px] font-medium leading-[22px] text-surface max-md:text-[16px] max-md:leading-[16px]">
                  Прекратить ожидание?
                </span>
              </button>

            </div>
          ) : (
            <button
              type="button"
              onClick={onStop}
              className="pressable-quiet flex items-center gap-[12px] px-[16px] py-[12px] opacity-70 max-md:gap-[8px] max-md:px-[11px] max-md:py-[8px]"
            >
              <Icon name="stop" width={24} height={24} className="hidden md:block" />
              <Icon name="stop" width={17} height={17} className="md:hidden" />
              <span className="font-ui text-[22px] font-medium leading-[22px] text-danger max-md:text-[16px] max-md:leading-[16px]">
                Прекратить ожидание
              </span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
