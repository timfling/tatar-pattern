"use client";

import { useId, type SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { title?: string };

export function GoldDefs() {
  return (
    <defs>
      <linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#7A5C12" />
        <stop offset="22%" stopColor="#F3D98A" />
        <stop offset="48%" stopColor="#C9A227" />
        <stop offset="62%" stopColor="#FFF6D4" />
        <stop offset="82%" stopColor="#C9A227" />
        <stop offset="100%" stopColor="#8A6D1F" />
      </linearGradient>
      <linearGradient id="goldVert" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#F3D98A" />
        <stop offset="50%" stopColor="#C9A227" />
        <stop offset="100%" stopColor="#8A6D1F" />
      </linearGradient>
      <radialGradient id="goldRadial" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="#FFF6D4" />
        <stop offset="45%" stopColor="#E8C547" />
        <stop offset="100%" stopColor="#8A6D1F" />
      </radialGradient>
    </defs>
  );
}

export function LogoMark({ className, ...props }: IconProps) {
  const uid = useId().replace(/:/g, "");
  const g = `${uid}logo`;
  return (
    <svg viewBox="0 0 64 64" className={className} fill="none" {...props}>
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7A5C12" />
          <stop offset="22%" stopColor="#F3D98A" />
          <stop offset="48%" stopColor="#C9A227" />
          <stop offset="62%" stopColor="#FFF6D4" />
          <stop offset="82%" stopColor="#C9A227" />
          <stop offset="100%" stopColor="#8A6D1F" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="30" stroke={`url(#${g})`} strokeWidth="1.2" />
      <circle cx="32" cy="32" r="26" stroke={`url(#${g})`} strokeWidth="0.4" opacity="0.7" />
      <path
        fill={`url(#${g})`}
        d="M32 6l3.2 9.2 7.4-6.4-2.2 9.6 9.4-2.6-6.6 7.2 9.2 3.2-9.2 3.2 6.6 7.2-9.4-2.6 2.2 9.6-7.4-6.4L32 58l-3.2-9.2-7.4 6.4 2.2-9.6-9.4 2.6 6.6-7.2L11.6 35.2l9.2-3.2-6.6-7.2 9.4 2.6-2.2-9.6 7.4 6.4z"
      />
      <path
        fill="#070605"
        d="M32 22c-1.4 6-1.1 10.5 0 14 1.1-3.5 1.4-8 0-14zm-7 4c3.4 3.2 7.2 4.8 11 5-3.8-.2-7.6-1.8-11-5zm14 0c-3.4 3.2-7.2 4.8-11 5 3.8-.2 7.6-1.8 11-5z"
      />
      <path
        fill="#070605"
        d="M32 20c-4.8-1.2-9 3.2-8.2 8.2 1.8-2.4 4.8-4.6 8.2-5.6 3.4 1 6.4 3.2 8.2 5.6.8-5-3.4-9.4-8.2-8.2z"
      />
    </svg>
  );
}

export function TulipPaths() {
  return (
    <>
      <path d="M50 96c-1.2-14 1.4-28 0-44" fill="none" stroke="currentColor" strokeWidth="2.2" />
      <path d="M50 72C34 70 22 58 26 48c8 6 16 14 24 20 8-6 16-14 24-20 4 10-8 22-24 24z" />
      <path d="M50 54C36 50 24 30 32 14c7 8 12 20 18 34 6-14 11-26 18-34 8 16-4 36-18 40z" />
      <path d="M50 52C44 28 46 10 50 4c4 6 6 24 0 48z" />
    </>
  );
}

export function TulipMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" {...props}>
      <TulipPaths />
    </svg>
  );
}

export function HornPaths() {
  return (
    <>
      <path
        d="M50 78c-18 0-30-14-30-28 0-16 12-26 24-26 8 0 14 6 14 14 0 8-6 12-12 12-4 0-8-3-8-8 0-3 2-6 6-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.2"
        strokeLinecap="round"
      />
      <path
        d="M50 78c18 0 30-14 30-28 0-16-12-26-24-26-8 0-14 6-14 14 0 8 6 12 12 12 4 0 8-3 8-8 0-3-2-6-6-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="3.2"
        strokeLinecap="round"
      />
      <circle cx="50" cy="80" r="3.2" fill="currentColor" />
    </>
  );
}

export function HornMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none" {...props}>
      <HornPaths />
    </svg>
  );
}

export function StarPaths() {
  return (
    <>
      <path d="M50 8l7 25h26l-21 15 8 26-20-15-20 15 8-26-21-15h26z" />
      <path
        d="M50 22l4.5 16h17l-13.5 10 5 16.5-13-10-13 10 5-16.5-13.5-10h17z"
        fill="none"
        stroke="#070605"
        strokeWidth="1.4"
      />
    </>
  );
}

export function StarMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" {...props}>
      <StarPaths />
    </svg>
  );
}

export function TrefoilPaths() {
  return (
    <>
      <path d="M50 92c-1-16 0-30 0-42" fill="none" stroke="currentColor" strokeWidth="2.2" />
      <path d="M50 52C34 40 18 42 16 28 14 14 30 10 42 22c4 4 7 10 8 16 1-6 4-12 8-16C70 10 86 14 84 28 82 42 66 40 50 52z" />
      <path d="M50 54C40 70 22 74 22 86c0 10 14 12 24-2 4-6 5-12 4-18 5 4 14 6 22 2 14 16 28 12 28-2 0-12-18-16-28-32-4 8-10 14-22 16z" opacity="0.95" />
    </>
  );
}

export function TrefoilMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" {...props}>
      <TrefoilPaths />
    </svg>
  );
}

export function CarnationPaths() {
  return (
    <>
      <path d="M50 96c0-18 2-34 0-50" fill="none" stroke="currentColor" strokeWidth="2.2" />
      <path d="M50 70C36 66 28 56 32 48c10 6 14 12 18 20 4-8 8-14 18-20 4 8-4 18-18 22z" />
      <path d="M50 50c-16-2-22-16-14-26 4 6 9 10 14 14 5-4 10-8 14-14 8 10 2 24-14 26z" />
      <path d="M28 28c8-10 16-8 22 0-8 2-16 4-22 0zm44 0c-8-10-16-8-22 0 8 2 16 4 22 0z" />
      <path d="M36 16c6-10 12-8 14 2-6 0-10 2-14-2zm28 0c-6-10-12-8-14 2 6 0 10 2 14-2zM50 12c-2-8 0-10 0-10s2 2 0 10z" />
    </>
  );
}

export function CarnationMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" {...props}>
      <CarnationPaths />
    </svg>
  );
}

export function IslimiPaths() {
  return (
    <>
      <path
        d="M12 78c18-6 22-24 38-30 16-6 22 8 38 2"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
      />
      <path
        d="M28 72c6-16 4-28-8-38"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path d="M20 34c-8 2-12 12-8 18 10-4 14-10 8-18z" fill="currentColor" />
      <path
        d="M50 50c8-18 22-22 34-16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path d="M82 30c10-2 16 8 12 16-12-2-16-8-12-16z" fill="currentColor" />
      <path d="M48 48c-4-12 2-22 14-24-6 10-8 16-14 24z" fill="currentColor" />
      <circle cx="50" cy="52" r="3" fill="currentColor" />
    </>
  );
}

export function IslimiMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none" {...props}>
      <IslimiPaths />
    </svg>
  );
}

export function RosettePaths() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <ellipse
          key={i}
          cx="50"
          cy="28"
          rx="8"
          ry="20"
          transform={`rotate(${i * 45} 50 50)`}
        />
      ))}
      <circle cx="50" cy="50" r="10" fill="#070605" />
      <circle cx="50" cy="50" r="5.5" />
    </>
  );
}

export function RosetteMotif({ className, ...props }: IconProps) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="currentColor" {...props}>
      <RosettePaths />
    </svg>
  );
}

const MOTIF_MAP = {
  tulip: TulipMotif,
  horn: HornMotif,
  star: StarMotif,
  trefoil: TrefoilMotif,
  carnation: CarnationMotif,
  islimi: IslimiMotif,
  rosette: RosetteMotif,
};

export type MotifId = keyof typeof MOTIF_MAP;

export function MotifById({ id, className }: { id: MotifId; className?: string }) {
  const Cmp = MOTIF_MAP[id];
  return <Cmp className={className} />;
}

export function MotifPaths({ id }: { id: MotifId }) {
  switch (id) {
    case "tulip":
      return <TulipPaths />;
    case "horn":
      return <HornPaths />;
    case "star":
      return <StarPaths />;
    case "trefoil":
      return <TrefoilPaths />;
    case "carnation":
      return <CarnationPaths />;
    case "islimi":
      return <IslimiPaths />;
    case "rosette":
      return <RosettePaths />;
  }
}

export function CornerFrame({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 80 80" className={className} fill="none">
      <path d="M8 48V12h36" stroke="currentColor" strokeWidth="1.4" />
      <path d="M8 28c12-2 18-12 20-20" stroke="currentColor" strokeWidth="1" />
      <circle cx="8" cy="12" r="2" fill="currentColor" />
      <path d="M18 12c6 8 14 10 22 8" stroke="currentColor" strokeWidth="1" />
    </svg>
  );
}

export function VerticalBorder({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 400" className={className} preserveAspectRatio="none" fill="none">
      <path d="M20 0v400" stroke="currentColor" strokeWidth="0.6" opacity="0.5" />
      {Array.from({ length: 8 }).map((_, i) => (
        <g key={i} transform={`translate(0 ${i * 50})`} fill="currentColor">
          <circle cx="20" cy="25" r="1.6" />
          <path d="M20 18c-8 4-8 10 0 14 8-4 8-10 0-14z" opacity="0.85" />
        </g>
      ))}
    </svg>
  );
}

export function DividerOrnament({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 24" className={className} fill="currentColor">
      <path d="M0 12h118" stroke="currentColor" strokeWidth="0.8" fill="none" />
      <path d="M202 12h118" stroke="currentColor" strokeWidth="0.8" fill="none" />
      <path d="M160 2c-10 6-14 10-14 10s4 4 14 10c10-6 14-10 14-10s-4-4-14-10z" />
      <circle cx="160" cy="12" r="2.4" />
      <path d="M132 12c8-8 16-8 28 0-12 8-20 8-28 0z" opacity="0.7" />
    </svg>
  );
}

export function MedallionSVG({ className }: { className?: string }) {
  const uid = useId().replace(/:/g, "");
  const g = `${uid}medal`;
  return (
    <svg viewBox="0 0 200 200" className={className}>
      <defs>
        <linearGradient id={g} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7A5C12" />
          <stop offset="22%" stopColor="#F3D98A" />
          <stop offset="48%" stopColor="#C9A227" />
          <stop offset="62%" stopColor="#FFF6D4" />
          <stop offset="82%" stopColor="#C9A227" />
          <stop offset="100%" stopColor="#8A6D1F" />
        </linearGradient>
      </defs>
      <circle cx="100" cy="100" r="96" fill="none" stroke={`url(#${g})`} strokeWidth="1.2" />
      <circle cx="100" cy="100" r="88" fill="none" stroke={`url(#${g})`} strokeWidth="0.4" />
      {Array.from({ length: 16 }).map((_, i) => (
        <path
          key={i}
          d="M100 18c-6 14-6 28 0 36 6-8 6-22 0-36z"
          fill={`url(#${g})`}
          transform={`rotate(${i * 22.5} 100 100)`}
        />
      ))}
      {Array.from({ length: 8 }).map((_, i) => (
        <path
          key={`p-${i}`}
          d="M100 46c-10 16-8 30 0 38 8-8 10-22 0-38z"
          fill={`url(#${g})`}
          opacity="0.9"
          transform={`rotate(${i * 45 + 22.5} 100 100)`}
        />
      ))}
      <circle cx="100" cy="100" r="22" fill="#070605" stroke={`url(#${g})`} strokeWidth="1.5" />
      <path
        fill={`url(#${g})`}
        d="M100 84c-8 6-12 12-12 16 0 8 6 12 12 16 6-4 12-8 12-16 0-4-4-10-12-16z"
      />
    </svg>
  );
}

export function TileMotif({
  id,
  color,
}: {
  id: MotifId;
  color: string;
}) {
  const Cmp = MOTIF_MAP[id];
  return <Cmp style={{ color }} width="100%" height="100%" />;
}
