"use client";
/* eslint-disable @next/next/no-img-element -- Temporary same-origin cookie-protected result previews. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { apiUrl } from "@/lib/api";
import { recentWorks } from "@/lib/guest-work";
export function LibraryScreen() {
  const [items,setItems] = useState<ReturnType<typeof recentWorks>>([]);
  useEffect(() => {const update=()=>setItems(recentWorks());update();const timer=setInterval(update,1000);return ()=>clearInterval(timer);},[]);
  return <section className="flex min-h-0 flex-1 flex-col overflow-y-auto rounded-tl-[24px] rounded-bl-[3px] bg-surface px-[58px] pt-[60px] pb-6 max-md:rounded-none max-md:bg-transparent max-md:px-[27px] max-md:pt-[24px]"><article><h1 className="mb-6 font-display text-[36px] italic leading-none text-black max-md:text-[28px]">Недавние генерации</h1>
    <div className="mt-8 grid grid-cols-4 gap-[22px] max-md:grid-cols-2 max-md:gap-[12px]">{items.map(g=><Link key={g.id} href={`/constructor?pattern=${encodeURIComponent(g.id)}&from=library`} className="rounded-3xl bg-white/60 p-3 shadow-sm">{g.imageUrl ? <img src={apiUrl(g.imageUrl)} alt={g.mode === "ai" ? "AI-вариант" : "Параметрический рисунок"} className="aspect-square w-full rounded-2xl object-contain" /> : null}<p className="my-2 font-semibold">{g.mode === "ai" ? "AI-вариант" : "Параметрический рисунок"}</p></Link>)}</div>
  </article></section>;
}
