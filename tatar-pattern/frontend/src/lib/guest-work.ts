import { api, ApiError, type GuestGeneration as Generation, type GuestRequest } from "./api";

// One current work per tab. No cookie/token, user identifier or history is stored here.
export const WORK_KEY = "tp-guest-work-v1";
export type CurrentWork = { body: GuestRequest; expiresAt: string; id?: string; submitted?: boolean; blocked?: boolean };
export function readWork(): CurrentWork | null {
  try {
    const value = sessionStorage.getItem(WORK_KEY);
    if (!value) return null;
    const work = JSON.parse(value) as CurrentWork;
    if (!work.body?.requestId || !["flat", "ai"].includes(work.body.mode) || !Number.isFinite(Date.parse(work.expiresAt))) throw Error();
    if (Date.parse(work.expiresAt) <= Date.now()) { forgetWork(); return null; }
    return work;
  } catch { return null; }
}
function writeWork(work: CurrentWork) {
  // If persistence is unavailable, stop before submitting: reload must not lose the UUID.
  sessionStorage.setItem(WORK_KEY, JSON.stringify(work));
  window.dispatchEvent(new Event("tp-guest-work"));
}
export function forgetWork() { sessionStorage.removeItem(WORK_KEY); window.dispatchEvent(new Event("tp-guest-work")); }
const recent = new Map<string, Pick<Generation, "id" | "mode" | "expiresAt" | "createdAt" | "imageUrl">>();
export function recentWorks() {
  for (const [id,g] of recent) if (Date.parse(g.expiresAt) <= Date.now()) recent.delete(id);
  return [...recent.values()].reverse();
}
export function rememberGeneration(g: Generation) {
  if (g.status === "done" && g.imageUrl && Date.parse(g.expiresAt) > Date.now()) {
    setTimeout(() => recent.delete(g.id), Math.max(0,Date.parse(g.expiresAt)-Date.now()));
    recent.set(g.id,{id:g.id,mode:g.mode,expiresAt:g.expiresAt,createdAt:g.createdAt,imageUrl:g.imageUrl});
    if(recent.size > 20) recent.delete(recent.keys().next().value!);
  }
  const work = readWork();
  if (work && work.body.requestId === g.requestId) writeWork({ ...work, id: g.id, expiresAt: g.expiresAt });
}
export function blockWork(error: unknown) {
  if (error instanceof ApiError && ([401,404,410].includes(error.status) || error.code === "IDEMPOTENCY_CONFLICT")) {
    const work = readWork(); if (work) writeWork({ ...work, blocked: true });
  }
}
let busy = false;
let bootstrap: Promise<{ expiresAt: string }> | null = null;
export async function createWork(body?: GuestRequest, signal?: AbortSignal): Promise<Generation> {
  if (busy) throw new ApiError("BUSY", "Запрос уже выполняется.");
  busy = true;
  try {
    let work = readWork();
    if (body && work) throw new ApiError("CURRENT_WORK_EXISTS", "Сначала откройте текущую работу или явно выберите новую.");
    if (!work) {
      if (!body) throw new ApiError("GUEST_ACCESS_EXPIRED", "Срок текущей попытки истёк.");
      bootstrap ??= api.guestSession().finally(() => { bootstrap = null; });
      const { expiresAt } = await bootstrap;
      work = { body, expiresAt }; writeWork(work);
    }
    if (work.blocked) throw new ApiError("GUEST_ACCESS_REQUIRED", "Доступ утрачен.");
    if (Date.parse(work.expiresAt) <= Date.now()) throw new ApiError("GUEST_ACCESS_EXPIRED", "Срок текущей попытки истёк.");
    if (work.id) return (await api.guestGeneration(work.id, signal)).generation;
    // Resume never bootstraps a replacement security context or creates a new UUID.
    if (!work.submitted) {
      await api.guestPreflight(work.body, signal);
      work = { ...work, submitted: true }; writeWork(work);
    }
    // A replay must reach create even if readiness changed after the original admission.
    const { generation } = await api.guestCreate(work.body, signal);
    rememberGeneration(generation);
    return generation;
  } catch (error) { blockWork(error); throw error; }
  finally { busy = false; }
}
// The Generate button is also the explicit action for another completed result.
// Unknown POST outcomes always keep their original UUID and body.
let starting = false;
export async function startWork(body: GuestRequest, signal?: AbortSignal): Promise<Generation> {
  if (starting || busy) throw new ApiError("BUSY", "Запрос уже выполняется.");
  starting = true;
  try {
    const current = readWork();
    if (current?.id && !current.blocked) {
      const { generation } = await api.guestGeneration(current.id, signal);
      if (["queued", "processing"].includes(generation.status)) return generation;
    } else if (current?.submitted && !current.blocked) {
      const recipe = (request: GuestRequest) => JSON.stringify(request.mode === "flat" ? { mode: request.mode, selections: request.selections } : { mode: request.mode, ai: request.ai });
      if (recipe(current.body) !== recipe(body)) throw new ApiError("PENDING_WORK", "Сначала завершите предыдущий запрос с прежними настройками.");
      return await createWork(undefined, signal);
    }
    if (current) forgetWork();
    return await createWork(body, signal);
  } finally { starting = false; }
}
export function expiryText(value: string) {
  return new Date(value).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}
