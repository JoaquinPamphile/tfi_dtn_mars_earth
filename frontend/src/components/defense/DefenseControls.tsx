import styles from "./DefenseControls.module.css";

export function DefenseControls({
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <>
      <button type="button" className={styles.button} onClick={onPrevious} disabled={!hasPrevious}>
        ← Anterior
      </button>
      <button type="button" className={`${styles.button} ${styles.next}`} onClick={onNext} disabled={!hasNext}>
        Siguiente →
      </button>
    </>
  );
}
