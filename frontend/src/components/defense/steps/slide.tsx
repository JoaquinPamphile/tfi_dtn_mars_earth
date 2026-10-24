import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useLabSession } from "../../../app/LabProvider";
import type { EvidenceAdapter } from "../../../adapters";
import { StatusBadge } from "../../common/StatusBadge";
import { presentationLabel, presentationTone } from "../../../domain";
import { formatRunCount, type ExperimentFacts } from "../../../defense/evidenceFacts";
import styles from "./slides.module.css";

export function useEvidenceAdapter(): EvidenceAdapter | null {
  const session = useLabSession();
  return session.kind === "ready" ? session.adapter : null;
}

export function SlideTitle({ lines }: { lines: readonly string[] }) {
  return (
    <h1 className={styles.title}>
      {lines.map((line, index) => (
        <span key={`${index}-${line}`} className={styles.titleLine}>
          {line}
        </span>
      ))}
    </h1>
  );
}

export function Inequality({
  before,
  mark,
  after,
  heading = false,
}: {
  before: string;
  mark: string;
  after: string;
  heading?: boolean;
}) {
  const contenido = (
    <>
      <span className={styles.statementLine}>{before}</span>
      <span className={styles.neq} aria-hidden="true">
        {mark}
      </span>
      <span className="srOnly">distinto de</span>
      <span className={styles.statementLine}>{after}</span>
    </>
  );
  if (heading) {
    return <h1 className={styles.statement}>{contenido}</h1>;
  }
  return <p className={styles.statement}>{contenido}</p>;
}

export function EvidenceStrip({ facts }: { facts: ExperimentFacts }) {
  return (
    <div className={styles.strip}>
      <StatusBadge size="stage" tone={presentationTone(facts.presentation)}>
        {presentationLabel(facts.presentation)}
      </StatusBadge>
      <p className={styles.stripText}>
        <span className={styles.stripCode}>{facts.code}</span>
        <span>{facts.campaignId}</span>
        <span>{facts.role}</span>
        <span>{formatRunCount(facts.runCount)}</span>
      </p>
    </div>
  );
}

export function EvidenceMissing() {
  return (
    <p className={styles.missing} role="status">
      Evidence RC1 no disponible.
    </p>
  );
}

export function LabLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link className={styles.labLink} to={to}>
      {children}
    </Link>
  );
}

export function Slide({
  children,
  centered = false,
  fill = false,
}: {
  children: ReactNode;
  centered?: boolean;
  fill?: boolean;
}) {
  const clase = [styles.slide, centered ? styles.center : "", fill ? styles.fill : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={clase} data-defense-visual={fill ? "fill" : undefined}>
      {children}
    </div>
  );
}
