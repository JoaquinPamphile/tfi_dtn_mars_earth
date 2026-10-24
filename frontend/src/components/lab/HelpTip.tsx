import { useId, useState } from "react";
import { GLOSSARY, type GlossaryId } from "../../domain/lab";
import styles from "./lab.module.css";

export function HelpTip({
  id,
  children,
  iconOnly = false,
}: {
  id: GlossaryId;
  children?: string;
  iconOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const tipId = useId();
  const item = GLOSSARY[id];
  return (
    <span className={styles.term}>
      {iconOnly ? null : <span>{children ?? item.label}</span>}
      <button
        type="button"
        className={styles.tipButton}
        aria-expanded={open}
        aria-controls={tipId}
        onClick={() => setOpen((value) => !value)}
      >
        ?
        <span className="srOnly">Ayuda: {item.label}</span>
      </button>
      {open ? (
        <span id={tipId} className={styles.tip} role="note">
          {item.text}
        </span>
      ) : null}
    </span>
  );
}
