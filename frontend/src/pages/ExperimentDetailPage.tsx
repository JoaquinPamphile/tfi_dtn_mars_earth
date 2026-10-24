import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useLabSession } from "../app/LabProvider";
import { ExperimentWorkspace } from "../components/lab/ExperimentWorkspace";
import { SectionHeader } from "../components/common/SectionHeader";
import { EvidenceUnavailable } from "../components/experiments/EvidenceUnavailable";
import { projectConfig } from "../config/project";
import pageStyles from "../styles/page.module.css";
import styles from "./ExperimentDetailPage.module.css";

export function ExperimentDetailPage() {
  const params = useParams();
  const experimentId = params.experimentId ?? "";
  const session = useLabSession();
  const detail =
    session.kind === "ready" ? session.adapter.getExperimentDetail(experimentId) : undefined;

  useEffect(() => {
    const titulo = detail ? `${detail.code} — ${detail.name}` : "Experimento";
    document.title = `${titulo} · ${projectConfig.projectName}`;
  }, [detail]);

  if (session.kind === "unavailable") {
    return (
      <div className={pageStyles.page}>
        <EvidenceUnavailable error={session.error} />
      </div>
    );
  }

  if (!detail || !detail.identity || !detail.lab) {
    return (
      <div className={pageStyles.page}>
        <SectionHeader
          title="Experimento"
          description="Ese identificador no está en la evidence RC1 cargada."
        />
        <Link className={styles.back} to="/experimentos">
          Volver a experimentos
        </Link>
      </div>
    );
  }

  return (
    <div className={`${pageStyles.page} ${pageStyles.lab}`}>
      <ExperimentWorkspace detail={detail} release={session.adapter.getRelease()} />
    </div>
  );
}
