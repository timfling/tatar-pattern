"use client";
/* eslint-disable @next/next/no-img-element -- Local design assets and the account's data URL avatar. */
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { motion, useMotionValueEvent, useReducedMotion, useScroll } from "motion/react";
import { HOME } from "@/content/home";

export function HomeHeader({ studioHref }: { studioHref: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [hidden, setHidden] = useState(false);
  const previous = useRef(0);
  const { scrollY } = useScroll();
  const reduce = useReducedMotion();
  useMotionValueEvent(scrollY, "change", (y) => {
    if (Math.abs(y - previous.current) < 7 && y > 40) return;
    setHidden(y > previous.current && y > 80);
    previous.current = y;
  });
  useEffect(() => {
    if (!open) return;
    const oldOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = oldOverflow; };
  }, [open]);
  function show() { dialog.current?.showModal(); setOpen(true); }
  function close() { dialog.current?.close(); }
  return <>
    <motion.header className={`home-topbar ${hidden && !open ? "is-scrolling-down" : ""}`}
      initial={reduce ? false : { opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
      transition={{ duration: .8, ease: [.32, .72, 0, 1], delay: .15 }}>
      <Link href="/" className="home-top-logo" aria-label="Татар Паттерн — главная"><img src="/home-v2/logo.svg" width="63" height="36" alt="" /></Link>
      <button ref={trigger} className="home-menu-trigger" aria-label="Открыть меню" aria-haspopup="dialog" aria-expanded={open} aria-controls="home-navigation" onClick={show}><img src="/home-v2/menu.svg" width="26" height="22" alt="" /></button>
    </motion.header>
    <dialog ref={dialog} id="home-navigation" className="home-menu" aria-label="Меню сайта" onClose={() => { setOpen(false); trigger.current?.focus({ preventScroll: true }); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
      <Link href="/" onClick={close} className="home-menu-logo" aria-label="На главную"><img src="/home-v2/logo.svg" width="63" height="36" alt="" /></Link>
      <button className="home-menu-close" aria-label="Закрыть меню" onClick={close} autoFocus><span /><span /></button>
      <nav className="home-menu-links" aria-label="Навигация">
        <Link href="/" aria-current="page" onClick={close}>[ Главная ]</Link>
        <Link href={studioHref} onClick={close}>Открыть конструктор</Link>
        <a href={`mailto:${HOME.contactEmail}`} onClick={close}>Связаться с нами</a>
      </nav>

    </dialog>
  </>;
}
