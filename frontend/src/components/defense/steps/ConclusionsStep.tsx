import { defenseContent } from "../../../defense/content";
import { DefenseMetric } from "../DefenseMetric";
import { Slide } from "./slide";
import styles from "./slides.module.css";

const relato = defenseContent.conclusions;

export function ConclusionsStep() {
  return (
    <Slide>
      <div className={styles.cards}>
        {relato.findings.map((hallazgo) => (
          <DefenseMetric key={hallazgo.id} kicker={hallazgo.id} title={hallazgo.title}>
            {hallazgo.lines.map((linea) => (
              <span key={linea} className={styles.cardLine}>
                {linea}
              </span>
            ))}
          </DefenseMetric>
        ))}
      </div>
      <h1 className={styles.closing}>
        {relato.closing.map((linea) => (
          <span key={linea} className={styles.closingLine}>
            {linea}
          </span>
        ))}
      </h1>
    </Slide>
  );
}
