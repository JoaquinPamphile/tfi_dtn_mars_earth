import styles from "./ScenarioNode.module.css";

export function ScenarioNode({
  code,
  role,
  size = "default",
}: {
  code: string;
  role: string;
  size?: "default" | "stage";
}) {
  const clase = size === "stage" ? `${styles.node} ${styles.stage}` : styles.node;
  return (
    <article className={clase}>
      <p className={styles.code}>{code}</p>
      <p className={styles.role}>{role}</p>
    </article>
  );
}
