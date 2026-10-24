import { StatusBadge } from "../../common/StatusBadge";
import { presentationLabel } from "../../../domain";
import { defenseContent } from "../../../defense/content";
import { releaseFacts } from "../../../defense/evidenceFacts";
import { EvidenceMissing, Slide, useEvidenceAdapter } from "./slide";
import styles from "./slides.module.css";

const relato = defenseContent.validity;

export function ValidityStep() {
  const adapter = useEvidenceAdapter();
  const release = adapter ? releaseFacts(adapter) : null;

  return (
    <Slide>
      <div className={styles.columns}>
        <section className={styles.column}>
          <h2 className={styles.columnTitle}>{relato.canTitle}</h2>
          <ul className={styles.list}>
            {relato.canAffirm.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
        <section className={styles.column}>
          <h2 className={styles.columnTitle}>{relato.cannotTitle}</h2>
          <ul className={styles.list}>
            {relato.cannotUniversalize.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      </div>
      {release ? (
        <div className={styles.release}>
          <p className={styles.version}>{release.version}</p>
          <p className={styles.revision}>
            <span>{relato.revisionLabel} </span>
            <span title={release.sourceRevision} aria-label={release.sourceRevision}>
              {release.abbreviatedRevision}
            </span>
          </p>
          {release.canonical ? (
            <StatusBadge size="stage" tone="canonical">
              {presentationLabel("rc1-canonical")}
            </StatusBadge>
          ) : null}
        </div>
      ) : (
        <EvidenceMissing />
      )}
    </Slide>
  );
}
