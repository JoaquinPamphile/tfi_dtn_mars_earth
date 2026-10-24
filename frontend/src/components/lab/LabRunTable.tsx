import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import type { LabRun } from "../../domain/lab";
import { HashValue } from "../experiments/HashValue";
import { HelpTip } from "./HelpTip";
import styles from "./lab.module.css";
import { columnById, columnsFor, type ColumnId, type PresetId } from "./runColumns";

export function LabRunTable({
  experimentId,
  runs,
  preset,
  selected,
  onToggle,
}: {
  experimentId: string;
  runs: readonly LabRun[];
  preset: PresetId;
  selected: readonly number[];
  onToggle: (index: number) => void;
}) {
  const columns = columnsFor(preset, runs);
  const [sort, setSort] = useState<{ id: ColumnId; dir: "asc" | "desc" }>({ id: "index", dir: "asc" });
  const ordered = useMemo(() => {
    const column = columnById(sort.id);
    const copy = [...runs];
    copy.sort((left, right) => compare(column.sortValue(left), column.sortValue(right), sort.dir));
    return copy;
  }, [runs, sort]);

  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">Comparar</th>
            {columns.map((column) => (
              <th key={column.id} scope="col" className={column.id === "label" ? styles.sticky : undefined}>
                <button
                  type="button"
                  className={styles.sort}
                  onClick={() =>
                    setSort((current) => ({
                      id: column.id,
                      dir: current.id === column.id && current.dir === "asc" ? "desc" : "asc",
                    }))
                  }
                >
                  {column.header}
                  {sort.id === column.id ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
                </button>
                {column.help ? <HelpTip id={column.help} iconOnly /> : null}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordered.map((run) => (
            <tr key={run.uiReference} data-selected={selected.includes(run.index) ? "true" : "false"}>
              <td>
                <input
                  type="checkbox"
                  checked={selected.includes(run.index)}
                  aria-label={`Comparar ${run.label}`}
                  onChange={() => onToggle(run.index)}
                />
              </td>
              {columns.map((column) => (
                <td
                  key={column.id}
                  className={column.id === "label" ? styles.sticky : undefined}
                  title={column.title(run)}
                >
                  {column.id === "label" ? (
                    <Link className={styles.link} to={`/experimentos/${experimentId}/run/${run.index}`}>
                      {column.text(run)}
                    </Link>
                  ) : column.id === "hash" ? (
                    <HashValue value={run.configurationHash} label="configuration hash" />
                  ) : column.id === "fingerprint" ? (
                    <HashValue value={run.datasetFingerprint} label="dataset fingerprint" />
                  ) : (
                    column.text(run)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function compare(left: number | string | null, right: number | string | null, dir: "asc" | "desc"): number {
  const sign = dir === "asc" ? 1 : -1;
  if (left === null && right === null) {
    return 0;
  }
  if (left === null) {
    return 1;
  }
  if (right === null) {
    return -1;
  }
  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * sign;
  }
  return String(left).localeCompare(String(right), "es") * sign;
}
