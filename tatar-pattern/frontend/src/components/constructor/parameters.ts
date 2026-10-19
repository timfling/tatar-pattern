import type { ParameterCardProps } from "@/components/constructor/ParameterCard";

/**
 * Условные графические режимы API v0; без искусствоведческой атрибуции.
 * Менять названия, тексты и список вариантов можно здесь,
 * не трогая само окно выбора: поведение у всех кнопок одно.
 */
export type ParameterKey =
  | "style"
  | "composition"
  | "parameters"
  | "motifs"
  | "palette"
  | "usage";

export type ParameterOption = {
  value: string;
  label: string;
  description: string;
};

export type ParameterTile = {
  key: ParameterKey;
  title: string;
  pickerTitle: string;
  confirmLabel: string;
  placeholder: string;
  /** На карточке значение в кавычках, как в макете. */
  quoted?: boolean;
  multi?: boolean;
  multiTotal?: number;
  defaultValue?: string;
  corner: ParameterCardProps["corner"];
  /** Углы в сетке 2×3 — не совпадают с десктопной 3×2. */
  mobileCorner: ParameterCardProps["mobileCorner"];
  options: ParameterOption[];
};

export const PARAMETER_TILES: ParameterTile[] = [
  {
    key: "style",
    title: "Исполнение",
    pickerTitle: "Выберите исполнение",
    confirmLabel: "Выбрать исполнение",
    placeholder: "Выберите",
    quoted: true,
    corner: "top-left",
    mobileCorner: "top-left",
    options: [
      { value: "modern", label: "Модерн", description: "Форма мотива заполняется одним цветом с чётким краем. Подходит для лаконичной графики и небольших размеров. Требует режима «Силуэт»." },
      {
        value: "porcelain-sign",
        label: "Фарфоровый знак",
        description: "Вместо сплошной заливки остаётся синий контур по краю формы. Даёт лёгкий рисунок для светлых фонов. Требует режима «Силуэт».",
      },
      { value: "heritage", label: "Наследие", description: "Сохраняет мягкость краёв исходного элемента. В режиме исходных цветов остаются его цвета; в силуэтном режиме форма окрашивается палитрой." },
      {
        value: "leather-mosaic",
        label: "Кожаная мозаика",
        description: "Цветная форма с пунктирным краем, напоминающим шов. Это цифровая графическая обработка, а не воспроизведение техники ручной кожаной мозаики.",
      },
      {
        value: "festive",
        label: "Праздничный",
        description: "Повторы чередуют несколько акцентных цветов палитры, создавая более насыщенный ритм. Работает в режиме «Силуэт».",
      },
    ],
  },
  {
    key: "composition",
    title: "Композиция",
    pickerTitle: "Выберите композицию",
    confirmLabel: "Выбрать эту композицию",
    placeholder: "Выберите",
    quoted: true,
    corner: "none",
    mobileCorner: "top-right",
    options: [
      {
        value: "medallion",
        label: "Медальон",
        description: "Мотивы располагаются вокруг общего центра, образуя розетку. Подходит для отдельного акцента на открытке, предмете или лицевой стороне упаковки.",
      },
      {
        value: "border",
        label: "Бордюр",
        description: "Мотивы повторяются в полосах. Используйте для края ткани, обрамления, этикетки или декоративной линии в макете.",
      },
      {
        value: "rapport",
        label: "Раппорт",
        description: "Повторяющийся модуль, у которого края стыкуются без разрыва. Подходит для ткани и фонов; проверьте стыки через просмотр повтора 3×3.",
      },
    ],
  },
  {
    key: "parameters",
    title: "Масштаб и ритм",
    pickerTitle: "Выберите ритм",
    confirmLabel: "Выбрать эти параметры",
    placeholder: "По умолчанию",
    defaultValue: "default",
    corner: "top-right",
    mobileCorner: "none",
    options: [
      {
        value: "default",
        label: "По умолчанию",
        description: "Сбалансированное количество повторов и свободного пространства. Удобная отправная точка: сравните с разреженным и плотным вариантом для вашего макета.",
      },
      { value: "sparse", label: "Разреженный", description: "Больше свободного пространства; размеры и интервалы пересчитываются вместе. Подходит для спокойного фона или когда каждый мотив должен хорошо читаться." },
      { value: "dense", label: "Плотный", description: "Меньше просветов, насыщеннее заполнение. Размеры и число повторов пересчитываются вместе; плотность не всегда увеличивает число мотивов." },
    ],
  },
  {
    key: "motifs",
    title: "Мотивы",
    pickerTitle: "Выберите мотивы",
    confirmLabel: "Выбрать этот мотив",
    placeholder: "Загрузка каталога",
    multi: true,
    multiTotal: 0,
    corner: "bottom-left",
    mobileCorner: "none",
    options: [],
  },
  {
    key: "palette",
    title: "Палитра",
    pickerTitle: "Выберите палитру",
    confirmLabel: "Выбрать эту палитру",
    placeholder: "Выберите",
    quoted: true,
    corner: "none",
    mobileCorner: "bottom-left",
    options: [
      {
        value: "emerald",
        label: "Казанский изумруд",
        description: "Тёмный зелёный фон и тёплые акценты. В режиме исходных цветов палитра меняет подложку; в силуэтном режиме также задаёт цвета рисунка.",
      },
      {
        value: "porcelain",
        label: "Фарфор и киноварь",
        description: "Светлая подложка с синими и красными акцентами. Хорошо читается на светлом макете. Цвет мотивов зависит от выбранного исполнения.",
      },
      {
        value: "leather",
        label: "Казанская кожа",
        description: "Тёплая коричневая подложка и светлые акценты. В исполнении «Кожаная мозаика» силуэты дополняются пунктирным контуром.",
      },
    ],
  },
  {
    key: "usage",
    title: "Применение",
    pickerTitle: "Выберите применение",
    confirmLabel: "Выбрать это применение",
    placeholder: "Выберите",
    corner: "bottom-right",
    mobileCorner: "bottom-right",
    options: [
      {
        value: "architecture",
        label: "Архитектура",
        description: "Квадратное изображение 1024 × 1024 px.",
      },
      {
        value: "textile",
        label: "Текстиль",
        description: "Квадратное изображение 1024 × 1024 px для работы с принтом.",
      },
      {
        value: "packaging",
        label: "Упаковка",
        description: "Изображение 1200 × 900 px. Формат раппорта зависит от выбора модуля или образца.",
      },
      {
        value: "interior",
        label: "Интерьер",
        description: "Изображение 1200 × 900 px для макета. Формат раппорта зависит от выбора модуля или образца.",
      },
      {
        value: "web",
        label: "Веб-дизайн",
        description: "Изображение 800 × 600 px. Формат раппорта зависит от выбора модуля или образца.",
      },
    ],
  },
];

const order: ParameterKey[] = ["composition", "motifs", "parameters", "palette", "style", "usage"];
PARAMETER_TILES.sort((a, b) => order.indexOf(a.key) - order.indexOf(b.key));
const corners = ["top-left", "none", "top-right", "bottom-left", "none", "bottom-right"] as const;
const mobileCorners = ["top-left", "top-right", "none", "none", "bottom-left", "bottom-right"] as const;
PARAMETER_TILES.forEach((tile, index) => { tile.corner = corners[index]; tile.mobileCorner = mobileCorners[index]; });

export type ParameterSelection = string | string[] | null;

export type ConstructorSelections = Record<ParameterKey, ParameterSelection>;

export function emptySelections(): ConstructorSelections {
  return {
    style: null,
    composition: null,
    parameters: "default",
    motifs: [],
    palette: null,
    usage: null,
  };
}

export function cardFromSelection(
  tile: ParameterTile,
  selection: ParameterSelection,
): ParameterCardProps {
  if (tile.multi) {
    const count = Array.isArray(selection) ? selection.length : 0;
    return {
      label: tile.title,
      value: `${count} из ${tile.multiTotal ?? 0}`,
      isSet: true,
      tone: count > 0 ? "strong" : "subtle",
      corner: tile.corner,
      mobileCorner: tile.mobileCorner,
    };
  }

  if (!selection) {
    return {
      label: tile.title,
      value: tile.placeholder,
      corner: tile.corner,
      mobileCorner: tile.mobileCorner,
    };
  }

  const option = tile.options.find((item) => item.value === selection);
  const name = option?.label ?? String(selection);
  return {
    label: tile.title,
    value: tile.quoted ? `“${name}”` : name,
    isSet: true,
    tone: "strong",
    corner: tile.corner,
    mobileCorner: tile.mobileCorner,
  };
}

export function selectionsReady(selections: ConstructorSelections): boolean {
  if (
    !selections.style ||
    !selections.composition ||
    !selections.parameters ||
    !selections.palette ||
    !selections.usage
  ) {
    return false;
  }
  return Array.isArray(selections.motifs) && selections.motifs.length > 0;
}

/** Подписи для окна «О генерации». */
export function recipeLines(
  selections: ConstructorSelections,
  prompt: string,
  tiles: ParameterTile[] = PARAMETER_TILES,
): { title: string; value: string }[] {
  const lines = tiles.map((tile) => {
    const selection = selections[tile.key];
    if (tile.multi) {
      const picked = Array.isArray(selection) ? selection : [];
      const names = picked
        .map((value) => tile.options.find((item) => item.value === value)?.label ?? value)
        .join("\n");
      return {
        title: tile.title,
        value: names || "не выбраны",
      };
    }
    if (!selection || typeof selection !== "string") {
      return { title: tile.title, value: tile.placeholder };
    }
    const name = tile.options.find((item) => item.value === selection)?.label ?? selection;
    return { title: tile.title, value: name };
  });
  lines.push({
    title: "Заметка",
    value: prompt.trim() || "Нет",
  });
  return lines;
}

export function optionIndex(tile: ParameterTile, selection: ParameterSelection): number {
  if (tile.multi) {
    const selected = Array.isArray(selection) ? selection : [];
    if (selected.length > 0) {
      const found = tile.options.findIndex((item) => item.value === selected[0]);
      if (found >= 0) return found;
    }
    return 0;
  }
  if (typeof selection === "string") {
    const found = tile.options.findIndex((item) => item.value === selection);
    if (found >= 0) return found;
  }
  if (tile.defaultValue) {
    const found = tile.options.findIndex((item) => item.value === tile.defaultValue);
    if (found >= 0) return found;
  }
  return 0;
}
