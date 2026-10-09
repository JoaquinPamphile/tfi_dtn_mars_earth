import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import styles from "./InfoCard.module.css";

export function InfoCard({
  title,
  to,
  children,
}: {
  title: string;
  to?: string;
  children: ReactNode;
}) {
  const contenido = (
    <>
      <h2 className={styles.title}>
        {title}
        {to ? (
          <span className={styles.goto} aria-hidden="true">
            →
          </span>
        ) : null}
      </h2>
      <div className={styles.body}>{children}</div>
    </>
  );

  if (to) {
    return (
      <Link to={to} className={styles.card}>
        {contenido}
      </Link>
    );
  }

  return <article className={styles.card}>{contenido}</article>;
}
