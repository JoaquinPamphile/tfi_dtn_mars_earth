import { createContext, useContext, type ReactNode } from "react";
import type { LabSession } from "../adapters";

const LabContext = createContext<LabSession | null>(null);

export function LabProvider({
  session,
  children,
}: {
  session: LabSession;
  children: ReactNode;
}) {
  return <LabContext.Provider value={session}>{children}</LabContext.Provider>;
}

export function useLabSession(): LabSession {
  const session = useContext(LabContext);
  if (!session) {
    throw new Error("useLabSession debe usarse dentro de LabProvider.");
  }
  return session;
}
