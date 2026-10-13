import { Icon } from "@/components/ui/Icon";

/**
 * Знак Pattern Lab: два ромба и два шеврона, как в шапке входа.
 * В экспорте Figma четыре фигуры уехали в ряд — собираем наложением.
 */
export function AuthMark({ className = "" }: { className?: string }) {
  return (
    <div className={`relative h-[28px] w-[49px] ${className}`} aria-hidden>
      <Icon
        name="9390dcfa"
        width={28}
        height={28}
        className="absolute left-0 top-0"
      />
      <Icon
        name="5f8f40e2"
        width={23}
        height={14}
        className="absolute left-[10px] top-0"
      />
      <Icon
        name="3a16f169"
        width={23}
        height={14}
        className="absolute left-[10px] top-[14px]"
      />
      <Icon
        name="9390dcfa"
        width={28}
        height={28}
        className="absolute left-[21px] top-0"
      />
    </div>
  );
}

export function AuthWordmark() {
  return (
    <div className="relative h-[21px] w-[146px] overflow-hidden" aria-hidden>
      <Icon
        name="cc4ba7ad"
        width={17}
        height={17}
        className="absolute left-0 top-[2px]"
      />
      <Icon
        name="64801d96"
        width={15}
        height={9}
        className="absolute left-[11px] top-0"
      />
      <Icon
        name="092bcb1f"
        width={15}
        height={9}
        className="absolute left-[11px] top-[13px]"
      />
      <Icon
        name="cc4ba7ad"
        width={17}
        height={17}
        className="absolute left-[21px] top-[2px]"
      />
      <span className="absolute left-[45px] top-[1px] font-[family-name:var(--font-instrument)] text-[19px] font-medium leading-[19px] text-[#333]">
        Pattern Lab
      </span>
    </div>
  );
}
