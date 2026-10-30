"use client";
/* eslint-disable @next/next/no-img-element -- Temporary same-origin cookie-protected result previews. */
import { useEffect, useState } from "react";
import Link from "next/link";
import { ModeIcon } from "@/components/ui/ModeIcon";
import { SendArrow } from "@/components/ui/SendArrow";
import { apiUrl } from "@/lib/api";
import { recentWorks } from "@/lib/guest-work";
export function LibraryScreen() {
  const [items,setItems] = useState<ReturnType<typeof recentWorks>>([]);
  useEffect(() => {const update=()=>setItems(recentWorks());update();const timer=setInterval(update,1000);return ()=>clearInterval(timer);},[]);
  return <section className="flex min-h-0 flex-1 flex-col overflow-y-auto rounded-tl-[24px] rounded-bl-[3px] bg-surface px-[58px] pt-[60px] pb-6 max-md:rounded-none max-md:bg-transparent max-md:px-[27px] max-md:pt-[24px]"><article className={items.length ? "" : "recent-empty"}>{!items.length ? <div className="recent-empty-content"><h1>Сейчас здесь пусто!</h1><Link href="/flat" className="ai-generate recent-empty-create"><span><ModeIcon mode="ai" />Сгенерировать первый узор</span><span className="ai-generate-arrow"><SendArrow /></span></Link></div> : <><h1 className="mb-6 font-display text-[36px] italic leading-none text-black max-md:text-[28px]">Недавние генерации</h1>
    <div className="mt-8 grid grid-cols-4 gap-[22px] max-md:grid-cols-2 max-md:gap-[12px]">{items.map(g=>{const title=g.title ?? (g.mode === "ai" ? "AI-вариант" : "Параметрический рисунок");return <Link key={g.id} href={g.href ?? `/constructor?pattern=${encodeURIComponent(g.id)}&from=library`} className="rounded-3xl bg-white/60 p-3 shadow-sm">{g.imageUrl ? <img src={apiUrl(g.imageUrl)} alt={title} className="aspect-square w-full rounded-2xl object-contain" /> : null}<p className="my-2 font-semibold">{title}</p></Link>;})}</div></>}
  </article></section>;
}
