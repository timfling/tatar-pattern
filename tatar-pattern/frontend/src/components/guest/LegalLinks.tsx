import Link from "next/link";
import { HOME } from "@/content/home";
export function LegalLinks({ contact = true }: { contact?: boolean }) {
  return <nav aria-label="Документы и контакты" className="flex flex-wrap justify-center gap-3 text-sm"><Link href="/legal/terms">Правила использования</Link><Link href="/legal/privacy">Обработка данных</Link><Link href="/legal/cookies">Cookies и хранилище</Link>{contact ? <a href={`mailto:${HOME.contactEmail}`}>Связаться с нами</a> : null}</nav>;
}
export function CreateNotice() {
  return <div className="my-3 text-center text-sm"><p>Нажимая “Создать рисунок”, вы принимаете <Link className="underline" href="/legal/terms">правила использования</Link>.</p><p><Link className="underline" href="/legal/privacy">Обработка данных</Link> · Временный доступ — до срока, указанного сервером.</p><p>Локальная версия: публичные документы ещё не опубликованы.</p></div>;
}
