import { useLabSession } from "../app/LabProvider";
import { InfoCard } from "../components/common/InfoCard";
import { SectionHeader } from "../components/common/SectionHeader";
import { StatusBadge } from "../components/common/StatusBadge";
import { EvidenceUnavailable } from "../components/experiments/EvidenceUnavailable";
import { projectConfig } from "../config/project";
import pageStyles from "../styles/page.module.css";
import styles from "./HomePage.module.css";

function enumerar(items: string[]): string {
  if (items.length <= 1) {
    return items[0] ?? "";
  }
  return `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`;
}

export function HomePage() {
  const session = useLabSession();
  const modo = projectConfig.readOnly ? projectConfig.readOnlyLabel : projectConfig.scientificMode;

  if (session.kind === "unavailable") {
    return (
      <div className={pageStyles.page}>
        <SectionHeader
          title={projectConfig.projectName}
          description={projectConfig.subtitle}
          addon={
            projectConfig.readOnly ? (
              <StatusBadge tone="readonly">{projectConfig.homeBadge}</StatusBadge>
            ) : undefined
          }
        />
        <EvidenceUnavailable error={session.error} />
      </div>
    );
  }

  const dataset = session.adapter.getDataset();
  const release = dataset.release;
  const source = dataset.source;
  const codigos = enumerar(dataset.experiments.map((item) => item.code));
  const familias =
    dataset.experiments.length === 1 ? "1 familia." : `${dataset.experiments.length} familias.`;
  const corridas = source.runCount === 1 ? "1 corrida." : `${source.runCount ?? 0} corridas.`;

  return (
    <div className={pageStyles.page}>
      <SectionHeader
        title={projectConfig.projectName}
        description={projectConfig.subtitle}
        addon={
          projectConfig.readOnly ? (
            <StatusBadge tone="readonly">{projectConfig.homeBadge}</StatusBadge>
          ) : undefined
        }
      />
      <p className={styles.lede}>
        El laboratorio visualiza la evidencia científica congelada. No modifica el backend ni las
        campañas.
      </p>
      <div className={styles.grid}>
        <InfoCard title="Escenario" to="/escenario">
          <p>MARS, RELAY y EARTH. Vista conceptual de los planos de datos y de confirmación.</p>
        </InfoCard>
        <InfoCard title="Experimentos" to="/experimentos">
          <p>
            {codigos}. {familias} {corridas}
          </p>
        </InfoCard>
        <InfoCard title="Release científica">
          <dl className={pageStyles.metaList}>
            <div>
              <dt>Versión</dt>
              <dd>{release.version}</dd>
            </div>
            <div>
              <dt>source revision</dt>
              <dd className={pageStyles.mono}>{release.sourceRevision}</dd>
            </div>
          </dl>
        </InfoCard>
        <InfoCard title="Estado del laboratorio">
          <dl className={pageStyles.metaList}>
            <div>
              <dt>Modo</dt>
              <dd>{modo}</dd>
            </div>
            <div>
              <dt>Fuente de datos</dt>
              <dd>{source.label}</dd>
            </div>
          </dl>
          <p>{source.integrationNote}</p>
        </InfoCard>
      </div>
    </div>
  );
}
