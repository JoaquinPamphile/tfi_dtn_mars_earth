import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useDefenseMode } from "../../app/DefenseModeProvider";
import { projectConfig } from "../../config/project";
import { defenseStepById } from "../../defense/defenseSteps";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import styles from "./AppShell.module.css";

const TITULOS: Record<string, string> = {
  "/": "Inicio",
  "/escenario": "Escenario",
  "/experimentos": "Experimentos",
  "/acerca": "Acerca",
};

function tituloDeRuta(pathname: string): string {
  if (pathname.startsWith("/defensa")) {
    const id = pathname.split("/").filter(Boolean)[1];
    const etapa = defenseStepById(id);
    return etapa ? `Defensa · ${etapa.title}` : "Defensa";
  }
  if (pathname.startsWith("/experimentos/")) {
    return "Experimento";
  }
  return TITULOS[pathname] ?? projectConfig.projectName;
}

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const movil = useEsMovil();
  const modoDefensa = useDefenseMode();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const enDefensa = location.pathname.startsWith("/defensa");
  const presentando = enDefensa && modoDefensa.presenting;

  useEffect(() => {
    setMenuAbierto(false);
  }, [location.pathname]);

  useEffect(() => {
    document.title = `${tituloDeRuta(location.pathname)} · ${projectConfig.projectName}`;
  }, [location.pathname]);

  const menuOculto = movil && !menuAbierto;
  const claseMain = presentando
    ? `${styles.main} ${styles.mainDefense} ${styles.mainPresenting}`
    : enDefensa
      ? `${styles.main} ${styles.mainDefense}`
      : styles.main;

  return (
    <div className={presentando ? `${styles.shell} ${styles.presenting}` : styles.shell}>
      {presentando ? null : <Sidebar open={menuAbierto} hidden={menuOculto} />}
      {movil && menuAbierto && !presentando ? (
        <button
          type="button"
          className={styles.backdrop}
          aria-label="Cerrar menú"
          onClick={() => setMenuAbierto(false)}
        />
      ) : null}
      <div className={styles.content}>
        {presentando ? null : (
          <TopBar
            menuOpen={menuAbierto}
            onMenuToggle={() => setMenuAbierto((abierto) => !abierto)}
          />
        )}
        <main className={claseMain} id="contenido">
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
