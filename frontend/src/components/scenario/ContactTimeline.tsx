import type { DirectedContact, GenerationSpan, ScenarioDefinition } from "../../domain/scenario";
import { formatDataRate, formatSimSeconds } from "../../domain/scenarioFormat";
import { usePinnedHover } from "../common/usePinnedHover";
import styles from "./ContactTimeline.module.css";

const PROMPT = "Elegí un contacto para ver inicio, fin, duración, tasa y procedencia.";

export function ContactTimeline({
  scenario,
  variant = "stage",
}: {
  scenario: ScenarioDefinition;
  variant?: "stage" | "detail";
}) {
  const seleccion = usePinnedHover();
  const contacto = findContact(scenario, seleccion.active);
  const generacionActiva = seleccion.active === "generation";
  const detalle = contacto
    ? contactDetail(contacto, variant)
    : generacionActiva && scenario.generation
      ? generationDetail(scenario.generation)
      : PROMPT;

  return (
    <div className={styles.timeline} data-variant={variant}>
      <div className={styles.tracks}>
      <div className={styles.axis}>
        <span />
        <div className={styles.ticks} aria-hidden="true">
          {ticks(scenario.horizonSeconds).map((marca, index, todas) => (
            <span key={marca}>
              {formatSimSeconds(marca).replace(/ s$/, index === todas.length - 1 ? " s" : "")}
            </span>
          ))}
        </div>
      </div>

      {scenario.generation ? (
        <div className={styles.row}>
          <div className={styles.rowLabel}>
            <span className={styles.route}>Generación</span>
            <span className={styles.meta}>
              <span className={styles.badge} data-kind="generation">
                {scenario.generation.campaignNote}
              </span>
              <span>{formatSimSeconds(scenario.generation.periodSeconds)}</span>
            </span>
          </div>
          <div className={styles.track}>
            <button
              type="button"
              className={`${styles.bar} ${styles.generation}`}
              style={placement(
                scenario.generation.startSeconds,
                scenario.generation.lastEventSeconds,
                scenario.horizonSeconds,
              )}
              aria-label={generationDetail(scenario.generation)}
              {...seleccion.bind("generation")}
            />
          </div>
        </div>
      ) : null}

      {scenario.links.map((enlace) => (
        <div key={enlace.id} className={styles.row}>
          <div className={styles.rowLabel}>
            <span className={styles.route}>{enlace.label}</span>
            <span className={styles.meta}>
              <span className={styles.badge} data-kind={enlace.direction}>
                {enlace.direction === "return" ? "retorno" : "ida"}
              </span>
              <span>{enlace.contacts.length}</span>
            </span>
          </div>
          <div className={styles.track}>
            {enlace.contacts.map((contactoItem) => (
              <button
                key={contactoItem.id}
                type="button"
                className={styles.bar}
                data-provenance={contactoItem.provenance}
                style={placement(contactoItem.startSeconds, contactoItem.endSeconds, scenario.horizonSeconds)}
                aria-label={contactDetail(contactoItem, variant)}
                {...seleccion.bind(contactoItem.id)}
              />
            ))}
          </div>
        </div>
      ))}
      </div>

      <div className={styles.legend}>
        <span className={styles.legendItem}>
          <i className={`${styles.swatch} ${styles.swatchForward}`} aria-hidden="true" />
          Ida · fuente aproximada / transformada
        </span>
        <span className={styles.legendItem}>
          <i className={`${styles.swatch} ${styles.swatchReturn}`} aria-hidden="true" />
          Retorno · supuesto TFI
        </span>
        {scenario.generation ? (
          <span className={styles.legendItem}>
            <i className={`${styles.swatch} ${styles.swatchGeneration}`} aria-hidden="true" />
            Generación de carga
          </span>
        ) : null}
      </div>

      <p className={styles.detail} data-empty={seleccion.active ? "false" : "true"}>
        {detalle}
      </p>
    </div>
  );
}

function findContact(scenario: ScenarioDefinition, id: string | null): DirectedContact | null {
  if (!id) {
    return null;
  }
  for (const enlace of scenario.links) {
    const contacto = enlace.contacts.find((item) => item.id === id);
    if (contacto) {
      return contacto;
    }
  }
  return null;
}

function placement(start: number, end: number, horizon: number): { left: string; width: string } {
  const left = (start / horizon) * 100;
  const width = ((end - start) / horizon) * 100;
  return { left: `${left}%`, width: `${Math.max(width, 0)}%` };
}

function ticks(horizon: number): number[] {
  return [0, 0.25, 0.5, 0.75, 1].map((fraccion) => horizon * fraccion);
}

function contactDetail(contacto: DirectedContact, variant: "stage" | "detail"): string {
  const duracion = contacto.endSeconds - contacto.startSeconds;
  const partes = [
    `${contacto.source} → ${contacto.destination}`,
    `inicio ${formatSimSeconds(contacto.startSeconds)}`,
    `fin ${formatSimSeconds(contacto.endSeconds)}`,
    `duración ${formatSimSeconds(duracion)}`,
    formatDataRate(contacto.dataRateBps),
    contacto.provenanceLabel,
  ];
  if (variant === "detail") {
    partes.push(`demora ${formatSimSeconds(contacto.propagationDelaySeconds)}`);
  }
  return partes.join(" · ");
}

function generationDetail(generacion: GenerationSpan): string {
  return [
    `Generación de carga ${generacion.workloadId}`,
    generacion.campaignNote,
    `inicio ${formatSimSeconds(generacion.startSeconds)}`,
    `último evento ${formatSimSeconds(generacion.lastEventSeconds)}`,
    `período ${formatSimSeconds(generacion.periodSeconds)}`,
    "derivado del perfil congelado, no de una corrida",
  ].join(" · ");
}
