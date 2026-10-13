import { Icon } from "@/components/ui/Icon";

export function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="pressable-quiet flex h-[52px] items-center gap-[10px] rounded-[52px] p-[16px]"
    >
      <Icon name="chevron-back" width={11} height={20} />
      <span className="text-[16px] font-bold leading-[16px] text-ink-subtle">
        Вернуться назад
      </span>
    </button>
  );
}
