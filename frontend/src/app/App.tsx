import { evidenceAdapter } from "../adapters";
import { AppShell } from "../components/layout/AppShell";
import { LabProvider } from "./LabProvider";
import { AppRoutes } from "./routes";
import { ThemeProvider } from "./ThemeProvider";

export function App() {
  return (
    <ThemeProvider>
      <LabProvider adapter={evidenceAdapter}>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </LabProvider>
    </ThemeProvider>
  );
}
