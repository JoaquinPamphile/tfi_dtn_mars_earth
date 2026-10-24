import type { ReactNode } from "react";
import { FlowArrow } from "../scenario/FlowArrow";
import { usePinnedHover } from "../common/usePinnedHover";
import {
  STATE_NOTE,
  dataBlocks,
  lifecycleBlocks,
  lifecycleConcepts,
  returnBlocks,
  type LifecycleBlock,
} from "./lifecycle";
import styles from "./ApplicationLifecycle.module.css";

const PROMPT = "Elegí un bloque para ver su papel en el ciclo.";

export function ApplicationLifecycle() {
  const seleccion = usePinnedHover();
  const activo = lifecycleBlocks.find((bloque) => bloque.id === seleccion.active);

  return (
    <div className={styles.root}>
      <section className={styles.plane} data-plane="data" aria-label="Plano de datos, de MARS a EARTH">
        <header className={styles.planeHead}>
          <h2>Plano de datos</h2>
          <p>MARS → RELAY → EARTH</p>
        </header>
        <div className={styles.columns}>
          <Nodo codigo="MARS">
            <div className={styles.grid}>
              {dataBlocks.mars.map((bloque) => (
                <Bloque key={bloque.id} bloque={bloque} seleccion={seleccion.bind(bloque.id)} />
              ))}
            </div>
          </Nodo>
          <div className={styles.arrow}>
            <FlowArrow />
          </div>
          <Nodo codigo="RELAY">
            <Bloque bloque={dataBlocks.relay} seleccion={seleccion.bind(dataBlocks.relay.id)} />
          </Nodo>
          <div className={styles.arrow}>
            <FlowArrow />
          </div>
          <Nodo codigo="EARTH">
            <div className={styles.grid}>
              {dataBlocks.earth.map((bloque) => (
                <Bloque key={bloque.id} bloque={bloque} seleccion={seleccion.bind(bloque.id)} />
              ))}
            </div>
          </Nodo>
        </div>
      </section>

      <section
        className={styles.plane}
        data-plane="knowledge"
        aria-label="Plano de conocimiento y confirmación, de EARTH a MARS"
      >
        <header className={styles.planeHead}>
          <h2>Plano de conocimiento / confirmación</h2>
          <p>EARTH → RELAY → MARS</p>
        </header>
        <div className={styles.columns}>
          <Nodo codigo="MARS">
            <Bloque bloque={returnBlocks.mars} seleccion={seleccion.bind(returnBlocks.mars.id)} />
          </Nodo>
          <div className={styles.arrow}>
            <FlowArrow direction="back" />
          </div>
          <Nodo codigo="RELAY">
            <Bloque bloque={returnBlocks.relay} seleccion={seleccion.bind(returnBlocks.relay.id)} />
          </Nodo>
          <div className={styles.arrow}>
            <FlowArrow direction="back" />
          </div>
          <Nodo codigo="EARTH">
            <Bloque bloque={returnBlocks.earth} seleccion={seleccion.bind(returnBlocks.earth.id)} />
          </Nodo>
        </div>
      </section>

      <ul className={styles.concepts}>
        {lifecycleConcepts.map((concepto) => (
          <li key={concepto.id}>
            <Bloque
              bloque={{ id: concepto.id, label: concepto.label, state: null, summary: concepto.summary }}
              seleccion={seleccion.bind(concepto.id)}
              compact
            />
          </li>
        ))}
      </ul>

      <p className={styles.detail} data-empty={activo ? "false" : "true"}>
        {activo ? activo.summary : PROMPT}
      </p>
      <p className={styles.note}>{STATE_NOTE}</p>
    </div>
  );
}

function Nodo({ codigo, children }: { codigo: string; children: ReactNode }) {
  return (
    <div className={styles.cell}>
      <p className={styles.node}>{codigo}</p>
      {children}
    </div>
  );
}

function Bloque({
  bloque,
  seleccion,
  compact = false,
}: {
  bloque: LifecycleBlock;
  seleccion: ReturnType<ReturnType<typeof usePinnedHover>["bind"]>;
  compact?: boolean;
}) {
  const clase = compact ? `${styles.block} ${styles.compact}` : styles.block;
  return (
    <button type="button" className={clase} aria-label={etiqueta(bloque)} {...seleccion}>
      {bloque.state ? <span className={styles.state}>{bloque.state}</span> : null}
      <span className={styles.name}>{bloque.label}</span>
    </button>
  );
}

function etiqueta(bloque: LifecycleBlock): string {
  return bloque.state ? `${bloque.label}. ${bloque.state}. ${bloque.summary}` : `${bloque.label}. ${bloque.summary}`;
}
