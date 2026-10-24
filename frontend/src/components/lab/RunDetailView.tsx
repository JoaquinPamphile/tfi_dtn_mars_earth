import { useLabSession } from "../../app/LabProvider";
import type { ExperimentDetail } from "../../domain";
import {
  GROUP_LABEL,
  LAB_METRICS,
  TRAFFIC_SECTIONS,
  loadLabel,
  presentStored,
  storedNumber,
  strategyLabel,
  type LabRun,
} from "../../domain/lab";
import { formatCount } from "../../domain/metricFormat";
import { formatSimSeconds } from "../../domain/scenarioFormat";
import { HashValue } from "../experiments/HashValue";
import { HelpTip } from "./HelpTip";
import { JsonBlock } from "./JsonBlock";
import { EpisodeTable, RecoveryBoard, ScenarioContacts } from "./RecoveryBoard";
import styles from "./lab.module.css";

export function RunDetailView({ detail, run }: { detail: ExperimentDetail; run: LabRun }) {
  const coverage = storedNumber(run, "freshness_coverage");
  const missing = run.metrics.not_persisted_on_earth;
  const unconfirmed = run.metrics.persisted_on_earth_but_unconfirmed;
  const backlog = storedNumber(run, "backlog");
  const showBacklog =
    missing?.status === "stored" &&
    typeof missing.value === "number" &&
    unconfirmed?.status === "stored" &&
    typeof unconfirmed.value === "number";

  return (
    <div className={styles.stack}>
      <section className={styles.card}>
        <h2>Identidad</h2>
        <dl className={styles.meta}>
          <Item label="Experimento" value={`${detail.code} — ${detail.name}`} />
          <Item label="Corrida" value={run.label} />
          <Item label="Índice" value={String(run.index)} />
          <Item label="UI reference" value={run.uiReference} mono />
          <Item label="Tipo de referencia" value={run.referenceKind} />
        </dl>
        <p className={styles.help}>
          execution_identity identifica una combinación reproducible, pero no necesariamente una fila
          única de campaign.
        </p>
        <dl className={styles.meta}>
          <HashItem label="execution_identity" value={run.executionIdentity} />
          <HashItem label="dataset_identity" value={run.datasetIdentity} />
          <HashItem label="configuration_hash" value={run.configurationHash} />
          <HashItem label="dataset_fingerprint" value={run.datasetFingerprint} />
          <Item label="Fuente" value={detail.locator.logicalPath} mono />
        </dl>
      </section>

      <section className={styles.card}>
        <h2>Configuración</h2>
        <dl className={styles.meta}>
          <Item label="Escenario" value={run.config.scenarioId} mono />
          <Item label="Workload" value={run.config.workloadId} mono />
          <Item label="Estrategia" value={strategyLabel(run.config.strategyType, run.config.batchSizeEvents)} />
          <Item label="strategy_type" value={run.config.strategyType} mono />
          <Item label="Batch" value={run.config.batchSizeEvents === null ? "null" : String(run.config.batchSizeEvents)} />
          <Item label="Semilla" value={String(run.config.seed)} />
          <Item label="Carga ofrecida" value={loadLabel(run.config.offeredLoadFraction)} />
          <Item label="Política de recuperación" value={run.config.recoveryPolicy} />
          <Item label="Falla" value={run.config.failure.enabled ? "on" : "off"} />
          <Item
            label="Pérdidas silenciosas"
            value={
              run.config.failure.sequences.length === 0
                ? "0"
                : run.config.failure.sequences.join(", ")
            }
          />
          <Item label="ACK drops" value={String(run.config.failure.ackDrops)} />
          <Item label="Cortes de contacto" value={String(run.config.failure.contactCuts)} />
          <Item label="Stop policy" value={run.config.stopPolicy} mono />
          <Item label="Horizonte" value={formatSimSeconds(run.config.horizonSeconds)} />
          <Item label="Trace level" value={run.config.traceLevel} />
          <Item label="Timeout de ACK" value={formatSimSeconds(run.config.ackTimeoutSeconds)} />
          <Item
            label="Timeout de GapRequest"
            value={
              run.config.gapRequestTimeoutSeconds === null
                ? "null"
                : formatSimSeconds(run.config.gapRequestTimeoutSeconds)
            }
          />
          <Item label="Eventos del dataset" value={formatCount(run.config.datasetEventCount)} />
          <Item label="Estado del motor" value={run.config.engineStatus} />
          <Item label="Completada" value={run.completed ? "sí" : "no"} />
          <Item label="Fallida" value={run.failed ? "sí" : "no"} />
        </dl>
        <h3>Workload</h3>
        <dl className={styles.meta}>
          <Item label="event_type" value={run.config.workload.eventType} mono />
          <Item label="flow" value={run.config.workload.flow} mono />
          <Item label="max_events" value={formatCount(run.config.workload.maxEvents)} />
          <Item label="tasa" value={String(run.config.workload.rateEventsPerSecond)} />
          <Item label="prioridad" value={run.config.workload.priority} />
          <Item label="source_id" value={run.config.workload.sourceId} mono />
          <Item label="bytes canónicos" value={formatCount(run.config.workload.canonicalBytes)} />
          <Item label="inicio" value={formatSimSeconds(run.config.workload.startTimeSim)} />
        </dl>
      </section>

      <section className={styles.card}>
        <h2>Estado final</h2>
        <div className={styles.grid}>
          {STATE_IDS.map((id) => (
            <MetricCard key={id} run={run} id={id} />
          ))}
        </div>
        {showBacklog ? (
          <div>
            <h3>
              <HelpTip id="backlog">Backlog</HelpTip>
            </h3>
            <ul className={styles.tree}>
              <li>Backlog total {backlog === null ? "—" : formatCount(backlog)}</li>
              <li>├── No persistido en Tierra (M) {formatCount(missing.value as number)}</li>
              <li>└── Persistido sin confirmar (U) {formatCount(unconfirmed.value as number)}</li>
            </ul>
          </div>
        ) : null}
      </section>

      <section className={styles.card}>
        <h2>Temporalidad</h2>
        {coverage !== null && coverage < 1 ? (
          <p className={styles.warn}>
            Las estadísticas de freshness cubren sólo los eventos persistidos observados.
          </p>
        ) : null}
        <div className={styles.grid}>
          {TIME_IDS.map((id) => (
            <MetricCard key={id} run={run} id={id} />
          ))}
        </div>
      </section>

      <section className={styles.card}>
        <h2>Tráfico</h2>
        {TRAFFIC_SECTIONS.map((section) => (
          <div key={section.title}>
            <h3>{section.title}</h3>
            <div className={styles.grid}>
              {section.ids.map((id) => (
                <MetricCard key={id} run={run} id={id} />
              ))}
            </div>
          </div>
        ))}
      </section>

      <section className={styles.card}>
        <h2>Contactos</h2>
        <p className={styles.help}>
          <HelpTip id="contactUtilization" /> es distinta de <HelpTip id="offeredLoad" />. El artefacto
          no trae utilización por contacto, solo estos agregados. La línea de abajo es el plan del
          escenario.
        </p>
        <div className={styles.grid}>
          {CONTACT_IDS.map((id) => (
            <MetricCard key={id} run={run} id={id} />
          ))}
        </div>
        <ScenarioContacts />
      </section>

      <section className={styles.card}>
        <h2>Recovery</h2>
        <RecoverySection detail={detail} run={run} />
      </section>

      <section className={styles.card}>
        <h2>Reproducibilidad</h2>
        <dl className={styles.meta}>
          <Item label="source_state" value={run.config.sourceState} />
          <Item label="stop policy" value={run.config.stopPolicy} mono />
          <Item label="semilla" value={String(run.config.seed)} />
          <HashItem label="configuration_hash" value={run.configurationHash} />
          <HashItem label="dataset_fingerprint" value={run.datasetFingerprint} />
          <HashItem label="execution_identity" value={run.executionIdentity} />
        </dl>
      </section>

      <section className={styles.card}>
        <h2>Raw source</h2>
        <JsonBlock source={run.source} />
      </section>
    </div>
  );
}

function RecoverySection({ detail, run }: { detail: ExperimentDetail; run: LabRun }) {
  const session = useLabSession();
  const official = session.kind === "ready" ? session.adapter.getE3Presentation()?.official ?? null : null;
  const count = storedNumber(run, "recovery.episode_count");
  const control = !run.config.failure.enabled && (detail.id === "e3" || detail.id === "e3-sensitivity");

  return (
    <div className={styles.stack}>
      {control || (count === 0 && !run.episode) ? (
        <p className={styles.note}>
          {detail.id === "e3" || detail.id === "e3-sensitivity"
            ? "Control sin falla: 0 episodios de recuperación."
            : "0 episodios de recuperación."}
        </p>
      ) : null}
      {run.episode ? <EpisodeTable run={run} /> : null}
      {detail.id === "e3" && run.episode && official ? <RecoveryBoard official={official} /> : null}
      <div className={styles.grid}>
        {LAB_METRICS.filter((item) => item.group === "recovery").map((item) => (
          <MetricCard key={item.id} run={run} id={item.id} />
        ))}
      </div>
    </div>
  );
}

const STATE_IDS = [
  "generated",
  "earth_persisted_unique",
  "confirmed",
  "backlog",
  "gaps_count",
  "completeness",
  "confirmation_ratio",
  "converged",
] as const;

const TIME_IDS = [
  "freshness.count",
  "freshness_coverage",
  "freshness.min_seconds",
  "freshness.p50_seconds",
  "freshness.p95_seconds",
  "freshness.max_seconds",
  "freshness.mean_seconds",
  "time_to_convergence_seconds",
  "converged_at_sim",
  "convergence_reference_at_sim",
  "view_age_seconds",
] as const;

const CONTACT_IDS = [
  "contacts.contacts_total",
  "contacts.contacts_used",
  "contacts.contacts_forced_cut",
  "contacts.contact_utilization_mean",
  "contacts.contact_utilization_weighted",
  "contacts.forward_contact_utilization_weighted",
  "contacts.reverse_contact_utilization_weighted",
] as const;

function MetricCard({ run, id }: { run: LabRun; id: string }) {
  const def = LAB_METRICS.find((item) => item.id === id);
  if (!def) {
    return null;
  }
  const shown = presentStored(def, run.metrics[id]);
  return (
    <article className={styles.card}>
      <h3>{def.name}</h3>
      <p title={shown.title}>{shown.text}</p>
      <p className={styles.help}>{GROUP_LABEL[def.group]}</p>
    </article>
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

function HashItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <HashValue value={value} label={label} variant="full" />
      </dd>
    </div>
  );
}
