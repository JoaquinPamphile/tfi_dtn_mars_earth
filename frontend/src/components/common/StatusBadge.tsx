import type { ReactNode } from "react";
import styles from "./StatusBadge.module.css";

type Tone = "neutral" | "valid" | "readonly" | "pending";

export function StatusBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>;
}
