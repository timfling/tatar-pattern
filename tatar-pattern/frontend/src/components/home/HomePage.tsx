"use client";
/* eslint-disable @next/next/no-img-element -- Original local Figma artwork, including SVG filter bounds. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, MotionConfig, useReducedMotion } from "motion/react";
import { HOME } from "@/content/home";
import { loadUser, type AuthUser } from "@/lib/auth";
import { HomeHeader } from "./HomeHeader";
import { GenerationStory } from "./GenerationStory";

export function WorkshopLink({ href, className = "" }: { href: string; className?: string }) {
  return <Link href={href} className={`home-workshop-link ${className}`}><span aria-hidden="true">✣</span> Перейти в мастерскую</Link>;
}
function Hero() {
  const reduce = useReducedMotion();
  return <section className="home-hero" aria-label="Татар Паттерн Лаб">
    <motion.div className="home-hero-art" aria-hidden="true" initial={reduce ? false : { opacity: 0, scale: 1.045 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 1.8, ease: [.28, .11, .32, 1] }}>
      <svg className="home-art-desktop" viewBox="0 0 1728 1229" preserveAspectRatio="xMidYMid slice">
        <image href="/home-v2/hero-left.png" x="0" y="22" width="794" height="1181" />
        <image href="/home-v2/hero-high.png" x="320" y="0" width="1083" height="558.75" />
        <image href="/home-v2/hero-right.png" x="926" y="40" width="802" height="1101" />
        <image href="/home-v2/hero-low.png" x="323.25" y="672" width="1082" height="557" />
        <image href="/home-v2/hero-mask.svg" width="1728" height="1229" />
      </svg>
      <svg className="home-art-mobile" viewBox="0 0 402 874" preserveAspectRatio="xMidYMid slice">
        <image href="/home-v2/hero-mobile-0.png" x="0" y="0" width="402" height="429" />
        <image href="/home-v2/hero-mobile-1.png" x="0" y="473" width="402" height="401" />
        <image href="/home-v2/hero-mobile-2.png" x="219" y="178.624" width="183" height="516.676" />
        <image href="/home-v2/hero-mobile-3.png" x="0" y="158.551" width="188" height="541.483" />
        <image href="/home-v2/hero-mobile-mask.svg" width="402" height="874" />
      </svg>
    </motion.div>
    <motion.h1 className="home-wordmark" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 1.2, delay: .3, ease: [.28, .11, .32, 1] }}>ТАТАР<br />ПАТТЕРН<br /><strong>ЛАБ</strong></motion.h1>
  </section>;
}
function About({ href }: { href: string }) {
  return <section className="home-about" id="about" aria-labelledby="home-about-title">
    <div className="home-app-window">
      <div className="home-placeholder-canvas" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <span className={`home-placeholder home-placeholder-${i}`} key={i} />)}</div>
      <div className="home-canvas-wash" aria-hidden="true" />
      <div className="home-window-bar" aria-hidden="true"><span /><span /><span /><small>TATAR PATTERN LAB</small></div>
      <div className="home-about-copy"><h2 id="home-about-title">Ваш узор<br />с персональным<br /><em>характером</em></h2><div><p>Орнамент живет в деталях. В линиях лепестка,<br className="home-desktop-break" /> в симметрии и чередовании форм.</p><p>Татар Паттерн помогает перенести этот язык<br className="home-desktop-break" /> в современный и воспроизводимый дизайн.</p></div></div>
      <Link href={href} className="home-paint-button" aria-label="Перейти в конструктор"><span>Перейти в конструктор</span><svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="m12 21 12-15c2-2 5 1 3 3L15 23M12 21c-7-2-3 7-9 6 5 5 12 0 12-4l-3-2ZM20 11l5 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg></Link>
    </div>
  </section>;
}
export default function HomePage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  useEffect(() => {
    let active = true;
    let request = 0;
    const refresh = () => { const version = ++request; loadUser().then(value => { if (active && version === request) setUser(value); }).catch(() => {}); };
    refresh();
    window.addEventListener("focus", refresh);
    window.addEventListener("pageshow", refresh);
    window.addEventListener("tp-profile-updated", refresh);
    return () => { active = false; window.removeEventListener("focus", refresh); window.removeEventListener("pageshow", refresh); window.removeEventListener("tp-profile-updated", refresh); };
  }, []);
  const href = user ? "/constructor" : "/login";
  return <MotionConfig reducedMotion="user"><div className="home-v2">
    <a className="home-skip" href="#main">К содержанию</a>
    <HomeHeader user={user} studioHref={href} />
    <main id="main"><Hero /><About href={href} /><GenerationStory href={href} />
      <section className="home-scenarios" aria-label="Два способа создать рисунок"><h2>Два способа создать рисунок</h2><p>В параметрическом flat-конструкторе схема, совместимые мотивы, ритм и размер управляют новой раскладкой исходных элементов. Параметрическая AI-форма варьирует выбранную основу по стилю и варианту.</p><p>Историческая атрибуция относится к мотивам, новая раскладка — современная. AI может изменить детали и оттенки; точные мотивы, бесшовность и прозрачность не гарантируются. Свободная перекраска AI-основы недоступна.</p><div><Link href="/flat">Параметрический рисунок ↗</Link><Link href="/constructor">AI-вариант основы ↗</Link></div></section>
      <section className="home-support" id="support" aria-label="Поддержка проекта"><p>{HOME.grant}</p><div className="home-support-logos"><a href="https://fasie.ru" target="_blank" rel="noreferrer"><img src="/logos/fasie.svg" width="244" height="118" alt="Фонд содействия инновациям" loading="lazy" /></a><a href="https://univertechpred.ru" target="_blank" rel="noreferrer"><img src="/logos/platform.svg" width="190" height="148" alt="Платформа университетского технологического предпринимательства" loading="lazy" /></a></div></section>
      <section className="home-final" aria-labelledby="home-final-title"><div className="home-final-brand"><img src="/home-v2/logo.svg" width="62" height="36" alt="" /><span>ТАТАР ПАТТЕРН</span></div><h2 id="home-final-title">Начните<br />с одного мотива</h2><WorkshopLink href={href} /></section>
    </main>
    <footer className="home-footer"><span>ООО «ПАТТЕРН ЛАБ»</span><span className="home-footer-city">Казань</span><span>2026</span><a href={`mailto:${HOME.contactEmail}`}>Нужна помощь?</a></footer>
  </div></MotionConfig>;
}
