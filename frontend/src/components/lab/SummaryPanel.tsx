import type { ExperimentDetail } from "../../domain";
import { loadLabel, strategyLabel } from "../../domain/lab";
import styles from "./lab.module.css";

export function SummaryPanel({ detail }: { detail: ExperimentDetail }) {
  const lab = detail.lab;
  const identidad = detail.identity;
  if (!lab || !identidad) {
    return null;
  }
  const corridas = detail.runCount === 1 ? "1 corrida" : `${detail.runCount} corridas`;

  return (
    <div className={styles.stack}>
      <section className={styles.card}>
        <h2>Pregunta</h2>
        <p className={styles.note}>{detail.objective}</p>
        <p className={styles.note}>{detail.description}</p>
      </section>
      <section className={styles.card}>
        <h2>Identidad</h2>
        <dl className={styles.meta}>
          <Item label="campaign id" value={identidad.campaignId} mono />
          <Item label="artifact id" value={identidad.campaignIdentity} mono />
          <Item label="family" value={identidad.family} />
          <Item label="role" value={identidad.role} />
          <Item label="release" value={identidad.softwareVersion} />
          <Item label="source revision" value={identidad.sourceRevision} mono />
          <Item label="estado de campaña" value={detail.campaignStatus ?? "—"} />
          <Item label="corridas" value={corridas} />
          <Item label="fuente lógica" value={detail.locator.logicalPath} mono />
        </dl>
      </section>
      <section className={styles.card}>
        <h2>Diseño</h2>
        <div className={styles.factors}>
          {lab.design.factors.map((factor) => (
            <div key={factor.name} className={styles.factor}>
              <h3>Factor: {factor.name}</h3>
              <ul className={styles.levels}>
                {factor.levels.map((level) => (
                  <li key={level}>{level}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        {lab.design.note ? <p className={styles.note}>{lab.design.note}</p> : null}
        {lab.design.controls.length > 0 ? (
          <>
            <h3>Controles comunes</h3>
            <dl className={styles.meta}>
              {lab.design.controls.map((control) => (
                <Item key={control.name} label={control.name} value={control.value} />
              ))}
            </dl>
          </>
        ) : null}
        <p className={styles.help}>
          Los niveles salen de los campos almacenados en las {detail.runCount} corridas. Un control
          aparece aquí solo cuando es el mismo en todas.
        </p>
      </section>
      <section className={styles.card}>
        <h2>Tratamientos</h2>
        <ul className={styles.levels}>
          {lab.runs.map((run) => (
            <li key={run.uiReference}>
              {run.label}
              {" · "}
              {strategyLabel(run.config.strategyType, run.config.batchSizeEvents)}
              {run.config.offeredLoadFraction !== null
                ? ` · ${loadLabel(run.config.offeredLoadFraction)}`
                : ""}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function Item({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? styles.mono : undefined}>{value}</dd>
    </div>
  );
}
