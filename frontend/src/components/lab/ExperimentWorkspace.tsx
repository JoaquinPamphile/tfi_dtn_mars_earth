import { Link, useSearchParams } from "react-router-dom";
import type { ExperimentDetail, ScientificRelease } from "../../domain";
import { defenseHref } from "../../domain/lab";
import { StatusBadge } from "../common/StatusBadge";
import { presentationLabel, presentationTone } from "../../domain/presentation";
import { Breadcrumbs } from "./Breadcrumbs";
import { HelpTip } from "./HelpTip";
import { ChartsPanel } from "./ChartsPanel";
import { EvidencePanel } from "./EvidencePanel";
import { MetricCatalogPanel } from "./MetricCatalogPanel";
import { ReproPanel } from "./ReproPanel";
import { RunsPanel } from "./RunsPanel";
import { SummaryPanel } from "./SummaryPanel";
import styles from "./lab.module.css";

const TABS = [
  { id: "resumen", label: "Resumen" },
  { id: "corridas", label: "Corridas" },
  { id: "graficos", label: "Gráficos" },
  { id: "metricas", label: "Métricas" },
  { id: "evidence", label: "Evidence" },
  { id: "repro", label: "Reproducibilidad" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export function ExperimentWorkspace({
  detail,
  release,
}: {
  detail: ExperimentDetail;
  release: ScientificRelease;
}) {
  const [params] = useSearchParams();
  const tab = parseTab(params.get("tab"));
  const runs = detail.lab?.runs ?? [];

  return (
    <div className={styles.workspace}>
      <Breadcrumbs
        items={[
          { label: "Experimentos", to: "/experimentos" },
          { label: `${detail.code} — ${detail.name}` },
        ]}
      />
      <header className={styles.head}>
        <div>
          <h1>
            {detail.code} — {detail.name}
          </h1>
          <p className={styles.note}>{detail.objective}</p>
        </div>
        <div className={styles.actions}>
          <StatusBadge tone={presentationTone(detail.presentation)}>
            {presentationLabel(detail.presentation)}
          </StatusBadge>
          <Link className={styles.button} to={defenseHref(detail.id)}>
            Ver en Defensa
          </Link>
        </div>
      </header>
      <nav aria-label="Secciones del experimento">
        <ul className={styles.tabs}>
          {TABS.map((item) => (
            <li key={item.id}>
              <Link className={styles.tab} to={tabHref(detail.id, item.id, params)} aria-current={tab === item.id ? "page" : undefined}>
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <p className={styles.help}>
        <HelpTip id="syncunit" />
        {" · "}
        <HelpTip id="applicationAck" />
        {" · "}
        <HelpTip id="backlog" />
        {" · "}
        <HelpTip id="gap" />
        {" · "}
        <HelpTip id="offeredLoad" />
        {" · "}
        <HelpTip id="contactUtilization" />
        {" · "}
        <HelpTip id="freshnessCoverage" />
        {" · "}
        <HelpTip id="ttc" />
        {" · "}
        <HelpTip id="mu" />
        {" · "}
        <HelpTip id="sender" />
        {" · "}
        <HelpTip id="receiver" />
      </p>
      {tab === "resumen" ? <SummaryPanel detail={detail} /> : null}
      {tab === "corridas" ? <RunsPanel experimentId={detail.id} runs={runs} /> : null}
      {tab === "graficos" ? <ChartsPanel detail={detail} /> : null}
      {tab === "metricas" ? <MetricCatalogPanel runs={runs} /> : null}
      {tab === "evidence" ? <EvidencePanel detail={detail} /> : null}
      {tab === "repro" ? <ReproPanel detail={detail} release={release} /> : null}
    </div>
  );
}

function parseTab(value: string | null): TabId {
  return TABS.some((item) => item.id === value) ? (value as TabId) : "resumen";
}

function tabHref(experimentId: string, tab: TabId, current: URLSearchParams): string {
  const next = new URLSearchParams(current);
  if (tab === "resumen") {
    next.delete("tab");
  } else {
    next.set("tab", tab);
  }
  const query = next.toString();
  return query ? `/experimentos/${experimentId}?${query}` : `/experimentos/${experimentId}`;
}
