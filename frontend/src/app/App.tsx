import { evidenceAdapter } from "../adapters";
import { AppShell } from "../components/layout/AppShell";
import { LabProvider } from "./LabProvider";
import { AppRoutes } from "./routes";

export function App() {
  return (
    <LabProvider adapter={evidenceAdapter}>
      <AppShell>
        <AppRoutes />
      </AppShell>
    </LabProvider>
  );
}
