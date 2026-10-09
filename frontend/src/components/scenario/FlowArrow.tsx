import styles from "./FlowArrow.module.css";

export function FlowArrow({
  direction = "forward",
}: {
  direction?: "forward" | "back";
}) {
  return (
    <span className={styles.arrow} data-direction={direction} aria-hidden="true">
      <span className={styles.line} />
      <span className={styles.head} />
    </span>
  );
}
