import styles from "./FlowArrow.module.css";

export function FlowArrow({
  direction = "forward",
  size = "default",
}: {
  direction?: "forward" | "back";
  size?: "default" | "stage";
}) {
  const clase = size === "stage" ? `${styles.arrow} ${styles.stage}` : styles.arrow;
  return (
    <span className={clase} data-direction={direction} aria-hidden="true">
      <span className={styles.line} />
      <span className={styles.head} />
    </span>
  );
}
