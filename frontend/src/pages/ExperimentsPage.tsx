import { useLabSession } from "../app/LabProvider";
import { EvidenceUnavailable } from "../components/experiments/EvidenceUnavailable";
import { ExperimentCard } from "../components/experiments/ExperimentCard";
import { SectionHeader } from "../components/common/SectionHeader";
import pageStyles from "../styles/page.module.css";
import styles from "./ExperimentsPage.module.css";

export function ExperimentsPage() {
  const session = useLabSession();
  if (session.kind === "unavailable") {
    return (
      <div className={pageStyles.page}>
        <EvidenceUnavailable error={session.error} />
      </div>
    );
  }

  const experimentos = session.adapter.getExperiments();

  return (
    <div className={`${pageStyles.page} ${pageStyles.lab}`}>
      <SectionHeader
        title="Experimentos"
        description="Laboratorio de la evidence RC1. Cada familia abre diseño, corridas, gráficos, métricas, procedencia y reproducibilidad."
      />
      <div className={styles.grid}>
        {experimentos.map((experimento) => (
          <ExperimentCard key={experimento.id} experiment={experimento} />
        ))}
      </div>
    </div>
  );
}
