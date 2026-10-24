import { defenseContent } from "../../../defense/content";
import { ApplicationLifecycle } from "../../model/ApplicationLifecycle";
import { Slide, SlideTitle } from "./slide";

const relato = defenseContent.applicationModel;

export function ApplicationModelStep() {
  return (
    <Slide fill>
      <SlideTitle lines={relato.title} />
      <ApplicationLifecycle />
    </Slide>
  );
}
