import { labSession } from "../adapters";
import { AppShell } from "../components/layout/AppShell";
import { DefenseModeProvider } from "./DefenseModeProvider";
import { DefensePresenterProvider } from "./DefensePresenterProvider";
import { LabProvider } from "./LabProvider";
import { AppRoutes } from "./routes";
import { ThemeProvider } from "./ThemeProvider";

export function App() {
  return (
    <ThemeProvider>
      <LabProvider session={labSession}>
        <DefenseModeProvider>
          <DefensePresenterProvider>
            <AppShell>
              <AppRoutes />
            </AppShell>
          </DefensePresenterProvider>
        </DefenseModeProvider>
      </LabProvider>
    </ThemeProvider>
  );
}
