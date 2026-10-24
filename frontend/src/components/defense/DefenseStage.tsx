import type { ReactNode } from "react";
import styles from "./DefenseStage.module.css";

export function DefenseStage({
  presenting,
  label,
  stageRef,
  children,
}: {
  presenting: boolean;
  label: string;
  stageRef: (node: HTMLElement | null) => void;
  children: ReactNode;
}) {
  const clase = presenting ? `${styles.stage} ${styles.presenting}` : styles.stage;
  return (
    <section ref={stageRef} className={clase} aria-label={label}>
      {children}
    </section>
  );
}
