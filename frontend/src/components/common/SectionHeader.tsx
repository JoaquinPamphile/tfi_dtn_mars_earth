import type { ReactNode } from "react";
import styles from "./SectionHeader.module.css";

export function SectionHeader({
  title,
  description,
  addon,
}: {
  title: string;
  description?: string;
  addon?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div>
        <h1 className={styles.title}>{title}</h1>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {addon ? <div className={styles.addon}>{addon}</div> : null}
    </header>
  );
}
