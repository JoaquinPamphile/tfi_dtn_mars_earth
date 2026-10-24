export interface LifecycleBlock {
  id: string;
  label: string;
  state: string | null;
  summary: string;
}

export interface LifecycleConcept {
  id: string;
  label: string;
  summary: string;
}

export const dataBlocks = {
  mars: [
    {
      id: "telemetry-event",
      label: "TelemetryEvent",
      state: "GENERATED",
      summary: "Evento de telemetría creado en MARS.",
    },
    {
      id: "local-persistence",
      label: "Persistencia local",
      state: "PERSISTED_LOCAL",
      summary: "El evento queda registrado en el origen antes de salir.",
    },
    {
      id: "outbox",
      label: "Outbox",
      state: "PENDING",
      summary: "Eventos todavía pendientes de confirmación en origen.",
    },
    {
      id: "sync-unit",
      label: "SyncUnit",
      state: "IN_FLIGHT",
      summary: "Unidad de aplicación que viaja hacia el relé.",
    },
  ],
  relay: {
    id: "relay-forward",
    label: "RELAY",
    state: "IN_FLIGHT",
    summary: "Store-and-forward: conserva la unidad hasta una ventana hacia Tierra.",
  },
  earth: [
    {
      id: "earth-ingest",
      label: "Earth ingest",
      state: null,
      summary: "Ingesta idempotente: una recepción duplicada no crea una nueva observación.",
    },
    {
      id: "earth-persistence",
      label: "Aceptación terrestre",
      state: "PERSISTED_EARTH",
      summary: "La observación queda aceptada en Tierra.",
    },
  ],
} as const satisfies {
  mars: readonly LifecycleBlock[];
  relay: LifecycleBlock;
  earth: readonly LifecycleBlock[];
};

export const returnBlocks = {
  mars: {
    id: "mars-confirmation",
    label: "Confirmación en MARS",
    state: "CONFIRMED",
    summary: "El origen registra que Tierra aceptó el evento.",
  },
  relay: {
    id: "relay-return",
    label: "Retorno",
    state: null,
    summary: "El acuse vuelve a cruzar el relé cuando hay contacto de retorno.",
  },
  earth: {
    id: "application-ack",
    label: "ApplicationAck",
    state: null,
    summary: "Acuse de aplicación. No es un status report de BPv7.",
  },
} as const satisfies {
  mars: LifecycleBlock;
  relay: LifecycleBlock;
  earth: LifecycleBlock;
};

export const lifecycleConcepts: readonly LifecycleConcept[] = [
  {
    id: "sync-unit-diff",
    label: "SyncUnit ≠ Bundle",
    summary: "La unidad de sincronización es de aplicación. No es un Bundle.",
  },
  {
    id: "ack-diff",
    label: "ApplicationAck ≠ BPv7 status report",
    summary: "El acuse lo emite la aplicación. No es un status report de BPv7.",
  },
  {
    id: "persistence-v1",
    label: "Persistencia V1 = lógica",
    summary: "En esta versión la persistencia es un hecho lógico del modelo.",
  },
  {
    id: "gap",
    label: "Gap observable",
    summary: "Hueco detectable en la secuencia recibida. No es un estado del evento.",
  },
];

export const lifecycleBlocks: readonly LifecycleBlock[] = [
  ...dataBlocks.mars,
  dataBlocks.relay,
  ...dataBlocks.earth,
  returnBlocks.earth,
  returnBlocks.relay,
  returnBlocks.mars,
  ...lifecycleConcepts.map((concept) => ({
    id: concept.id,
    label: concept.label,
    state: null,
    summary: concept.summary,
  })),
];

export const STATE_NOTE =
  "Los estados representan hechos observables del ciclo; no constituyen una única variable global de estado.";
