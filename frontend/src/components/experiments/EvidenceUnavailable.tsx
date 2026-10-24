import type { EvidenceAccessError } from "../../adapters";
import styles from "./EvidenceUnavailable.module.css";

export function EvidenceUnavailable({ error }: { error: EvidenceAccessError }) {
  return (
    <section className={styles.panel} role="alert">
      <h2 className={styles.title}>Evidence no disponible</h2>
      <p className={styles.lead}>
        Hace falta el artefacto RC1 para mostrar esta sección.
      </p>
      <p className={styles.code}>{error.name}</p>
      <p>{error.message}</p>
    </section>
  );
}
