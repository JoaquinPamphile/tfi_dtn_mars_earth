import { useLabSession } from "../../app/LabProvider";
import type { ExperimentDetail } from "../../domain";
import { loadLabel, strategyLabel, type LabRun } from "../../domain/lab";
import { CategoricalBarChart } from "../charts/CategoricalBarChart";
import { ObservedPointChart } from "../charts/ObservedPointChart";
import type { ChartSeries } from "../charts/types";
import { RecoverySensitivity } from "../defense/recovery/RecoverySensitivity";
import { HelpTip } from "./HelpTip";
import { BacklogChart } from "./BacklogChart";
import { EpisodeTable, RecoveryBoard } from "./RecoveryBoard";
import styles from "./lab.module.css";
import {
  asCount,
  asMegabytes,
  asPercent,
  categoriesOf,
  loadCategories,
  seriesFor,
  seriesOnLoads,
  showCount,
  showMb,
  showPercent,
  showSeconds,
  tickCount,
  tickMb,
  tickPercent,
  tickSeconds,
} from "./series";

export function ChartsPanel({ detail }: { detail: ExperimentDetail }) {
  const session = useLabSession();
  const runs = detail.lab?.runs ?? [];
  if (session.kind !== "ready" || runs.length === 0) {
    return <p className={styles.note}>No hay corridas para graficar.</p>;
  }

  if (detail.id === "e1") {
    return <E1Charts runs={runs} />;
  }
  if (detail.id === "e2") {
    return <E2Charts runs={runs} />;
  }
  if (detail.id === "e3") {
    const presentation = session.adapter.getE3Presentation();
    return (
      <div className={styles.charts}>
        <p className={styles.note}>Episodio oficial B/D, con los controles A/C leídos del artefacto.</p>
        {presentation?.official ? <RecoveryBoard official={presentation.official} /> : <p>No disponible en evidence</p>}
        {runs.filter((run) => run.episode).map((run) => (
          <EpisodeTable key={run.uiReference} run={run} />
        ))}
        {runs.filter((run) => !run.episode).map((run) => (
          <p key={run.uiReference} className={styles.note}>
            {run.label}: Control sin falla: 0 episodios de recuperación.
          </p>
        ))}
      </div>
    );
  }

  const presentation = session.adapter.getE3Presentation();
  return (
    <div className={styles.charts}>
      <h2>3 posiciones deterministas</h2>
      <p className={styles.note}>
        Secuencias almacenadas 1, 5000 y 9998. Sender y receiver en cada posición. Sin promedio, sin
        barras de error y sin regresión.
      </p>
      {presentation?.sensitivity ? (
        <RecoverySensitivity view={presentation.sensitivity} />
      ) : (
        <p>No disponible en evidence</p>
      )}
      {runs.map((run) => (
        <EpisodeTable key={run.uiReference} run={run} />
      ))}
    </div>
  );
}

function E1Charts({ runs }: { runs: readonly LabRun[] }) {
  const label = (run: LabRun) => strategyLabel(run.config.strategyType, run.config.batchSizeEvents);
  return (
    <div className={styles.charts}>
      <Bar title="SyncUnits" summary="SyncUnits creadas por tratamiento" yLabel="SyncUnits" runs={runs} label={label} metricId="sync_units_created" transform={asCount} display={showCount} tick={tickCount} />
      <Bar title="Bytes de telemetría creados" summary="Bytes de telemetría al crear la SyncUnit" yLabel="MB" runs={runs} label={label} metricId="traffic.telemetry_syncunit_bytes_created" transform={asMegabytes} display={showMb} tick={tickMb} />
      <Multi
        title="Frescura"
        summary="Percentiles p50 y p95 de frescura, en segundos"
        yLabel="s"
        runs={runs}
        label={label}
        tick={tickSeconds}
        series={[
          seriesFor(runs, "freshness.p50_seconds", "circle", asCount, showSeconds, label),
          seriesFor(runs, "freshness.p95_seconds", "square", asCount, showSeconds, label),
        ]}
      />
      <Bar title="Tiempo hasta convergencia" summary="TTC almacenado por tratamiento" yLabel="s" runs={runs} label={label} metricId="time_to_convergence_seconds" transform={asCount} display={showSeconds} tick={tickSeconds} />
      <Bar title="Transporte de telemetría" summary="Bytes de transporte de telemetría" yLabel="MB" runs={runs} label={label} metricId="traffic.telemetry_transport_bytes" transform={asMegabytes} display={showMb} tick={tickMb} />
      <Bar title="Transporte total de aplicación" summary="Total de bytes de transporte de aplicación" yLabel="MB" runs={runs} label={label} metricId="traffic.total_transport_application_bytes" transform={asMegabytes} display={showMb} tick={tickMb} />
      <Bar title="Utilización de contacto" summary="Utilización ponderada de contacto. No es una carga ofrecida." yLabel="%" runs={runs} label={label} metricId="contacts.contact_utilization_weighted" transform={asPercent} display={showPercent} tick={tickPercent} />
      <p className={styles.help}>
        Cada gráfico usa una sola unidad. La utilización de contacto no es la carga ofrecida: E1 no
        tiene offered load.
      </p>
    </div>
  );
}

function E2Charts({ runs }: { runs: readonly LabRun[] }) {
  const groups = groupByStrategy(runs);
  return (
    <div className={styles.charts}>
      <p className={styles.note}>
        Completitud y confirmación van en gráficos separados. La carga ofrecida es el eje de
        categorías. <HelpTip id="contactUtilization" /> no comparte eje con la carga.
      </p>
      <p className={styles.warn}>
        <HelpTip id="gap">gaps = 0 no implica completitud.</HelpTip> En 120 % Individual el artefacto
        puede guardar gaps = 0 con completitud menor que 1.
      </p>
      {groups.map(([name, group]) => (
        <section key={name} className={styles.stack}>
          <h2>{name}</h2>
          <div className={styles.pair}>
            <Point title={`Completitud · ${name}`} summary="Completitud en Tierra" yLabel="%" runs={group} metricId="completeness" />
            <Point title={`Confirmación · ${name}`} summary="Confirmación en origen" yLabel="%" runs={group} metricId="confirmation_ratio" />
          </div>
          <Multi
            title={`Generados, persistidos y confirmados · ${name}`}
            summary="Tres conteos almacenados"
            yLabel="eventos"
            runs={group}
            label={(run) => loadLabel(run.config.offeredLoadFraction)}
            tick={tickCount}
            series={[
              seriesFor(group, "generated", "circle", asCount, showCount, (run) => run.label),
              seriesFor(group, "earth_persisted_unique", "square", asCount, showCount, (run) => run.label),
              seriesFor(group, "confirmed", "diamond", asCount, showCount, (run) => run.label),
            ]}
          />
          <Point title={`Gaps · ${name}`} summary="gaps_count almacenado" yLabel="huecos" runs={group} metricId="gaps_count" percent={false} />
        </section>
      ))}
      <BacklogChart runs={runs} />
      <CategoricalBarChart
        title="Utilización de contacto"
        summary="Utilización ponderada por estrategia. No es la carga ofrecida."
        yLabel="%"
        categories={loadCategories(runs)}
        series={groups.map(([name, group], index) =>
          seriesOnLoads(
            group,
            "contacts.contact_utilization_weighted",
            name,
            name,
            symbolAt(index),
            asPercent,
            showPercent,
          ),
        )}
        formatTick={tickPercent}
      />
    </div>
  );
}

function Bar({
  title,
  summary,
  yLabel,
  runs,
  label,
  metricId,
  transform,
  display,
  tick,
}: {
  title: string;
  summary: string;
  yLabel: string;
  runs: readonly LabRun[];
  label: (run: LabRun) => string;
  metricId: string;
  transform: (value: number) => number;
  display: (value: number) => string;
  tick: (value: number) => string;
}) {
  return (
    <CategoricalBarChart
      title={title}
      summary={summary}
      yLabel={yLabel}
      categories={categoriesOf(runs, label)}
      series={[seriesFor(runs, metricId, "circle", transform, display, label)]}
      formatTick={tick}
    />
  );
}

function Multi({
  title,
  summary,
  yLabel,
  runs,
  label,
  tick,
  series,
}: {
  title: string;
  summary: string;
  yLabel: string;
  runs: readonly LabRun[];
  label: (run: LabRun) => string;
  tick: (value: number) => string;
  series: ChartSeries[];
}) {
  return (
    <CategoricalBarChart
      title={title}
      summary={summary}
      yLabel={yLabel}
      categories={categoriesOf(runs, label)}
      series={series}
      formatTick={tick}
    />
  );
}

function Point({
  title,
  summary,
  yLabel,
  runs,
  metricId,
  percent = true,
}: {
  title: string;
  summary: string;
  yLabel: string;
  runs: readonly LabRun[];
  metricId: string;
  percent?: boolean;
}) {
  return (
    <ObservedPointChart
      title={title}
      summary={summary}
      yLabel={yLabel}
      categories={categoriesOf(runs, (run) => loadLabel(run.config.offeredLoadFraction))}
      series={[
        seriesFor(
          runs,
          metricId,
          "circle",
          percent ? asPercent : asCount,
          percent ? showPercent : showCount,
        ),
      ]}
      formatTick={percent ? tickPercent : tickCount}
    />
  );
}

function groupByStrategy(runs: readonly LabRun[]): [string, LabRun[]][] {
  const groups = new Map<string, LabRun[]>();
  for (const run of runs) {
    const label = strategyLabel(run.config.strategyType, run.config.batchSizeEvents);
    groups.set(label, [...(groups.get(label) ?? []), run]);
  }
  return [...groups.entries()];
}

function symbolAt(index: number): "circle" | "square" | "diamond" {
  return index === 0 ? "circle" : index === 1 ? "square" : "diamond";
}
