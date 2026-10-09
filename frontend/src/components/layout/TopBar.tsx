import { projectConfig } from "../../config/project";
import { StatusBadge } from "../common/StatusBadge";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./TopBar.module.css";

export function TopBar({
  menuOpen,
  onMenuToggle,
}: {
  menuOpen: boolean;
  onMenuToggle: () => void;
}) {
  return (
    <header className={styles.bar}>
      <div className={styles.left}>
        <button
          type="button"
          className={styles.menuButton}
          aria-expanded={menuOpen}
          aria-controls="navegacion-lateral"
          onClick={onMenuToggle}
        >
          <span className="srOnly">{menuOpen ? "Cerrar menú" : "Abrir menú"}</span>
          <MenuIcon open={menuOpen} />
        </button>
        <p className={styles.title}>{projectConfig.projectName}</p>
      </div>
      <div className={styles.actions}>
        <ThemeToggle />
        {projectConfig.readOnly ? (
          <StatusBadge tone="readonly">{projectConfig.headerBadge}</StatusBadge>
        ) : null}
      </div>
    </header>
  );
}

function MenuIcon({ open }: { open: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      {open ? (
        <path
          d="M4 4l10 10M14 4L4 14"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      ) : (
        <path
          d="M3 5h12M3 9h12M3 13h12"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      )}
    </svg>
  );
}
