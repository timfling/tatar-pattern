"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cubicBezier, motion, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform, type MotionValue } from "motion/react";
import { HOME } from "@/content/home";

// All phases share one scroll clock: reversing the scroll reverses every morph.
const EASE = cubicBezier(.28, .11, .32, 1);
const DESKTOP_SELECTIONS = [4, 1, 10, 3];
const MOBILE_SELECTIONS = [3, 6, 1, 11];
const ACTIVATION = [.17, .26, .35, .44];
type Scene = { width: number; height: number; mobile: boolean };

function SelectedTile({ order, progress, scene }: { order: number; progress: MotionValue<number>; scene: Scene }) {
  const { width: w, height: h, mobile } = scene;
  const columns = mobile ? 3 : 4, rows = mobile ? 4 : 3;
  const index = (mobile ? MOBILE_SELECTIONS : DESKTOP_SELECTIONS)[order];
  const gap = w * (mobile ? .045 : .01756);
  const tw = (w - gap * (columns - 1)) / columns;
  const th = (h - gap * (rows - 1)) / rows;
  const startX = (index % columns) * (tw + gap), startY = Math.floor(index / columns) * (th + gap);
  const dot = w * (mobile ? .085 : .032);
  const centerX = w * (mobile ? .5 : .327), centerY = h * .5;
  const ring = dot * .86;
  const angle = order * Math.PI / 2;
  const endX = centerX + Math.cos(angle) * ring - dot / 2;
  const endY = centerY + Math.sin(angle) * ring - dot / 2;
  const x = useTransform(progress, [.51, .64], [startX, endX], { ease: EASE });
  const y = useTransform(progress, [.51, .64], [startY, endY], { ease: EASE });
  const scaleX = useTransform(progress, [.51, .64], [1, dot / tw], { ease: EASE });
  const scaleY = useTransform(progress, [.51, .64], [1, dot / th], { ease: EASE });
  const opacity = useTransform(progress, [ACTIVATION[order], ACTIVATION[order] + .014, .65, .665], [0, 1, 1, 0]);
  const white = useTransform(progress, [.52, .625], [0, 1]);
  const radius = useTransform(progress, [.51, .64], [mobile ? 20 : 14, Math.max(tw, th)]);
  const glow = useTransform(progress, [.51, .64], ["0px 1px 8px #00000026", "0px 0px 18px #ffffff, 0px 0px 36px #ffffff, 0px 0px 6px #ffffff"]);
  return <motion.div className="story-selected-tile" style={{ width: tw, height: th, x, y, scaleX, scaleY, opacity, borderRadius: radius, boxShadow: glow }}><motion.span style={{ opacity: white }} /></motion.div>;
}
function StoryStep({ i, progress, width }: { i: number; progress: MotionValue<number>; width: number }) {
  const opacity = useTransform(progress, i === 0 ? [.01, .065, .53, .62] : i === 1 ? [.51, .62, .78, .86] : [.77, .86, .91, .96], i === 0 ? [0, 1, 1, .3] : [ .3, 1, 1, .3]);
  const bodyOpacity = useTransform(progress, i === 0 ? [.015, .07, .51, .58] : i === 1 ? [.54, .63, .77, .83] : [.8, .87, .91, .96], [0, 1, 1, 0]);
  return <motion.article className="story-step" style={{ opacity, width }}><h2 tabIndex={-1}>{HOME.steps[i].title}</h2><svg viewBox="0 0 650 40" preserveAspectRatio="none" aria-hidden="true"><path d="M0 20H645M624 1l21 19-21 19" fill="none" stroke="currentColor" strokeWidth="3" /></svg><motion.p style={{ opacity: bodyOpacity }}>{HOME.steps[i].body}</motion.p></motion.article>;
}
export function CirclePattern() {
  // Exact original Figma circle groups, including per-circle gradients and transforms.
  return <div className="story-circle-pattern" aria-hidden="true"><picture><source media="(max-width: 767px)" srcSet="/home-v2/circle-pattern-m.svg" /><img src="/home-v2/circle-pattern-d.svg" alt="" width="930" height="633" loading="lazy" /></picture></div>;
}
function LibraryShell() {
  return <><div className="story-library-sidebar"><i /><i /><i /><i /></div><div className="story-library-grid">{Array.from({ length: 28 }, (_, i) => <span key={i} />)}</div></>;
}
function StaticStory({ href }: { href: string }) {
  return <div className="story-static">{HOME.steps.map((step, i) => <section key={step.title}><div className={`story-static-art story-static-art-${i}`} aria-hidden="true">{i === 0 ? Array.from({ length: 12 }, (_, n) => <span className={DESKTOP_SELECTIONS.includes(n) ? "selected" : ""} key={n} />) : i === 1 ? <span className="story-static-gradient">Генерируем узор</span> : <LibraryShell />}</div><h2>{step.title}</h2><p>{step.body}</p></section>)}<section className="story-static-final"><CirclePattern /><h2>Создайте свой узор</h2><Link href={href} className="story-cta-link">✣ Перейти в мастерскую <span aria-hidden="true">→</span></Link></section></div>;
}
export function GenerationStory({ href }: { href: string }) {
  const root = useRef<HTMLElement>(null);
  const visual = useRef<HTMLDivElement>(null);
  const [scene, setScene] = useState<Scene>({ width: 968, height: 436, mobile: false });
  const [loading, setLoading] = useState(false);
  const [finalActive, setFinalActive] = useState(false);
  const [nextActive, setNextActive] = useState(false);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: root, offset: ["start start", "end end"] });
  // Short damping removes wheel noise; it does not advance the narrative on its own.
  const smoothProgress = useSpring(scrollYProgress, { stiffness: 160, damping: 32, mass: .35 });
  const progress = reduce ? scrollYProgress : smoothProgress;
  useEffect(() => {
    const node = visual.current;
    if (!node) return;
    const resize = new ResizeObserver(() => { const rect = node.getBoundingClientRect(); setScene({ width: rect.width, height: rect.height, mobile: matchMedia("(max-width: 767px)").matches }); });
    resize.observe(node);
    return () => resize.disconnect();
  }, []);
  useMotionValueEvent(progress, "change", p => { setLoading(p >= .64 && p < .8); setFinalActive(p >= .955); setNextActive(p >= .13 && p < .51); });
  const w = scene.width, h = scene.height;
  const columns = scene.mobile ? 3 : 4, rows = scene.mobile ? 4 : 3;
  const gap = w * (scene.mobile ? .045 : .01756);
  const tw = (w - gap * (columns - 1)) / columns, th = (h - gap * (rows - 1)) / rows;
  const indices = scene.mobile ? MOBILE_SELECTIONS : DESKTOP_SELECTIONS;
  const cx = (n: number) => (n % columns) * (tw + gap) + tw * .83;
  const cy = (n: number) => Math.floor(n / columns) * (th + gap) + th * .6;
  const cursorX = useTransform(progress, [.12, .17, .23, .26, .32, .35, .41, .44, .48, .5], [-w * .15, cx(indices[0]), cx(indices[0]), cx(indices[1]), cx(indices[1]), cx(indices[2]), cx(indices[2]), cx(indices[3]), scene.mobile ? cx(indices[3]) : w * 1.145, scene.mobile ? cx(indices[3]) : w * 1.145], { ease: EASE });
  const cursorY = useTransform(progress, [.12, .17, .23, .26, .32, .35, .41, .44, .48], [h * .5, cy(indices[0]), cy(indices[0]), cy(indices[1]), cy(indices[1]), cy(indices[2]), cy(indices[2]), cy(indices[3]), scene.mobile ? cy(indices[3]) : h * .5], { ease: EASE });
  const cursorOpacity = useTransform(progress, [.12, .145, .505, .535], [0, 1, 1, 0]);
  const cursorScale = useTransform(progress, [.475, .49, .5, .515], scene.mobile ? [1, 1, 1, 1] : [1, .8, .8, 1]);
  const gridOpacity = useTransform(progress, [.07, .13, .51, .6], [0, 1, 1, 0]);
  const gridX = useTransform(progress, [.51, .64], [0, -w * .45], { ease: EASE });
  const gradientOpacity = useTransform(progress, [.53, .625, .91, .955], [0, 1, 1, 0]);
  const gradientScaleX = useTransform(progress, [.775, .87], [1, scene.mobile ? .269 : .10], { ease: EASE });
  const gradientScaleY = useTransform(progress, [.775, .87], [1, scene.mobile ? .215 : .22], { ease: EASE });
  const gradientX = useTransform(progress, [.775, .87], [0, w * (scene.mobile ? .05 : .215)], { ease: EASE });
  const gradientY = useTransform(progress, [.775, .87], [0, h * .06], { ease: EASE });
  const labelOpacity = useTransform(progress, [.60, .65, .765, .805], [0, 1, 1, 0]);
  const orbitOpacity = useTransform(progress, [.64, .665, .775, .81], [0, 1, 1, 0]);
  const libraryOpacity = useTransform(progress, [.79, .86, .93, .975], [0, 1, 1, 0]);
  const libraryScale = useTransform(progress, [.91, .975], [1, scene.mobile ? 1 : 1.2], { ease: EASE });
  const finalOpacity = useTransform(progress, [.935, .98], [0, 1]);
  const finalScale = useTransform(progress, [.925, .985], [.88, 1], { ease: EASE });
  const stepWidth = w * (scene.mobile ? .9 : .672);
  const stepGap = w * (scene.mobile ? .1 : .0723);
  const railX = useTransform(progress, [.51, .64, .775, .87], [0, -(stepWidth + stepGap), -(stepWidth + stepGap), -2 * (stepWidth + stepGap)], { ease: EASE });
  const railOpacity = useTransform(progress, [0, .055, .91, .96], [0, 1, 1, 0]);
  function next() {
    const node = root.current; if (!node) return;
    node.querySelectorAll<HTMLElement>(".story-step h2")[1]?.focus({ preventScroll: true });
    const top = node.getBoundingClientRect().top + window.scrollY;
    window.scrollTo({ top: top + (node.offsetHeight - window.innerHeight) * .69, behavior: reduce ? "instant" : "smooth" });
  }
  return <section ref={root} className="story-scroll" id="method" aria-label="Как создаётся узор">
    <div className="story-sticky">
      <a className="story-skip" href="#support">Пропустить анимацию</a>
      <div ref={visual} className="story-visual" aria-hidden="true">
        <motion.div className="story-grid" style={{ opacity: gridOpacity, x: gridX }}>{Array.from({ length: 12 }, (_, i) => <span key={i} />)}</motion.div>
        <motion.div className="story-library" style={{ opacity: libraryOpacity, scale: libraryScale }}><LibraryShell /></motion.div>
        <motion.div className="story-gradient" style={{ opacity: gradientOpacity, scaleX: gradientScaleX, scaleY: gradientScaleY, x: gradientX, y: gradientY }}><div className="story-gradient-drift" /><motion.span className="story-generating-label" style={{ opacity: labelOpacity }}>Генерируем узор</motion.span></motion.div>
        {[0, 1, 2, 3].map(order => <SelectedTile key={order} order={order} progress={progress} scene={scene} />)}
        <motion.div className={`story-loading-orbit ${loading ? "is-loading" : ""}`} style={{ opacity: orbitOpacity }}>{[0, 1, 2, 3].map(i => <span key={i} />)}</motion.div>
        <motion.div className="story-cursor" style={{ x: cursorX, y: cursorY, opacity: cursorOpacity, scale: cursorScale }} />
      </div>
      <motion.button className="story-next" aria-label="Следующий шаг: соберите рисунок" onClick={next} style={{ opacity: gridOpacity, scale: cursorScale, pointerEvents: nextActive ? "auto" : "none" }} aria-hidden={!nextActive} tabIndex={nextActive ? 0 : -1}><span aria-hidden="true">→</span></motion.button>
      <motion.div className="story-rail" style={{ x: railX, opacity: railOpacity, gap: stepGap }}>{[0, 1, 2].map(i => <StoryStep i={i} key={i} progress={progress} width={stepWidth} />)}</motion.div>
      <motion.div className="story-final-window" style={{ opacity: finalOpacity, scale: finalScale }} inert={!finalActive}>
        <div className="story-final-sidebar" aria-hidden="true"><i /><i /><i /><i /></div><div className="story-final-content"><CirclePattern /><div className="story-final-copy"><h2>Создайте свой узор</h2><Link href={href} className="story-cta-link">✣ Перейти в мастерскую <span aria-hidden="true">→</span></Link></div></div>
      </motion.div>
    </div>
    <StaticStory href={href} />
    <noscript><style>{`.home-hero-art,.home-wordmark,.home-topbar{opacity:1!important;transform:none!important}.home-menu-trigger{display:none}.story-scroll{height:auto}.story-sticky{display:none}.story-static{display:block}.story-static>section{min-height:70vh;padding:12vh 10vw;position:relative;overflow:hidden}.story-static h2{font-size:30px;margin:25px 0}.story-static-art{display:none}.story-static-final .story-circle-pattern{display:none}`}</style></noscript>
  </section>;
}
