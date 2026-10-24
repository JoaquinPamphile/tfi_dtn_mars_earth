import { formatCount } from "../../domain/metricFormat";
import { loadLabel, storedNumber, strategyLabel, type LabRun } from "../../domain/lab";
import { ValuesTable } from "../charts/ValuesTable";
import styles from "./lab.module.css";

export function BacklogChart({ runs }: { runs: readonly LabRun[] }) {
  const groups = groupByStrategy(runs);
  return (
    <div className={styles.stack}>
      <p className={styles.note}>
        M es metrics.not_persisted_on_earth. U es metrics.persisted_on_earth_but_unconfirmed. El total
        etiquetado es metrics.backlog. La barra se apila solo cuando M + U coincide con ese backlog.
      </p>
      {groups.map(([label, group]) => {
        const ok = group.every(stackAgrees);
        const max = Math.max(1, ...group.map((run) => storedNumber(run, "backlog") ?? 0));
        return (
          <section key={label} className={styles.card}>
            <h3>Backlog · {label}</h3>
            {ok ? (
              <div className={styles.stack}>
                {group.map((run) => {
                  const missing = storedNumber(run, "not_persisted_on_earth") ?? 0;
                  const unconfirmed = storedNumber(run, "persisted_on_earth_but_unconfirmed") ?? 0;
                  const backlog = storedNumber(run, "backlog") ?? 0;
                  return (
                    <div key={run.uiReference}>
                      <div className={styles.note}>
                        {loadLabel(run.config.offeredLoadFraction)} · backlog {formatCount(backlog)}
                      </div>
                      <div
                        className={styles.barTrack}
                        style={{ height: 18 }}
                        title={`M ${formatCount(missing)} · U ${formatCount(unconfirmed)} · backlog ${formatCount(backlog)}`}
                      >
                        <div
                          className={styles.barFill}
                          style={{
                            width: `${(backlog / max) * 100}%`,
                            display: "flex",
                            background: "transparent",
                          }}
                        >
                          <span
                            style={{
                              width: backlog === 0 ? "0%" : `${(missing / backlog) * 100}%`,
                              background: "var(--chart-series-1)",
                            }}
                          />
                          <span
                            style={{
                              width: backlog === 0 ? "0%" : `${(unconfirmed / backlog) * 100}%`,
                              background: "var(--chart-series-2)",
                            }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
                <ul className={styles.levels}>
                  <li>M · no persistido en Tierra</li>
                  <li>U · persistido sin confirmar</li>
                </ul>
              </div>
            ) : (
              <p className={styles.warn}>
                M + U no coincide con el backlog almacenado en todas las corridas de {label}. No se
                dibuja una suma.
              </p>
            )}
            <ValuesTable
              caption={`M, U y backlog almacenados · ${label}`}
              columns={[
                { key: "load", label: "Carga" },
                { key: "m", label: "M" },
                { key: "u", label: "U" },
                { key: "backlog", label: "Backlog" },
              ]}
              rows={group.map((run) => ({
                key: run.uiReference,
                cells: {
                  load: { text: loadLabel(run.config.offeredLoadFraction) },
                  m: cell(run, "not_persisted_on_earth"),
                  u: cell(run, "persisted_on_earth_but_unconfirmed"),
                  backlog: cell(run, "backlog"),
                },
              }))}
            />
          </section>
        );
      })}
    </div>
  );
}

function cell(run: LabRun, id: string): { text: string; title: string } {
  const value = storedNumber(run, id);
  if (value === null) {
    return { text: "No disponible", title: id };
  }
  return { text: formatCount(value), title: String(value) };
}

function stackAgrees(run: LabRun): boolean {
  const missing = storedNumber(run, "not_persisted_on_earth");
  const unconfirmed = storedNumber(run, "persisted_on_earth_but_unconfirmed");
  const backlog = storedNumber(run, "backlog");
  if (missing === null || unconfirmed === null || backlog === null) {
    return false;
  }
  return missing + unconfirmed === backlog;
}

function groupByStrategy(runs: readonly LabRun[]): [string, LabRun[]][] {
  const groups = new Map<string, LabRun[]>();
  for (const run of runs) {
    const label = strategyLabel(run.config.strategyType, run.config.batchSizeEvents);
    groups.set(label, [...(groups.get(label) ?? []), run]);
  }
  return [...groups.entries()];
}
