import styles from "./charts.module.css";

/** Lectura visual entre gráficos. No agrega una cifra que la evidence no guardó. */
export function MetricCallout({ title, note }: { title: string; note: string }) {
  return (
    <p className={styles.callout}>
      <span className={styles.calloutTitle}>{title}</span>
      <span className={styles.calloutNote}>{note}</span>
    </p>
  );
}
