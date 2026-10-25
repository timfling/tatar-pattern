import Link from "next/link";
import { LegalLinks } from "./LegalLinks";
// Only approved immutable editions may be added here. Draft legal source files are never served.
export function LegalPage({ title }: { title: string }) {
  return <main className="studio-page"><article className="studio-article"><Link href="/">← На главную</Link><h1>{title}</h1><p>Документ ещё не опубликован. Публичный выпуск сервиса готовится.</p><LegalLinks /></article></main>;
}
