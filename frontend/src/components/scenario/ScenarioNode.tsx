import styles from "./ScenarioNode.module.css";

export function ScenarioNode({ code, role }: { code: string; role: string }) {
  return (
    <article className={styles.node}>
      <p className={styles.code}>{code}</p>
      <p className={styles.role}>{role}</p>
    </article>
  );
}
