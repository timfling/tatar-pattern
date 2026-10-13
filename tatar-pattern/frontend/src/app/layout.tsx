import type { Metadata, Viewport } from "next";
import {
  Raleway,
  Playfair_Display,
  Instrument_Sans,
  Cormorant_Garamond,
} from "next/font/google";
import "./globals.css";

const raleway = Raleway({
  variable: "--font-raleway",
  subsets: ["latin", "cyrillic"],
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin", "cyrillic"],
});

// В макетах — подписи кнопок конструктора. Кириллицы у шрифта нет,
// поэтому используется только для латиницы (напр. «Pattern Lab 01»).
const instrument = Instrument_Sans({
  variable: "--font-instrument",
  subsets: ["latin"],
});

const cormorant = Cormorant_Garamond({
  variable: "--font-cormorant",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "ТАТАР ПАТТЕРН ЛАБ",
  description:
    "Параметрический конструктор узоров на основе татарских орнаментов. Создавайте композиции, сохраняйте результаты и экспортируйте PNG и JPG.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ru"
      className={`${raleway.variable} ${playfair.variable} ${instrument.variable} ${cormorant.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
