"use client";
import { useEffect, useState } from "react";
import { api, apiMessage, type Project } from "@/lib/api";
export function ProjectPicker({ patternId, value, onChange, onError }: { patternId: string; value: string | null; onChange: (id: string | null) => void; onError: (message: string) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [pending, setPending] = useState(false);
  useEffect(() => { let active = true; api.projects().then(({items}) => { if (active) setProjects(items); }).catch((e) => { if (active) onError(apiMessage(e)); }); return () => { active = false; }; }, [onError]);
  async function change(id: string) {
    setPending(true);
    try { const {generation} = await api.patchGeneration(patternId, { projectId: id || null }); onChange(generation.projectId); onError(""); }
    catch (e) { onError(apiMessage(e)); } finally { setPending(false); }
  }
  return <label className="api-notice shrink-0">Сохранено в истории · Проект: <select aria-label="Проект результата" value={value ?? ""} disabled={pending} onChange={(e) => change(e.target.value)} className="max-w-[180px] rounded-lg bg-white p-2"><option value="">Без проекта</option>{projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></label>;
}
