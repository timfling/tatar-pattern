import { LegalBack } from "./LegalBack";
import { LegalLinks } from "./LegalLinks";
import styles from "./legal.module.css";

export function LegalPage({ title, children }: { title: string; children: React.ReactNode }) {
  return <main className={`studio-page ${styles.page}`}><article className={`studio-article ${styles.article}`}><LegalBack /><h1>{title}</h1>{children}<footer><LegalLinks /></footer></article></main>;
}
