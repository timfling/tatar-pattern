"use client";

import { useEffect, useId, useRef, useState } from "react";
import styles from "./ai-unavailable.module.css";

export function AiUnavailable() {
  const [visible, setVisible] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const explanationId = useId();
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  function explain() {
    if (timer.current) clearTimeout(timer.current);
    setVisible(true);
    timer.current = setTimeout(() => { setVisible(false); timer.current = null; }, 6000);
  }
  return <div className={styles.notice}>
    <p className={styles.label} role="status"><svg aria-hidden="true" viewBox="0 0 16 16"><path d="m1 1 14 14M15 1 1 15" /></svg><span>ИИ-генерация временно недоступна</span></p>
    <button type="button" className={styles.help} aria-label="Почему ИИ-генерация недоступна?" aria-controls={explanationId} aria-expanded={visible} onClick={explain}>?</button>
    <p id={explanationId} className={styles.explanation} data-visible={visible} aria-hidden={!visible} role="status">ИИ-генерация требует платных вычислительных ресурсов и пока приостановлена. Сейчас можно создавать узоры в параметрическом режиме.</p>
  </div>;
}
