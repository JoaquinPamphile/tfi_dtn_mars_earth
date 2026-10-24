import styles from "./DefenseProgress.module.css";

export function DefenseProgress({ current, total }: { current: number; total: number }) {
  const ancho = total > 0 ? (current / total) * 100 : 0;
  return (
    <div
      className={styles.track}
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={current}
      aria-label="Progreso de la defensa"
      aria-valuetext={`Etapa ${current} de ${total}`}
    >
      <div className={styles.fill} style={{ width: `${ancho}%` }} />
    </div>
  );
}
