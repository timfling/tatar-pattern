"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { splitNav, type NavItem } from "@/components/layout/Sidebar";

type MobileMenuProps = {
  active: string;
  onClose: () => void;
  onConstructorClick?: () => void;
};

export function MobileMenu({
  active,
  onClose,
  onConstructorClick,
}: MobileMenuProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [activeMenu, setActiveMenu] = useState(false);
  const closing = useRef<ReturnType<typeof setTimeout> | null>(null);
  const close = useCallback(() => {
    if (closing.current) return;
    setActiveMenu(false);
    closing.current = setTimeout(onClose, 280);
  }, [onClose]);
  useEffect(() => {
    const el = dialog.current;
    const previous = document.activeElement as HTMLElement | null;
    el?.showModal();
    const desktop = matchMedia("(min-width:768px)");
    const resized = () => { if(desktop.matches) onClose(); };
    desktop.addEventListener("change",resized);
    let second = 0;
    const first = requestAnimationFrame(() => { second = requestAnimationFrame(() => setActiveMenu(true)); });
    return () => { desktop.removeEventListener("change",resized); cancelAnimationFrame(first); cancelAnimationFrame(second); if(closing.current) clearTimeout(closing.current); el?.close(); requestAnimationFrame(() => previous?.focus({preventScroll:true})); };
  }, [onClose]);

  const { before, current, after } = splitNav(active);

  function go(href: string) {
    if (href === "/constructor") onConstructorClick?.();
    close();
  }

  return (
    <dialog
      ref={dialog}
      data-active={activeMenu}
      onCancel={e => {e.preventDefault();close();}}
      role="dialog"
      aria-label="Меню"
      className="mobile-menu-v2 fixed inset-0 z-50 flex flex-col items-center px-[19px] pb-[max(24px,env(safe-area-inset-bottom))] pt-[max(13px,env(safe-area-inset-top))] md:hidden"
    >
      <div className="flex h-[50px] w-full max-w-[365px] items-center justify-between">
        <button type="button" aria-label="Закрыть меню" onClick={close}>
          <Icon name="menu-close" width={42} height={42} />
        </button>

      </div>

      <div className="mt-[65px] flex w-full max-w-[349px] flex-col items-center gap-[47px]">
        <Link
          href="/"
          onClick={close}
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
        </nav><nav aria-label="Документы" className="flex flex-wrap justify-center gap-3 text-sm"><Link href="/legal/terms" onClick={close}>Правила</Link><Link href="/legal/privacy" onClick={close}>Обработка данных</Link><Link href="/legal/cookies" onClick={close}>Хранилище</Link></nav>

        <Link
          href="/"
          onClick={close}
          className="flex items-center justify-center gap-[12px] overflow-hidden rounded-[22px] px-[44px] py-[16px]"
        >
          <Icon name="home" width={16} height={18} />
          <span className="text-[14px] font-semibold text-ink-faint">
            Вернуться на главную страницу
          </span>
        </Link>
      </div>
    </dialog>
  );
}

function iconSize(item: NavItem) {
  return {
    iconW: item.href === "/library" ? 20 : item.w === 23 ? 20 : item.href === "/constructor" ? 25 : 22,
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
