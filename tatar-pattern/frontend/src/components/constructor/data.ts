export const DEFAULT_PATTERN_NAME = "Паттерн без имени";

export function formatPatternStamp(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(date.getHours())}:${pad(date.getMinutes())} — ${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()}`;
}
