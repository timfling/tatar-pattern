import { ApiError, type AiBaseCatalog, type AiGenerateRequest, type OrnamentStyle } from "./api";

export const ORNAMENT_STYLES = {
  graphic: { label: "Графический стиль", description: "Чёткие контуры и ровные цветовые заливки" },
  textured: { label: "Фактурный стиль", description: "Декоративная поверхность и мягкий рельеф. Детали композиции могут изменяться" },
} as const;
const REASONS: Record<string, string> = {
  AI_DISABLED: "AI-сервис пока выключен",
  AI_PROVIDER_UNVERIFIED: "Подключение GPU ещё не подтверждено",
  AI_PROFILE_NOT_RELEASED: "Оформление этой основы ещё не готово к запуску",
  MATERIAL_TRANSFER_NOT_AUTHORIZED: "Передача материалов сервису ещё не разрешена",
  AI_PROVIDER_UNCONFIGURED: "GPU-сервис ещё не подключён",
};
export function unavailableText(reasons: string[] = []) {
  return REASONS[reasons[0]] ?? "Эта связка пока недоступна";
}
// Explicit projection: old selections/prompt and technical parameters never enter AI JSON.
export function aiRequest(catalog: AiBaseCatalog | null, baseId: string | null, style: OrnamentStyle | null, seed: number, requestId: string, projectId?: string): AiGenerateRequest {
  const base = catalog?.bases.find(item => item.id === baseId);
  const profile = base?.styles.find(item => item.id === style);
  if (!base || !profile) throw new ApiError("AI_SELECTION_REQUIRED", "Выберите основу и стиль орнамента.");
  if (!profile.available || !profile.profileVersion) throw new ApiError("AI_UNAVAILABLE", unavailableText(profile.unavailableReasons));
  if (!Number.isInteger(seed) || seed < 0 || seed > 2147483647) throw new ApiError("AI_SEED_INVALID", "Не удалось подготовить вариант. Выберите новый вариант.");
  return { mode: "ai", ai: { baseId: base.id, ornamentStyle: profile.id, profileVersion: profile.profileVersion }, seed, requestId, ...(projectId ? { projectId } : {}) };
}
export function randomSeed() { return crypto.getRandomValues(new Uint32Array(1))[0] & 0x7fffffff; }
