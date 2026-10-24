import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { scenarioSession } from "../../../adapters";
import { defenseContent } from "../../../defense/content";
import { isInteractiveEventTarget } from "../../../defense/keyboard";
import type {
  RecoveryControlPair,
  RecoveryPlaybackStep,
  RecoveryTimelineRun,
} from "../../../domain/recovery";
import { contactWindow, episodeDomain, selectReturnOpportunities } from "../../../domain/recovery";
import type { DirectedContact } from "../../../domain/scenario";
import { MetricToggle } from "../../charts/MetricToggle";
import { ContactTimeline } from "../../scenario/ContactTimeline";
import { DefenseCallout } from "../DefenseCallout";
import { RecoveryCompare } from "../recovery/RecoveryCompare";
import { RecoverySensitivity } from "../recovery/RecoverySensitivity";
import { RecoveryTimeline } from "../recovery/RecoveryTimeline";
import { usePrefersReducedMotion, useRecoveryPlayback } from "../recovery/useRecoveryPlayback";
import { EvidenceMissing, LabLink, Slide, useEvidenceAdapter } from "./slide";
import styles from "../recovery/recovery.module.css";

const relato = defenseContent.e3;
type Vista = "official" | "sensitivity";

export function E3Step() {
  const adapter = useEvidenceAdapter();
  const presentation = adapter?.getE3Presentation() ?? null;
  const reduced = usePrefersReducedMotion();
  const steps = presentation?.official?.steps ?? [];
  const playback = useRecoveryPlayback(steps.length, reduced);
  const [searchParams] = useSearchParams();
  const [vista, setVista] = useState<Vista>(
    searchParams.get("vista") === "sensitivity" ? "sensitivity" : "official",
  );
  const [controles, setControles] = useState(false);
  const [contexto, setContexto] = useState(false);
  const { toggle, previous, next, pause } = playback;

  useEffect(() => {
    if (vista !== "official") {
      pause();
    }
  }, [pause, vista]);

  useEffect(() => {
    if (vista !== "official") {
      return;
    }
    const alPulsar = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      if (isInteractiveEventTarget(event.target) || document.querySelector("[data-defense-overlay]")) {
        return;
      }
      if (event.key === " " || event.key === "Spacebar") {
        if (event.repeat) {
          return;
        }
        event.preventDefault();
        toggle();
        return;
      }
      if (event.key === "j" || event.key === "J") {
        event.preventDefault();
        previous();
        return;
      }
      if (event.key === "k" || event.key === "K") {
        event.preventDefault();
        next();
      }
    };
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, [next, previous, toggle, vista]);

  if (!presentation?.ok || !presentation.official) {
    return (
      <Slide fill>
        <div className={styles.board}>
          <Title />
          <EvidenceMissing />
          {presentation && presentation.gaps.length > 0 ? (
            <p className={styles.gaps}>{presentation.gaps.map((gap) => gap.path).join(" · ")}</p>
          ) : null}
        </div>
      </Slide>
    );
  }

  const official = presentation.official;
  const step = steps[playback.index] ?? null;
  const scenario = scenarioSession.kind === "ready" ? scenarioSession.scenario : null;
  const marsReturn =
    scenario?.links.find((link) => link.source === "RELAY" && link.destination === "MARS")?.contacts ??
    [];
  const returns = selectReturnOpportunities(
    marsReturn,
    instants(official.sender, official.receiver, "earth-recovered"),
    instants(official.sender, official.receiver, "origin-confirmed"),
  );
  const bands = [returns.previous, returns.next].filter((item): item is DirectedContact => item !== null);
  const domain = episodeDomain(
    [...official.sender.events, ...official.receiver.events],
    bands,
    contexto ? "scenario" : "episode",
    scenario?.horizonSeconds ?? null,
  );

  return (
    <Slide fill>
      <div className={styles.board}>
        <header className={styles.toolbar}>
          <Title />
          <MetricToggle
            label="Vista de E3"
            value={vista}
            onChange={setVista}
            options={[
              { id: "official", label: relato.views.official },
              { id: "sensitivity", label: relato.views.sensitivity },
            ]}
          />
        </header>

        {vista === "sensitivity" ? (
          presentation.sensitivity ? (
            <RecoverySensitivity view={presentation.sensitivity} />
          ) : (
            <EvidenceMissing />
          )
        ) : (
          <div className={styles.official}>
            <div className={styles.playback}>
              <div className={styles.transport} role="group" aria-label={relato.playback}>
                <button type="button" onClick={toggle} disabled={reduced} aria-pressed={playback.playing}>
                  {playback.playing ? relato.pause : relato.play}
                </button>
                <button type="button" onClick={playback.restart}>
                  {relato.restart}
                </button>
                <button type="button" onClick={previous}>
                  {relato.previousMark}
                </button>
                <button type="button" onClick={next}>
                  {relato.nextMark}
                </button>
                <span className={styles.speed} role="group" aria-label="Velocidad de presentación">
                  {([1, 2, 4] as const).map((velocidad) => (
                    <button
                      key={velocidad}
                      type="button"
                      disabled={reduced}
                      aria-pressed={playback.speed === velocidad}
                      onClick={() => playback.setSpeed(velocidad)}
                    >
                      {velocidad}×
                    </button>
                  ))}
                </span>
              </div>
              <p className={styles.playbackNote}>{reduced ? relato.reducedMotion : relato.playback}</p>
              <button type="button" aria-pressed={controles} onClick={() => setControles((actual) => !actual)}>
                {controles ? relato.controlsOff : relato.controlsOn}
              </button>
              <button
                type="button"
                aria-pressed={contexto}
                disabled={!scenario}
                onClick={() => setContexto((actual) => !actual)}
              >
                {contexto ? relato.contextOff : relato.contextOn}
              </button>
            </div>
            <p className={styles.hotkeys}>{relato.hotkeys}</p>
            {controles && official.controls ? <ControlsNote controls={official.controls} /> : null}
            {step ? (
              <p className={styles.narrative} aria-live="polite">
                <strong>{scopeLabel(step, official.sender, official.receiver)}</strong>
                <span>{step.displayTime}</span>
                {step.narrative}
              </p>
            ) : null}
            <RecoveryTimeline
              sender={official.sender}
              receiver={official.receiver}
              steps={steps}
              activeIndex={playback.index}
              sameLoss={official.sameLoss}
              focused={!contexto}
              domain={domain}
              previousReturn={returns.previous}
              nextReturn={returns.next}
              onSelect={playback.select}
            />
            {returns.previous && returns.next ? (
              <p className={styles.waiting}>
                {relato.waiting}{" "}
                <span className={styles.micro}>
                  Retorno previo {contactWindow(returns.previous)}. Próximo retorno{" "}
                  {contactWindow(returns.next)}. Las confirmaciones almacenadas caen dentro de ese
                  contacto siguiente.
                </span>
              </p>
            ) : null}
            <div className={styles.lower}>
              {contexto && scenario ? (
                <ContactTimeline scenario={scenario} variant="stage" />
              ) : (
                <RecoveryCompare sender={official.sender} receiver={official.receiver} />
              )}
            </div>
          </div>
        )}

        <footer className={styles.foot}>
          <DefenseCallout>
            {relato.phrase}
            <span className={styles.calloutSub}>{relato.returnLimit}</span>
          </DefenseCallout>
          <p className={styles.scope}>{relato.scope}</p>
          <div className={styles.links}>
            <LabLink to={relato.labPath}>{relato.labLinkLabel}</LabLink>
            <LabLink to={relato.sensitivityPath}>{relato.sensitivityLinkLabel}</LabLink>
          </div>
        </footer>
      </div>
    </Slide>
  );
}

function Title() {
  return (
    <h1 className={styles.title}>
      {relato.question.map((line) => (
        <span key={line}>{line}</span>
      ))}
    </h1>
  );
}

function ControlsNote({ controls }: { controls: RecoveryControlPair }) {
  if (controls.sameFinalState && controls.noRecoveryEpisodes) {
    return (
      <p className={styles.controls}>
        Sin falla, <strong>{controls.senderLabel}</strong> y <strong>{controls.receiverLabel}</strong> coinciden
        en el estado final y no generan episodios de recuperación. Persistencia {controls.completeness}.
        Confirmación {controls.confirmation}. Backlog {controls.backlog}. Episodios {controls.episodeCount}.
      </p>
    );
  }
  return (
    <p className={styles.controls}>
      {controls.senderLabel} y {controls.receiverLabel} no comparten el mismo estado final almacenado.
    </p>
  );
}

function scopeLabel(
  step: RecoveryPlaybackStep,
  sender: RecoveryTimelineRun,
  receiver: RecoveryTimelineRun,
): string {
  if (step.scopeLabel === "Misma pérdida" || step.scopeLabel === "Ambas corridas") {
    return step.scopeLabel;
  }
  if (step.scopeLabel === sender.label) {
    return `${sender.policyLabel} · ${sender.label}`;
  }
  if (step.scopeLabel === receiver.label) {
    return `${receiver.policyLabel} · ${receiver.label}`;
  }
  return step.scopeLabel;
}

function instants(
  sender: RecoveryTimelineRun,
  receiver: RecoveryTimelineRun,
  kind: RecoveryTimelineRun["events"][number]["kind"],
): number[] {
  return [...sender.events, ...receiver.events]
    .filter((event) => event.kind === kind)
    .map((event) => event.scientificSeconds);
}
