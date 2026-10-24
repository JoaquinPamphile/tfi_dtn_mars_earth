import { Navigate, Route, Routes } from "react-router-dom";
import { defensePath } from "../defense/defenseSteps";
import { AboutPage } from "../pages/AboutPage";
import { DefensePage } from "../pages/DefensePage";
import { CompareRunsPage } from "../pages/CompareRunsPage";
import { ExperimentDetailPage } from "../pages/ExperimentDetailPage";
import { ExperimentsPage } from "../pages/ExperimentsPage";
import { RunDetailPage } from "../pages/RunDetailPage";
import { HomePage } from "../pages/HomePage";
import { ScenarioPage } from "../pages/ScenarioPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/defensa" element={<Navigate to={defensePath("problem")} replace />} />
      <Route path="/defensa/:stepId" element={<DefensePage />} />
      <Route path="/" element={<HomePage />} />
      <Route path="/escenario" element={<ScenarioPage />} />
      <Route path="/experimentos" element={<ExperimentsPage />} />
      <Route path="/experimentos/:experimentId/run/:runRef" element={<RunDetailPage />} />
      <Route path="/experimentos/:experimentId/comparar" element={<CompareRunsPage />} />
      <Route path="/experimentos/:experimentId" element={<ExperimentDetailPage />} />
      <Route path="/acerca" element={<AboutPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
