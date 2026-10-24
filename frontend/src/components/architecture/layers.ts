export interface ArchitectureLayer {
  id: string;
  spoken: string;
  technical: string;
  items: readonly string[];
  responsibility: string;
  flowIds: readonly string[];
}

export interface ArchitectureFlowStep {
  id: string;
  label: string;
}

export const architectureLayers: readonly ArchitectureLayer[] = [
  {
    id: "simulation",
    spoken: "Motor",
    technical: "Simulación",
    items: ["SimulationClock", "EventScheduler", "SimulationEngine", "StopPolicy"],
    responsibility:
      "Avanza el reloj y ejecuta los eventos hasta que la política de parada cierra la corrida.",
    flowIds: ["engine"],
  },
  {
    id: "transport",
    spoken: "Transporte",
    technical: "Transporte",
    items: ["ContactPlan", "EmulatedTransport", "colas por enlace dirigido", "store-and-forward"],
    responsibility:
      "Mueve bytes mientras un contacto dirigido está abierto. Cada sentido tiene su cola, y lo que no puede salir queda guardado para reenviar.",
    flowIds: ["nodes"],
  },
  {
    id: "application",
    spoken: "Aplicación",
    technical: "Aplicación",
    items: ["MarsNode", "RelayNode", "EarthNode", "TelemetrySyncSession", "Individual", "FixedBatch", "RecoveryPolicy"],
    responsibility:
      "Los nodos generan, reenvían y aceptan telemetría. La sesión aplica la estrategia de sincronización y la política de recuperación.",
    flowIds: ["nodes"],
  },
  {
    id: "science",
    spoken: "Ejecución científica",
    technical: "Ciencia / evidence",
    items: [
      "ScientificRunSpec",
      "Campaign",
      "Metrics",
      "Manifest",
      "Evidence",
      "Dataset fingerprint",
      "Configuration hash",
    ],
    responsibility:
      "Cada corrida parte de una especificación congelada. La campaña deja métricas, manifiesto y evidence, con la huella del dataset y el hash de configuración.",
    flowIds: ["campaign", "spec", "trace", "evidence"],
  },
];

export const architectureFlow: readonly ArchitectureFlowStep[] = [
  { id: "campaign", label: "Campaign" },
  { id: "spec", label: "ScientificRunSpec" },
  { id: "engine", label: "SimulationEngine" },
  { id: "nodes", label: "Nodos / transporte" },
  { id: "trace", label: "Traza / métricas" },
  { id: "evidence", label: "Evidence" },
];

export const ARCHITECTURE_LEAD =
  "El backend está separado en cuatro capas: motor, transporte, aplicación y ejecución científica.";
