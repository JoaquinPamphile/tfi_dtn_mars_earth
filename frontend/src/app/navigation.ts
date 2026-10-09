export interface NavItem {
  to: string;
  label: string;
  end: boolean;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: "/", label: "Inicio", end: true },
  { to: "/escenario", label: "Escenario", end: false },
  { to: "/experimentos", label: "Experimentos", end: false },
  { to: "/acerca", label: "Acerca", end: false },
];
