import type { ScientificValue } from "../../domain/metrics";
import type { StoredRecovery, StoredRecoveryEpisode } from "../../domain/recovery";

/**
 * Lee metrics.recovery tal como está en el artefacto.
 * No resta instantes y no completa ausencias con cero.
 */

export function readStoredRecovery(metrics: unknown, metricsPath: string): StoredRecovery {
  const gaps: string[] = [];
  const root = asRecord(metrics);
  const path = `${metricsPath}.recovery`;
  const recovery = root ? asRecord(root.recovery) : null;
  if (!recovery) {
    gaps.push(path);
    return emptyRecovery(path, gaps);
  }

  const episode = readEpisode(recovery, path, gaps);
  return {
    episodeCount: take(readNumber(recovery, "episode_count", path), gaps),
    latencies: {
      lossToTrigger: take(readNumber(recovery, "loss_to_trigger_seconds", path), gaps),
      triggerToEarth: take(readNumber(recovery, "trigger_to_earth_recovery_seconds", path), gaps),
      lossToEarth: take(readNumber(recovery, "loss_to_earth_recovery_seconds", path), gaps),
      earthToOrigin: take(
        readNumber(recovery, "earth_recovery_to_origin_confirmation_seconds", path),
        gaps,
      ),
      lossToOrigin: take(readNumber(recovery, "loss_to_origin_confirmation_seconds", path), gaps),
    },
    counts: {
      senderTimeouts: take(readNumber(recovery, "sender_ack_timeout_count", path), gaps),
      senderRetries: take(readNumber(recovery, "sender_retry_attempt_count", path), gaps),
      gapRequests: take(readNumber(recovery, "receiver_gap_request_logical_count", path), gaps),
      repairAttempts: take(readNumber(recovery, "receiver_repair_attempt_count", path), gaps),
    },
    traffic: {
      forward: take(readNumber(recovery, "policy_recovery_forward_bytes", path), gaps),
      reverse: take(readNumber(recovery, "policy_recovery_reverse_bytes", path), gaps),
      total: take(readNumber(recovery, "policy_recovery_network_bytes_total", path), gaps),
    },
    episode,
    gaps,
  };
}

function readEpisode(
  recovery: Record<string, unknown>,
  path: string,
  gaps: string[],
): StoredRecoveryEpisode | null {
  const episodePath = `${path}.episodes`;
  if (!Object.prototype.hasOwnProperty.call(recovery, "episodes")) {
    gaps.push(episodePath);
    return null;
  }
  const episodes = recovery.episodes;
  if (!Array.isArray(episodes)) {
    gaps.push(episodePath);
    return null;
  }
  if (episodes.length === 0) {
    return null;
  }
  if (episodes.length !== 1) {
    gaps.push(episodePath);
    return null;
  }
  const episode = asRecord(episodes[0]);
  const itemPath = `${episodePath}[0]`;
  if (!episode) {
    gaps.push(itemPath);
    return null;
  }
  return {
    trigger: readTrigger(episode, itemPath, gaps),
    sequenceNumber: readSequence(episode, itemPath, gaps),
    lossAt: take(readNumber(episode, "loss_at_sim", itemPath), gaps),
    gapObservedAt: take(readNumber(episode, "gap_observed_at_sim", itemPath), gaps),
    triggeredAt: take(readNumber(episode, "recovery_triggered_at_sim", itemPath), gaps),
    departedAt: take(readNumber(episode, "first_recovery_data_departed_mars_at_sim", itemPath), gaps),
    earthAt: take(readNumber(episode, "earth_recovered_at_sim", itemPath), gaps),
    originAt: take(readNumber(episode, "origin_confirmed_at_sim", itemPath), gaps),
    commonLostMarsRelay: take(readNumber(episode, "common_lost_attempt_bytes_mars_relay", itemPath), gaps),
    commonLostRelayEarth: take(readNumber(episode, "common_lost_attempt_bytes_relay_earth", itemPath), gaps),
  };
}

function readTrigger(
  episode: Record<string, unknown>,
  path: string,
  gaps: string[],
): string | null {
  const full = `${path}.recovery_trigger`;
  if (!Object.prototype.hasOwnProperty.call(episode, "recovery_trigger")) {
    gaps.push(full);
    return null;
  }
  const value = episode.recovery_trigger;
  if (value === null) {
    return null;
  }
  if (typeof value !== "string" || value.length === 0) {
    gaps.push(full);
    return null;
  }
  return value;
}

function readSequence(
  episode: Record<string, unknown>,
  path: string,
  gaps: string[],
): number | null {
  const reading = readNumber(episode, "sequence_number", path);
  if (reading.status === "missing") {
    gaps.push(reading.path);
    return null;
  }
  if (reading.value === null || !Number.isInteger(reading.value)) {
    gaps.push(reading.path);
    return null;
  }
  return reading.value;
}

function readNumber(
  record: Record<string, unknown> | null,
  key: string,
  path: string,
): ScientificValue {
  const full = `${path}.${key}`;
  if (!record || !Object.prototype.hasOwnProperty.call(record, key)) {
    return { status: "missing", path: full };
  }
  const value = record[key];
  if (value === null) {
    return { status: "stored", path: full, value: null };
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    return { status: "stored", path: full, value };
  }
  return { status: "missing", path: full };
}

function take(reading: ScientificValue, gaps: string[]): ScientificValue {
  if (reading.status === "missing") {
    gaps.push(reading.path);
  }
  return reading;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function missing(path: string): ScientificValue {
  return { status: "missing", path };
}

function emptyRecovery(path: string, gaps: string[]): StoredRecovery {
  return {
    episodeCount: missing(`${path}.episode_count`),
    latencies: {
      lossToTrigger: missing(`${path}.loss_to_trigger_seconds`),
      triggerToEarth: missing(`${path}.trigger_to_earth_recovery_seconds`),
      lossToEarth: missing(`${path}.loss_to_earth_recovery_seconds`),
      earthToOrigin: missing(`${path}.earth_recovery_to_origin_confirmation_seconds`),
      lossToOrigin: missing(`${path}.loss_to_origin_confirmation_seconds`),
    },
    counts: {
      senderTimeouts: missing(`${path}.sender_ack_timeout_count`),
      senderRetries: missing(`${path}.sender_retry_attempt_count`),
      gapRequests: missing(`${path}.receiver_gap_request_logical_count`),
      repairAttempts: missing(`${path}.receiver_repair_attempt_count`),
    },
    traffic: {
      forward: missing(`${path}.policy_recovery_forward_bytes`),
      reverse: missing(`${path}.policy_recovery_reverse_bytes`),
      total: missing(`${path}.policy_recovery_network_bytes_total`),
    },
    episode: null,
    gaps,
  };
}
