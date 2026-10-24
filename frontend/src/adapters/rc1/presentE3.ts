import type { ExperimentDetail, RunMeasurement, RunSummary } from "../../domain";
import type { MetricGap, ScientificValue } from "../../domain/metrics";
import { isStoredNumber } from "../../domain/metrics";
import type {
  E3RecoveryPresentation,
  RecoveryControlPair,
  RecoveryCountsView,
  RecoveryEvent,
  RecoveryEventKind,
  RecoveryFinalState,
  RecoveryLatencyView,
  RecoveryOfficialView,
  RecoverySensitivityPoint,
  RecoverySensitivityView,
  RecoveryTimelineRun,
  RecoveryTrafficView,
  StoredRecovery,
  StoredRecoveryEpisode,
} from "../../domain/recovery";
import {
  actorFor,
  buildPlaybackSteps,
  displayBytes,
  displayCount,
  displayInstant,
  displayLatency,
  displayRatio,
  EVENT_LABEL,
  narrativeFor,
  numbersOf,
} from "../../domain/recovery";

/**
 * Arma la vista de E3 con campos ya almacenados.
 * Los instantes posicionan la línea de tiempo.
 * Los intervalos salen de loss_to_* y no se vuelven a restar.
 */

interface BoundRun {
  run: RunSummary;
  measurement: RunMeasurement;
  recovery: StoredRecovery;
}

export function mapE3Recovery(
  official: ExperimentDetail,
  sensitivity: ExperimentDetail | null,
): E3RecoveryPresentation {
  const gaps: MetricGap[] = [];
  const view = mapOfficial(official, gaps);
  const sensitivityView = sensitivity ? mapSensitivity(sensitivity, view, gaps) : null;
  return {
    ok: view !== null,
    gaps,
    official: view,
    sensitivity: sensitivityView,
  };
}

function mapOfficial(detail: ExperimentDetail, gaps: MetricGap[]): RecoveryOfficialView | null {
  const sender = bindLabeled(detail, "B", gaps);
  const receiver = bindLabeled(detail, "D", gaps);
  if (!sender || !receiver) {
    return null;
  }
  if (sender.run.recoveryPolicy !== "sender-driven" || receiver.run.recoveryPolicy !== "receiver-driven") {
    gaps.push({ runLabel: "B/D", path: "recovery_policy" });
    return null;
  }
  const senderRun = toTimelineRun(sender, gaps);
  const receiverRun = toTimelineRun(receiver, gaps);
  const senderLoss = instant(sender.recovery.episode?.lossAt);
  const receiverLoss = instant(receiver.recovery.episode?.lossAt);
  const controls = mapControls(detail, gaps);
  return {
    sender: senderRun,
    receiver: receiverRun,
    sameLoss: senderLoss !== null && senderLoss === receiverLoss,
    controls,
    steps: buildPlaybackSteps([...senderRun.events, ...receiverRun.events]),
  };
}

function mapControls(detail: ExperimentDetail, gaps: MetricGap[]): RecoveryControlPair | null {
  const sender = bindLabeled(detail, "A", gaps);
  const receiver = bindLabeled(detail, "C", gaps);
  if (!sender || !receiver) {
    return null;
  }
  const senderFinal = finalNumbers(sender);
  const receiverFinal = finalNumbers(receiver);
  const senderEpisodes = sender.recovery.episodeCount;
  const receiverEpisodes = receiver.recovery.episodeCount;
  const noRecoveryEpisodes =
    isStoredNumber(senderEpisodes) &&
    senderEpisodes.value === 0 &&
    isStoredNumber(receiverEpisodes) &&
    receiverEpisodes.value === 0 &&
    sender.recovery.episode === null &&
    receiver.recovery.episode === null;
  const sameFinalState =
    senderFinal !== null &&
    receiverFinal !== null &&
    senderFinal.completeness === receiverFinal.completeness &&
    senderFinal.confirmation === receiverFinal.confirmation &&
    senderFinal.backlog === receiverFinal.backlog;
  const shown = senderFinal ?? receiverFinal;
  return {
    senderLabel: sender.run.label,
    receiverLabel: receiver.run.label,
    sameFinalState,
    noRecoveryEpisodes,
    completeness: shown ? displayRatio(shown.completenessValue).display : "—",
    confirmation: shown ? displayRatio(shown.confirmationValue).display : "—",
    backlog: shown ? displayCount(shown.backlogValue).display : "—",
    episodeCount: noRecoveryEpisodes ? "0" : "—",
  };
}

function mapSensitivity(
  detail: ExperimentDetail,
  official: RecoveryOfficialView | null,
  gaps: MetricGap[],
): RecoverySensitivityView | null {
  const officialSequence = official?.sender.sequenceNumber ?? null;
  const buckets = new Map<number, { sender?: BoundRun; receiver?: BoundRun }>();
  for (const run of detail.runs) {
    const measurement = detail.measurements.find((item) => item.index === run.index);
    if (!measurement?.recovery || !measurement.metrics) {
      gaps.push({ runLabel: run.label, path: `${detail.locator.logicalPath} metrics.recovery` });
      continue;
    }
    const planned = run.targetSequences;
    if (!planned || planned.length !== 1) {
      gaps.push({ runLabel: run.label, path: "failure_plan.silent_forward_delivery_losses" });
      continue;
    }
    const sequence = planned[0];
    if (sequence === undefined) {
      continue;
    }
    const episodeSequence = measurement.recovery.episode?.sequenceNumber ?? null;
    if (episodeSequence !== null && episodeSequence !== sequence) {
      gaps.push({ runLabel: run.label, path: "recovery.episodes[0].sequence_number" });
      continue;
    }
    for (const path of measurement.recovery.gaps) {
      gaps.push({ runLabel: run.label, path });
    }
    const bound: BoundRun = { run, measurement, recovery: measurement.recovery };
    const bucket = buckets.get(sequence) ?? {};
    if (run.recoveryPolicy === "sender-driven") {
      bucket.sender = bound;
    } else if (run.recoveryPolicy === "receiver-driven") {
      bucket.receiver = bound;
    } else {
      gaps.push({ runLabel: run.label, path: "recovery_policy" });
      continue;
    }
    buckets.set(sequence, bucket);
  }

  const points: RecoverySensitivityPoint[] = [];
  for (const sequence of [...buckets.keys()].sort((left, right) => left - right)) {
    const bucket = buckets.get(sequence);
    if (!bucket?.sender || !bucket.receiver) {
      gaps.push({ runLabel: `seq${sequence}`, path: "par sender/receiver" });
      continue;
    }
    points.push({
      sequenceNumber: sequence,
      sequenceLabel: `seq${sequence}`,
      officialCase: officialSequence !== null && sequence === officialSequence,
      sender: toTimelineRun(bucket.sender, gaps),
      receiver: toTimelineRun(bucket.receiver, gaps),
    });
  }
  if (points.length === 0) {
    return null;
  }
  return {
    points,
    receiverTriggersEarlier: allLower(points, (run) => numbersOf(run.latencies.lossToTrigger)),
    receiverRecoversEarthEarlier: allLower(points, (run) => numbersOf(run.latencies.lossToEarth)),
    receiverUsesLessTraffic: allLower(points, (run) => numbersOf(run.traffic.total)),
    originDirectionStable: originStable(points),
  };
}

function allLower(
  points: readonly RecoverySensitivityPoint[],
  read: (run: RecoveryTimelineRun) => number | null,
): boolean {
  if (points.length !== 3) {
    return false;
  }
  return points.every((point) => {
    const sender = read(point.sender);
    const receiver = read(point.receiver);
    return sender !== null && receiver !== null && receiver < sender;
  });
}

function originStable(points: readonly RecoverySensitivityPoint[]): boolean {
  if (points.length !== 3) {
    return false;
  }
  const signs: number[] = [];
  for (const point of points) {
    const sender = numbersOf(point.sender.latencies.lossToOrigin);
    const receiver = numbersOf(point.receiver.latencies.lossToOrigin);
    if (sender === null || receiver === null) {
      return false;
    }
    if (receiver < sender) {
      signs.push(-1);
    } else if (receiver > sender) {
      signs.push(1);
    } else {
      signs.push(0);
    }
  }
  return signs.every((sign) => sign === signs[0]);
}

function bindLabeled(detail: ExperimentDetail, label: string, gaps: MetricGap[]): BoundRun | null {
  const run = detail.runs.find((item) => item.label === label);
  if (!run) {
    gaps.push({ runLabel: label, path: `${detail.locator.logicalPath} runs` });
    return null;
  }
  const measurement = detail.measurements.find((item) => item.index === run.index);
  if (!measurement?.recovery || !measurement.metrics) {
    gaps.push({
      runLabel: label,
      path: `${detail.locator.logicalPath}.campaign_manifest.runs[${run.index}].manifest.metrics.recovery`,
    });
    return null;
  }
  for (const path of measurement.recovery.gaps) {
    gaps.push({ runLabel: label, path });
  }
  return { run, measurement, recovery: measurement.recovery };
}

function toTimelineRun(bound: BoundRun, gaps: MetricGap[]): RecoveryTimelineRun {
  const policy = bound.run.recoveryPolicy === "receiver-driven" ? "receiver-driven" : "sender-driven";
  const episode = bound.recovery.episode;
  const sequence = sequenceOf(bound, gaps);
  return {
    label: bound.run.label,
    policy,
    policyLabel: policy === "sender-driven" ? "SENDER-DRIVEN" : "RECEIVER-DRIVEN",
    failureEnabled: bound.run.failureEnabled === true,
    sequenceNumber: sequence,
    events: episode ? eventsOf(bound.run.label, episode) : [],
    latencies: latenciesOf(bound.recovery),
    traffic: trafficOf(bound.recovery),
    counts: countsOf(bound.recovery),
    finalState: finalStateOf(bound),
  };
}

function sequenceOf(bound: BoundRun, gaps: MetricGap[]): number | null {
  const planned = bound.run.targetSequences;
  const plannedSequence = planned && planned.length === 1 ? planned[0] ?? null : null;
  const episodeSequence = bound.recovery.episode?.sequenceNumber ?? null;
  if (plannedSequence !== null && episodeSequence !== null && plannedSequence !== episodeSequence) {
    gaps.push({ runLabel: bound.run.label, path: "sequence_number" });
    return episodeSequence;
  }
  return episodeSequence ?? plannedSequence;
}

function eventsOf(runLabel: string, episode: StoredRecoveryEpisode): RecoveryEvent[] {
  const trigger = episode.trigger;
  const specs: readonly { kind: RecoveryEventKind; value: ScientificValue }[] = [
    { kind: "loss", value: episode.lossAt },
    { kind: "gap-observed", value: episode.gapObservedAt },
    { kind: "recovery-trigger", value: episode.triggeredAt },
    { kind: "recovery-departure", value: episode.departedAt },
    { kind: "earth-recovered", value: episode.earthAt },
    { kind: "origin-confirmed", value: episode.originAt },
  ];
  const events: RecoveryEvent[] = [];
  for (const spec of specs) {
    if (!isStoredNumber(spec.value)) {
      continue;
    }
    events.push({
      id: `${runLabel}:${spec.kind}`,
      kind: spec.kind,
      scientificSeconds: spec.value.value,
      displayTime: displayInstant(spec.value.value),
      actor: actorFor(spec.kind, trigger),
      label: EVENT_LABEL[spec.kind],
      narrative: narrativeFor(spec.kind, trigger),
      sourceRunLabel: runLabel,
      sourcePath: spec.value.path,
    });
  }
  return events;
}

function latenciesOf(recovery: StoredRecovery): RecoveryLatencyView {
  return {
    lossToTrigger: displayLatency(recovery.latencies.lossToTrigger),
    lossToEarth: displayLatency(recovery.latencies.lossToEarth),
    lossToOrigin: displayLatency(recovery.latencies.lossToOrigin),
  };
}

function trafficOf(recovery: StoredRecovery): RecoveryTrafficView {
  const episode = recovery.episode;
  const separates =
    episode !== null &&
    isStoredNumber(episode.commonLostMarsRelay) &&
    isStoredNumber(episode.commonLostRelayEarth);
  return {
    forward: displayBytes(recovery.traffic.forward),
    reverse: displayBytes(recovery.traffic.reverse),
    total: displayBytes(recovery.traffic.total),
    separatesCommonLostAttempt: separates,
  };
}

function countsOf(recovery: StoredRecovery): RecoveryCountsView {
  return {
    senderTimeouts: displayCount(recovery.counts.senderTimeouts),
    senderRetries: displayCount(recovery.counts.senderRetries),
    gapRequests: displayCount(recovery.counts.gapRequests),
    repairAttempts: displayCount(recovery.counts.repairAttempts),
  };
}

function finalStateOf(bound: BoundRun): RecoveryFinalState {
  const metrics = bound.measurement.metrics;
  if (!metrics) {
    const missing = displayCount({ status: "missing", path: "metrics" });
    return {
      completeness: missing,
      confirmation: missing,
      backlog: missing,
      converged: null,
    };
  }
  return {
    completeness: displayRatio(metrics.state.completeness),
    confirmation: displayRatio(metrics.state.confirmationRatio),
    backlog: displayCount(metrics.state.finalBacklog),
    converged: metrics.convergence.converged,
  };
}

function instant(value: ScientificValue | undefined): number | null {
  return value && isStoredNumber(value) ? value.value : null;
}

function finalNumbers(bound: BoundRun): {
  completeness: number;
  confirmation: number;
  backlog: number;
  completenessValue: ScientificValue;
  confirmationValue: ScientificValue;
  backlogValue: ScientificValue;
} | null {
  const metrics = bound.measurement.metrics;
  if (!metrics) {
    return null;
  }
  const completeness = metrics.state.completeness;
  const confirmation = metrics.state.confirmationRatio;
  const backlog = metrics.state.finalBacklog;
  if (!isStoredNumber(completeness) || !isStoredNumber(confirmation) || !isStoredNumber(backlog)) {
    return null;
  }
  return {
    completeness: completeness.value,
    confirmation: confirmation.value,
    backlog: backlog.value,
    completenessValue: completeness,
    confirmationValue: confirmation,
    backlogValue: backlog,
  };
}
