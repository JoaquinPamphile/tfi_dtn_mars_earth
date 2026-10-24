import { GROUP_LABEL, GROUP_ORDER, LAB_METRICS, presentStored, type LabRun } from "../../domain/lab";
import { abbreviateHash } from "../../domain/format";
import styles from "./lab.module.css";

export function MetricCatalogPanel({ runs }: { runs: readonly LabRun[] }) {
  return (
    <div className={styles.stack}>
      <p className={styles.note}>
        Cada entrada es un campo almacenado. El valor original queda en el título de la celda o en el
        JSON de la corrida.
      </p>
      {GROUP_ORDER.map((group) => {
        const items = LAB_METRICS.filter((item) => item.group === group);
        return (
          <section key={group} className={styles.stack}>
            <h2>{GROUP_LABEL[group]}</h2>
            {items.map((item) => (
              <details key={item.id} className={styles.card}>
                <summary>
                  <strong>{item.name}</strong>
                  <span className={styles.mono}> {item.path}</span>
                </summary>
                <p className={styles.note}>{item.description}</p>
                <p className={styles.help}>Unidad: {item.unit}</p>
                <div className={styles.scroll}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th scope="col">Corrida</th>
                        <th scope="col">Valor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((run) => {
                        const shown = presentStored(item, run.metrics[item.id]);
                        const text =
                          item.kind === "text" && shown.text.length > 20
                            ? abbreviateHash(shown.text)
                            : shown.text;
                        return (
                          <tr key={run.uiReference}>
                            <th scope="row">{run.label}</th>
                            <td title={shown.title}>{text}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            ))}
          </section>
        );
      })}
    </div>
  );
}
