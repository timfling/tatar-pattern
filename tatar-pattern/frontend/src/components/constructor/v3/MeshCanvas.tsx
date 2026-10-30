"use client";
import { useEffect, useRef } from "react";

/**
 * Mesh gradient из «html дизайнов/v3/Mesh-gradient-source/main.ts»:
 * сетка 4×4 цветовых точек, интерполяция Catmull-Rom по строкам и столбцам в линейном цвете.
 * Здесь — CPU-версия на маленьком canvas (растягивается CSS со сглаживанием).
 * Анимация: внутренние точки сетки плавно смещаются (как перетаскивание точек в Figma),
 * поэтому цвета «перетекают», а не просто вращаются.
 */
const COLORS: [number, number, number][] = [
  [1, 0.42, 0.42], [1, 0.64, 0.42], [1, 0.82, 0.42], [1, 0.82, 0.4],
  [0.7, 0.3, 0.6], [0.8, 0.55, 0.5], [0.9, 0.7, 0.45], [0.5, 0.7, 0.35],
  [0.4, 0.5, 0.7], [0.35, 0.65, 0.65], [0.2, 0.65, 0.55], [0.1, 0.55, 0.7],
  [0.02, 0.84, 0.63], [0.1, 0.7, 0.65], [0.1, 0.6, 0.7], [0.07, 0.54, 0.7],
];
const toLin = (v: number) => (v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4));
const toSrgb = (v: number) => { const s = Math.max(0, v); return s <= 0.0031308 ? s * 12.92 : 1.055 * Math.pow(s, 1 / 2.4) - 0.055; };
const LIN = COLORS.map(c => c.map(toLin) as [number, number, number]);

function catmull(a: number, b: number, c: number, d: number, t: number) {
  const t2 = t * t, t3 = t2 * t;
  return 0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t2 + (-a + 3 * b - 3 * c + d) * t3);
}
function seg(v: number) { const s = Math.min(Math.max(v, 0), 1) * 3; const i = Math.min(Math.floor(s), 2); return [i, s - i] as const; }

export function MeshCanvas({ className = "", animated = true }: { className?: string; animated?: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current; if (!canvas) return;
    const ctx = canvas.getContext("2d"); if (!ctx) return;
    const W = 96, H = 24; canvas.width = W; canvas.height = H;
    const image = ctx.createImageData(W, H);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0; let alive = true;
    const t0 = performance.now();
    function draw(now: number) {
      const t = (now - t0) / 1000;
      // Сдвиг координаты выборки ≈ перемещению внутренних точек сетки.
      for (let y = 0; y < H; y++) {
        for (let x = 0; x < W; x++) {
          let u = x / (W - 1), v = y / (H - 1);
          u += 0.16 * Math.sin(t * 0.9 + v * 3.1) * Math.sin(Math.PI * u);
          v += 0.22 * Math.sin(t * 0.7 + u * 4.2 + 1.3) * Math.sin(Math.PI * v);
          u = (u + 0.06 * Math.sin(t * 0.35)) ; v = v + 0.04 * Math.cos(t * 0.4);
          const [ix, fx] = seg(u), [iy, fy] = seg(v);
          const xs = [Math.max(ix - 1, 0), ix, ix + 1, Math.min(ix + 2, 3)];
          const ys = [Math.max(iy - 1, 0), iy, iy + 1, Math.min(iy + 2, 3)];
          const o = (y * W + x) * 4;
          for (let ch = 0; ch < 3; ch++) {
            const rows = ys.map(r => catmull(LIN[r * 4 + xs[0]][ch], LIN[r * 4 + xs[1]][ch], LIN[r * 4 + xs[2]][ch], LIN[r * 4 + xs[3]][ch], fx));
            image.data[o + ch] = Math.round(Math.min(1, Math.max(0, toSrgb(catmull(rows[0], rows[1], rows[2], rows[3], fy)))) * 255);
          }
          image.data[o + 3] = 255;
        }
      }
      ctx!.putImageData(image, 0, 0);
      if (alive && animated && !reduce) frame = requestAnimationFrame(draw);
    }
    frame = requestAnimationFrame(draw);
    return () => { alive = false; cancelAnimationFrame(frame); };
  }, [animated]);
  return <canvas ref={ref} className={className} aria-hidden="true" />;
}
