import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useDefenseMode } from "../../app/DefenseModeProvider";
import { useDefensePresenter } from "../../app/DefensePresenterProvider";
import { useDefenseKeyboard } from "../../defense/useDefenseKeyboard";
import type { DefenseNavigationState } from "../../defense/types";
import { DefenseFooter } from "./DefenseFooter";
import { DefenseHeader } from "./DefenseHeader";
import { DefenseStage } from "./DefenseStage";
import styles from "./DefenseLayout.module.css";

export function DefenseLayout({
  navigation,
  notesVisible,
  children,
}: {
  navigation: DefenseNavigationState;
  notesVisible: boolean;
  children: ReactNode;
}) {
  const step = navigation.step;
  const modo = useDefenseMode();
  const presenter = useDefensePresenter();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [escenario, setEscenario] = useState<HTMLElement | null>(null);
  const sincronizar = useRef(presenter.syncStep);
  sincronizar.current = presenter.syncStep;

  const cerrarMenu = useCallback(() => {
    setMenuAbierto(false);
  }, []);

  useDefenseKeyboard({
    menuOpen: menuAbierto,
    presenting: modo.presenting,
    fullscreen: modo.fullscreenActive,
    helpOpen: presenter.helpOpen && !modo.fullscreenActive,
    confirmOpen: presenter.confirmRestart && !modo.fullscreenActive,
    closeMenu: cerrarMenu,
    exitPresentation: modo.exitPresentation,
    goPrevious: navigation.goPrevious,
    goNext: navigation.goNext,
    goFirst: navigation.goFirst,
    goLast: navigation.goLast,
    togglePresenter: presenter.toggleEnabled,
    toggleTimer: presenter.toggleTimer,
    restartRehearsal: presenter.requestRehearsal,
    toggleHelp: presenter.toggleHelp,
    closeHelp: presenter.closeHelp,
    cancelRestart: presenter.cancelRestart,
  });

  useEffect(() => {
    setMenuAbierto(false);
  }, [step?.id]);

  useEffect(() => {
    if (step?.id) {
      sincronizar.current(step.id);
    }
  }, [step?.id]);

  if (!step || navigation.index < 0) {
    return null;
  }

  const presentar = () => {
    if (escenario) {
      void modo.enterPresentation(escenario);
    }
  };

  return (
    <DefenseStage
      stageRef={setEscenario}
      presenting={modo.presenting}
      label={`Defensa. ${step.title}`}
    >
      <p className="srOnly" aria-live="polite">
        {`Etapa ${step.number} de ${navigation.total}. ${step.title}.`}
      </p>
      <DefenseHeader
        step={step}
        index={navigation.index}
        total={navigation.total}
        presenting={modo.presenting}
        menuOpen={menuAbierto}
        onMenuOpenChange={setMenuAbierto}
        onPresent={presentar}
        onExit={modo.exitPresentation}
        showPrivateTools={!modo.fullscreenActive}
        presenterOn={presenter.enabled}
        notesVisible={notesVisible}
        onTogglePresenter={presenter.toggleEnabled}
        onRehearse={presenter.requestRehearsal}
        onShowHelp={presenter.openHelp}
      />
      <div className={styles.body}>
        <div className={styles.inner} data-defense-step={step.id}>
          {children}
        </div>
      </div>
      <DefenseFooter
        hasPrevious={navigation.hasPrevious}
        hasNext={navigation.hasNext}
        onPrevious={navigation.goPrevious}
        onNext={navigation.goNext}
      />
    </DefenseStage>
  );
}
