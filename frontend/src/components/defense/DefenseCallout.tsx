import type { ReactNode } from "react";
import styles from "./DefenseCallout.module.css";

export function DefenseCallout({ children }: { children: ReactNode }) {
  return <blockquote className={styles.callout}>{children}</blockquote>;
}
