import { api, apiUrl, type Generation, type Rating } from "@/lib/api";
import { formatPatternStamp } from "@/components/constructor/data";
import type { ConstructorSelections } from "@/components/constructor/parameters";
export type PatternRating = Rating;
export type SavedPattern = {
  mode: "flat" | "ai";
  id: string; name: string; stamp: string; createdAt: number;
  imageUrl: string | null; rating: Rating; prompt: string;
  selections: ConstructorSelections; projectId: string | null; status: Generation["status"];
};
export function savedPattern(g: Generation): SavedPattern {
  return { mode: g.mode ?? "flat", id: g.id, name: g.title, stamp: formatPatternStamp(new Date(g.createdAt)), createdAt: Date.parse(g.createdAt), imageUrl: g.imageUrl ? apiUrl(g.imageUrl) : null, rating: g.rating, prompt: g.prompt, selections: g.selections, projectId: g.projectId, status: g.status === "done" && !g.imageUrl ? "error" : g.status };
}
export async function loadLibrary(): Promise<SavedPattern[]> {
  const items: SavedPattern[] = [];
  let total = Infinity;
  while (items.length < total) {
    const page = await api.generations(items.length);
    items.push(...page.items.map(savedPattern)); total = page.total;
    if (!page.items.length) break;
  }
  return items;
}
export async function updatePattern(id: string, patch: { name?: string; rating?: Rating; projectId?: string | null }) {
  return savedPattern((await api.patchGeneration(id, { ...(patch.name !== undefined ? { title: patch.name } : {}), ...(patch.rating !== undefined ? { rating: patch.rating } : {}), ...(patch.projectId !== undefined ? { projectId: patch.projectId } : {}) })).generation);
}
export async function getPattern(id: string) { return savedPattern((await api.generation(id)).generation); }
