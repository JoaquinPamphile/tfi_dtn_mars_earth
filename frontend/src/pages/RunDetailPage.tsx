import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useLabSession } from "../app/LabProvider";
import { SectionHeader } from "../components/common/SectionHeader";
import { EvidenceUnavailable } from "../components/experiments/EvidenceUnavailable";
import { Breadcrumbs } from "../components/lab/Breadcrumbs";
import { RunDetailView } from "../components/lab/RunDetailView";
import styles from "../components/lab/lab.module.css";
import { projectConfig } from "../config/project";
import { findLabRun, loadLabel, strategyLabel } from "../domain/lab";
import pageStyles from "../styles/page.module.css";

export function RunDetailPage() {
  const params = useParams();
  const experimentId = params.experimentId ?? "";
  const runRef = params.runRef ?? "";
  const session = useLabSession();
  const detail =
    session.kind === "ready" ? session.adapter.getExperimentDetail(experimentId) : undefined;
  const run = detail?.lab ? findLabRun(detail.lab, experimentId, runRef) : undefined;

  useEffect(() => {
    const titulo = run && detail ? `${detail.code} · ${run.label}` : "Corrida";
    document.title = `${titulo} · ${projectConfig.projectName}`;
  }, [detail, run]);

  if (session.kind === "unavailable") {
    return (
      <div className={pageStyles.page}>
        <EvidenceUnavailable error={session.error} />
      </div>
    );
  }

  if (!detail || !detail.lab || !run) {
    return (
      <div className={pageStyles.page}>
        <SectionHeader
          title="Corrida"
          description="Esa referencia de UI no está en la evidence RC1 de este experimento."
        />
        <Link to="/experimentos">Volver a experimentos</Link>
      </div>
    );
  }

  const tratamiento = [
    run.config.offeredLoadFraction !== null ? loadLabel(run.config.offeredLoadFraction) : null,
    strategyLabel(run.config.strategyType, run.config.batchSizeEvents),
  ]
    .filter((item) => item && item !== "—")
    .join(" · ");

  return (
    <div className={`${pageStyles.page} ${pageStyles.lab} ${styles.workspace}`}>
      <Breadcrumbs
        items={[
          { label: "Experimentos", to: "/experimentos" },
          { label: `${detail.code} — ${detail.name}`, to: `/experimentos/${detail.id}` },
          { label: tratamiento || run.label },
        ]}
      />
      <h1>
        {detail.code} · {run.label}
      </h1>
      <p className={styles.help}>
        UI_REFERENCE {run.uiReference}. No es un SCIENTIFIC_RUN_ID.
      </p>
      <RunDetailView detail={detail} run={run} />
    </div>
  );
}
