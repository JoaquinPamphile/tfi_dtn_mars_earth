import type { ReactNode } from "react";
import { useDefenseMode } from "../../../app/DefenseModeProvider";
import { useDefensePresenter } from "../../../app/DefensePresenterProvider";
import type { DefenseNavigationState } from "../../../defense/types";
import { DefenseLayout } from "../DefenseLayout";
import { PresenterOverlays } from "./PresenterOverlays";
import { PresenterPanel } from "./PresenterPanel";
import styles from "./presenter.module.css";

/**
 * El panel queda fuera del elemento que entra en fullscreen.
 * Así la pantalla pública no muestra notas, y al salir vuelven si el modo sigue activo.
 */
export function DefenseWorkspace({
  navigation,
  children,
}: {
  navigation: DefenseNavigationState;
  children: ReactNode;
}) {
  const modo = useDefenseMode();
  const presenter = useDefensePresenter();
  const paso = navigation.step;
  const panelVisible = presenter.enabled && !presenter.collapsed && !modo.fullscreenActive;
  const rielVisible = presenter.enabled && presenter.collapsed && !modo.fullscreenActive;

  return (
    <div className={styles.workspace}>
      <div className={styles.stageSlot}>
        <DefenseLayout navigation={navigation} notesVisible={panelVisible}>
          {children}
        </DefenseLayout>
      </div>
      {panelVisible && paso ? <PresenterPanel step={paso} index={navigation.index} /> : null}
      {rielVisible ? (
        <button type="button" className={styles.rail} onClick={presenter.expand}>
          Notas
        </button>
      ) : null}
      {modo.fullscreenActive ? null : <PresenterOverlays />}
    </div>
  );
}
