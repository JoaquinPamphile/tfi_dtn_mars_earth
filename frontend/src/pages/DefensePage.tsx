import { Navigate, useParams } from "react-router-dom";
import { DefenseWorkspace } from "../components/defense/presenter/DefenseWorkspace";
import { ApplicationModelStep } from "../components/defense/steps/ApplicationModelStep";
import { ArchitectureStep } from "../components/defense/steps/ArchitectureStep";
import { ConclusionsStep } from "../components/defense/steps/ConclusionsStep";
import { CoreIdeaStep } from "../components/defense/steps/CoreIdeaStep";
import { E1Step } from "../components/defense/steps/E1Step";
import { E2Step } from "../components/defense/steps/E2Step";
import { E3Step } from "../components/defense/steps/E3Step";
import { ProblemStep } from "../components/defense/steps/ProblemStep";
import { ScenarioStep } from "../components/defense/steps/ScenarioStep";
import { ValidityStep } from "../components/defense/steps/ValidityStep";
import { defensePath } from "../defense/defenseSteps";
import { useDefenseNavigation } from "../defense/useDefenseNavigation";
import type { DefenseStepId } from "../defense/types";

function StepView({ id }: { id: DefenseStepId }) {
  switch (id) {
    case "problem":
      return <ProblemStep />;
    case "core-idea":
      return <CoreIdeaStep />;
    case "application-model":
      return <ApplicationModelStep />;
    case "architecture":
      return <ArchitectureStep />;
    case "scenario":
      return <ScenarioStep />;
    case "e1":
      return <E1Step />;
    case "e2":
      return <E2Step />;
    case "e3":
      return <E3Step />;
    case "validity":
      return <ValidityStep />;
    case "conclusions":
      return <ConclusionsStep />;
    default: {
      const desconocida: never = id;
      return desconocida;
    }
  }
}

export function DefensePage() {
  const params = useParams();
  const navigation = useDefenseNavigation(params.stepId);
  if (!navigation.step) {
    return <Navigate to={defensePath("problem")} replace />;
  }
  return (
    <DefenseWorkspace navigation={navigation}>
      <StepView id={navigation.step.id} />
    </DefenseWorkspace>
  );
}
