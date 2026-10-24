import { defenseContent } from "../../../defense/content";
import { ArchitectureLayers } from "../../architecture/ArchitectureLayers";
import { Slide, SlideTitle } from "./slide";

const relato = defenseContent.architecture;

export function ArchitectureStep() {
  return (
    <Slide fill>
      <SlideTitle lines={relato.title} />
      <ArchitectureLayers />
    </Slide>
  );
}
