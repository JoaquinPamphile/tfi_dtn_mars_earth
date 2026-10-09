import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { projectConfig } from "../../config/project";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import styles from "./AppShell.module.css";

const TITULOS: Record<string, string> = {
  "/": "Inicio",
  "/escenario": "Escenario",
  "/experimentos": "Experimentos",
  "/acerca": "Acerca",
};

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const movil = useEsMovil();
  const [menuAbierto, setMenuAbierto] = useState(false);

  useEffect(() => {
    setMenuAbierto(false);
  }, [location.pathname]);

  useEffect(() => {
    const seccion = TITULOS[location.pathname] ?? projectConfig.projectName;
    document.title = `${seccion} · ${projectConfig.projectName}`;
  }, [location.pathname]);

  const menuOculto = movil && !menuAbierto;

  return (
    <div className={styles.shell}>
      <Sidebar open={menuAbierto} hidden={menuOculto} />
      {movil && menuAbierto ? (
        <button
          type="button"
          className={styles.backdrop}
          aria-label="Cerrar menú"
          onClick={() => setMenuAbierto(false)}
        />
      ) : null}
      <div className={styles.content}>
        <TopBar
          menuOpen={menuAbierto}
          onMenuToggle={() => setMenuAbierto((abierto) => !abierto)}
        />
        <main className={styles.main} id="contenido">
          {children}
        </main>
      </div>
    </div>
  );
}

function useEsMovil(): boolean {
  const consulta = "(max-width: 900px)";
  const [movil, setMovil] = useState(() => window.matchMedia(consulta).matches);

  useEffect(() => {
    const media = window.matchMedia(consulta);
    const alCambiar = () => setMovil(media.matches);
    alCambiar();
    media.addEventListener("change", alCambiar);
    return () => media.removeEventListener("change", alCambiar);
  }, []);

  return movil;
}
