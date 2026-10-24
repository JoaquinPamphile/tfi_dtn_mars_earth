import { defenseContent } from "../../../defense/content";
import type { DisplayMetric, RecoverySensitivityView, RecoveryTimelineRun } from "../../../domain/recovery";
import { numbersOf, stackAgrees } from "../../../domain/recovery";
import styles from "./recovery.module.css";

const relato = defenseContent.e3;

export function RecoverySensitivity({ view }: { view: RecoverySensitivityView }) {
  const maxTraffic = Math.max(
    0,
    ...view.points.flatMap((point) => [
      numbersOf(point.sender.traffic.total) ?? 0,
      numbersOf(point.receiver.traffic.total) ?? 0,
    ]),
  );
  return (
    <section className={styles.sensitivity} aria-label="Tres posiciones deterministas de la pérdida">
      <div className={styles.sensitivityGrid}>
        {view.points.map((point) => (
          <article key={point.sequenceLabel} className={styles.position} data-official={point.officialCase ? "true" : "false"}>
            <header>
              <h3>{point.sequenceLabel}</h3>
              {point.officialCase ? <p className={styles.officialBadge}>{relato.officialMark}</p> : null}
            </header>
            <MetricLine
              label="LOSS → TRIGGER"
              sender={point.sender.latencies.lossToTrigger}
              receiver={point.receiver.latencies.lossToTrigger}
              senderRun={point.sender}
              receiverRun={point.receiver}
            />
            <MetricLine
              label="LOSS → EARTH"
              sender={point.sender.latencies.lossToEarth}
              receiver={point.receiver.latencies.lossToEarth}
              senderRun={point.sender}
              receiverRun={point.receiver}
            />
            <MetricLine
              label="LOSS → ORIGIN"
              sender={point.sender.latencies.lossToOrigin}
              receiver={point.receiver.latencies.lossToOrigin}
              senderRun={point.sender}
              receiverRun={point.receiver}
            />
            <MiniTraffic sender={point.sender} receiver={point.receiver} max={maxTraffic} />
            {point.officialCase ? (
              <p className={styles.micro}>
                {point.sequenceLabel}. {relato.notReplica}
              </p>
            ) : null}
          </article>
        ))}
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
      <ul className={styles.sensitivityNotes}>
        {view.receiverTriggersEarlier ? <li>Receiver dispara antes en las tres posiciones.</li> : null}
        {view.receiverRecoversEarthEarlier ? <li>Receiver recupera Tierra antes en las tres posiciones.</li> : null}
        {view.receiverUsesLessTraffic ? <li>Receiver usa menos tráfico de recuperación en las tres posiciones.</li> : null}
        {view.originDirectionStable ? null : <li>{relato.sensitivityOrigin}</li>}
        <li>{relato.sensitivityNote}</li>
        <li>{relato.originNote}</li>
        <li>{relato.trafficNote}</li>
      </ul>
    </section>
  );
}

function MetricLine({
  label,
  sender,
  receiver,
  senderRun,
  receiverRun,
}: {
  label: string;
  sender: DisplayMetric;
  receiver: DisplayMetric;
  senderRun: RecoveryTimelineRun;
  receiverRun: RecoveryTimelineRun;
}) {
  const senderValue = numbersOf(sender);
  const receiverValue = numbersOf(receiver);
  const max = Math.max(senderValue ?? 0, receiverValue ?? 0);
  return (
    <div className={styles.metricLine}>
      <p>{label}</p>
      <Pair lane="sender" label={senderRun.label} metric={sender} max={max} />
      <Pair lane="receiver" label={receiverRun.label} metric={receiver} max={max} />
    </div>
  );
}

function Pair({
  lane,
  label,
  metric,
  max,
}: {
  lane: "sender" | "receiver";
  label: string;
  metric: DisplayMetric;
  max: number;
}) {
  const value = numbersOf(metric);
  const width = max > 0 && value !== null ? `${(value / max) * 100}%` : "0%";
  return (
    <div className={styles.barRow}>
      <span className={styles.barName}>
        <i className={styles.laneKey} data-lane={lane} aria-hidden="true" />
        {label}
      </span>
      <span className={styles.track} aria-hidden="true">
        <span className={styles.fill} data-lane={lane} style={{ width }} />
      </span>
      <span className={styles.barValue} title={metric.raw}>
        {metric.display}
      </span>
    </div>
  );
}

function MiniTraffic({
  sender,
  receiver,
  max,
}: {
  sender: RecoveryTimelineRun;
  receiver: RecoveryTimelineRun;
  max: number;
}) {
  return (
    <div className={styles.miniTraffic}>
      <p>Recovery traffic</p>
      <div className={styles.stacks}>
        <MiniStack run={sender} lane="sender" max={max} />
        <MiniStack run={receiver} lane="receiver" max={max} />
      </div>
    </div>
  );
}

function MiniStack({
  run,
  lane,
  max,
}: {
  run: RecoveryTimelineRun;
  lane: "sender" | "receiver";
  max: number;
}) {
  const forward = numbersOf(run.traffic.forward);
  const reverse = numbersOf(run.traffic.reverse);
  const total = numbersOf(run.traffic.total);
  const agreed = stackAgrees(run.traffic);
  const scale = max > 0 && total !== null ? total / max : 0;
  return (
    <div className={styles.stackColumn}>
      <p className={styles.total} title={run.traffic.total.raw}>
        {run.traffic.total.display}
      </p>
      {agreed && forward !== null && reverse !== null && total !== null && total > 0 ? (
        <div className={styles.stack} style={{ height: `${Math.max(8, scale * 48)}px` }} aria-hidden="true">
          <span className={styles.reverse} data-lane={lane} style={{ flexGrow: reverse }} />
          <span className={styles.forward} data-lane={lane} style={{ flexGrow: forward }} />
        </div>
      ) : null}
      <p className={styles.stackName}>{run.label}</p>
    </div>
  );
}
