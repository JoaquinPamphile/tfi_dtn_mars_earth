import { ThemeToggle } from "../layout/ThemeToggle";
import { DefenseProgress } from "./DefenseProgress";
import { DefenseStepMenu } from "./DefenseStepMenu";
import type { DefenseStep } from "../../defense/types";
import { DEFENSE_STEPS } from "../../defense/defenseSteps";
import styles from "./DefenseHeader.module.css";

export function DefenseHeader({
  step,
  index,
  total,
  presenting,
  menuOpen,
  onMenuOpenChange,
  onPresent,
  onExit,
  showPrivateTools,
  presenterOn,
  notesVisible,
  onTogglePresenter,
  onRehearse,
  onShowHelp,
}: {
  step: DefenseStep;
  index: number;
  total: number;
  presenting: boolean;
  menuOpen: boolean;
  onMenuOpenChange: (open: boolean) => void;
  onPresent: () => void;
  onExit: () => void;
  showPrivateTools: boolean;
  presenterOn: boolean;
  notesVisible: boolean;
  onTogglePresenter: () => void;
  onRehearse: () => void;
  onShowHelp: () => void;
}) {
  return (
    <header className={styles.header}>
      <div className={styles.row}>
        <p className={styles.count}>
          <span>{step.number}</span>
          <span className={styles.total}> / {total}</span>
        </p>
        <div className={styles.actions}>
          <DefenseStepMenu
            steps={DEFENSE_STEPS}
            currentId={step.id}
            open={menuOpen}
            onOpenChange={onMenuOpenChange}
          />
          {presenting ? (
            <button type="button" className={styles.present} onClick={onExit}>
              Salir de presentación
            </button>
          ) : (
            <button type="button" className={styles.present} onClick={onPresent}>
              Presentar
            </button>
          )}
          {showPrivateTools ? (
            <>
              <button
                type="button"
                className={`${styles.present} ${styles.privateTool}`}
                aria-pressed={presenterOn}
                aria-expanded={notesVisible}
                aria-controls={notesVisible ? "notas-del-presentador" : undefined}
                title="Presentador (P)"
                onClick={onTogglePresenter}
              >
                Presentador
              </button>
              <button
                type="button"
                className={`${styles.present} ${styles.privateTool}`}
                title="Ensayar defensa (R)"
                onClick={onRehearse}
              >
                Ensayar defensa
              </button>
              <button
                type="button"
                className={`${styles.present} ${styles.privateTool} ${styles.icon}`}
                title="Atajos (?)"
                aria-label="Atajos de defensa"
                onClick={onShowHelp}
              >
                ?
              </button>
            </>
          ) : null}
          {presenting ? <ThemeToggle /> : null}
        </div>
        <p className={styles.section}>{step.section}</p>
      </div>
      <DefenseProgress current={index + 1} total={total} />
    </header>
  );
}
