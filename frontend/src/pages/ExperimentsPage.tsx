import { useEvidence } from "../app/LabProvider";
import { ExperimentCard } from "../components/experiments/ExperimentCard";
import { SectionHeader } from "../components/common/SectionHeader";
import pageStyles from "../styles/page.module.css";
import styles from "./ExperimentsPage.module.css";

export function ExperimentsPage() {
  const experimentos = useEvidence().getExperiments();

  return (
    <div className={pageStyles.page}>
      <SectionHeader
        title="Experimentos"
        description="Familias cerradas de la release. El detalle numérico queda para V0.1."
      />
      <div className={styles.grid}>
        {experimentos.map((experimento) => (
          <ExperimentCard key={experimento.id} experiment={experimento} />
        ))}
      </div>
    </div>
  );
}
