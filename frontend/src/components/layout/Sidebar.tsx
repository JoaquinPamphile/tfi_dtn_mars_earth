import { NavLink } from "react-router-dom";
import { NAV_ITEMS } from "../../app/navigation";
import { useEvidence } from "../../app/LabProvider";
import { projectConfig } from "../../config/project";
import styles from "./Sidebar.module.css";

export function Sidebar({ open, hidden }: { open: boolean; hidden: boolean }) {
  const adapter = useEvidence();
  const release = adapter.getRelease();
  const source = adapter.getDataset().source;
  const clase = open ? `${styles.sidebar} ${styles.open}` : styles.sidebar;

  return (
    <aside className={clase} aria-hidden={hidden} inert={hidden ? true : undefined}>
      <div className={styles.brand}>
        <p className={styles.name}>{projectConfig.projectName}</p>
        <p className={styles.version}>{release.version}</p>
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
        <p className={styles.footerValue}>{source.label}</p>
        <p className={styles.footerNote}>{source.integrationNote}</p>
      </footer>
    </aside>
  );
}
