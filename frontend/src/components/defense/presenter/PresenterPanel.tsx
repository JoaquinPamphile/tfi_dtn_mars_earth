import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useDefensePresenter } from "../../../app/DefensePresenterProvider";
import { DEFENSE_STEPS } from "../../../defense/defenseSteps";
import type { StoredRehearsal } from "../../../defense/rehearsal";
import { speakerNotesFor } from "../../../defense/speakerNotes";
import {
  exposureMarginMs,
  formatClock,
  formatMinutesInput,
  formatSignedDuration,
  MAX_TOTAL_DURATION_MS,
  MIN_TOTAL_DURATION_MS,
  paceLabel,
  paceOf,
} from "../../../defense/timing";
import { clockRead, type ClockStatus } from "../../../defense/timer";
import type { DefenseStep } from "../../../defense/types";
import styles from "./presenter.module.css";

export function PresenterPanel({ step, index }: { step: DefenseStep; index: number }) {
  const presenter = useDefensePresenter();
  const now = useTickingNow(presenter.clock.status === "running");
  const read = clockRead(presenter.clock, now);
  const notes = speakerNotesFor(step.id);
  const target = presenter.targets[step.id];
  const margin = exposureMarginMs({
    ledger: presenter.ledger,
    currentId: step.id,
    currentElapsedMs: read.stageMs,
    targets: presenter.targets,
  });
  const pace = paceOf(margin);
  const siguiente = DEFENSE_STEPS[index + 1];
  const enMarcha = presenter.clock.status === "running";

  return (
    <aside id="notas-del-presentador" className={styles.panel} aria-label="Notas del presentador" data-presenter-panel="">
      <div className={styles.head}>
        <div className={styles.identity}>
          <div>
            <p className={styles.kicker}>Notas privadas</p>
            <p className={styles.stepTitle}>
              {step.number} · {step.title}
            </p>
          </div>
          <button type="button" className={styles.textButton} onClick={presenter.collapse}>
            Ocultar
          </button>
        </div>
        <p className={styles.nextStep}>{siguiente ? `Siguiente: ${siguiente.title}` : "Última etapa"}</p>
        <p className={styles.pace} data-pace={pace} data-defense-pace={pace}>
          <b>{paceLabel(pace)}</b>
          {pace === "on-time" ? null : <span>{formatSignedDuration(margin)}</span>}
        </p>
        <dl className={styles.clocks} data-defense-timer={presenter.clock.status}>
          <div>
            <dt>Etapa</dt>
            <dd>
              {formatClock(read.stageMs)} / {formatClock(target)}
            </dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd>
              {formatClock(read.totalMs)} / {formatClock(presenter.totalDurationMs)}
            </dd>
          </div>
        </dl>
        <p className={styles.session}>
          {presenter.rehearsalActive ? "Ensayo en curso. " : ""}
          {estadoReloj(presenter.clock.status)}. Tiempo de exposición, no de la simulación.
        </p>
        <div className={styles.controls}>
          <button type="button" onClick={presenter.toggleTimer} disabled={enMarcha}>
            Iniciar
          </button>
          <button type="button" onClick={presenter.toggleTimer} disabled={!enMarcha}>
            Pausar
          </button>
          <button type="button" onClick={presenter.resetTimer} title="Poner el cronómetro en cero">
            Reiniciar
          </button>
          {presenter.rehearsalActive ? (
            <button type="button" className={styles.primary} onClick={presenter.finishRehearsal}>
              Finalizar ensayo
            </button>
          ) : (
            <button type="button" className={styles.primary} onClick={presenter.requestRehearsal}>
              Ensayar defensa
            </button>
          )}
        </div>
      </div>
      <div className={styles.scroll}>
        {presenter.summary ? (
          <section className={styles.block} aria-label="Resumen del ensayo" data-rehearsal-summary="">
            <h3>Resumen del ensayo</h3>
            <p>Duración total {formatClock(presenter.summary.totalMs)}</p>
            <h3>Tiempo por etapa</h3>
            <ul className={styles.summaryList}>
              {presenter.summary.stages.map((etapa) => (
                <li key={etapa.stepId}>
                  {etapa.title}: {formatClock(etapa.elapsedMs)} / {formatClock(etapa.targetMs)}
                </li>
              ))}
            </ul>
            <h3>Etapas sobre objetivo</h3>
            <StageNames stages={presenter.summary.overTarget.map((etapa) => etapa.title)} empty="Ninguna" />
            <h3>Etapas bajo objetivo</h3>
            <StageNames stages={presenter.summary.underTarget.map((etapa) => etapa.title)} empty="Ninguna" />
            <button type="button" className={styles.quiet} onClick={presenter.dismissSummary}>
              Cerrar resumen
            </button>
          </section>
        ) : null}

        <section className={styles.block}>
          <h3>Objetivo</h3>
          <p>{notes.objective}</p>
        </section>
        <section className={styles.block}>
          <h3>Qué decir</h3>
          <ul>
            {notes.say.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className={styles.block}>
          <h3>No olvidar</h3>
          <ul>
            {notes.remember.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        {notes.transition ? (
          <section className={styles.block}>
            <h3>Siguiente transición</h3>
            <p className={styles.transition}>{notes.transition}</p>
          </section>
        ) : null}
        {notes.closing ? (
          <section className={`${styles.block} ${styles.closing}`} aria-label="Cierre recomendado">
            <h3>Cierre recomendado</h3>
            <ol>
              {notes.closing.ideas.map((idea) => (
                <li key={idea}>{idea}</li>
              ))}
            </ol>
            <p className={styles.phrase}>{notes.closing.phrase}</p>
          </section>
        ) : null}
        <section className={styles.block}>
          <h3>Preguntas probables</h3>
          {notes.questions.map((pregunta) => (
            <details key={pregunta.prompt} className={styles.question}>
              <summary>{pregunta.prompt}</summary>
              <p className={styles.answer}>{pregunta.answer}</p>
              {pregunta.links && pregunta.links.length > 0 ? (
                <div className={styles.links}>
                  {pregunta.links.map((link) => (
                    <Link key={`${link.href}-${link.label}`} className={styles.link} to={link.href}>
                      {link.label}
                    </Link>
                  ))}
                </div>
              ) : null}
            </details>
          ))}
        </section>

        <DurationField totalMs={presenter.totalDurationMs} onCommit={presenter.setTotalDurationMs} />
        <label className={styles.save}>
          <input
            type="checkbox"
            checked={presenter.saveHistory}
            onChange={(event) => presenter.setSaveHistory(event.target.checked)}
          />
          Guardar el ensayo en este navegador
        </label>
        <History history={presenter.history} />
      </div>
    </aside>
  );
}

function StageNames({ stages, empty }: { stages: readonly string[]; empty: string }) {
  if (stages.length === 0) {
    return <p>{empty}</p>;
  }
  return (
    <ul className={styles.summaryList}>
      {stages.map((nombre) => (
        <li key={nombre}>{nombre}</li>
      ))}
    </ul>
  );
}

function History({ history }: { history: readonly StoredRehearsal[] }) {
  return (
    <section className={styles.block}>
      <h3>Ensayos recientes</h3>
      {history.length === 0 ? <p className={styles.note}>Todavía no hay ensayos guardados en este navegador.</p> : null}
      {history.map((ensayo) => (
        <details key={ensayo.finishedAt} className={styles.history}>
          <summary>
            {fechaLocal(ensayo.finishedAt)} · {formatClock(ensayo.totalMs)}
          </summary>
          <ul className={styles.historyList}>
            {DEFENSE_STEPS.map((etapa) => {
              const elapsed = ensayo.stages.find((item) => item.stepId === etapa.id)?.elapsedMs ?? 0;
              return (
                <li key={etapa.id}>
                  {etapa.title}: {formatClock(elapsed)}
                </li>
              );
            })}
          </ul>
        </details>
      ))}
    </section>
  );
}

function DurationField({ totalMs, onCommit }: { totalMs: number; onCommit: (totalMs: number) => void }) {
  const [draft, setDraft] = useState(() => formatMinutesInput(totalMs));

  useEffect(() => {
    setDraft(formatMinutesInput(totalMs));
  }, [totalMs]);

  const confirmar = () => {
    const parsed = Number(draft.replace(",", ".").trim());
    if (!Number.isFinite(parsed)) {
      setDraft(formatMinutesInput(totalMs));
      return;
    }
    onCommit(parsed * 60_000);
  };

  return (
    <label className={styles.duration}>
      Objetivo total
      <input
        type="number"
        min={MIN_TOTAL_DURATION_MS / 60_000}
        max={MAX_TOTAL_DURATION_MS / 60_000}
        step={1}
        inputMode="numeric"
        value={draft}
        aria-label="Duración objetivo total, en minutos"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={confirmar}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.currentTarget.blur();
          }
        }}
      />
      <span>min</span>
    </label>
  );
}

function estadoReloj(status: ClockStatus): string {
  if (status === "running") {
    return "En marcha";
  }
  if (status === "paused") {
    return "En pausa";
  }
  return "Detenido";
}

function fechaLocal(iso: string): string {
  const fecha = new Date(iso);
  if (Number.isNaN(fecha.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" }).format(fecha);
}

function useTickingNow(running: boolean): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setNow(Date.now());
    if (!running) {
      return;
    }
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [running]);

  return now;
}
