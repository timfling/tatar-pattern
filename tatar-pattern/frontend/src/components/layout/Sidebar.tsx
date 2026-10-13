"use client";
/* eslint-disable @next/next/no-img-element -- Avatar is a bounded local data URL. */

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "@/components/ui/Icon";

export const NAV_ITEMS = [
  { href: "/constructor", label: "Конструктор", icon: "constructor", w: 27, h: 26 },
  { href: "/about-pattern", label: "Про татарский узор", icon: "about-pattern", w: 23, h: 23 },
  { href: "/help", label: "Помощь", icon: "help", w: 26, h: 23 },
  { href: "/library", label: "Библиотека", icon: "library", w: 22, h: 22 },
] as const;

export type NavItem = (typeof NAV_ITEMS)[number];

export function splitNav(active: string) {
  const index = NAV_ITEMS.findIndex((item) => item.href === active);
  const at = index >= 0 ? index : 0;
  return {
    before: NAV_ITEMS.slice(0, at),
    current: NAV_ITEMS[at],
    after: NAV_ITEMS.slice(at + 1),
  };
}

type NavLinkProps = {
  item: NavItem;
  isActive: boolean;
  /** Сбросить конструктор, если уже на /constructor. */
  onConstructorClick?: () => void;
};

function NavLink({ item, isActive, onConstructorClick }: NavLinkProps) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <Link
      href={item.href}
      onClick={(event) => {
        if (item.href !== "/constructor") return;
        onConstructorClick?.();
        if (pathname === "/constructor") {
          event.preventDefault();
          router.replace("/constructor");
        }
      }}
      className={
        isActive
          ? "nav-item flex w-full items-center gap-[11px] overflow-hidden rounded-[16px] bg-surface-raised p-[22px] shadow-[0px_1px_28px_rgba(0,0,0,0.10)]"
          : "nav-item pressable-quiet flex w-full items-center gap-[10px] overflow-hidden rounded-[16px] px-[21px] py-[7px] opacity-80"
      }
    >
      <Icon name={item.icon} width={item.w} height={item.h} className="shrink-0" />
      <span className="text-[20px] font-semibold text-ink-muted">{item.label}</span>
    </Link>
  );
}

export function SideNav({
  active,
  onConstructorClick,
}: {
  active: string;
  onConstructorClick?: () => void;
}) {
  return (
    <nav className="mt-[clamp(24px,8vh,92px)] flex w-full flex-col items-start">
      {NAV_ITEMS.map((item, index) => {
        const isActive = item.href === active;
        const prevActive = index > 0 && NAV_ITEMS[index - 1].href === active;
        const gapBefore = index > 0 && (isActive || prevActive);
        return (
          <div
            key={item.href}
            className="nav-slot w-full"
            style={{ marginTop: gapBefore ? 19 : 0 }}
          >
            <NavLink
              item={item}
              isActive={isActive}
              onConstructorClick={onConstructorClick}
            />
          </div>
        );
      })}
    </nav>
  );
}

type SidebarProps = {
  /** href активного пункта меню. */
  active: string;
  userName: string; avatar?: string | null;
  className?: string;
  onConstructorClick?: () => void;
};

export function Sidebar({
  active,
  userName, avatar,
  className = "",
  onConstructorClick,
}: SidebarProps) {
  const [accountOpen, setAccountOpen] = useState(false);
  return (
    <aside
      className={[
        "h-full w-[min(390px,32vw)] min-w-[280px] shrink-0 flex-col px-[22px] pb-[31px] pt-[26px]",
        className || "flex",
      ].join(" ")}
    >
      <Link
        href="/"
        className="ml-[10px] block w-[178px] font-display text-[32px] leading-[32px] tracking-[1.92px] text-ink-title"
      >
        ТАТАР
        <br />
        ПАТТЕРН
        <br />
        <span className="font-black italic">ЛАБ</span>
      </Link>

      <SideNav active={active} onConstructorClick={onConstructorClick} />

      <div className="relative mt-auto flex flex-col items-center gap-[7px] pt-[40px]">
        <Link
          href="/"
          className="home-return flex h-[48px] w-full items-center gap-[9px] overflow-hidden rounded-[24px] pl-[33px]"
        >
          <Icon name="arrow-left" width={20} height={15} className="shrink-0" />
          <span className="text-[16px] font-semibold text-ink-faint">
            Вернуться на главную страницу
          </span>
        </Link>

        {accountOpen ? <><button aria-label="Закрыть меню аккаунта" className="fixed inset-0 z-40 cursor-default" onClick={() => setAccountOpen(false)} /><nav aria-label="Меню аккаунта" className="account-popover absolute bottom-[88px] left-0 right-0 z-50 flex flex-col gap-2 rounded-3xl bg-white/95 p-3 shadow-xl">{[["/profile", "Аккаунт"], ["/settings", "Настройки конструктора"], ["/trash", "Корзина"], ["/rules", "Правила сервиса"]].map(([href,label]) => <Link key={href} href={href} onClick={() => setAccountOpen(false)} className="rounded-2xl px-4 py-3 hover:bg-surface">{label}</Link>)}</nav></> : null}
        <button type="button" aria-expanded={accountOpen} onClick={() => setAccountOpen(v => !v)}
          className="pressable flex w-full items-center justify-between overflow-hidden rounded-[24px] px-[9px] py-[8px] shadow-[0px_1px_28px_rgba(0,0,0,0.10)] outline outline-[0.5px] -outline-offset-[0.5px] outline-white/50"
        >
          <span className="flex items-center gap-[9px]">
            {avatar ?  <img src={avatar} width={57} height={57} alt="" className="size-[57px] shrink-0 rounded-full object-cover" /> : <Icon name="user" width={57} height={57} className="shrink-0" />}
            <span className="flex flex-col gap-px">
              <span className="break-all text-[16px] font-semibold text-[#343434]">
                {userName}
              </span>
              <span className="text-[13px] font-medium text-ink-muted opacity-80">
                Аккаунт и настройки
              </span>
            </span>
          </span>
          <Icon name="chevron-up" width={21} height={11} className="mr-[12px] shrink-0" />
        </button>
      </div>
    </aside>
  );
}
