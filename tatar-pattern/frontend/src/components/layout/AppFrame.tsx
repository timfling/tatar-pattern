"use client";

/* eslint-disable react-hooks/refs -- useShell exposes context data and event callbacks, not a ref read during render. */

import { GuestCleanup } from "@/components/guest/GuestCleanup";
import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { Sidebar, NAV_ITEMS } from "@/components/layout/Sidebar";
import { MobileHeader } from "@/components/layout/MobileHeader";
import { MobileMenu } from "@/components/layout/MobileMenu";
import { ShellProvider, useShell } from "@/components/layout/shell-context";

function activeFromPath(pathname: string) {
  const match = NAV_ITEMS.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );
  return match?.href ?? pathname;
}

function AppFrameInner({ children }: { children: React.ReactNode }) {

  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const shell = useShell();
  useEffect(() => {
    const aside = document.querySelector('.app-screen > aside');
    if(!aside) return;
    const update = () => document.documentElement.style.setProperty('--studio-sidebar-width', `${aside.getBoundingClientRect().right}px`);
    const observer = new ResizeObserver(update); observer.observe(aside); window.addEventListener('resize', update); update();
    return () => { observer.disconnect(); window.removeEventListener('resize', update); };
  }, []);
  const active = activeFromPath(pathname);

  return (
    <div className="app-viewport"><GuestCleanup />
      <main
        ref={shell.setScreenEl}
        className="app-screen relative flex bg-[image:var(--gradient-canvas)] pt-[14px] max-md:flex-col max-md:bg-surface max-md:bg-none max-md:pt-[max(13px,env(safe-area-inset-top))]"
      >
        <Sidebar
          active={active}
          className="hidden md:flex"
          onConstructorClick={shell.runConstructorClick}
        />
        <MobileHeader
          showBack={shell.showBack}
          onBack={shell.showBack ? shell.runBack : undefined}
          onMenu={() => setMenuOpen(true)}
        />
        {children}
      </main>
      {menuOpen ? (
        <MobileMenu
          active={active}
          onClose={closeMenu}
          onConstructorClick={shell.runConstructorClick}
        />
      ) : null}
    </div>
  );
}

export function AppFrame({ children }: { children: React.ReactNode }) {
  return (
    <ShellProvider>
      <AppFrameInner>{children}</AppFrameInner>
    </ShellProvider>
  );
}
