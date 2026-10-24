import { useState } from "react";
import { abbreviateHash } from "../../domain";
import styles from "./HashValue.module.css";

export function HashValue({
  value,
  label,
  variant = "short",
}: {
  value: string;
  label: string;
  variant?: "short" | "full";
}) {
  const [copied, setCopied] = useState(false);

  async function copiar() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }

  return (
    <span className={styles.hash}>
      <code title={value}>{variant === "full" ? value : abbreviateHash(value)}</code>
      <button type="button" className={styles.copy} onClick={() => void copiar()}>
        {copied ? "Copiado" : "Copiar"}
        <span className="srOnly"> {label}</span>
      </button>
    </span>
  );
}
