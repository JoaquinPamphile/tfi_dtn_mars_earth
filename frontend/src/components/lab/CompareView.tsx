import type { ExperimentDetail } from "../../domain";
import {
  GROUP_LABEL,
  GROUP_ORDER,
  LAB_METRICS,
  loadLabel,
  presentStored,
  storedNumber,
  strategyLabel,
  type LabMetricDef,
  type LabRun,
} from "../../domain/lab";
import { HashValue } from "../experiments/HashValue";
import styles from "./lab.module.css";

export function CompareView({ detail, runs }: { detail: ExperimentDetail; runs: readonly LabRun[] }) {
  const first = runs[0];
  return (
    <div className={styles.compare}>
      <p className={styles.note}>
        {detail.code}. Las flechas comparan conteos con la primera corrida elegida ({first?.label}). No
        son una métrica nueva.
      </p>
      <section className={styles.card}>
        <h2>Configuración</h2>
        <CompareTable
          runs={runs}
          rows={[
            { label: "Estrategia", text: (run) => strategyLabel(run.config.strategyType, run.config.batchSizeEvents) },
            { label: "Batch", text: (run) => (run.config.batchSizeEvents === null ? "null" : String(run.config.batchSizeEvents)) },
            { label: "Carga ofrecida", text: (run) => loadLabel(run.config.offeredLoadFraction) },
            { label: "Política", text: (run) => run.config.recoveryPolicy },
            { label: "Falla", text: (run) => (run.config.failure.enabled ? "on" : "off") },
            { label: "Secuencia", text: (run) => run.config.failure.sequences.join(", ") || "—" },
            { label: "Semilla", text: (run) => String(run.config.seed) },
            { label: "Escenario", text: (run) => run.config.scenarioId },
            { label: "Stop policy", text: (run) => run.config.stopPolicy },
          ]}
        />
      </section>
      {GROUP_ORDER.filter((group) => group !== "identidad").map((group) => (
        <section key={group} className={styles.card}>
          <h2>{GROUP_LABEL[group]}</h2>
          {LAB_METRICS.filter((item) => item.group === group && item.kind !== "text").map((item) => (
            <MetricCompare key={item.id} runs={runs} def={item} />
          ))}
        </section>
      ))}
      <section className={styles.card}>
        <h2>Hashes</h2>
        <div className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Campo</th>
                {runs.map((run) => (
                  <th key={run.uiReference} scope="col">
                    {run.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <HashRow label="configuration_hash" runs={runs} pick={(run) => run.configurationHash} />
              <HashRow label="dataset_fingerprint" runs={runs} pick={(run) => run.datasetFingerprint} />
              <HashRow label="execution_identity" runs={runs} pick={(run) => run.executionIdentity} />
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function CompareTable({
  runs,
  rows,
}: {
  runs: readonly LabRun[];
  rows: readonly { label: string; text: (run: LabRun) => string }[];
}) {
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Campo</th>
            {runs.map((run) => (
              <th key={run.uiReference} scope="col">
                {run.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              {runs.map((run) => (
                <td key={run.uiReference}>{row.text(run)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricCompare({ runs, def }: { runs: readonly LabRun[]; def: LabMetricDef }) {
  const numbers = runs.map((run) => storedNumber(run, def.id));
  const max = Math.max(0, ...numbers.flatMap((value) => (value === null ? [] : [Math.abs(value)])));
  const baseline = numbers[0] ?? null;
  const hasValue = runs.some((run) => {
    const item = run.metrics[def.id];
    return item?.status === "stored" && item.value !== null;
  });
  const keepNull =
    def.id === "time_to_convergence_seconds" || def.id === "converged_at_sim";
  if (!hasValue && !keepNull) {
    return null;
  }
  return (
    <div className={styles.compareRow}>
      <div>
        <strong>{def.name}</strong>
        <div className={styles.help}>{def.path}</div>
      </div>
      {runs.map((run, index) => {
        const shown = presentStored(def, run.metrics[def.id]);
        const value = numbers[index] ?? null;
        const mark = def.kind === "count" && index > 0 ? readingMark(baseline, value) : "";
        const width = value === null || max === 0 ? 0 : (Math.abs(value) / max) * 100;
        return (
          <div key={run.uiReference}>
            <div title={shown.title}>
              {shown.text} {mark ? <span className={styles.arrow}>{mark}</span> : null}
            </div>
            {def.kind === "count" || def.kind === "bytes" || def.kind === "ratio" ? (
              <div className={styles.barTrack} aria-hidden="true">
                <div className={styles.barFill} style={{ width: `${width}%` }} />
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function readingMark(baseline: number | null, value: number | null): string {
  if (baseline === null || value === null || baseline === value) {
    return "";
  }
  return value > baseline ? "↑" : "↓";
}

function HashRow({
  label,
  runs,
  pick,
}: {
  label: string;
  runs: readonly LabRun[];
  pick: (run: LabRun) => string;
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      {runs.map((run) => (
        <td key={run.uiReference}>
          <HashValue value={pick(run)} label={label} />
        </td>
      ))}
    </tr>
  );
}
