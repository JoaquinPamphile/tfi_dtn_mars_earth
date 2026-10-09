import { useTheme } from "../../app/ThemeProvider";
import styles from "./ThemeToggle.module.css";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const etiqueta = theme === "light" ? "Tema claro" : "Tema oscuro";

  return (
    <button
      type="button"
      className={styles.button}
      onClick={toggleTheme}
      aria-label={etiqueta}
      aria-pressed={theme === "light"}
      title={etiqueta}
    >
      {theme === "light" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="9" cy="9" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M9 1.8v1.7M9 14.5v1.7M1.8 9h1.7M14.5 9h1.7M3.8 3.8l1.2 1.2M13 13l1.2 1.2M14.2 3.8 13 5M5 13l-1.2 1.2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        d="M10.1 2.3a6.1 6.1 0 1 0 5.5 8.2A4.9 4.9 0 0 1 10.1 2.3z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
