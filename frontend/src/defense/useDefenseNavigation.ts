import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { DEFENSE_STEPS, defensePath, defenseStepById, defenseStepIndex } from "./defenseSteps";
import type { DefenseNavigationState, DefenseStepId } from "./types";

export function useDefenseNavigation(stepId: string | undefined): DefenseNavigationState {
  const navigate = useNavigate();
  const step = defenseStepById(stepId);
  const index = defenseStepIndex(stepId);
  const total = DEFENSE_STEPS.length;

  const goTo = useCallback(
    (id: DefenseStepId) => {
      navigate(defensePath(id));
    },
    [navigate],
  );

  const goPrevious = useCallback(() => {
    if (index <= 0) {
      return;
    }
    const anterior = DEFENSE_STEPS[index - 1];
    if (anterior) {
      navigate(defensePath(anterior.id));
    }
  }, [index, navigate]);

  const goNext = useCallback(() => {
    if (index < 0 || index >= DEFENSE_STEPS.length - 1) {
      return;
    }
    const siguiente = DEFENSE_STEPS[index + 1];
    if (siguiente) {
      navigate(defensePath(siguiente.id));
    }
  }, [index, navigate]);

  const goFirst = useCallback(() => {
    const primera = DEFENSE_STEPS[0];
    if (primera) {
      navigate(defensePath(primera.id));
    }
  }, [navigate]);

  const goLast = useCallback(() => {
    const ultima = DEFENSE_STEPS[DEFENSE_STEPS.length - 1];
    if (ultima) {
      navigate(defensePath(ultima.id));
    }
  }, [navigate]);

  return {
    step,
    index,
    total,
    hasPrevious: index > 0,
    hasNext: index >= 0 && index < total - 1,
    goTo,
    goPrevious,
    goNext,
    goFirst,
    goLast,
  };
}
