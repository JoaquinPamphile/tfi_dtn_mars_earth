import type { ExperimentDetail, ScientificRelease } from "../../domain";
import { HashValue } from "../experiments/HashValue";
import styles from "./lab.module.css";

export function ReproPanel({
  detail,
  release,
}: {
  detail: ExperimentDetail;
  release: ScientificRelease;
}) {
  const lab = detail.lab;
  const identidad = detail.identity;
  if (!lab || !identidad) {
    return null;
  }
  const scenario = shared(lab.runs.map((run) => run.config.scenarioId));
  const seed = shared(lab.runs.map((run) => String(run.config.seed)));
  const stop = shared(lab.runs.map((run) => run.config.stopPolicy));
  const fingerprint = shared(lab.runs.map((run) => run.datasetFingerprint));
  const execution = shared(lab.runs.map((run) => run.executionIdentity));

  return (
    <div className={styles.stack}>
      <section className={styles.card}>
        <h2>Identidad reproducible</h2>
        <dl className={styles.meta}>
          <Item label="release" value={release.version} />
          <Item label="software_version" value={identidad.softwareVersion} mono />
          <Item label="source_revision" value={identidad.sourceRevision} mono />
          <Item label="source_state" value={lab.sourceState} />
          <Item label="scenario id" value={scenario ?? "varía entre corridas"} mono />
          <Item label="seed" value={seed ?? "varía entre corridas"} />
          <Item label="stop policy" value={stop ?? "varía entre corridas"} mono />
          <Item label="campaign identity" value={identidad.campaignIdentity} hash />
          <Item label="dataset fingerprint" value={fingerprint ?? "varía entre corridas"} hash={fingerprint !== null} />
          <Item label="execution identity" value={execution ?? "varía entre corridas"} hash={execution !== null} />
        </dl>
        <p className={styles.help}>
          execution_identity identifica una combinación reproducible, pero no necesariamente una fila
          única de campaign.
        </p>
        <p className={styles.warn}>
          Los comandos literales históricos no forman parte de la evidence recuperada por el frontend.
        </p>
      </section>
      <section className={styles.card}>
        <h2>Qué entra en cada identidad</h2>
        <p className={styles.note}>Campos declarados en reproducibility del paquete.</p>
        <dl className={styles.meta}>
          <Item label="dataset_identity" value={lab.datasetIdentityInputs.join(", ")} mono />
          <Item label="execution_identity" value={lab.executionIdentityInputs.join(", ")} mono />
          <Item label="dataset_fingerprint" value={lab.datasetFingerprintFields.join(", ")} mono />
          <Item label="hash" value={lab.hashAlgorithm} />
          <Item
            label="reloj de pared en la identidad"
            value={lab.wallClockInIdentity ? "sí" : "no"}
          />
          <Item
            label="trace_level es factor científico"
            value={lab.traceLevelIsFactor ? "sí" : "no"}
          />
        </dl>
        <h3>Nota almacenada</h3>
        <p className={styles.note}>{lab.reproNote}</p>
      </section>
      {fingerprint === null || execution === null ? (
        <section className={styles.card}>
          <h2>Por corrida</h2>
          <div className={styles.scroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Corrida</th>
                  <th scope="col">execution_identity</th>
                  <th scope="col">configuration_hash</th>
                  <th scope="col">dataset_fingerprint</th>
                </tr>
              </thead>
              <tbody>
                {lab.runs.map((run) => (
                  <tr key={run.uiReference}>
                    <th scope="row">{run.label}</th>
                    <td>
                      <HashValue value={run.executionIdentity} label="execution identity" />
                    </td>
                    <td>
                      <HashValue value={run.configurationHash} label="configuration hash" />
                    </td>
                    <td>
                      <HashValue value={run.datasetFingerprint} label="dataset fingerprint" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function shared(values: string[]): string | null {
  if (values.length === 0 || values.some((item) => item !== values[0])) {
    return null;
  }
  return values[0];
}

function Item({
  label,
  value,
  mono,
  hash,
}: {
  label: string;
  value: string;
  mono?: boolean;
  hash?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? styles.mono : undefined}>
        {hash ? <HashValue value={value} label={label} variant="full" /> : value}
      </dd>
    </div>
  );
}
