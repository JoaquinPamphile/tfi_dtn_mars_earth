import { useState } from "react";
import { runJsonDocument } from "../../domain/lab";
import styles from "./lab.module.css";

export function JsonBlock({ source }: { source: Record<string, unknown> }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const text = open ? JSON.stringify(runJsonDocument(source), null, 2) : "";

  async function copiar() {
    const payload = JSON.stringify(runJsonDocument(source), null, 2);
    try {
      await navigator.clipboard.writeText(payload);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className={styles.stack}>
      <div className={styles.actions}>
        <button type="button" className={styles.ghost} aria-expanded={open} onClick={() => setOpen((value) => !value)}>
          {open ? "Ocultar JSON de corrida" : "Ver JSON de corrida"}
        </button>
        <button type="button" className={styles.ghost} onClick={() => void copiar()}>
          {copied ? "Copiado" : "Copiar JSON"}
        </button>
      </div>
      <p className={styles.note}>
        Lectura sola del manifiesto de esta corrida, incluida metrics. No es el paquete completo.
      </p>
      {open ? <pre className={styles.json}>{text}</pre> : null}
    </div>
  );
}
