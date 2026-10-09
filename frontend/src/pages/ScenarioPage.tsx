import { Fragment } from "react";
import { FlowArrow } from "../components/scenario/FlowArrow";
import { ScenarioNode } from "../components/scenario/ScenarioNode";
import { SectionHeader } from "../components/common/SectionHeader";
import pageStyles from "../styles/page.module.css";
import styles from "./ScenarioPage.module.css";

const NODOS = [
  { code: "MARS", role: "Fuente de telemetría" },
  { code: "RELAY", role: "Almacenamiento y reenvío" },
  { code: "EARTH", role: "Persistencia / aceptación" },
] as const;

const PLANO_DATOS = ["MARS", "RELAY", "EARTH"] as const;
const PLANO_CONFIRMACION = ["EARTH", "RELAY", "MARS"] as const;

export function ScenarioPage() {
  return (
    <div className={pageStyles.page}>
      <SectionHeader
        title="Escenario"
        description="Representación conceptual del sistema. Sin ventanas de contacto y sin tráfico simulado."
      />

      <div className={styles.topology}>
        {NODOS.map((nodo, index) => (
          <Fragment key={nodo.code}>
            {index > 0 ? (
              <div className={styles.connector}>
                <FlowArrow />
              </div>
            ) : null}
            <div className={styles.nodeSlot}>
              <ScenarioNode code={nodo.code} role={nodo.role} />
            </div>
          </Fragment>
        ))}
      </div>
      <p className={styles.note}>El enlace entre los nodos admite dos sentidos de información.</p>

      <div className={styles.planes}>
        <section className={styles.plane}>
          <h2>Plano de datos</h2>
          <Recorrido pasos={PLANO_DATOS} />
          <p className={styles.caption}>
            La telemetría avanza desde el origen hacia la persistencia terrestre.
          </p>
        </section>

        <section className={styles.plane}>
          <div className={styles.planeHead}>
            <h2>Plano de conocimiento / confirmación</h2>
            <span className={styles.ack}>ApplicationAck</span>
          </div>
          <Recorrido pasos={PLANO_CONFIRMACION} />
          <p className={styles.caption}>
            La confirmación recorre el camino de regreso hacia el origen.
          </p>
        </section>
      </div>

      <aside className={styles.callout}>
        <h2>Tierra posee ≠ Marte conoce</h2>
        <p>
          La persistencia terrestre puede producirse antes de que la confirmación
          regrese al origen.
        </p>
      </aside>
    </div>
  );
}

function Recorrido({ pasos }: { pasos: readonly string[] }) {
  return (
    <div className={styles.flow}>
      {pasos.map((paso, index) => (
        <Fragment key={paso}>
          {index > 0 ? <FlowArrow /> : null}
          <span className={styles.step}>{paso}</span>
        </Fragment>
      ))}
    </div>
  );
}
