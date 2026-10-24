import { useState } from "react";
import { scenarioSession } from "../../adapters";
import type { LabRun } from "../../domain/lab";
import { formatBytes, formatCount, formatSecondsDetail } from "../../domain/metricFormat";
import type { RecoveryOfficialView } from "../../domain/recovery";
import { contactWindow, episodeDomain, selectReturnOpportunities } from "../../domain/recovery";
import type { DirectedContact } from "../../domain/scenario";
import { formatSimSeconds } from "../../domain/scenarioFormat";
import { ContactTimeline } from "../scenario/ContactTimeline";
import { RecoveryCompare } from "../defense/recovery/RecoveryCompare";
import { RecoveryTimeline } from "../defense/recovery/RecoveryTimeline";
import { EPISODE_LABEL, type LabEpisodeField } from "../../domain/lab";
import styles from "./lab.module.css";

export function RecoveryBoard({ official }: { official: RecoveryOfficialView }) {
  const [index, setIndex] = useState(0);
  const scenario = scenarioSession.kind === "ready" ? scenarioSession.scenario : null;
  const marsReturn =
    scenario?.links.find((link) => link.source === "RELAY" && link.destination === "MARS")?.contacts ??
    [];
  const earthAt = instants(official, "earth-recovered");
  const originAt = instants(official, "origin-confirmed");
  const returns = selectReturnOpportunities(marsReturn, earthAt, originAt);
  const bands = [returns.previous, returns.next].filter((item): item is DirectedContact => item !== null);
  const domain = episodeDomain(
    [...official.sender.events, ...official.receiver.events],
    bands,
    "episode",
    scenario?.horizonSeconds ?? null,
  );

  return (
    <div className={`${styles.stack} ${styles.boundPlots}`}>
      <RecoveryTimeline
        sender={official.sender}
        receiver={official.receiver}
        steps={official.steps}
        activeIndex={index}
        sameLoss={official.sameLoss}
        focused
        domain={domain}
        previousReturn={returns.previous}
        nextReturn={returns.next}
        onSelect={setIndex}
      />
      {returns.previous && returns.next ? (
        <p className={styles.note}>
          Retorno previo {contactWindow(returns.previous)}. Siguiente retorno{" "}
          {contactWindow(returns.next)}.
        </p>
      ) : null}
      <RecoveryCompare sender={official.sender} receiver={official.receiver} />
      {official.controls ? (
        <p className={styles.note}>
          Controles {official.controls.senderLabel} y {official.controls.receiverLabel}:{" "}
          {official.controls.noRecoveryEpisodes
            ? "sin episodios de recuperación."
            : official.controls.episodeCount}
          {" "}
          Completitud {official.controls.completeness}. Confirmación {official.controls.confirmation}.
          Backlog {official.controls.backlog}.
        </p>
      ) : null}
    </div>
  );
}

export function EpisodeTable({ run }: { run: LabRun }) {
  if (!run.episode) {
    return null;
  }
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <caption className={styles.note}>Episodio almacenado · {run.label}</caption>
        <thead>
          <tr>
            <th scope="col">Campo</th>
            <th scope="col">Nombre</th>
            <th scope="col">Valor</th>
          </tr>
        </thead>
        <tbody>
          {run.episode.map((field) => {
            const shown = formatEpisode(field);
            return (
              <tr key={field.key}>
                <td className={styles.mono}>{field.key}</td>
                <td>{EPISODE_LABEL[field.key] ?? field.key}</td>
                <td title={shown.title}>{shown.text}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function ScenarioContacts() {
  if (scenarioSession.kind !== "ready") {
    return <p className={styles.note}>El plan de contactos no está disponible en esta sesión.</p>;
  }
  return (
    <div className={styles.stack}>
      <p className={styles.note}>
        Plan de contactos del escenario. No es la utilización de una corrida y no equivale a la carga
        ofrecida.
      </p>
      <ContactTimeline scenario={scenarioSession.scenario} variant="detail" />
    </div>
  );
}

function instants(official: RecoveryOfficialView, kind: "earth-recovered" | "origin-confirmed"): number[] {
  return [...official.sender.events, ...official.receiver.events]
    .filter((event) => event.kind === kind)
    .map((event) => event.scientificSeconds);
}

function formatEpisode(field: LabEpisodeField): { text: string; title: string } {
  const value = field.value;
  if (value === null) {
    return { text: "—", title: "null" };
  }
  if (typeof value === "boolean") {
    return { text: value ? "sí" : "no", title: String(value) };
  }
  if (typeof value === "string") {
    return { text: value, title: value };
  }
  const raw = String(value);
  if (field.key.includes("bytes")) {
    return {
      text: value >= 1_000_000 ? formatBytes(value) : formatBytes(value),
      title: `${raw} B`,
    };
  }
  if (field.key.endsWith("_seconds") || field.key.endsWith("_at_sim")) {
    return {
      text: field.key.endsWith("_seconds") ? formatSecondsDetail(value) : formatSimSeconds(value),
      title: `${raw} s`,
    };
  }
  if (Number.isInteger(value)) {
    return { text: formatCount(value), title: raw };
  }
  return { text: raw, title: raw };
}
