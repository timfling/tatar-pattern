import type { Element } from "@/lib/api";
/** Server review family membership only; no title matching or arbitrary truncation. */
export function motifPresets(items: Element[], max: number) {
  const groups = new Map<string,Element[]>();
  for (const item of items) {
    const id = item.compositionMetadata?.compatibility?.family_id;
    if(id) groups.set(id,[...(groups.get(id) ?? []),item]);
  }
  return [...groups].map(([id,elements]) => ({ id, name: `Семейство ${id}`, text: `Группа из серверной ревизии · ${elements.length} эл. Предложение по сочетанию, без подтверждения культурной совместимости.`, elements })).filter(group => group.elements.length <= max);
}
