import { useEffect } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useLabSession } from "../app/LabProvider";
import { SectionHeader } from "../components/common/SectionHeader";
import { EvidenceUnavailable } from "../components/experiments/EvidenceUnavailable";
import { Breadcrumbs } from "../components/lab/Breadcrumbs";
import { CompareView } from "../components/lab/CompareView";
import styles from "../components/lab/lab.module.css";
import { projectConfig } from "../config/project";
import pageStyles from "../styles/page.module.css";

export function CompareRunsPage() {
  const params = useParams();
  const [search] = useSearchParams();
  const experimentId = params.experimentId ?? "";
  const session = useLabSession();
  const detail =
    session.kind === "ready" ? session.adapter.getExperimentDetail(experimentId) : undefined;
  const indexes = (search.get("runs") ?? "")
    .split(",")
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item));
  const unique = [...new Set(indexes)].slice(0, 4);
  const runs =
    detail?.lab === null || detail?.lab === undefined
      ? []
      : unique.flatMap((index) => {
          const found = detail.lab?.runs.find((run) => run.index === index);
          return found ? [found] : [];
        });

  useEffect(() => {
    const titulo = detail ? `Comparar ${detail.code}` : "Comparar";
    document.title = `${titulo} · ${projectConfig.projectName}`;
  }, [detail]);

  if (session.kind === "unavailable") {
    return (
      <div className={pageStyles.page}>
        <EvidenceUnavailable error={session.error} />
      </div>
    );
  }

  if (!detail || !detail.lab || runs.length < 2) {
    return (
      <div className={pageStyles.page}>
        <SectionHeader
          title="Comparar corridas"
          description="Elegí entre 2 y 4 corridas del mismo experimento."
        />
        <Link to={detail ? `/experimentos/${detail.id}?tab=corridas` : "/experimentos"}>
          Volver a corridas
        </Link>
      </div>
    );
  }

  return (
    <div className={`${pageStyles.page} ${pageStyles.lab} ${styles.workspace}`}>
      <Breadcrumbs
        items={[
          { label: "Experimentos", to: "/experimentos" },
          { label: `${detail.code} — ${detail.name}`, to: `/experimentos/${detail.id}?tab=corridas` },
          { label: "Comparación" },
        ]}
      />
      <h1>Comparar {detail.code}</h1>
      <CompareView detail={detail} runs={runs} />
    </div>
  );
}
