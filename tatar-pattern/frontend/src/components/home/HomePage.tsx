"use client";
import { useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { HOME } from "@/content/home";
import { useStudioHref } from "@/lib/studio-href";
import { Artwork } from "@/components/home/Artwork";

export default function HomePage() {
  const {href, authed} = useStudioHref();
  const [variant, setVariant] = useState<"medallion" | "border" | "rapport">("medallion");
  const menu = useRef<HTMLDetailsElement>(null);
  const closeMenu = () => { if (menu.current) menu.current.open = false; };
  return <div className="lp">
    <a className="lp-skip" href="#main">К содержанию</a>
    <header className="lp-header">
      <Link href="/" className="lp-brand" aria-label="TATAR PATTERN — главная"><BrandMark /><span className="lp-wordmark">ТАТАР<br />ПАТТЕРН<br /><strong>ЛАБ</strong></span></Link>
      <nav className="lp-nav" aria-label="Основная навигация"><Link href="/about-pattern">Про татарский узор</Link><Link href="/help">Помощь</Link></nav>
      <Link className="lp-entry" href={href}>{authed ? "В конструктор" : "Войти"}<span aria-hidden>↗</span></Link>
      <details ref={menu} className="lp-mobile-menu"><summary aria-label="Меню"><span /><span /></summary><nav aria-label="Мобильная навигация"><Link onClick={closeMenu} href="/about-pattern">Про татарский узор</Link><Link onClick={closeMenu} href="/help">Помощь</Link><Link onClick={closeMenu} href={href}>Открыть конструктор ↗</Link></nav></details>
    </header>
    <main id="main">
      <section className="lp-hero">
        <div className="lp-hero-copy"><p className="lp-eyebrow">Цифровая мастерская орнамента · Казань</p>
          <h1>Ваш узор.<br /><em>Татарский характер.</em></h1>
          <p className="lp-lead">{HOME.lead}</p>
          <Link href={href} className="lp-button">Создать свой узор<span aria-hidden>↗</span></Link>
          <div className="lp-hero-foot"><span>От мотива — к композиции</span><span>Форма, которую выбираете вы</span></div>
        </div>
        <figure className="lp-hero-art"><Artwork variant={variant} /><div className="lp-art-top"><span>TATAR PATTERN</span><span>Этюд / 0{variant === "medallion" ? 1 : variant === "border" ? 2 : 3}</span></div><figcaption><span>Ритм. Форма. Цвет.</span><span>Графический эскиз</span></figcaption></figure>
      </section>
      <section className="lp-about lp-section" id="about"><div><h2>Наследие, с которым<br />можно <em>работать.</em></h2><div className="lp-about-text"><p>Орнамент живёт в деталях: в линии лепестка, в симметрии, в чередовании форм. TATAR PATTERN помогает перенести этот язык в современный дизайн.</p><p>Вы выбираете параметры. Конструктор собирает рисунок, а вы решаете, как он продолжится в ткани, предмете или визуальном образе.</p></div></div></section>
      <section className="lp-collection lp-section" id="collection"><div className="lp-section-heading"><div><h2>Один мотив.<br /><em>Разные ритмы.</em></h2></div><p>Центр, линия или бесконечный повтор.<br />Выберите композицию для эскиза.</p></div>
        <div className="lp-studies">{([{id:"medallion", name:"Медальон", text:"Рисунок вокруг одного центра."},{id:"border", name:"Бордюр", text:"Направленный ритм вдоль линии."},{id:"rapport", name:"Раппорт", text:"Повтор, заполняющий плоскость."}] as const).map((item) => <button key={item.id} className={`lp-study ${variant === item.id ? "is-selected" : ""}`} onClick={() => setVariant(item.id)} aria-pressed={variant === item.id}><div className={`lp-study-art lp-study-art-${item.id}`}><Artwork variant={item.id} /></div><div className="lp-study-heading"><h3>{item.name}</h3><span aria-hidden>{variant === item.id ? "●" : "↗"}</span></div><p>{item.text}</p></button>)}</div>
        <p className="lp-caption">Эскизы показывают принцип композиции. Результат конструктора создаётся из доступных элементов каталога.</p>
      </section>
      <section className="lp-method lp-section" id="method"><div className="lp-section-heading"><div><h2>Ваш рисунок.<br /><em>Ваше решение.</em></h2></div><Link href={href} className="lp-button lp-button-light">Открыть конструктор<span aria-hidden>↗</span></Link></div><div className="lp-steps">{HOME.steps.map((step) => <article key={step.title}><h3>{step.title}</h3><p>{step.body}</p></article>)}</div><p className="lp-method-note">Первая версия использует алгоритмическую генерацию. Текст запроса сохраняется как заметка; свободная генерация и редактирование с ИИ — следующий этап.</p></section>
      <section className="lp-uses lp-section" id="uses"><h2>Из рисунка —<br /><em>в вашу работу.</em></h2><div>{HOME.uses.map((use) => <article key={use.title}><h3>{use.title}</h3><p>{use.body}</p></article>)}</div></section>
      <section className="lp-support lp-section" id="support"><p className="lp-eyebrow">Поддержка проекта</p><div className="lp-support-content"><p className="lp-grant">{HOME.grant}</p><div className="lp-support-logos"><a href="https://fasie.ru" target="_blank" rel="noreferrer"><Image unoptimized width={185} height={110} src="/logos/fasie.svg" alt="Фонд содействия инновациям" /></a><a href="https://univertechpred.ru" target="_blank" rel="noreferrer"><Image unoptimized width={180} height={110} src="/logos/platform.svg" alt="Платформа университетского технологического предпринимательства" /></a></div></div></section>
      <section className="lp-final"><BrandMark /><p className="lp-eyebrow">TATAR PATTERN</p><h2>Начните<br /><em>с одного мотива.</em></h2><Link href={href} className="lp-button">Перейти в мастерскую<span aria-hidden>↗</span></Link></section>
    </main>
    <footer className="lp-footer"><Link href="/" className="lp-footer-brand">TATAR PATTERN</Link><span>ООО «ПАТТЕРН ЛАБ» · Казань</span><Link href="/help">Помощь</Link><span>© {new Date().getFullYear()}</span></footer>
  </div>;
}
function BrandMark() { return <Image className="lp-logo" src="/logos/tatar-pattern.svg" width={65} height={37} alt="Логотип Татар Паттерн" unoptimized />; }
