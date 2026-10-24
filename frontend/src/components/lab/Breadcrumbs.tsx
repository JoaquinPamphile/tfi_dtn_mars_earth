import { Link } from "react-router-dom";
import styles from "./lab.module.css";

export function Breadcrumbs({ items }: { items: readonly { label: string; to?: string }[] }) {
  return (
    <nav className={styles.crumbs} aria-label="Miga de pan">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`}>
          {index > 0 ? <span aria-hidden="true"> &gt; </span> : null}
          {item.to ? <Link to={item.to}>{item.label}</Link> : <span>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}
