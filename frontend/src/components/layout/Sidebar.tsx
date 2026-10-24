import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../app/navigation";
import { useLabSession } from "../../app/LabProvider";
import { projectConfig } from "../../config/project";
import styles from "./Sidebar.module.css";

export function Sidebar({ open, hidden }: { open: boolean; hidden: boolean }) {
  const session = useLabSession();
  const release =
    session.kind === "ready" ? session.adapter.getRelease() : null;
  const source = session.kind === "ready" ? session.adapter.getDataset().source : null;
  const clase = open ? `${styles.sidebar} ${styles.open}` : styles.sidebar;
  const version = release?.version ?? projectConfig.releaseVersion;

  return (
    <aside className={clase} aria-hidden={hidden} inert={hidden ? true : undefined}>
      <div className={styles.brand}>
        <p className={styles.name}>{projectConfig.projectName}</p>
        <p className={styles.version}>{version}</p>
      </div>
      <nav className={styles.nav} aria-label="Secciones" id="navegacion-lateral">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              isActive ? `${styles.link} ${styles.active}` : styles.link
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <footer className={styles.footer}>
        <p className={styles.footerLabel}>Fuente de datos</p>
        <p className={styles.footerValue}>{source?.label ?? "NO DISPONIBLE"}</p>
        <p className={styles.footerLabel}>Estado</p>
        <p className={styles.footerValue}>
          {source?.stateLabel ?? projectConfig.readOnlyStateLabel}
        </p>
        {source?.artifactCount != null && source.runCount != null ? (
          <p className={styles.footerNote}>
            {source.artifactCount} artifacts · {source.runCount} runs
          </p>
        ) : session.kind === "unavailable" ? (
          <p className={styles.footerNote}>{session.error.name}</p>
        ) : null}
      </footer>
    </aside>
  );
}
