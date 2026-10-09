import { useEvidence } from "../app/LabProvider";
import { InfoCard } from "../components/common/InfoCard";
import { SectionHeader } from "../components/common/SectionHeader";
import { projectConfig } from "../config/project";
import pageStyles from "../styles/page.module.css";
import styles from "./AboutPage.module.css";

const ALCANCE = [
  "El frontend no forma parte de la evidencia oficial.",
  "No implementa BPv7.",
  "No modifica campañas.",
];

const PROXIMAS = [
  "Lectura de evidence",
  "Explorador de corridas",
  "Timeline de contactos",
  "Métricas",
  "Visualización de recovery",
];

export function AboutPage() {
  const adapter = useEvidence();
  const release = adapter.getRelease();
  const source = adapter.getDataset().source;
  const modo = projectConfig.readOnly
    ? projectConfig.readOnlyLabel
    : projectConfig.scientificMode;

  return (
    <div className={pageStyles.page}>
      <SectionHeader
        title="Acerca"
        description="El Laboratorio DTN es una interfaz de exploración del TFI."
      />

      <InfoCard title="Identidad">
        <dl className={pageStyles.metaList}>
          <div>
            <dt>Backend científico</dt>
            <dd>{release.version}</dd>
          </div>
          <div>
            <dt>Modo</dt>
            <dd>{modo}</dd>
          </div>
          <div>
            <dt>source revision</dt>
            <dd className={pageStyles.mono}>{release.sourceRevision}</dd>
          </div>
          <div>
            <dt>Fuente de datos</dt>
            <dd>{source.label}</dd>
          </div>
        </dl>
        <p>{source.integrationNote}</p>
      </InfoCard>

      <InfoCard title="Alcance de esta interfaz">
        <ul className={styles.list}>
          {ALCANCE.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </InfoCard>

      <InfoCard title="Próximas capacidades">
        <ul className={`${styles.list} ${styles.upcoming}`}>
          {PROXIMAS.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </InfoCard>
    </div>
  );
}
