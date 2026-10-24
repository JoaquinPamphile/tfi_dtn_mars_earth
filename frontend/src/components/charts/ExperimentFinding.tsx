import styles from "./charts.module.css";

export function ExperimentFinding({ title, note }: { title: string; note?: string }) {
  return (
    <blockquote className={styles.finding}>
      <p className={styles.findingTitle}>{title}</p>
      {note ? <p className={styles.findingNote}>{note}</p> : null}
    </blockquote>
  );
}
