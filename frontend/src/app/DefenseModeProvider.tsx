import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

interface DefenseModeContextValue {
  presenting: boolean;
  fullscreenActive: boolean;
  enterPresentation: (element: HTMLElement) => Promise<void>;
  exitPresentation: () => void;
}

const DefenseModeContext = createContext<DefenseModeContextValue | null>(null);

export function DefenseModeProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [presenting, setPresenting] = useState(false);
  const [fullscreenActive, setFullscreenActive] = useState(false);
  const tokenRef = useRef(0);
  const expectingFullscreenExit = useRef(false);
  const presentingRef = useRef(presenting);
  presentingRef.current = presenting;

  const exitPresentation = useCallback(() => {
    tokenRef.current += 1;
    expectingFullscreenExit.current = false;
    setPresenting(false);
    setFullscreenActive(false);
    if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
      void document.exitFullscreen().catch(() => undefined);
    }
  }, []);

  const enterPresentation = useCallback(async (element: HTMLElement) => {
    const token = ++tokenRef.current;
    setPresenting(true);
    const fullscreenDisponible =
      typeof element.requestFullscreen === "function" && document.fullscreenEnabled !== false;
    if (!fullscreenDisponible) {
      expectingFullscreenExit.current = false;
      return;
    }
    expectingFullscreenExit.current = true;
    try {
      await element.requestFullscreen();
    } catch {
      if (tokenRef.current === token) {
        expectingFullscreenExit.current = false;
        setFullscreenActive(false);
      }
      return;
    }
    if (tokenRef.current !== token) {
      if (document.fullscreenElement) {
        void document.exitFullscreen().catch(() => undefined);
      }
      return;
    }
    const activo = document.fullscreenElement === element;
    setFullscreenActive(activo);
    if (!activo) {
      expectingFullscreenExit.current = false;
    }
  }, []);

  useEffect(() => {
    const alCambiar = () => {
      const activo = document.fullscreenElement !== null;
      setFullscreenActive(activo);
      if (!activo && expectingFullscreenExit.current) {
        expectingFullscreenExit.current = false;
        setPresenting(false);
      }
    };
    document.addEventListener("fullscreenchange", alCambiar);
    return () => document.removeEventListener("fullscreenchange", alCambiar);
  }, []);

  useEffect(() => {
    if (!location.pathname.startsWith("/defensa") && presentingRef.current) {
      exitPresentation();
    }
  }, [exitPresentation, location.pathname]);

  useEffect(() => {
    return () => {
      if (document.fullscreenElement && typeof document.exitFullscreen === "function") {
        void document.exitFullscreen().catch(() => undefined);
      }
    };
  }, []);

  const valor = useMemo(
    () => ({ presenting, fullscreenActive, enterPresentation, exitPresentation }),
    [enterPresentation, exitPresentation, fullscreenActive, presenting],
  );

  return <DefenseModeContext.Provider value={valor}>{children}</DefenseModeContext.Provider>;
}

export function useDefenseMode(): DefenseModeContextValue {
  const contexto = useContext(DefenseModeContext);
  if (!contexto) {
    throw new Error("useDefenseMode debe usarse dentro de DefenseModeProvider.");
  }
  return contexto;
}
