import type { ReactNode } from "react";
import {
  formatBatch,
  formatFailure,
  formatLoad,
  formatOptional,
  formatSequences,
  type RunSummary,
} from "../../domain";
import { HashValue } from "./HashValue";
import styles from "./RunTable.module.css";

interface RunColumn {
  id: string;
  header: string;
  render: (run: RunSummary) => ReactNode;
}

const COLUMNAS: Record<string, RunColumn[]> = {
  e1: [
    { id: "run", header: "Run", render: (run) => run.label },
    { id: "strategy", header: "Strategy", render: (run) => formatOptional(run.strategyType) },
    { id: "batch", header: "Batch", render: (run) => formatBatch(run.batchSizeEvents) },
    { id: "seed", header: "Seed", render: (run) => formatOptional(run.seed) },
    {
      id: "fingerprint",
      header: "Dataset fingerprint",
      render: (run) => hashCell(run.datasetFingerprint, "dataset fingerprint"),
    },
    {
      id: "hash",
      header: "Configuration hash",
      render: (run) => hashCell(run.configurationHash, "configuration hash"),
    },
  ],
  e2: [
    { id: "run", header: "Run", render: (run) => run.label },
    { id: "load", header: "Offered load", render: (run) => formatLoad(run.offeredLoadFraction) },
    { id: "strategy", header: "Strategy", render: (run) => formatOptional(run.strategyType) },
    { id: "batch", header: "Batch", render: (run) => formatBatch(run.batchSizeEvents) },
    { id: "seed", header: "Seed", render: (run) => formatOptional(run.seed) },
    {
      id: "fingerprint",
      header: "Dataset fingerprint",
      render: (run) => hashCell(run.datasetFingerprint, "dataset fingerprint"),
    },
    {
      id: "hash",
      header: "Configuration hash",
      render: (run) => hashCell(run.configurationHash, "configuration hash"),
    },
  ],
  e3: [
    { id: "cell", header: "Celda", render: (run) => run.label },
    { id: "recovery", header: "Recovery", render: (run) => formatOptional(run.recoveryPolicy) },
    { id: "failure", header: "Failure", render: (run) => formatFailure(run.failureEnabled) },
    {
      id: "sequence",
      header: "Target sequence",
      render: (run) => formatSequences(run.targetSequences),
    },
    { id: "seed", header: "Seed", render: (run) => formatOptional(run.seed) },
    {
      id: "hash",
      header: "Configuration hash",
      render: (run) => hashCell(run.configurationHash, "configuration hash"),
    },
  ],
  "e3-sensitivity": [
    { id: "run", header: "Run", render: (run) => run.label },
    {
      id: "sequence",
      header: "Target sequence",
      render: (run) => formatSequences(run.targetSequences),
    },
    {
      id: "direction",
      header: "Sender / receiver",
      render: (run) => formatOptional(run.recoveryPolicy),
    },
    { id: "failure", header: "Failure", render: (run) => formatFailure(run.failureEnabled) },
    { id: "seed", header: "Seed", render: (run) => formatOptional(run.seed) },
    {
      id: "hash",
      header: "Configuration hash",
      render: (run) => hashCell(run.configurationHash, "configuration hash"),
    },
  ],
};

export function RunTable({
  experimentId,
  runs,
}: {
  experimentId: string;
  runs: RunSummary[];
}) {
  const columns = COLUMNAS[experimentId];
  if (!columns) {
    return <p>Esta familia no tiene columnas de corrida definidas.</p>;
  }

  return (
    <div className={styles.wrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.id} scope="col">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id} title={tituloCorrida(run)}>
              {columns.map((column) => (
                <td key={column.id} data-label={column.header}>
                  {column.render(run)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function hashCell(value: string | null, label: string): ReactNode {
  if (!value) {
    return "—";
  }
  return <HashValue value={value} label={label} />;
}

function tituloCorrida(run: RunSummary): string {
  const ejecucion = run.executionIdentity
    ? `execution_identity ${run.executionIdentity}`
    : "sin execution_identity";
  return `Referencia de UI derivada ${run.id}. No es un UUID de corrida. ${ejecucion}.`;
}
