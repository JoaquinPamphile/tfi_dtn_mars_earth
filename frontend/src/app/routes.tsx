import { Navigate, Route, Routes } from "react-router-dom";
import { AboutPage } from "../pages/AboutPage";
import { ExperimentsPage } from "../pages/ExperimentsPage";
import { HomePage } from "../pages/HomePage";
import { ScenarioPage } from "../pages/ScenarioPage";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/escenario" element={<ScenarioPage />} />
      <Route path="/experimentos" element={<ExperimentsPage />} />
      <Route path="/acerca" element={<AboutPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
