import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { aplicarTema, guardarTema, temaInicial, type LabTheme } from "../domain/theme";

interface ThemeContextValue {
  theme: LabTheme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<LabTheme>(() => temaInicial());

  useEffect(() => {
    aplicarTema(theme);
  }, [theme]);

  const toggleTheme = useCallback(() => {
    setTheme((actual) => {
      const siguiente: LabTheme = actual === "dark" ? "light" : "dark";
      guardarTema(siguiente);
      return siguiente;
    });
  }, []);

  const valor = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);

  return <ThemeContext.Provider value={valor}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const contexto = useContext(ThemeContext);
  if (!contexto) {
    throw new Error("useTheme debe usarse dentro de ThemeProvider.");
  }
  return contexto;
}
