import { defenseContent } from "../../../defense/content";
import type { DisplayMetric, RecoveryTimelineRun } from "../../../domain/recovery";
import { numbersOf, stackAgrees } from "../../../domain/recovery";
import styles from "./recovery.module.css";

const relato = defenseContent.e3;

export function RecoveryCompare({
  sender,
  receiver,
}: {
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
}) {
  return (
    <div className={styles.compare}>
      <section className={styles.latencies} aria-label="Latencias almacenadas">
        <LatencyRow
          title="LOSS → TRIGGER"
          caption={caption("trigger", sender.latencies.lossToTrigger, receiver.latencies.lossToTrigger)}
          sender={sender}
          receiver={receiver}
          senderMetric={sender.latencies.lossToTrigger}
          receiverMetric={receiver.latencies.lossToTrigger}
        />
        <LatencyRow
          title="LOSS → EARTH RECOVERY"
          caption={caption("earth", sender.latencies.lossToEarth, receiver.latencies.lossToEarth)}
          sender={sender}
          receiver={receiver}
          senderMetric={sender.latencies.lossToEarth}
          receiverMetric={receiver.latencies.lossToEarth}
        />
        <LatencyRow
          title="LOSS → ORIGIN CONFIRMATION"
          caption={relato.sameReturn}
          sender={sender}
          receiver={receiver}
          senderMetric={sender.latencies.lossToOrigin}
          receiverMetric={receiver.latencies.lossToOrigin}
          note={relato.originNote}
        />
      </section>
      <TrafficPanel sender={sender} receiver={receiver} />
      <CountsPanel sender={sender} receiver={receiver} />
    </div>
  );
}

function LatencyRow({
  title,
  caption,
  sender,
  receiver,
  senderMetric,
  receiverMetric,
  note,
}: {
  title: string;
  caption: string;
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
  senderMetric: DisplayMetric;
  receiverMetric: DisplayMetric;
  note?: string;
}) {
  const senderValue = numbersOf(senderMetric);
  const receiverValue = numbersOf(receiverMetric);
  const max =
    senderValue === null && receiverValue === null
      ? null
      : Math.max(senderValue ?? 0, receiverValue ?? 0);
  return (
    <div className={styles.latency}>
      <div className={styles.latencyHead}>
        <h3>{title}</h3>
        {caption ? <p>{caption}</p> : null}
      </div>
      <Bar
        lane="sender"
        label={`${sender.policyLabel} · ${sender.label}`}
        metric={senderMetric}
        max={max}
      />
      <Bar
        lane="receiver"
        label={`${receiver.policyLabel} · ${receiver.label}`}
        metric={receiverMetric}
        max={max}
      />
      {note ? <p className={styles.micro}>{note}</p> : null}
    </div>
  );
}

function Bar({
  lane,
  label,
  metric,
  max,
}: {
  lane: "sender" | "receiver";
  label: string;
  metric: DisplayMetric;
  max: number | null;
}) {
  const value = numbersOf(metric);
  const width = max && max > 0 && value !== null ? `${(value / max) * 100}%` : "0%";
  return (
    <div className={styles.barRow}>
      <span className={styles.barName}>
        <i className={styles.laneKey} data-lane={lane} aria-hidden="true" />
        {label}
      </span>
      <span className={styles.track} aria-hidden="true">
        <span className={styles.fill} data-lane={lane} style={{ width }} />
      </span>
      <span className={styles.barValue} title={metric.present ? metric.raw : metric.path}>
        {metric.display}
      </span>
    </div>
  );
}

function caption(kind: "trigger" | "earth", sender: DisplayMetric, receiver: DisplayMetric): string {
  if (sender.display === receiver.display) {
    return relato.sameReturn;
  }
  const senderValue = numbersOf(sender);
  const receiverValue = numbersOf(receiver);
  if (senderValue === null || receiverValue === null || !(receiverValue < senderValue)) {
    return "";
  }
  return kind === "trigger" ? relato.reacts : relato.recovers;
}

function TrafficPanel({
  sender,
  receiver,
}: {
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
}) {
  const showStack = stackAgrees(sender.traffic) && stackAgrees(receiver.traffic);
  const max = Math.max(numbersOf(sender.traffic.total) ?? 0, numbersOf(receiver.traffic.total) ?? 0);
  return (
    <section className={styles.traffic} aria-label="Tráfico de recuperación">
      <h3>Recovery traffic</h3>
      <div className={styles.stacks}>
        <Stack run={sender} lane="sender" max={max} showStack={showStack} />
        <Stack run={receiver} lane="receiver" max={max} showStack={showStack} />
      </div>
      <ul className={styles.trafficLegend}>
        <li>
          <i className={styles.forwardSwatch} aria-hidden="true" />
          Forward
        </li>
        <li>
          <i className={styles.reverseSwatch} aria-hidden="true" />
          Reverse
        </li>
      </ul>
      {sender.traffic.separatesCommonLostAttempt && receiver.traffic.separatesCommonLostAttempt ? (
        <p className={styles.micro}>{relato.trafficNote}</p>
      ) : null}
    </section>
  );
}

function Stack({
  run,
  lane,
  max,
  showStack,
}: {
  run: RecoveryTimelineRun;
  lane: "sender" | "receiver";
  max: number;
  showStack: boolean;
}) {
  const forward = numbersOf(run.traffic.forward);
  const reverse = numbersOf(run.traffic.reverse);
  const total = numbersOf(run.traffic.total);
  const scale = max > 0 && total !== null ? total / max : 0;
  return (
    <div className={styles.stackColumn}>
      <p className={styles.total} title={run.traffic.total.raw}>
        {run.traffic.total.display}
      </p>
      {showStack && forward !== null && reverse !== null && total !== null && total > 0 ? (
        <div className={styles.stack} style={{ height: `${Math.max(8, scale * 72)}px` }} aria-hidden="true">
          <span className={styles.reverse} data-lane={lane} style={{ flexGrow: reverse }} />
          <span className={styles.forward} data-lane={lane} style={{ flexGrow: forward }} />
        </div>
      ) : (
        <p className={styles.micro}>
          {run.traffic.forward.display} forward · {run.traffic.reverse.display} reverse
        </p>
      )}
      <p className={styles.stackName}>
        <i className={styles.laneKey} data-lane={lane} aria-hidden="true" />
        {run.policyLabel} · {run.label}
      </p>
    </div>
  );
}

function CountsPanel({
  sender,
  receiver,
}: {
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
}) {
  return (
    <section className={styles.counts} aria-label="Timeouts, retries y GapRequests">
      <h3>Mecanismo</h3>
      <div>
        <p className={styles.stackName}>
          <i className={styles.laneKey} data-lane="sender" aria-hidden="true" />
          {sender.policyLabel} · {sender.label}
        </p>
        <dl>
          <div>
            <dt>Timeouts</dt>
            <dd title={sender.counts.senderTimeouts.raw}>{sender.counts.senderTimeouts.display}</dd>
          </div>
          <div>
            <dt>Retries</dt>
            <dd title={sender.counts.senderRetries.raw}>{sender.counts.senderRetries.display}</dd>
          </div>
        </dl>
      </div>
      <div>
        <p className={styles.stackName}>
          <i className={styles.laneKey} data-lane="receiver" aria-hidden="true" />
          {receiver.policyLabel} · {receiver.label}
        </p>
        <dl>
          <div>
            <dt>GapRequests</dt>
            <dd title={receiver.counts.gapRequests.raw}>{receiver.counts.gapRequests.display}</dd>
          </div>
          <div>
            <dt>Reparaciones</dt>
            <dd title={receiver.counts.repairAttempts.raw}>{receiver.counts.repairAttempts.display}</dd>
          </div>
        </dl>
      </div>
      <p className={styles.micro}>{relato.countsNote}</p>
    </section>
  );
}
