import { defenseContent } from "../../../defense/content";
import { DefenseCallout } from "../DefenseCallout";
import { DefenseNodeSequence } from "../DefenseNodeSequence";
import { Inequality, Slide } from "./slide";
import styles from "./slides.module.css";

const relato = defenseContent.coreIdea;

export function CoreIdeaStep() {
  const posee = relato.statement[0];
  const conoce = relato.statement[1];
  return (
    <Slide centered>
      <Inequality before={posee} mark={relato.inequality} after={conoce} heading />
      <div className={styles.planes}>
        <section className={styles.plane}>
          <h2 className={styles.planeTitle}>{relato.dataPlane.title}</h2>
          <DefenseNodeSequence nodes={relato.dataPlane.nodes} />
        </section>
        <section className={styles.plane}>
          <h2 className={styles.planeTitle}>{relato.knowledgePlane.title}</h2>
          <DefenseNodeSequence nodes={relato.knowledgePlane.nodes} />
        </section>
      </div>
      <div className={styles.milestones}>
        {relato.milestones.map((hito) => (
          <p key={hito.id} className={styles.milestone}>
            {hito.label}{" "}
            <span className={hito.pending ? styles.pending : styles.done} aria-hidden="true">
              {hito.mark}
            </span>
            <span className="srOnly">{hito.pending ? "pendiente" : "cumplido"}</span>
          </p>
        ))}
      </div>
      <DefenseCallout>{relato.phrase}</DefenseCallout>
    </Slide>
  );
}
