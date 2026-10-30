import { apiUrl, ApiError, type GuestGeneration, type GuestRequest } from "@/lib/api";
import { forgetRecent, markCreatedInTab, rememberRecent } from "@/lib/guest-work";

/** Параметры конструктора v3 (см. backend/app/v3, models.V3Params). */
export type V3Params = {
  composition: string; motifs: string[]; tradition: string; density: number;
  palette: string; background: string; format: string; frame: string;
};
export type V3Option = { id: string; title: string };
export type V3Composition = V3Option & { hint: string; note: string; preview: string };
export type V3Palette = V3Option & { bg: string; colors: string[]; hint: string };
export type V3Background = V3Option & { color: string | null };
export type V3Format = V3Option & { w: number; h: number };
export type V3Motif = { code: string; name: string; source: string | null; technique: string | null; categories: string[]; traditions: string[]; thumb: string };
export type V3Catalog = {
  version: string; compositions: V3Composition[]; density: (V3Option & { id: number; hint: string })[];
  traditions: V3Option[]; categories: V3Option[]; motifs: V3Motif[]; palettes: V3Palette[];
  backgrounds: V3Background[]; formats: V3Format[]; frames: V3Option[]; maxMotifs: number;
  previewPatterns: { density: string; palette: string };
};
export type V3Used = { code: string; name: string; source: string | null; technique: string | null };
export type V3Info = { composition: string; compositionId: string; note: string; tradition: string; traditionTitle: string; used: V3Used[] };
export type V3Variant = { seed: number; image: string; size: number[]; fullSize?: number[]; info: V3Info };

export const V3_DEFAULTS: V3Params = { composition: "bouquet", motifs: [], tradition: "auto", density: 2, palette: "original", background: "palette", format: "square", frame: "none" };

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), { credentials: "include", cache: "no-store", ...init, headers: init?.body ? { "Content-Type": "application/json" } : undefined });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError("NETWORK_ERROR", "Сервис недоступен. Проверьте соединение и попробуйте снова.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error?.code ?? "HTTP_ERROR", data?.error?.message ?? `Сервис вернул ошибку (${response.status}).`, response.status, data?.error?.details);
  return data as T;
}

export const v3Api = {
  catalog: (signal?: AbortSignal) => call<V3Catalog>("/api/v3/catalog", { signal }),
  variants: (params: V3Params, seeds: number[], signal?: AbortSignal) =>
    call<{ results: V3Variant[] }>("/api/v3/variants", { method: "POST", body: JSON.stringify({ params, seeds }), signal }),
};

export function v3Preview(pattern: string, values: Record<string, string | number>) {
  return apiUrl(pattern.replace(/\{(\w+)\}/g, (_, key: string) => String(values[key] ?? "")));
}

export function randomSeeds(count = 4) {
  const values = crypto.getRandomValues(new Uint32Array(count));
  return [...values].map(v => v % 2147483648);
}

/**
 * Наборы вариантов v3 для «Недавних генераций». Хранятся только в памяти вкладки (как и весь список):
 * после перезагрузки страницы исчезают. Сохранённые при экспорте файлы привязаны к своему набору,
 * поэтому повторный экспорт из истории не создаёт новую серверную работу.
 */
export type V3Session = { id: string; params: V3Params; variants: V3Variant[]; index: number; createdAt: string; saved: Record<number, GuestGeneration> };
const sessions = new Map<string, V3Session>();
const SESSION_TTL = 24 * 60 * 60 * 1000;
export function v3Session(id: string) { return sessions.get(id) ?? null; }
export function saveV3Session(params: V3Params, variants: V3Variant[]): V3Session {
  const session: V3Session = { id: `v3-${crypto.randomUUID()}`, params, variants, index: 0, createdAt: new Date().toISOString(), saved: {} };
  sessions.set(session.id, session);
  markCreatedInTab();
  syncRecent(session);
  // Память ограничена тем же числом записей, что и список «Недавние генерации».
  while (sessions.size > 20) { const old = sessions.keys().next().value!; sessions.delete(old); forgetRecent(old); }
  return session;
}
export function updateV3Session(id: string, patch: Partial<Pick<V3Session, "index" | "saved">>) {
  const session = sessions.get(id); if (!session) return;
  Object.assign(session, patch); syncRecent(session);
}
function syncRecent(s: V3Session) {
  const variant = s.variants[s.index] ?? s.variants[0];
  rememberRecent({ id: s.id, mode: "flat", createdAt: s.createdAt, expiresAt: new Date(Date.parse(s.createdAt) + SESSION_TTL).toISOString(),
    imageUrl: variant?.image ?? null, href: `/constructor?v3=${encodeURIComponent(s.id)}&from=library`,
    title: `${variant?.info.composition ?? "Параметрический узор"} · ${s.variants.length} ${s.variants.length === 1 ? "вариант" : "варианта"}` });
}

/** Запрос гостевой генерации: сохраняет выбранный вариант в полном размере (PNG/JPG/модуль). */
export function v3GuestRequest(params: V3Params, seed: number): GuestRequest {
  return {
    mode: "flat", requestId: crypto.randomUUID(), seed,
    selections: { style: "heritage", composition: "medallion", parameters: "default", motifs: [], palette: "porcelain", usage: "web", renderer: "composition-v3", v3: params },
  };
}
