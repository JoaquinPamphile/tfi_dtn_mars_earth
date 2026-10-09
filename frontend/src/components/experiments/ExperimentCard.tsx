import type { ExperimentSummary } from "../../domain";
import { StatusBadge } from "../common/StatusBadge";
import styles from "./ExperimentCard.module.css";

const ETIQUETA_ESTADO = {
  EVIDENCE_VALID: "EVIDENCE VALID",
} as const;

function etiquetaCorridas(cantidad: number): string {
  return cantidad === 1 ? "1 corrida" : `${cantidad} corridas`;
}

export function ExperimentCard({ experiment }: { experiment: ExperimentSummary }) {
  const { family } = experiment;
  const ayudaId = `${family.id}-explorar-ayuda`;

  return (
    <article className={styles.card}>
      <div className={styles.head}>
        <h2 className={styles.code}>{family.code}</h2>
        <StatusBadge tone="valid">{ETIQUETA_ESTADO[family.status]}</StatusBadge>
      </div>
      <p className={styles.name}>{family.name}</p>
      <p className={styles.objective}>{family.objective}</p>
      {family.scopeNote ? <p className={styles.scope}>{family.scopeNote}</p> : null}
      <p className={styles.runs}>{etiquetaCorridas(family.runCount)}</p>
      <div className={styles.actions}>
        <button type="button" className={styles.explore} disabled aria-describedby={ayudaId}>
          Explorar
        </button>
        <p id={ayudaId} className={styles.hint}>
          El detalle de corridas llega en V0.1.
        </p>
      </div>
    </article>
  );
}
