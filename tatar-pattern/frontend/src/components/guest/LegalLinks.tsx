import Link from "next/link";
import { HOME } from "@/content/home";
export function LegalLinks({ contact = true }: { contact?: boolean }) {
  return <nav aria-label="Документы и контакты" className="flex flex-wrap justify-center gap-3 text-sm"><Link href="/legal/terms">Правила использования</Link><Link href="/legal/privacy">Обработка данных</Link><Link href="/legal/cookies">Cookies и хранилище</Link>{contact ? <a href={`mailto:${HOME.contactEmail}`}>Связаться с нами</a> : null}</nav>;
}
