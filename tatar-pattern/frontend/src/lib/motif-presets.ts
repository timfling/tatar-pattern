import type { Element } from "@/lib/api";
// Group only by the server's literal form names; these labels do not assert historical symbolism.
const definitions = [
  { id: "floral", name: "Цветы и листья", text: "Мягкие растительные формы для центральных акцентов и ткани.", match: /цвет|лист|лепест|тюльпан|бутон|вет|раст|пальмет/i },
  { id: "border", name: "Линии и края", text: "Направленные формы для полос, обрамлений и краёв макета.", match: /рам|борд|полос|угол|лен|кайм/i },
  { id: "geometry", name: "Геометрический ритм", text: "Чёткие повторяющиеся формы для фонов и графических систем.", match: /ромб|круг|треуг|геометр|зуб|квадрат|розет|звезд|зигз/i },
];
export function motifPresets(items: Element[], max: number) { return definitions.map(preset => { const candidates = items.filter(item => !item.isFixture && preset.match.test(`${item.nameRu} ${item.motifClass}`)); const classes = new Set<string>(); const elements = candidates.filter(item => { if(classes.has(item.motifClass)) return false; classes.add(item.motifClass); return true; }).slice(0,Math.min(max,4)); return { ...preset, elements }; }).filter(preset => preset.elements.length > 0); }
