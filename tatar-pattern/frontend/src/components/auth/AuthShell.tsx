"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { Icon } from "@/components/ui/Icon";
import { AuthMark, AuthWordmark } from "@/components/auth/AuthMark";

const FOOTER = [
  { href: "/#method", label: "Нужна помощь?", weight: "font-medium" },
] as const;

type AuthShellProps = {
  children: ReactNode;
  hideFooter?: boolean;
  mobileHelp?: boolean;
};

export function AuthShell({
  children,
  hideFooter = false,
  mobileHelp = false,
}: AuthShellProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-auth max-md:bg-surface">
      <header className="flex shrink-0 items-center justify-between px-[47px] pt-[39px] max-md:h-[50px] max-md:px-[22px] max-md:pt-[max(13px,env(safe-area-inset-top))]">
        <Link href="/" className="pressable-quiet max-md:hidden" aria-label="На главную">
          <AuthMark />
        </Link>
        <button
          type="button"
          aria-label="Открыть меню"
          onClick={() => setMenuOpen(true)}
          className="pressable-icon md:hidden"
        >
          <Icon name="menu" width={42} height={42} />
        </button>
        <nav className="hidden items-center gap-[83px] md:flex">
          <Link
            href="/"
            className="pressable-quiet text-[24px] font-normal leading-[24px] text-black"
          >
            О проекте
          </Link>
          <Link href="/help" className="pressable-quiet text-[24px] font-normal leading-[24px] text-black">Как это работает</Link>
          <Link
            href="/register"
            className="pressable-quiet text-[24px] font-medium leading-[24px] text-black"
          >
            [ Попробовать ]
          </Link>
        </nav>
      </header>

      <div className="flex min-h-0 flex-1 flex-col">{children}</div>

      {hideFooter ? null : (
        <footer className="hidden shrink-0 items-center justify-center gap-[64px] px-[48px] pb-[40px] pt-[16px] text-[20px] leading-[20px] text-black opacity-60 md:flex">
          <FooterItems />
        </footer>
      )}

      {mobileHelp ? (
        <p className="shrink-0 pb-[max(24px,env(safe-area-inset-bottom))] pt-[16px] text-center text-[14px] font-medium leading-[14px] text-black/50 underline md:hidden">
          <Link href="/help">Нужна помощь?</Link>
        </p>
      ) : null}

      {menuOpen ? <AuthMobileMenu onClose={() => setMenuOpen(false)} /> : null}
    </div>
  );
}

function FooterItems() {
  return (
    <>
      {FOOTER.map((item) =>
        item.href ? (
          <Link
            key={item.label}
            href={item.href}
            className={`pressable-quiet ${item.weight}`}
          >
            {item.label}
          </Link>
        ) : (
          <span key={item.label} className={item.weight}>
            {item.label}
          </span>
        ),
      )}
    </>
  );
}

function AuthMobileMenu({ onClose }: { onClose: () => void }) {
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
      aria-label="Меню"
      className="absolute inset-0 z-50 flex flex-col bg-white/15 px-[22px] pb-[max(24px,env(safe-area-inset-bottom))] pt-[max(13px,env(safe-area-inset-top))] backdrop-blur-[24px] md:hidden"
    >
      <div className="flex h-[50px] items-center justify-between">
        <button type="button" aria-label="Закрыть меню" onClick={onClose}>
          <Icon name="menu-close" width={42} height={42} />
        </button>
        <Link href="/" onClick={onClose} aria-label="На главную">
          <AuthWordmark />
        </Link>
      </div>

      <nav className="mt-[154px] flex flex-col items-start gap-[28px] px-[14px]">
        <Link
          href="/"
          onClick={onClose}
          className="pressable-quiet text-[24px] font-normal leading-[24px] text-black"
        >
          О проекте
        </Link>
        <Link href="/help" onClick={onClose} className="pressable-quiet text-[24px] font-normal leading-[24px] text-black">Как это работает</Link>
        <Link
          href="/register"
          onClick={onClose}
          className="pressable-quiet text-[32px] font-medium leading-[32px] text-black"
        >
          [ Попробовать ]
        </Link>
      </nav>

      <div className="mt-[80px] flex flex-col items-start gap-[14px] px-[14px] text-[16px] leading-[16px] text-black opacity-60">
        <FooterItems />
      </div>
    </div>
  );
}
