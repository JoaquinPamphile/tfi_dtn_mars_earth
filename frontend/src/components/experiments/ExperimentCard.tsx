import { Link } from "react-router-dom";
import { abbreviateHash, presentationLabel, presentationTone, type ExperimentSummary } from "../../domain";
import { StatusBadge } from "../common/StatusBadge";
import styles from "./ExperimentCard.module.css";

function etiquetaCorridas(cantidad: number): string {
  return cantidad === 1 ? "1 corrida" : `${cantidad} corridas`;
}

export function ExperimentCard({ experiment }: { experiment: ExperimentSummary }) {
  const identidad = experiment.identity;

  return (
    <article className={styles.card}>
      <div className={styles.head}>
        <h2 className={styles.code}>{experiment.code}</h2>
        <StatusBadge tone={presentationTone(experiment.presentation)}>
          {presentationLabel(experiment.presentation)}
        </StatusBadge>
      </div>
      <p className={styles.name}>{experiment.name}</p>
      <p className={styles.objective}>{experiment.objective}</p>
      {experiment.scopeNote ? <p className={styles.scope}>{experiment.scopeNote}</p> : null}
      <p className={styles.runs}>{etiquetaCorridas(experiment.runCount)}</p>
      {identidad ? (
        <dl className={styles.identity}>
          <div>
            <dt>Artefacto</dt>
            <dd title={identidad.campaignIdentity}>{abbreviateHash(identidad.campaignIdentity)}</dd>
          </div>
          <div>
            <dt>campaign_id</dt>
            <dd>{identidad.campaignId}</dd>
          </div>
        </dl>
      ) : null}
      <div className={styles.actions}>
        <Link className={styles.explore} to={`/experimentos/${experiment.id}`}>
          Explorar
        </Link>
      </div>
    </article>
  );
}
