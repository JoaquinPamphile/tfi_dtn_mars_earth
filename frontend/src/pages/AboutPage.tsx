import { useLabSession } from "../app/LabProvider";
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

export function AboutPage() {
  const session = useLabSession();
  const lista = session.kind === "ready";
  const release = lista ? session.adapter.getRelease() : null;
  const source = lista ? session.adapter.getDataset().source : null;
  const modo = projectConfig.readOnly ? projectConfig.readOnlyLabel : projectConfig.scientificMode;
  const capacidades = [
    ["Lectura de evidence", lista ? "COMPLETA" : "NO DISPONIBLE"],
    ["Explorador de corridas", lista ? "METADATOS V0.1" : "NO DISPONIBLE"],
    ["Timeline de contactos", "Futuro"],
    ["Métricas", "Futuro"],
    ["Visualización de recovery", "Futuro"],
  ] as const;

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
            <dd>{release?.version ?? projectConfig.releaseVersion}</dd>
          </div>
          <div>
            <dt>Modo</dt>
            <dd>{modo}</dd>
          </div>
          <div>
            <dt>source revision</dt>
            <dd className={pageStyles.mono}>{release?.sourceRevision ?? projectConfig.sourceRevision}</dd>
          </div>
          <div>
            <dt>Fuente de datos</dt>
            <dd>{source?.label ?? "NO DISPONIBLE"}</dd>
          </div>
        </dl>
        {source ? <p>{source.integrationNote}</p> : null}
        {session.kind === "unavailable" ? (
          <p>
            {session.error.name}: {session.error.message}
          </p>
        ) : null}
      </InfoCard>

      <InfoCard title="Alcance de esta interfaz">
        <ul className={styles.list}>
          {ALCANCE.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </InfoCard>

      <InfoCard title="Capacidades">
        <dl className={pageStyles.metaList}>
          {capacidades.map(([nombre, estado]) => (
            <div key={nombre}>
              <dt>{nombre}</dt>
              <dd className={estado === "Futuro" ? styles.future : undefined}>{estado}</dd>
            </div>
          ))}
        </dl>
      </InfoCard>
    </div>
  );
}
