import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import type { LabRun } from "../../domain/lab";
import { loadLabel, storedNumber, strategyLabel } from "../../domain/lab";
import { LabRunTable } from "./LabRunTable";
import styles from "./lab.module.css";
import { PRESET_LABEL, parsePreset, type PresetId } from "./runColumns";

const MAX = 4;

export function RunsPanel({ experimentId, runs }: { experimentId: string; runs: readonly LabRun[] }) {
  const [params, setParams] = useSearchParams();
  const preset = parsePreset(params.get("cols"));
  const selected = parseIndexes(params.get("cmp"));
  const filtered = runs.filter((run) => matches(run, params, experimentId));
  const loads = unique(runs.map((run) => run.config.offeredLoadFraction).filter((item): item is number => item !== null));
  const strategies = unique(runs.map((run) => run.config.strategyType));
  const sequences = unique(
    runs.flatMap((run) => run.config.failure.sequences.map((item) => String(item))),
  );
  const policies = unique(runs.map((run) => run.config.recoveryPolicy));

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (!value) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setParams(next, { replace: true });
  }

  function setPreset(value: PresetId) {
    setParam("cols", value === "basico" ? "" : value);
  }

  function toggle(index: number) {
    const next = new URLSearchParams(params);
    const current = parseIndexes(next.get("cmp"));
    const exists = current.includes(index);
    const updated = exists ? current.filter((item) => item !== index) : [...current, index].slice(0, MAX);
    if (!exists && current.length >= MAX) {
      return;
    }
    if (updated.length === 0) {
      next.delete("cmp");
    } else {
      next.set("cmp", updated.join(","));
    }
    setParams(next, { replace: true });
  }

  const compareTo =
    selected.length >= 2 ? `/experimentos/${experimentId}/comparar?runs=${selected.join(",")}` : "";

  return (
    <div className={styles.stack}>
      <div className={styles.toolbar}>
        <label className={styles.field}>
          <span>Buscar</span>
          <input
            value={params.get("q") ?? ""}
            onChange={(event) => setParam("q", event.target.value)}
            placeholder="Etiqueta, hash, política"
          />
        </label>
        {experimentId === "e2" ? (
          <>
            <Select label="Carga" value={params.get("load") ?? ""} onChange={(value) => setParam("load", value)}>
              <option value="">Todas</option>
              {loads.map((load) => (
                <option key={load} value={String(load)}>
                  {loadLabel(load)}
                </option>
              ))}
            </Select>
            <Select
              label="Estrategia"
              value={params.get("strategy") ?? ""}
              onChange={(value) => setParam("strategy", value)}
            >
              <option value="">Todas</option>
              {strategies.map((item) => (
                <option key={item} value={item}>
                  {strategyLabel(item, null)}
                </option>
              ))}
            </Select>
            <Select
              label="Convergió"
              value={params.get("converged") ?? ""}
              onChange={(value) => setParam("converged", value)}
            >
              <option value="">Todas</option>
              <option value="si">sí</option>
              <option value="no">no</option>
            </Select>
            <Select
              label="Tierra completa"
              value={params.get("earth") ?? ""}
              onChange={(value) => setParam("earth", value)}
            >
              <option value="">Todas</option>
              <option value="si">completitud = 1</option>
              <option value="no">completitud &lt; 1</option>
            </Select>
            <Select
              label="Origen confirmado"
              value={params.get("origin") ?? ""}
              onChange={(value) => setParam("origin", value)}
            >
              <option value="">Todas</option>
              <option value="si">confirmación = 1</option>
              <option value="no">confirmación &lt; 1</option>
            </Select>
          </>
        ) : null}
        {experimentId === "e3-sensitivity" ? (
          <>
            <Select
              label="Secuencia"
              value={params.get("seq") ?? ""}
              onChange={(value) => setParam("seq", value)}
            >
              <option value="">Todas</option>
              {sequences.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
            <Select
              label="Política"
              value={params.get("policy") ?? ""}
              onChange={(value) => setParam("policy", value)}
            >
              <option value="">Todas</option>
              {policies.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </Select>
          </>
        ) : null}
      </div>
      <div className={styles.toolbar} role="group" aria-label="Columnas visibles">
        <span className={styles.legend}>Columnas visibles</span>
        {(Object.keys(PRESET_LABEL) as PresetId[]).map((item) => (
          <button
            key={item}
            type="button"
            className={item === preset ? styles.button : styles.ghost}
            aria-pressed={item === preset}
            onClick={() => setPreset(item)}
          >
            {PRESET_LABEL[item]}
          </button>
        ))}
      </div>
      <p className={styles.note}>
        {filtered.length} de {runs.length} corridas. La referencia de cada fila es UI_REFERENCE, no un
        identificador científico. gaps = 0 no implica completitud.
      </p>
      <div className={styles.actions}>
        {compareTo ? (
          <Link className={styles.button} to={compareTo}>
            Comparar {selected.length} corridas
          </Link>
        ) : (
          <button type="button" className={styles.button} disabled>
            Comparar corridas
          </button>
        )}
        <span className={styles.help}>Elegí entre 2 y 4 corridas de este experimento.</span>
      </div>
      {filtered.length === 0 ? (
        <p className={styles.note}>Ninguna corrida coincide con el filtro.</p>
      ) : (
        <LabRunTable
          experimentId={experimentId}
          runs={filtered}
          preset={preset}
          selected={selected}
          onToggle={toggle}
        />
      )}
      <p className={styles.help}>En pantallas angostas la tabla se desplaza dentro de este recuadro.</p>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className={styles.field}>
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function matches(run: LabRun, params: URLSearchParams, experimentId: string): boolean {
  const query = (params.get("q") ?? "").trim().toLowerCase();
  if (query) {
    const haystack = [run.label, run.configurationHash, run.datasetFingerprint, run.config.recoveryPolicy, run.uiReference]
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(query)) {
      return false;
    }
  }
  if (experimentId === "e2") {
    const load = params.get("load");
    if (load && String(run.config.offeredLoadFraction) !== load) {
      return false;
    }
    const strategy = params.get("strategy");
    if (strategy && run.config.strategyType !== strategy) {
      return false;
    }
    const converged = params.get("converged");
    if (converged) {
      const value = run.metrics.converged;
      const flag = value?.status === "stored" && value.value === true;
      if (converged === "si" && !flag) {
        return false;
      }
      if (converged === "no" && flag) {
        return false;
      }
    }
    const earth = params.get("earth");
    if (earth && !ratioFlag(storedNumber(run, "completeness"), earth)) {
      return false;
    }
    const origin = params.get("origin");
    if (origin && !ratioFlag(storedNumber(run, "confirmation_ratio"), origin)) {
      return false;
    }
  }
  if (experimentId === "e3-sensitivity") {
    const sequence = params.get("seq");
    if (sequence && !run.config.failure.sequences.map(String).includes(sequence)) {
      return false;
    }
    const policy = params.get("policy");
    if (policy && run.config.recoveryPolicy !== policy) {
      return false;
    }
  }
  return true;
}

function ratioFlag(value: number | null, flag: string): boolean {
  if (value === null) {
    return false;
  }
  if (flag === "si") {
    return value === 1;
  }
  if (flag === "no") {
    return value < 1;
  }
  return true;
}

function parseIndexes(value: string | null): number[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item))
    .slice(0, MAX);
}

function unique<T>(values: T[]): T[] {
  return [...new Set(values)];
}
