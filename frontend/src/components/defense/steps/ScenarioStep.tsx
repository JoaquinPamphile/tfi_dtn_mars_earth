import { scenarioSession } from "../../../adapters";
import { defenseContent } from "../../../defense/content";
import { ScenarioExhibit } from "../../scenario/ScenarioExhibit";
import { Slide, SlideTitle } from "./slide";
import styles from "./slides.module.css";

const relato = defenseContent.scenario;

export function ScenarioStep() {
  if (scenarioSession.kind !== "ready") {
    return (
      <Slide fill>
        <SlideTitle lines={relato.title} />
        <p className={styles.missing} role="status">
          {scenarioSession.error.message}
        </p>
      </Slide>
    );
  }
  return (
    <Slide fill>
      <SlideTitle lines={relato.title} />
      <ScenarioExhibit scenario={scenarioSession.scenario} variant="stage" />
    </Slide>
  );
}
