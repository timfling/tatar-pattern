import { useId } from "react";
import { TulipPaths } from "@/components/home/Ornaments";

export function Artwork({ variant = "medallion" }: { variant?: "medallion" | "border" | "rapport" }) {
  const uid = useId().replace(/:/g, "");
  const motif = <g transform="translate(-50,-84)"><TulipPaths /><path d="M50 91C13 78 9 52 21 35M50 91C87 78 91 52 79 35" fill="none" stroke="currentColor" strokeWidth=".65" /><path d="M21 35C6 38 2 50 14 61C17 50 20 45 21 35M79 35C94 38 98 50 86 61C83 50 80 45 79 35" /></g>;
  return <svg viewBox="0 0 520 600" fill="none" aria-hidden="true" className="lp-artwork">
    <defs>
      <radialGradient id={`${uid}light`} cx="35%" cy="25%" r="90%"><stop stopColor="#3d4d39" /><stop offset="1" stopColor="#13271e" /></radialGradient>
      <linearGradient id={`${uid}metal`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#b6ae80" /><stop offset=".5" stopColor="#e0d9b8" /><stop offset="1" stopColor="#8b8965" /></linearGradient>
      <pattern id={`${uid}weave`} width="4" height="4" patternUnits="userSpaceOnUse"><path d="M0 0H4M0 2H4" stroke="#ffffff" strokeOpacity=".035" strokeWidth=".5" /></pattern>
    </defs>
    <rect width="520" height="600" fill={`url(#${uid}light)`} />
    <rect width="520" height="600" fill={`url(#${uid}weave)`} />
    <g color="#c8c49d" fill={`url(#${uid}metal)`}>
      {variant === "medallion" ? <g transform="translate(260 305)">
        <circle fill="none" r="214" stroke="currentColor" strokeOpacity=".25" strokeWidth=".5" />
        <circle fill="none" r="207" stroke="currentColor" strokeOpacity=".3" strokeWidth=".5" />
        <circle fill="none" r="170" stroke="currentColor" strokeOpacity=".5" strokeWidth=".5" />
        {Array.from({ length: 12 }, (_, i) => <g key={i} transform={`rotate(${i * 30}) translate(0 -94) scale(.87)`}>{motif}</g>)}
        {Array.from({ length: 24 }, (_, i) => <g key={i} transform={`rotate(${i * 15})`}><path d="M0-203q-5 8 0 12q5-4 0-12Z" /><path d="M0-157v14" stroke="currentColor" strokeWidth=".5" /></g>)}
        {Array.from({ length: 8 }, (_, i) => <g key={i} transform={`rotate(${i * 45}) scale(.42)`}>{motif}</g>)}
        <circle fill="none" r="13" stroke="currentColor" strokeWidth=".6" /><circle r="7" fill="currentColor" />
      </g> : variant === "border" ? <g>
        {[105,260,415].map((x) => <g key={x}><path d={`M${x-63} 0v600M${x+63} 0v600`} stroke="currentColor" strokeOpacity=".4" strokeWidth=".5" />{[110,260,410,560].map((y,i) => <g key={y} transform={`translate(${x} ${y}) rotate(${i%2 ? 180 : 0}) scale(.8)`}>{motif}</g>)}</g>)}
      </g> : <g>{Array.from({length: 5}, (_, row) => Array.from({length: 5}, (_, col) => <g key={`${row}-${col}`} transform={`translate(${col*125+(row%2?63:0)} ${row*145+65}) scale(.85)`}>{motif}</g>))}</g>}
    </g>
  </svg>;
}
