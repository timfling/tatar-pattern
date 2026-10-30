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
  style: ["normal", "italic"],
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
  metadataBase: new URL("https://tatar-pattern.ru"),
  title: "ТАТАР ПАТТЕРН ЛАБ",
  description:
    "Параметрический конструктор узоров на основе татарских орнаментов. Создавайте композиции, сохраняйте результаты и экспортируйте PNG и JPG.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

/*
  Телефоны: интерфейс в масштабе 85% (решение владельца 30.10.2026 —
  при 100% мобильная версия выглядит крупной). Меняем initial-scale
  в meta viewport — так же работает масштаб страницы в браузере:
  пропорции сохраняются, а innerWidth, медиазапросы, координаты касаний
  и getBoundingClientRect остаются согласованными (в отличие от CSS zoom/transform).
  Телефон определяем по короткой стороне экрана < 600px (iPad mini — 744px, его не трогаем), поэтому решение
  не меняется при повороте. Планшеты и десктоп не затрагиваются.
  Next при гидрации и переходах заново вставляет свой meta viewport,
  поэтому MutationObserver поддерживает нужное значение у любого из них.
  Часть движков (WebKit) не пересчитывает svh/lvh под initial-scale:
  100lvh оказывается меньше окна. Тогда --svh = 1svh / 0.85; иначе
  переменная не задаётся и home.css берёт обычный 1svh.
*/
const MOBILE_SCALE = 0.85;
const MOBILE_VIEWPORT = `width=device-width, initial-scale=${MOBILE_SCALE}, viewport-fit=cover`;
const mobileScaleScript = `(function(){try{var s=window.screen,m=Math.min(s.width,s.height);if(!m||m>=600)return;var c=${JSON.stringify(MOBILE_VIEWPORT)},d=document.documentElement;function f(){var l=document.querySelectorAll('meta[name="viewport"]');for(var i=0;i<l.length;i++)if(l[i].getAttribute("content")!==c)l[i].setAttribute("content",c);}function u(){var p=document.createElement("div");p.style.cssText="position:absolute;visibility:hidden;width:0;height:100lvh";d.appendChild(p);var h=p.getBoundingClientRect().height;p.remove();if(h&&h<innerHeight*0.97)d.style.setProperty("--svh","calc(1svh / ${MOBILE_SCALE})");else d.style.removeProperty("--svh");}f();u();addEventListener("resize",u);new MutationObserver(f).observe(document.head,{childList:true,subtree:true,attributes:true,attributeFilter:["content"]});}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="ru"
      // Скрипт mobile-scale до гидрации задаёт style --svh на <html>.
      suppressHydrationWarning
      className={`${raleway.variable} ${playfair.variable} ${instrument.variable} ${cormorant.variable}`}
    >
      <head>
        <script id="mobile-scale" dangerouslySetInnerHTML={{ __html: mobileScaleScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
