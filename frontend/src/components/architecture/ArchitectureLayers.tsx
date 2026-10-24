import { usePinnedHover } from "../common/usePinnedHover";
import { ARCHITECTURE_LEAD, architectureFlow, architectureLayers } from "./layers";
import styles from "./ArchitectureLayers.module.css";

export function ArchitectureLayers() {
  const seleccion = usePinnedHover();
  const capa = architectureLayers.find((item) => item.id === seleccion.active) ?? null;
  const haySeleccion = capa !== null;

  return (
    <div className={styles.root}>
      <div className={styles.stack} data-selected={haySeleccion ? "true" : "false"}>
        {architectureLayers.map((capaItem, index) => {
          const atenuada = haySeleccion && capa?.id !== capaItem.id;
          return (
            <div key={capaItem.id} className={styles.slot}>
              {index > 0 ? <span className={styles.joint} aria-hidden="true" /> : null}
              <button
                type="button"
                className={styles.layer}
                data-layer={capaItem.id}
                data-attenuated={atenuada ? "true" : "false"}
                aria-label={`${capaItem.spoken}. ${capaItem.technical}. ${capaItem.items.join(", ")}`}
                {...seleccion.bind(capaItem.id)}
              >
                <span className={styles.identity}>
                  <span className={styles.spoken}>{capaItem.spoken}</span>
                  {capaItem.spoken !== capaItem.technical ? (
                    <span className={styles.technical}>{capaItem.technical}</span>
                  ) : null}
                </span>
                <span className={styles.items}>{capaItem.items.join(" · ")}</span>
              </button>
            </div>
          );
        })}
      </div>

      <ol className={styles.flow} aria-label="Recorrido de una corrida">
        {architectureFlow.map((paso, index) => {
          const caliente = !haySeleccion || (capa?.flowIds.includes(paso.id) ?? false);
          return (
            <li key={paso.id} className={styles.flowStep} data-hot={caliente ? "true" : "false"}>
              {index > 0 ? (
                <span className={styles.flowArrow} aria-hidden="true">
                  →
                </span>
              ) : null}
              <span>{paso.label}</span>
            </li>
          );
        })}
      </ol>

      <div className={styles.responsibility}>
        <p className={styles.kicker}>Responsabilidad{capa ? ` · ${capa.spoken}` : ""}</p>
        <p className={styles.text}>{capa ? capa.responsibility : ARCHITECTURE_LEAD}</p>
      </div>
    </div>
  );
}
