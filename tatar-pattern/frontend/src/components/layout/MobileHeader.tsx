import { Icon } from "@/components/ui/Icon";

type MobileHeaderProps = {
  showBack?: boolean;
  onBack?: () => void;
  onMenu: () => void;
};

/**
 * Верхняя полоса мобильного конструктора: меню, опционально «назад», профиль.
 * Рамку телефона и системный status bar из макета не переносим.
 */
export function MobileHeader({
  showBack = false,
  onBack,
  onMenu,
}: MobileHeaderProps) {
  return (
    <header className="studio-mobile-header relative flex h-[50px] w-full shrink-0 items-center justify-between px-[22px] md:hidden">
      <button
        type="button"
        aria-label="Открыть меню"
        onClick={onMenu}
        className="pressable-icon shrink-0"
      >
        <Icon name="menu" width={42} height={42} />
      </button>

      {showBack && onBack ? (
        <button
          type="button"
          onClick={onBack}
          className="studio-mobile-back pressable-quiet absolute left-1/2 flex -translate-x-1/2 items-center gap-[5px] whitespace-nowrap rounded-[24px] px-[10px] py-[9px]"
        >
          <Icon name="chevron-back" width={8} height={15} />
          <span className="text-[13px] font-semibold leading-[15px] text-ink-subtle">
            Вернуться назад
          </span>
        </button>
      ) : (
        <span className="min-w-0 flex-1" />
      )}


    </header>
  );
}
