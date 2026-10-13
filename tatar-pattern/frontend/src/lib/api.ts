import type { ConstructorSelections } from "@/components/constructor/parameters";

export type Profile = { firstName: string; lastName: string; occupation: string; avatar: string | null };
export type User = { id: string; email: string } & Partial<Profile>;
export type Rating = "like" | "dislike" | null;
export type GenerationMode = "flat" | "ai";
export type Capabilities = {
  outputSizes?: [number, number][]; profile?: boolean; trash?: boolean;
  modes?: Partial<Record<GenerationMode, { available: boolean; verified?: boolean; reason?: string }>>;
  elementSelection?: string; scaleRange?: [number, number]; transparentPng?: boolean;
  colorModes?: string[]; usageSizes?: Record<string, [number, number]>;
  compositions?: string[]; parameters?: string[]; palettes?: string[]; styles?: Record<string, string>;
  formats?: ("png" | "jpg")[]; maxSelectedElements?: number; unsupported?: string[];
};
export type Selections = {
  style: string; composition: string; parameters: string;
  motifs: string[]; palette: string; usage: string;
  elementCodes?: string[]; scale?: number; transparentBackground?: boolean;
  outputSize?: [number, number] | null;
  backgroundColor?: string | null; colorMode?: "original" | "silhouette";
};
export type Generation = {
  mode?: GenerationMode; formats?: ("png" | "jpg")[]; finishedAt?: string | null;
  deletedAt?: string | null;
  id: string; status: "queued" | "processing" | "done" | "failed" | "error" | "cancelled";
  progress?: number; imageUrl?: string | null; title: string; createdAt: string;
  selections: Selections; prompt: string; rating: Rating; projectId: string | null;
  warnings?: { code: string; message: string }[];
  recipe?: { isFixture?: boolean; [key: string]: unknown };
  error?: { code: string; message: string } | string | null;
};
export type Project = { id: string; title: string; createdAt: string };
export type Element = { code: string; nameRu: string; motifClass: string; motifKey?: string; imageUrl: string; isFixture?: boolean; motifIdentity?: string; provenanceStatus?: string; artifactCode?: string; sourceFrame?: string; qualityAcceptance?: unknown };
export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0, public details?: unknown) {
    super(message); this.name = "ApiError";
  }
}
const origin = (process.env.NEXT_PUBLIC_API_ORIGIN ?? "").replace(/\/$/, "");
export function apiUrl(path: string) {
  if (/^https?:\/\//.test(path)) return path;
  return `${origin}${path.startsWith("/") ? path : `/${path}`}`;
}
// Injectable transport for isolated contract tests; production always uses fetch.
export function createApi(transport: typeof fetch = fetch) {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await transport(apiUrl(`/api${path}`), {
        ...init, credentials: "include", cache: "no-store",
        headers: { ...(init.method && !["GET", "HEAD"].includes(init.method) ? { "Content-Type": "application/json" } : {}), ...init.headers },
      });
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") throw error;
      throw new ApiError("NETWORK_ERROR", "Сервис недоступен. Проверьте соединение и попробуйте снова.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const e = data?.error;
      if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event("tp-session-expired"));
      throw new ApiError(e?.code ?? "HTTP_ERROR", e?.message ?? `Сервис вернул ошибку (${response.status}).`, response.status, e?.details);
    }
    if (!data) throw new ApiError("INVALID_RESPONSE", "Сервис вернул пустой ответ.");
    return data as T;
  }
  const json = (method: string, value?: unknown): RequestInit => ({ method, ...(value !== undefined ? { body: JSON.stringify(value) } : {}) });
  return {
    me: () => request<{ user: User }>("/auth/me"),
    login: (email: string, password: string) => request<{ user: User }>("/auth/login", json("POST", { email, password })),
    register: (email: string, password: string, profile?: Profile) => request<{ user: User }>("/auth/register", json("POST", { email, password, ...profile })),
    updateProfile: (profile: Profile) => request<{ user: User }>("/auth/profile", json("PATCH", profile)),
    trashGeneration: (id: string) => request<{ ok: boolean }>(`/generations/${encodeURIComponent(id)}`, json("DELETE")),
    restoreGeneration: (id: string) => request<{ generation: Generation }>(`/generations/${encodeURIComponent(id)}/restore`, json("POST")),
    trash: (offset = 0) => request<{ items: Generation[]; total: number }>(`/generations?trash=true&limit=100&offset=${offset}`),
    logout: () => request<{ ok: boolean }>("/auth/logout", json("POST")),
    elements: (signal?: AbortSignal) => request<{ items: Element[]; total?: number }>("/elements", { signal }),
    health: () => request<{ ok: boolean }>("/health"),
    capabilities: () => request<Capabilities>("/capabilities"),
    generate: (selections: Selections, prompt = "", projectId?: string, signal?: AbortSignal, mode?: GenerationMode) => request<{ generation: Generation }>("/generations", { ...json("POST", { selections, prompt, ...(mode ? { mode } : {}), ...(projectId ? { projectId } : {}) }), signal }),
    generation: (id: string, signal?: AbortSignal) => request<{ generation: Generation }>(`/generations/${encodeURIComponent(id)}`, { signal }),
    generations: (offset = 0, projectId?: string) => request<{ items: Generation[]; total: number }>(`/generations?limit=100&offset=${offset}${projectId ? `&projectId=${encodeURIComponent(projectId)}` : ""}`),
    patchGeneration: (id: string, patch: Partial<Pick<Generation, "title" | "rating" | "projectId">>) => request<{ generation: Generation }>(`/generations/${encodeURIComponent(id)}`, json("PATCH", patch)),
    projects: () => request<{ items: Project[] }>("/projects"),
    addProject: (title: string) => request<{ project: Project }>("/projects", json("POST", { title })),
    renameProject: (id: string, title: string) => request<{ project: Project }>(`/projects/${encodeURIComponent(id)}`, json("PATCH", { title })),
    deleteProject: (id: string) => request<{ ok: boolean }>(`/projects/${encodeURIComponent(id)}`, json("DELETE")),
  };
}
export const api = createApi();
export function apiMessage(error: unknown) {
  if (error instanceof ApiError && error.code === "VALIDATION_ERROR" && Array.isArray(error.details)) {
    const fields = error.details.map((d: { field?: string }) => d.field ?? "");
    if (fields.some((f) => f.includes("email"))) return "Проверьте адрес электронной почты.";
    if (fields.some((f) => f.includes("password"))) return "Пароль должен содержать от 10 до 128 символов.";
  }
  return error instanceof Error ? error.message : "Не удалось выполнить действие. Попробуйте снова.";
}
export function toApiSelections(value: ConstructorSelections): Selections {
  const keys = ["style", "composition", "parameters", "palette", "usage"] as const;
  for (const key of keys) if (typeof value[key] !== "string" || !value[key]) throw new ApiError("SELECTIONS_REQUIRED", "Настройте все параметры генерации.");
  if (!Array.isArray(value.motifs) || !value.motifs.length) throw new ApiError("MOTIFS_REQUIRED", "Выберите хотя бы один мотив.");
  return { style: value.style as string, composition: value.composition as string, parameters: value.parameters as string, palette: value.palette as string, usage: value.usage as string, motifs: value.motifs };
}
export function exportUrl(id: string, format: "png" | "jpg") {
  return apiUrl(`/api/generations/${encodeURIComponent(id)}/file?format=${format}&download=true`);
}
