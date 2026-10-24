import type { ScenarioDefinition } from "../../domain/scenario";
import { ContactTimeline } from "./ContactTimeline";
import styles from "./ScenarioExhibit.module.css";

export function ScenarioExhibit({
  scenario,
  variant = "stage",
}: {
  scenario: ScenarioDefinition;
  variant?: "stage" | "detail";
}) {
  return (
    <div className={styles.exhibit} data-variant={variant}>
      <p className={styles.route} aria-label="Topología lógica">
        {scenario.nodes.map((nodo, index) => (
          <span key={nodo.id} className={styles.routePart}>
            {index > 0 ? <span className={styles.routeArrow}>→</span> : null}
            <span>{nodo.label}</span>
          </span>
        ))}
      </p>
      <div className={styles.chart}>
        <ContactTimeline scenario={scenario} variant={variant} />
      </div>
      <ul className={styles.parameters}>
        {scenario.parameters.map((parametro) => (
          <li key={parametro.id} className={styles.parameter}>
            <p className={styles.kicker}>{parametro.label}</p>
            <p className={styles.value}>{parametro.value}</p>
            <p className={styles.caption}>{parametro.detail}</p>
          </li>
        ))}
      </ul>
      <div className={styles.provenance}>
        {scenario.figureNote ? <p className={styles.figure}>{scenario.figureNote}</p> : null}
        <p className={styles.entries}>
          {scenario.provenance.map((entrada, index) => (
            <span key={entrada.id}>
              {index > 0 ? <span className={styles.dot}>·</span> : null}
              <span className={styles.term}>{entrada.term}</span> {entrada.meaning}
            </span>
          ))}
        </p>
        {scenario.limitNote ? <p className={styles.limit}>{scenario.limitNote}</p> : null}
        <p className={styles.source}>{scenario.sourceNote}</p>
      </div>
    </div>
  );
}
