"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { cubicBezier, motion, useAnimationFrame, useMotionValue, useMotionValueEvent, useReducedMotion, useScroll, useSpring, useTransform, type MotionValue } from "motion/react";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { HOME } from "@/content/home";

// All phases share one scroll clock: reversing the scroll reverses every morph.
const EASE = cubicBezier(.28, .11, .32, 1);
const DESKTOP_SELECTIONS = [4, 1, 10, 3];
const MOBILE_SELECTIONS = [3, 6, 1, 11];
const ACTIVATION = [.17, .26, .35, .44];
type Scene = { width: number; height: number; mobile: boolean; viewportWidth: number; viewportHeight: number; sendX: number; sendY: number };

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
  const turn = useMotionValue(0);
  useAnimationFrame((_, delta) => {
    const p = progress.get();
    if (p >= .64 && p < .83) turn.set(turn.get() + Math.min(delta, 40) / 2400 * Math.PI * 2 * EASE(Math.min(1, (p - .64) / .025)));
  });
  const morph = useTransform(progress, [.51, .64], [0, 1], { ease: EASE });
  const x = useTransform(() => {
    const angle = order * Math.PI / 2 + turn.get();
    return startX + (centerX + Math.cos(angle) * ring - dot / 2 - startX) * morph.get();
  });
  const y = useTransform(() => {
    const angle = order * Math.PI / 2 + turn.get();
    return startY + (centerY + Math.sin(angle) * ring - dot / 2 - startY) * morph.get();
  });
  const width = useTransform(morph, [0, 1], [tw, dot]);
  const height = useTransform(morph, [0, 1], [th, dot]);
  const opacity = useTransform(progress, [ACTIVATION[order], ACTIVATION[order] + .014, .765, .805], [0, 1, 1, 0]);
  const color = useTransform(progress, [.52, .64], ["#f39a5d", "#ffffff"]);
  const radius = useTransform(morph, [0, 1], [mobile ? 20 : 14, dot / 2]);
  const glow = useTransform(progress, [.51, .64], ["0px 1px 8px #00000026", "0px 0px 18px #ffffff, 0px 0px 36px #ffffff, 0px 0px 6px #ffffff"]);
  return <motion.div className="story-selected-tile" style={{ width, height, x, y, opacity, borderRadius: radius, boxShadow: glow, backgroundColor: color }} />;
}
function StoryStep({ i, progress, width }: { i: number; progress: MotionValue<number>; width: number }) {
  const opacity = useTransform(progress, i === 0 ? [.01, .065, .53, .62] : i === 1 ? [.51, .62, .78, .86] : [.77, .86, .91, .96], i === 0 ? [0, 1, 1, .3] : [ .3, 1, 1, .3]);
  const bodyOpacity = useTransform(progress, i === 0 ? [.015, .07, .51, .58] : i === 1 ? [.54, .63, .77, .83] : [.8, .87, .91, .96], [0, 1, 1, 0]);
  return <motion.article className="story-step" style={{ opacity, width }}><h2 tabIndex={-1}>{HOME.steps[i].title}</h2><svg viewBox="0 0 650 40" preserveAspectRatio="none" aria-hidden="true"><path d="M0 20H645M624 1l21 19-21 19" fill="none" stroke="currentColor" strokeWidth="3" /></svg><motion.p style={{ opacity: bodyOpacity }}>{HOME.steps[i].body}</motion.p></motion.article>;
}
export function CirclePattern() {
  return <div className="story-circle-pattern" aria-hidden="true">{[0, 1, 2].map(i => <picture key={i}><source media="(max-width: 767px)" srcSet={`/home-v2/circle-ring-m-${i}.webp`} /><img src={`/home-v2/circle-ring-d-${i}.webp`} alt="" width="930" height="633" loading="lazy" /></picture>)}</div>;
}
function LibraryShell() {
  return <><div className="story-library-sidebar"><i /><i /><i /><i /></div><div className="story-library-grid">{Array.from({ length: 28 }, (_, i) => <span key={i} />)}</div></>;
}
function StaticStory({ href }: { href: string }) {
  return <div className="story-static">{HOME.steps.map((step, i) => <section key={step.title}><div className={`story-static-art story-static-art-${i}`} aria-hidden="true">{i === 0 ? Array.from({ length: 12 }, (_, n) => <span className={DESKTOP_SELECTIONS.includes(n) ? "selected" : ""} key={n} />) : i === 1 ? <span className="story-static-gradient">Генерируем узор</span> : <LibraryShell />}</div><h2>{step.title}</h2><p>{step.body}</p></section>)}<section className="story-static-final"><CirclePattern /><h2>Создайте свой узор</h2><Link href={href} className="story-cta-link"><ModeIcon mode="ai" /> Перейти в мастерскую <span className="story-cta-arrow" aria-hidden="true"><svg viewBox="0 0 36 18"><path d="M1 9h32M26 2l7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2" /></svg></span></Link></section></div>;
}
export function GenerationStory({ href }: { href: string }) {
  const root = useRef<HTMLElement>(null);
  const visual = useRef<HTMLDivElement>(null);
  const sendButton = useRef<HTMLButtonElement>(null);
  const resultCell = useRef<HTMLSpanElement>(null);
  const [destination, setDestination] = useState({x:230,y:20,width:80,height:90});
  const [scene, setScene] = useState<Scene>({ width: 968, height: 436, mobile: false, viewportWidth: 1728, viewportHeight: 1229, sendX: 1100, sendY: 218 });
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
    const update = () => {
      const rect = node.getBoundingClientRect(), send = sendButton.current?.getBoundingClientRect();
      const cell=resultCell.current;
      if(cell) {
        const cells=cell.offsetParent as HTMLElement, content=cells.offsetParent as HTMLElement;
        setDestination({x:cell.offsetLeft+cells.offsetLeft+content.offsetLeft+content.clientLeft,y:cell.offsetTop+cells.offsetTop+content.offsetTop+content.clientTop,width:cell.offsetWidth,height:cell.offsetHeight});
      }
      setScene({ width: rect.width, height: rect.height, mobile: matchMedia("(max-width: 767px)").matches, viewportWidth: node.parentElement!.clientWidth, viewportHeight: node.parentElement!.clientHeight, sendX: send ? send.left + send.width / 2 - rect.left - 3 : rect.width, sendY: send ? send.top + send.height / 2 - rect.top - 2 : rect.height / 2 });
    };
    const resize = new ResizeObserver(update);
    resize.observe(node); resize.observe(node.parentElement!);
    if (sendButton.current) resize.observe(sendButton.current);
    if (resultCell.current) resize.observe(resultCell.current);
    window.addEventListener("resize", update); update();
    return () => { resize.disconnect(); window.removeEventListener("resize", update); };
  }, []);
  useMotionValueEvent(progress, "change", p => { setFinalActive(p >= .955); setNextActive(p >= .13 && p < .51); });
  const w = scene.width, h = scene.height;
  const columns = scene.mobile ? 3 : 4, rows = scene.mobile ? 4 : 3;
  const gap = w * (scene.mobile ? .045 : .01756);
  const tw = (w - gap * (columns - 1)) / columns, th = (h - gap * (rows - 1)) / rows;
  const indices = scene.mobile ? MOBILE_SELECTIONS : DESKTOP_SELECTIONS;
  const cx = (n: number) => (n % columns) * (tw + gap) + tw * .83;
  const cy = (n: number) => Math.floor(n / columns) * (th + gap) + th * .6;
  const cursorX = useTransform(progress, [.12, .17, .23, .26, .32, .35, .41, .44, .48, .5], [-scene.viewportWidth * .12 - w, cx(indices[0]), cx(indices[0]), cx(indices[1]), cx(indices[1]), cx(indices[2]), cx(indices[2]), cx(indices[3]), scene.mobile ? cx(indices[3]) : scene.sendX, scene.mobile ? cx(indices[3]) : scene.sendX], { ease: EASE });
  const cursorY = useTransform(progress, [.12, .17, .23, .26, .32, .35, .41, .44, .48], [h * .5, cy(indices[0]), cy(indices[0]), cy(indices[1]), cy(indices[1]), cy(indices[2]), cy(indices[2]), cy(indices[3]), scene.mobile ? cy(indices[3]) : scene.sendY], { ease: EASE });
  const cursorOpacity = useTransform(progress, [.115, .12, .505, .535], [0, 1, 1, 0]);
  const cursorScale = useTransform(progress, [.475, .49, .5, .515], scene.mobile ? [1, 1, 1, 1] : [1, .8, .8, 1]);
  const gridOpacity = useTransform(progress, [.07, .13, .51, .6], [0, 1, 1, 0]);
  const gridX = useTransform(progress, [.51, .64], [0, -w * .45], { ease: EASE });
  const gradientOpacity = useTransform(progress, [.53, .625, .915, .97], [0, 1, 1, 0]);
  const gradientScaleX = useTransform(progress, [.775, .87], [1, destination.width / w], { ease: EASE });
  const gradientScaleY = useTransform(progress, [.775, .87], [1, destination.height / h], { ease: EASE });
  const gradientX = useTransform(progress, [.775, .87], [0, destination.x], { ease: EASE });
  const gradientY = useTransform(progress, [.775, .87], [0, destination.y], { ease: EASE });
  const labelOpacity = useTransform(progress, [.60, .65, .765, .805], [0, 1, 1, 0]);
  const libraryOpacity = useTransform(progress, [.79, .86], [0, 1]);
  const libraryBackground = useTransform(progress, [.91, .985], ["#dad7d5", scene.mobile ? "#f7f5f6" : "#dad7d5"]);
  const libraryScale = useTransform(progress, [.91, .985], [1, scene.mobile ? 1.06 : 1.25], { ease: EASE });
  const libraryX = useTransform(progress, [.91, .985], [0, scene.viewportWidth * (.5 - .097) - w * (scene.mobile ? 1.06 : 1.25) / 2], { ease: EASE });
  const libraryY = useTransform(progress, [.91, .985], [0, scene.viewportHeight * (.5 - (scene.mobile ? .1487 : .1456)) - h * (scene.mobile ? 1.06 : 1.25) / 2], { ease: EASE });
  const finalOpacity = useTransform(progress, [.92, .98], [0, 1]);
  const cellsOpacity = useTransform(progress, [.915, .97], [1, 0]);
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

        <motion.div className="story-cursor" style={{ x: cursorX, y: cursorY, opacity: cursorOpacity, scale: cursorScale }} />
      </div>
      <motion.button ref={sendButton} className="story-next" aria-label="Следующий шаг: соберите рисунок" onClick={next} style={{ opacity: gridOpacity, scale: cursorScale, pointerEvents: nextActive ? "auto" : "none" }} aria-hidden={!nextActive} tabIndex={nextActive ? 0 : -1}><span className="story-cta-arrow" aria-hidden="true"><svg viewBox="0 0 36 18"><path d="M1 9h32M26 2l7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2" /></svg></span></motion.button>
      <motion.div className="story-rail" style={{ x: railX, opacity: railOpacity, gap: stepGap }}>{[0, 1, 2].map(i => <StoryStep i={i} key={i} progress={progress} width={stepWidth} />)}</motion.div>
      <div className="story-window-anchor">
        <motion.div className="story-shared-window" style={{ opacity: libraryOpacity, scale: libraryScale, x: libraryX, y: libraryY, backgroundColor: libraryBackground }} inert={!finalActive}>
          <div className="story-library-sidebar" aria-hidden="true"><i /><i /><i /><i /></div>
          <div className="story-shared-content">
            <motion.div className="story-shared-cells" style={{ opacity: cellsOpacity }} aria-hidden="true">{Array.from({ length: 28 }, (_, i) => <span key={i} ref={i === 0 ? resultCell : undefined} className={i === 0 ? "story-library-result" : undefined} />)}</motion.div>
            <motion.div className="story-final-scene" style={{ opacity: finalOpacity }}><CirclePattern /><div className="story-final-copy"><h2>Создайте свой узор</h2><Link href={href} className="story-cta-link"><ModeIcon mode="ai" /> Перейти в мастерскую <span className="story-cta-arrow" aria-hidden="true"><svg viewBox="0 0 36 18"><path d="M1 9h32M26 2l7 7-7 7" fill="none" stroke="currentColor" strokeWidth="2" /></svg></span></Link></div></motion.div>
          </div>
        </motion.div>
        <motion.div className="story-generating-frame" style={{scale:libraryScale,x:libraryX,y:libraryY}} aria-hidden="true">
          <motion.div className="story-generating-object" style={{scaleX:gradientScaleX,scaleY:gradientScaleY,x:gradientX,y:gradientY}}>
            <motion.div className="story-gradient" style={{opacity:gradientOpacity}}><div className="story-gradient-drift" /><motion.span className="story-generating-label" style={{opacity:labelOpacity}}>Генерируем узор</motion.span></motion.div>
            {[0,1,2,3].map(order=><SelectedTile key={order} order={order} progress={progress} scene={scene} />)}
          </motion.div>
        </motion.div>
      </div>
    </div>
    <StaticStory href={href} />
    <noscript><style>{`.home-hero-art,.home-wordmark,.home-topbar{opacity:1!important;transform:none!important}.home-menu-trigger{display:none}.story-scroll{height:auto}.story-sticky{display:none}.story-static{display:block}.story-static>section{min-height:70vh;padding:12vh 10vw;position:relative;overflow:hidden}.story-static h2{font-size:30px;margin:25px 0}.story-static-art{display:none}.story-static-final .story-circle-pattern{display:none}`}</style></noscript>
  </section>;
}
