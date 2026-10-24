import type { ReactNode } from "react";
import styles from "./StatusBadge.module.css";

type Tone = "neutral" | "valid" | "canonical" | "readonly" | "pending";

export function StatusBadge({
  children,
  tone = "neutral",
  size = "default",
}: {
  children: ReactNode;
  tone?: Tone;
  size?: "default" | "stage";
}) {
  const clase =
    size === "stage"
      ? `${styles.badge} ${styles[tone]} ${styles.stage}`
      : `${styles.badge} ${styles[tone]}`;
  return <span className={clase}>{children}</span>;
}
