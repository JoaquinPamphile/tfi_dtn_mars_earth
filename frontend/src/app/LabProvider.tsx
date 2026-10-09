import { createContext, useContext, type ReactNode } from "react";
import type { EvidenceAdapter } from "../adapters";

const LabContext = createContext<EvidenceAdapter | null>(null);

export function LabProvider({
  adapter,
  children,
}: {
  adapter: EvidenceAdapter;
  children: ReactNode;
}) {
  return <LabContext.Provider value={adapter}>{children}</LabContext.Provider>;
}

export function useEvidence(): EvidenceAdapter {
  const adapter = useContext(LabContext);
  if (!adapter) {
    throw new Error("useEvidence debe usarse dentro de LabProvider.");
  }
  return adapter;
}
