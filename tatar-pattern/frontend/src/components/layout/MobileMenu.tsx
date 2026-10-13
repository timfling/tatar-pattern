"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { splitNav, type NavItem } from "@/components/layout/Sidebar";

type MobileMenuProps = {
  active: string;
  onClose: () => void;
  onConstructorClick?: () => void;
};

/**
 * Полноэкранное меню поверх конструктора.
 * В экспорте Figma нет backdrop-filter — полупрозрачный белый слой
 * без размытия не читается поверх карточек, поэтому blur восстановлен.
 */
export function MobileMenu({
  active,
  onClose,
  onConstructorClick,
}: MobileMenuProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const { before, current, after } = splitNav(active);

  function go(href: string) {
    if (href === "/constructor") onConstructorClick?.();
    onClose();
  }

  return (
    <div
      role="dialog"
      aria-label="Меню"
      className="mobile-menu-enter fixed inset-0 z-50 flex flex-col items-center bg-white/15 px-[19px] pb-[max(24px,env(safe-area-inset-bottom))] pt-[max(13px,env(safe-area-inset-top))] shadow-[0px_0px_28px_rgba(0,0,0,0.15)] outline outline-[0.6px] -outline-offset-[0.6px] outline-[#E6E6E6]/60 backdrop-blur-[24px] md:hidden"
    >
      <div className="flex h-[50px] w-full max-w-[365px] items-center justify-between">
        <button type="button" aria-label="Закрыть меню" onClick={onClose}>
          <Icon name="menu-close" width={42} height={42} />
        </button>
        <Link
          href="/profile"
          onClick={onClose}
          className="flex items-center gap-[10px] rounded-[48px] bg-white/20 py-[4px] pl-[12px] pr-[4px] outline outline-[0.5px] -outline-offset-[0.5px] outline-white/50"
        >
          <span className="text-[15px] font-bold leading-[15px] text-[#585858]">
            Настройки
          </span>
          <Icon name="user" width={42} height={42} />
        </Link>
      </div>

      <div className="mt-[65px] flex w-full max-w-[349px] flex-col items-center gap-[47px]">
        <Link
          href="/"
          onClick={onClose}
          className="w-[178px] text-center font-display text-[32px] leading-[32px] tracking-[1.92px] text-ink-title"
        >
          ТАТАР
          <br />
          ПАТТЕРН
          <br />
          <span className="font-black italic">ЛАБ</span>
        </Link>

        <nav className="flex w-full flex-col items-center">
          {before.length > 0 ? (
            <div className="flex w-full max-w-[339px] flex-col gap-[11px]">
              {before.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  isActive={false}
                  onClick={() => go(item.href)}
                />
              ))}
            </div>
          ) : null}
          {before.length > 0 ? <div className="h-[16px]" /> : null}
          <NavLink item={current} isActive onClick={() => go(current.href)} />
          {after.length > 0 ? <div className="h-[16px]" /> : null}
          {after.length > 0 ? (
            <div className="flex w-full max-w-[339px] flex-col gap-[11px]">
              {after.map((item) => (
                <NavLink
                  key={item.href}
                  item={item}
                  isActive={false}
                  onClick={() => go(item.href)}
                />
              ))}
            </div>
          ) : null}
        </nav>

        <Link
          href="/"
          onClick={onClose}
          className="flex items-center justify-center gap-[12px] overflow-hidden rounded-[22px] px-[44px] py-[16px]"
        >
          <Icon name="home" width={16} height={18} />
          <span className="text-[14px] font-semibold text-ink-faint">
            Вернуться на главную страницу
          </span>
        </Link>
      </div>
    </div>
  );
}

function iconSize(item: NavItem) {
  return {
    iconW: item.w === 23 ? 20 : item.href === "/constructor" ? 25 : 22,
    iconH: item.h === 23 ? (item.icon === "help" ? 19 : 20) : item.href === "/constructor" ? 24 : 20,
  };
}

function NavLink({
  item,
  isActive,
  onClick,
}: {
  item: NavItem;
  isActive: boolean;
  onClick: () => void;
}) {
  const { iconW, iconH } = iconSize(item);
  return (
    <Link
      href={item.href}
      onClick={onClick}
      className={
        isActive
          ? "flex h-[70px] w-full items-center gap-[10px] overflow-hidden rounded-[22px] bg-white px-[20px] shadow-[0px_1px_25px_rgba(0,0,0,0.10)]"
          : "pressable-quiet flex h-[50px] w-full items-center gap-[9px] overflow-hidden rounded-[22px] px-[19px] opacity-80 outline outline-[0.6px] -outline-offset-[0.6px] outline-hairline/60"
      }
    >
      <Icon name={item.icon} width={iconW} height={iconH} className="shrink-0" />
      <span className="text-[18px] font-semibold text-ink-muted">{item.label}</span>
    </Link>
  );
}
