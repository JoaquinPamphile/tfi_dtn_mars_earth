import { defenseContent } from "../../../defense/content";
import { DefenseCallout } from "../DefenseCallout";
import { LabLink, Slide, SlideTitle } from "./slide";
import styles from "./slides.module.css";

const relato = defenseContent.problem;

export function ProblemStep() {
  return (
    <Slide centered>
      <SlideTitle lines={relato.title} />
      <div className={styles.chain}>
        {relato.chain.map((item) =>
          item.kind === "place" ? (
            <p key={item.label} className={styles.place}>
              {item.label}
            </p>
          ) : (
            <p key={item.label} className={styles.transition}>
              ↓ {item.label}
            </p>
          ),
        )}
      </div>
      <ul className={styles.ideas}>
        {relato.ideas.map((idea) => (
          <li key={idea} className={styles.idea}>
            {idea}
          </li>
        ))}
      </ul>
      <DefenseCallout>{relato.phrase}</DefenseCallout>
      <LabLink to={relato.scenarioPath}>{relato.scenarioLabel}</LabLink>
    </Slide>
  );
}
