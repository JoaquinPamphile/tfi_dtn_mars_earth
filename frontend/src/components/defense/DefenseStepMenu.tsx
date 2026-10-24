import type { DefenseStep, DefenseStepId } from "../../defense/types";
import { defensePath } from "../../defense/defenseSteps";
import styles from "./DefenseStepMenu.module.css";
import { useEffect, useId, useRef } from "react";
import { Link } from "react-router-dom";

export function DefenseStepMenu({
  steps,
  currentId,
  open,
  onOpenChange,
}: {
  steps: readonly DefenseStep[];
  currentId: DefenseStepId;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const panelId = useId();
  const raiz = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }
    const alPulsar = (event: PointerEvent) => {
      if (!raiz.current?.contains(event.target as Node)) {
        onOpenChange(false);
      }
    };
    document.addEventListener("pointerdown", alPulsar);
    return () => document.removeEventListener("pointerdown", alPulsar);
  }, [onOpenChange, open]);

  return (
    <div className={styles.wrap} ref={raiz}>
      <button
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => onOpenChange(!open)}
      >
        Etapas
      </button>
      {open ? (
        <nav id={panelId} className={styles.panel} aria-label="Etapas de la defensa">
          <ol className={styles.list}>
            {steps.map((step) => {
              const actual = step.id === currentId;
              const clase = actual ? `${styles.link} ${styles.current}` : styles.link;
              return (
                <li key={step.id}>
                  <Link
                    className={clase}
                    to={defensePath(step.id)}
                    aria-current={actual ? "page" : undefined}
                    onClick={() => onOpenChange(false)}
                  >
                    <span className={styles.number}>{step.number}</span>
                    <span>{step.title}</span>
                  </Link>
                </li>
              );
            })}
          </ol>
        </nav>
      ) : null}
    </div>
  );
}
