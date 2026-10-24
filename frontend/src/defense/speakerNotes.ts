import type { DefenseSpeakerNotes, DefenseStepId } from "./types";

/**
 * Notas privadas para ensayar la defensa.
 * Son un recordatorio del hilo, no un discurso ni una copia de la evidence.
 */

export const SPEAKER_NOTES: Record<DefenseStepId, DefenseSpeakerNotes> = {
  problem: {
    stepId: "problem",
    objective: "Plantear que el problema es saber qué está sincronizado.",
    say: [
      "Marte, relé y Tierra no comparten un enlace continuo.",
      "Hay retardo, ventanas limitadas y estado repartido.",
      "Enviar la telemetría no dice qué quedó sincronizado.",
    ],
    remember: ["La pregunta es de estado, no solo de envío."],
    transition: "Antes de medir nada, separo dos planos que el envío suele mezclar.",
    questions: [
      {
        prompt: "¿El problema es la latencia o la falta de un enlace continuo?",
        answer:
          "Importan las dos, y ninguna alcanza sola. Con retardos y ventanas, el estado queda repartido: hay que saber qué está sincronizado, no solo si un envío salió.",
        links: [{ label: "Ir a escenario", href: "/escenario" }],
      },
      {
        prompt: "¿Esto representa una misión Marte–Tierra completa?",
        answer:
          "No. Es un escenario lógico de contacto para comparar mecanismos. No se presenta como una misión completa ni como una red BPv7 real.",
        links: [{ label: "Ir a escenario", href: "/escenario" }],
      },
    ],
  },
  "core-idea": {
    stepId: "core-idea",
    objective: "Fijar que Tierra posee no es lo mismo que Marte conoce.",
    say: [
      "Plano de datos: Marte origina, el relé reenvía, Tierra persiste.",
      "Plano de conocimiento: Tierra acepta, el retorno informa, Marte conoce.",
      "Persistido en Tierra y confirmado en Marte son hitos distintos.",
    ],
    remember: ["Tierra posee ≠ Marte conoce."],
    transition: "Esa diferencia se recorre en el ciclo de un evento.",
    questions: [
      {
        prompt: "¿Por qué no alcanza con persistir en Tierra?",
        answer:
          "Porque la aceptación terrestre y el conocimiento del origen son hitos distintos. Tierra puede poseer el dato mientras Marte todavía no registró esa aceptación.",
      },
      {
        prompt: "¿El relé confirma el dato?",
        answer:
          "No cierra ninguno de los dos hitos. Reenvía en el plano de datos y puede transportar el retorno; no sustituye la persistencia ni el conocimiento del origen.",
        links: [{ label: "Ir a escenario", href: "/escenario" }],
      },
    ],
  },
  "application-model": {
    stepId: "application-model",
    objective: "Recorrer el ciclo desde el evento hasta la confirmación en origen.",
    say: [
      "El evento se genera, queda en el origen y viaja como SyncUnit.",
      "La aceptación en Tierra no cierra el ciclo.",
      "El ApplicationAck vuelve por el contacto de retorno.",
    ],
    remember: ["No presentar el ciclo como un ACK inmediato.", "SyncUnit no es un Bundle."],
    transition: "El ciclo no está en un solo módulo. Está repartido en cuatro capas.",
    questions: [
      {
        prompt: "¿SyncUnit es un Bundle?",
        answer:
          "No. Es la unidad de aplicación que viaja hacia el relé. No es un Bundle ni un status report de BPv7.",
      },
      {
        prompt: "¿El ApplicationAck confirma el enlace?",
        answer:
          "Confirma aceptación de aplicación en el modelo. No es un informe de estado de BPv7, y vuelve a Marte cuando hay contacto de retorno.",
      },
      {
        prompt: "¿La persistencia de esta versión es física?",
        answer: "No. En esta versión la persistencia es un hecho lógico del modelo, no un almacenamiento de misión.",
      },
    ],
  },
  architecture: {
    stepId: "architecture",
    objective: "Mostrar las cuatro capas sin abrir el backend.",
    say: [
      "Motor: avanza el reloj simulado hasta la política de parada.",
      "Transporte: mueve bytes mientras un contacto dirigido está abierto.",
      "Aplicación: genera, reenvía, acepta y recupera.",
      "Ejecución científica: parte de una spec congelada y deja evidence.",
    ],
    remember: ["El reloj del motor no es el cronómetro de esta exposición."],
    transition: "Esas capas corren sobre un escenario de contacto, no sobre un enlace siempre abierto.",
    questions: [
      {
        prompt: "¿El laboratorio ejecuta BPv7?",
        answer:
          "No. La aplicación sincroniza con sus propias unidades y acuses. El transporte emulado mueve bytes durante contactos dirigidos.",
      },
      {
        prompt: "¿Dónde queda la evidence?",
        answer:
          "La ejecución científica deja métricas, manifiesto y evidence a partir de una especificación congelada. Esta defensa la lee; no la recalcula.",
        links: [{ label: "Ir a evidence", href: "/experimentos" }],
      },
      {
        prompt: "¿Qué hace el motor?",
        answer:
          "Avanza el reloj de la simulación y ejecuta los eventos hasta que la política de parada cierra la corrida. Ese tiempo no mide la exposición oral.",
      },
    ],
  },
  scenario: {
    stepId: "scenario",
    objective: "Dejar claro el escenario lógico de contacto antes de los experimentos.",
    say: [
      "Hay ventanas dirigidas, no un canal siempre abierto.",
      "Lo que no sale en un contacto espera a la ventana siguiente.",
      "El mismo escenario sostiene las tres comparaciones.",
    ],
    remember: ["No describir los contactos como conectividad continua."],
    transition: "Con el escenario fijo, la primera pregunta es qué cambia al agrupar eventos.",
    questions: [
      {
        prompt: "¿Los contactos son continuos?",
        answer:
          "No. Son ventanas dirigidas. Lo que no cabe en un contacto queda para una oportunidad posterior.",
        links: [{ label: "Ir a escenario", href: "/escenario" }],
      },
      {
        prompt: "¿E1, E2 y E3 cambian de escenario?",
        answer:
          "Comparan tratamientos sobre el escenario de contacto del laboratorio. Cada lectura queda acotada a ese escenario.",
        links: [{ label: "Ir a escenario", href: "/escenario" }],
      },
    ],
  },
  e1: {
    stepId: "e1",
    objective: "Mostrar qué cambia al agrupar eventos, y qué no.",
    say: [
      "Batching baja fuerte la cantidad de SyncUnits.",
      "Los bytes bajan menos: el evento sigue en el contenido.",
      "p95 no mejora de forma uniforme.",
      "La escala temporal sigue atada a los contactos.",
    ],
    remember: ["No afirmar un batch óptimo."],
    transition: "Ya vimos qué cambia al modificar granularidad. Ahora aumentamos la presión sobre el mismo sistema.",
    questions: [
      {
        prompt: "¿Batching reduce el tiempo de confirmación?",
        answer:
          "No de forma uniforme. Reduce con fuerza la cantidad de SyncUnits y de manera moderada los bytes. La escala temporal sigue condicionada por los contactos.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e1" }],
      },
      {
        prompt: "¿Menos unidades equivalen a menos bytes en la misma proporción?",
        answer:
          "No. Los eventos siguen formando parte del contenido. El batching comparte la estructura fija de la SyncUnit, así que el costo no baja en la misma proporción.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e1" }],
      },
      {
        prompt: "¿Hay un tamaño de batch óptimo?",
        answer: "No se afirma. La etapa de validez deja fuera un batch óptimo universal.",
      },
    ],
  },
  e2: {
    stepId: "e2",
    objective: "Mostrar la separación de planos cuando sube la presión de carga.",
    say: [
      "Carga ofrecida no es utilización del contacto.",
      "25–75: Tierra y Marte completos.",
      "90–100: Tierra completa, Marte incompleto.",
      "120: ambos incompletos.",
      "No afirmar un threshold.",
    ],
    remember: ["Tierra posee ≠ Marte conoce."],
    transition: "Esto nos lleva al problema de qué hacer cuando además se pierde una entrega.",
    questions: [
      {
        prompt: "¿Carga ofrecida es lo mismo que utilización del contacto?",
        answer:
          "No. La carga ofrecida es la presión que se pide generar. La utilización describe cómo se ocupó el contacto. No se sustituyen.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e2" }],
      },
      {
        prompt: "¿Hay un umbral a partir del cual el sistema falla?",
        answer:
          "No se afirma un threshold universal. En los puntos observados, 25–75 completan ambos planos; 90–100 separan Tierra completa de Marte incompleto; 120 deja ambos incompletos.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e2" }],
      },
      {
        prompt: "¿Si Tierra está completa, Marte ya confirmó?",
        answer:
          "No. Que Tierra tenga todos los datos no implica que Marte los tenga todos confirmados. La presión puede separar los dos planos.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e2" }],
      },
    ],
  },
  e3: {
    stepId: "e3",
    objective: "Mostrar quién detecta y repara antes, y qué no se adelanta.",
    say: [
      "Sender espera un timeout. Receiver ve un gap.",
      "Receiver reacciona antes, recupera Tierra antes y usa menos tráfico de recuperación.",
      "La confirmación en origen espera la misma oportunidad de retorno.",
      "Tres posiciones, mismo régimen. No es una estadística.",
    ],
    remember: ["Recuperar antes los datos no implica confirmar antes al origen."],
    transition: "Antes de cerrar, digo qué sí podemos afirmar y qué no se puede universalizar.",
    questions: [
      {
        prompt: "¿Por qué receiver-driven no confirma antes en Marte?",
        answer:
          "Porque recuperar antes los datos en Tierra no adelanta, por sí solo, el conocimiento del origen. Las dos reparaciones esperan la siguiente oportunidad de retorno.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e3" }],
      },
      {
        prompt: "¿Los 80 μs son significativos?",
        answer:
          "La defensa los trata como una diferencia numérica, sin interpretación de precisión física. No se presentan como un hallazgo de tiempo de misión.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e3" }],
      },
      {
        prompt: "¿Esto implica que receiver-driven es siempre mejor?",
        answer:
          "No. El resultado está acotado al escenario y a los mecanismos evaluados. Receiver puede recuperar Tierra antes y con menos tráfico, sin garantía de confirmación más temprana en Marte.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e3" }],
      },
      {
        prompt: "¿Por qué solo tres posiciones?",
        answer:
          "La sensibilidad mira tres posiciones dentro del mismo régimen de contacto. No es una estadística ni una réplica independiente del caso oficial.",
        links: [{ label: "Ir a experimento", href: "/experimentos/e3-sensitivity" }],
      },
    ],
  },
  validity: {
    stepId: "validity",
    objective: "Delimitar qué se puede afirmar con RC1 y qué no se universaliza.",
    say: [
      "Sí: determinismo, evidence reproducible, comparaciones controladas, release congelada.",
      "No: batch óptimo, threshold universal, receiver siempre mejor.",
      "Tampoco una misión completa ni BPv7 real.",
    ],
    remember: ["Leer las dos columnas. El límite es parte del resultado."],
    transition: "Con ese límite explícito, las tres preguntas quedan en una sola lectura.",
    questions: [
      {
        prompt: "¿Se puede citar un batch o un threshold óptimo?",
        answer:
          "No. Hay resultados deterministas y comparaciones controladas sobre la release congelada. No hay batch óptimo, threshold universal ni receiver siempre mejor.",
        links: [{ label: "Ir a evidence", href: "/experimentos" }],
      },
      {
        prompt: "¿Esta pantalla puede regenerar RC1?",
        answer:
          "No. El visor lee la release congelada. No ejecuta campañas ni reescribe evidence.",
        links: [{ label: "Ir a evidence", href: "/experimentos" }],
      },
    ],
  },
  conclusions: {
    stepId: "conclusions",
    objective: "Cerrar las tres lecturas en una sola frase.",
    say: [
      "Granularidad: cambia el costo, no el tiempo de forma uniforme.",
      "Carga: la persistencia terrestre puede separarse de la confirmación.",
      "Recovery: Tierra puede recuperarse antes; Marte sigue esperando el retorno.",
    ],
    remember: ["No agregar un umbral ni un ganador universal en el cierre."],
    questions: [
      {
        prompt: "¿Cuál es la frase de cierre?",
        answer:
          "Entrega, persistencia y conocimiento no avanzan necesariamente al mismo ritmo. Las tres lecturas —costo, separación de planos y recuperación condicionada por el retorno— sostienen esa frase.",
      },
      {
        prompt: "¿Receiver-driven resuelve la confirmación en origen?",
        answer:
          "No. Puede recuperar Tierra antes. La confirmación en Marte sigue dependiendo de una oportunidad de contacto de retorno.",
        links: [{ label: "Ir a evidence", href: "/experimentos/e3" }],
      },
    ],
    closing: {
      ideas: [
        "Persistencia ≠ confirmación.",
        "La granularidad cambia el costo.",
        "La recuperación y el conocimiento dependen de las oportunidades de contacto.",
      ],
      phrase: "Entrega, persistencia y conocimiento no avanzan necesariamente al mismo ritmo.",
    },
  },
};

export function speakerNotesFor(id: DefenseStepId): DefenseSpeakerNotes {
  return SPEAKER_NOTES[id];
}
