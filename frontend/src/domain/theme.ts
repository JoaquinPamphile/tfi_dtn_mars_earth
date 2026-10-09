/** Clave de localStorage. El script de index.html debe usar el mismo valor. */
export const THEME_STORAGE_KEY = "dtn-lab-theme";

/** Color de la barra del navegador. Debe coincidir con --color-bg de cada tema. */
export const THEME_COLORS = {
  light: "#eef3f7",
  dark: "#0e141b",
} as const;

export type LabTheme = keyof typeof THEME_COLORS;

export function esTema(valor: string | null): valor is LabTheme {
  return valor === "light" || valor === "dark";
}

export function leerTemaGuardado(): LabTheme | null {
  try {
    const valor = localStorage.getItem(THEME_STORAGE_KEY);
    return esTema(valor) ? valor : null;
  } catch {
    return null;
  }
}

export function temaDelSistema(): LabTheme {
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/** La preferencia guardada gana. Si no hay, se usa la del sistema. */
export function resolverTema(guardado: LabTheme | null, sistema: LabTheme): LabTheme {
  return guardado ?? sistema;
}

export function temaInicial(): LabTheme {
  return resolverTema(leerTemaGuardado(), temaDelSistema());
}

export function aplicarTema(tema: LabTheme): void {
  const raiz = document.documentElement;
  raiz.dataset.theme = tema;
  raiz.style.backgroundColor = THEME_COLORS[tema];
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", THEME_COLORS[tema]);
}

export function guardarTema(tema: LabTheme): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, tema);
  } catch {
    /* Si el navegador bloquea el almacenamiento, el tema sigue en la sesión. */
  }
}
