/**
 * Relato de la defensa oral.
 * No es evidence: no copia métricas ni reemplaza al adapter.
 */

export interface ChainPlace {
  kind: "place";
  label: string;
}

export interface ChainTransition {
  kind: "transition";
  label: string;
}

export type ProblemChainItem = ChainPlace | ChainTransition;

export interface PlaneNode {
  code: string;
  role: string;
}

export const defenseContent = {
  problem: {
    title: ["Sincronizar cuando", "no existe conectividad continua"],
    chain: [
      { kind: "place", label: "MARTE" },
      { kind: "transition", label: "ventanas limitadas" },
      { kind: "place", label: "RELÉ" },
      { kind: "transition", label: "demora" },
      { kind: "place", label: "TIERRA" },
    ] as const satisfies readonly ProblemChainItem[],
    ideas: ["retardos elevados", "conectividad intermitente", "estado distribuido"],
    phrase: "El problema no es solamente enviar telemetría: es saber qué está sincronizado.",
    scenarioLabel: "Ver escenario",
    scenarioPath: "/escenario",
  },
  coreIdea: {
    statement: ["TIERRA POSEE", "MARTE CONOCE"],
    inequality: "≠",
    dataPlane: {
      title: "Plano de datos",
      nodes: [
        { code: "MARS", role: "origen" },
        { code: "RELAY", role: "reenvío" },
        { code: "EARTH", role: "persistencia" },
      ] as const satisfies readonly PlaneNode[],
    },
    knowledgePlane: {
      title: "Plano de conocimiento",
      nodes: [
        { code: "EARTH", role: "aceptación" },
        { code: "RELAY", role: "retorno" },
        { code: "MARS", role: "conocimiento" },
      ] as const satisfies readonly PlaneNode[],
    },
    milestones: [
      { id: "earth", label: "Persistido en Tierra", mark: "✓", pending: false },
      { id: "mars", label: "Confirmado en Marte", mark: "?", pending: true },
    ],
    phrase: "La aceptación terrestre y el conocimiento del origen son hitos diferentes.",
  },
  applicationModel: {
    title: ["Del evento a la confirmación"],
  },
  architecture: {
    title: ["Cuatro capas del laboratorio"],
  },
  scenario: {
    title: ["Un escenario lógico de contacto"],
  },
  e1: {
    question: ["¿Qué cambia", "cuando agrupamos eventos?"],
    views: { cost: "Costo", time: "Temporalidad" },
    costCallout: "Menos unidades ≠ reducción proporcional de bytes",
    costNote:
      "Los eventos siguen formando parte del contenido; el batching comparte la estructura fija de SyncUnit.",
    timeCaution: "p95 no mejora de forma uniforme.",
    conclusion:
      "Batching reduce fuertemente la cantidad de SyncUnits y moderadamente los bytes, pero la escala temporal sigue condicionada por los contactos.",
    valuesLabel: "Ver valores",
    chartsLabel: "Ver gráficos",
    labLinkLabel: "Explorar evidence",
    labPath: "/experimentos/e1",
    controls: {
      earth: "Persistencia Tierra",
      mars: "Confirmación Marte",
      backlog: "Backlog final",
    },
  },
  e2: {
    question: ["¿Qué ocurre", "cuando aumenta la presión de carga?"],
    views: { states: "Estados", composition: "Composición" },
    axisLabel: "Carga ofrecida canónica",
    conclusion: "Que Tierra tenga todos los datos no implica que Marte los tenga todos confirmados.",
    conclusionNote:
      "La presión de carga puede separar el plano de datos del plano de confirmación.",
    valuesLabel: "Ver valores",
    chartsLabel: "Ver gráficos",
    labLinkLabel: "Explorar evidence",
    labPath: "/experimentos/e2",
    series: {
      earth: "Persistencia en Tierra",
      origin: "Confirmación en Marte",
      generated: "Generados",
      persisted: "Persistidos en Tierra",
      confirmed: "Confirmados en origen",
    },
  },
  e3: {
    question: ["¿Quién detecta", "y repara antes una pérdida silenciosa?"],
    concepts: {
      "sender-driven": "timeout",
      "receiver-driven": "gap observable",
    },
    outcomeLead: "Receiver",
    outcome: ["reacciona antes", "recupera Tierra antes", "menos recovery traffic"],
    returnNote: "origin confirmation ≈ misma oportunidad de retorno",
    phrase: "Recuperar antes los datos no implica confirmar antes al origen.",
    returnLimit: "Los contactos de retorno limitan cuándo esa información puede regresar a Marte.",
    scope: "Resultado acotado al escenario y mecanismos evaluados.",
    waiting:
      "Ambas reparaciones terminan esperando la siguiente oportunidad de retorno hacia Marte.",
    sensitivityTitle: "Sensitivity",
    sensitivityNote:
      "En las tres posiciones evaluadas dentro del mismo régimen de contacto. No es una estadística.",
    sensitivityOrigin: "La dirección de la confirmación de origen no es estable.",
    officialMark: "Caso oficial",
    notReplica: "Corresponde al caso central de E3. No es una réplica independiente.",
    labLinkLabel: "Explorar evidence E3",
    labPath: "/experimentos/e3",
    sensitivityLinkLabel: "Ver sensibilidad",
    sensitivityPath: "/experimentos/e3-sensitivity",
    views: { official: "Caso oficial", sensitivity: "Sensibilidad" },
    controlsOn: "Ver controles",
    controlsOff: "Ocultar controles",
    contextOn: "Ver en contexto del escenario",
    contextOff: "Volver al episodio",
    focused: "Vista enfocada del episodio",
    scenarioContext: "Contexto del escenario",
    playback: "Reproducción visual",
    play: "Reproducir episodio",
    pause: "Pausa",
    restart: "Reiniciar",
    previousMark: "Hito anterior",
    nextMark: "Siguiente hito",
    hotkeys: "Espacio reproduce o pausa. J y K cambian de hito. Las flechas siguen cambiando de etapa.",
    reducedMotion: "Movimiento reducido: los hitos se eligen a mano.",
    originNote: "Diferencia numérica sin interpretación de precisión física.",
    trafficNote:
      "El tráfico de recuperación sigue el contrato métrico RC1; el intento común perdido se contabiliza separadamente.",
    countsNote: "Conteos del episodio. No se usa el retry general de la corrida.",
    reacts: "Receiver reacciona antes",
    recovers: "Receiver recupera Tierra antes",
    sameReturn: "Misma oportunidad de retorno",
  },
  validity: {
    canTitle: "PODEMOS AFIRMAR",
    canAffirm: [
      "resultados deterministas",
      "evidence reproducible",
      "comparaciones controladas",
      "release RC1 congelada",
    ],
    cannotTitle: "NO PODEMOS UNIVERSALIZAR",
    cannotUniversalize: [
      "batch óptimo",
      "threshold universal",
      "receiver siempre mejor",
      "misión Marte–Tierra completa",
      "BPv7 real",
    ],
    revisionLabel: "source revision",
  },
  conclusions: {
    findings: [
      {
        id: "RQ1",
        title: "Granularidad",
        lines: [
          "Batching reduce",
          "costo de representación,",
          "sin mejora temporal uniforme.",
        ],
      },
      {
        id: "RQ2",
        title: "Carga",
        lines: [
          "La persistencia terrestre",
          "puede separarse",
          "de la confirmación en origen.",
        ],
      },
      {
        id: "RQ3",
        title: "Recovery",
        lines: [
          "Receiver-driven puede recuperar",
          "Tierra antes y con menor tráfico,",
          "sin garantizar confirmación",
          "más temprana en Marte.",
        ],
      },
    ],
    closing: ["Entrega, persistencia", "y conocimiento", "no avanzan necesariamente", "al mismo ritmo."],
  },
} as const;
