import styles from "./charts.module.css";

export interface ValueColumn {
  key: string;
  label: string;
}

export interface ValueCell {
  text: string;
  title?: string;
}

export function ValuesTable({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: readonly ValueColumn[];
  rows: readonly { key: string; cells: Record<string, ValueCell> }[];
}) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              {columns.map((column) => {
                const cell = row.cells[column.key];
                return (
                  <td key={column.key} title={cell?.title}>
                    {cell?.text ?? "No disponible"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
