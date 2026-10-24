import { useState } from "react";
import type { ExperimentDetail } from "../../domain";
import { catalogStoredCount } from "../../domain/lab";
import { HashValue } from "../experiments/HashValue";
import styles from "./lab.module.css";

export function EvidencePanel({ detail }: { detail: ExperimentDetail }) {
  const lab = detail.lab;
  const identidad = detail.identity;
  const [onlyHidden, setOnlyHidden] = useState(false);
  if (!lab || !identidad) {
    return null;
  }
  const counts = catalogStoredCount(lab);
  const rows = onlyHidden ? lab.audit.filter((row) => !row.shown) : lab.audit;
  const hidden = lab.audit.filter((row) => !row.shown).length;

  return (
    <div className={styles.stack}>
      <section className={styles.card}>
        <h2>Paquete</h2>
        <dl className={styles.meta}>
          <Item label="artifact file" value={detail.locator.logicalPath} mono />
          <Item label="artifact UUID" value={identidad.campaignIdentity} hash />
          <Item label="campaign identity" value={identidad.campaignIdentity} hash />
          <Item label="campaign id" value={identidad.campaignId} mono />
          <Item label="family" value={identidad.family} />
          <Item label="role" value={identidad.role} />
          <Item label="schema version" value={lab.evidenceSchemaVersion} />
          <Item label="manifest schema" value={lab.manifestSchemaVersion} />
          <Item label="software version" value={identidad.softwareVersion} />
          <Item label="source revision" value={identidad.sourceRevision} mono />
          <Item label="source state" value={lab.sourceState} />
          <Item label="campaign status" value={detail.campaignStatus ?? "—"} />
          <Item label="run count" value={String(detail.runCount)} />
          <Item label="hash" value={lab.hashAlgorithm} />
        </dl>
        <p className={styles.help}>
          Catálogo científico con valor presente: {counts.present}. De esos, {counts.numeric} tienen
          un número en al menos una corrida. Los null almacenados, como un TTC ausente, cuentan como
          presentes.
        </p>
      </section>
      <section className={styles.card}>
        <h2>Relación con el manifiesto</h2>
        {detail.locator.provenancePath ? (
          <p className={styles.note}>
            Manifest <span className={styles.mono}>{detail.locator.provenancePath}</span>
            {" → "}
            Evidence package{" "}
            <span className={styles.mono}>
              {detail.locator.evidenceFileRef ?? detail.locator.logicalPath}
            </span>
          </p>
        ) : (
          <p className={styles.note}>
            El artifact funciona como paquete completo; no existe evidence_file separado.
          </p>
        )}
        <p className={styles.help}>Los paths son lógicos del repositorio. No son rutas del equipo.</p>
      </section>
      <section className={styles.card}>
        <h2>Auditoría de metrics</h2>
        <p className={styles.note}>
          {lab.audit.length} hojas detectadas en metrics, incluidos los escalares de episodio. {hidden}{" "}
          quedan solo en el JSON.
        </p>
        <button type="button" className={styles.ghost} aria-pressed={onlyHidden} onClick={() => setOnlyHidden((value) => !value)}>
          {onlyHidden ? "Ver todas las hojas" : "Ver solo las no expuestas"}
        </button>
        <div className={styles.scroll}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Campo</th>
                <th scope="col">En la UI</th>
                <th scope="col">Dónde</th>
                <th scope="col">Motivo si no se muestra</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.field}>
                  <td className={styles.mono}>{row.field}</td>
                  <td>{row.shown ? "sí" : "no"}</td>
                  <td>{row.surface}</td>
                  <td>{row.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Item({
  label,
  value,
  mono,
  hash,
}: {
  label: string;
  value: string;
  mono?: boolean;
  hash?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={mono ? styles.mono : undefined}>
        {hash ? <HashValue value={value} label={label} variant="full" /> : value}
      </dd>
    </div>
  );
}
