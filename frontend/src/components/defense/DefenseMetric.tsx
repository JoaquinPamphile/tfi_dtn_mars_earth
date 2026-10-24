import type { ReactNode } from "react";
import styles from "./DefenseMetric.module.css";

export function DefenseMetric({
  kicker,
  title,
  emphasis = false,
  children,
}: {
  kicker: string;
  title: string;
  emphasis?: boolean;
  children?: ReactNode;
}) {
  const clase = emphasis ? `${styles.metric} ${styles.emphasis}` : styles.metric;
  return (
    <article className={clase}>
      <p className={styles.kicker}>{kicker}</p>
      <h2 className={styles.title}>{title}</h2>
      {children ? <div className={styles.body}>{children}</div> : null}
    </article>
  );
}
