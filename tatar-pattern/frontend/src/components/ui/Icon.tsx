import Image from "next/image";

type IconProps = {
  /** Имя файла в /public/icons без расширения. */
  name: string;
  width: number;
  height: number;
  className?: string;
};

/**
 * Иконки выгружены из Figma как есть, вместе с зашитыми цветами.
 * Если понадобится перекрашивать их по состоянию, конкретная иконка
 * переносится в инлайновый React-компонент с currentColor.
 */
export function Icon({ name, width, height, className }: IconProps) {
  return (
    <Image
      src={`/icons/${name}.svg`}
      alt=""
      width={width}
      height={height}
      className={className}
      aria-hidden
    />
  );
}
