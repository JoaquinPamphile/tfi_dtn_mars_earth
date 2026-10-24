import { Fragment, useEffect, useId, useRef } from "react";
import { useDefensePresenter } from "../../../app/DefensePresenterProvider";
import { DEFENSE_SHORTCUTS } from "../../../defense/keyboard";
import styles from "./presenter.module.css";

export function PresenterOverlays() {
  const presenter = useDefensePresenter();
  return (
    <>
      {presenter.helpOpen ? <ShortcutHelp onClose={presenter.closeHelp} /> : null}
      {presenter.confirmRestart ? (
        <RestartDialog onCancel={presenter.cancelRestart} onConfirm={presenter.confirmRestartNow} />
      ) : null}
    </>
  );
}

function ShortcutHelp({ onClose }: { onClose: () => void }) {
  const titulo = useId();
  const cierre = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cierre.current?.focus();
  }, []);

  return (
    <div className={styles.overlay} data-defense-overlay="help" onMouseDown={onClose}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titulo}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id={titulo}>Atajos de defensa</h2>
        <dl className={styles.shortcuts}>
          {DEFENSE_SHORTCUTS.map((atajo) => (
            <Fragment key={atajo.keys}>
              <dt>{atajo.keys}</dt>
              <dd>{atajo.label}</dd>
            </Fragment>
          ))}
        </dl>
        <div className={styles.dialogActions}>
          <button ref={cierre} type="button" className={styles.primary} onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

function RestartDialog({ onCancel, onConfirm }: { onCancel: () => void; onConfirm: () => void }) {
  const titulo = useId();
  const cancelar = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelar.current?.focus();
  }, []);

  return (
    <div className={styles.overlay} data-defense-overlay="restart" onMouseDown={onCancel}>
      <div
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titulo}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <h2 id={titulo}>Reiniciar ensayo</h2>
        <p>Hay un ensayo en curso. Volver a Problema pone el cronómetro en cero.</p>
        <div className={styles.dialogActions}>
          <button ref={cancelar} type="button" className={styles.textButton} onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" className={styles.primary} onClick={onConfirm}>
            Reiniciar
          </button>
        </div>
      </div>
    </div>
  );
}
