import type {
  ContactDirection,
  ContactProvenance,
  DirectedContact,
  GenerationSpan,
  ProvenanceEntry,
  ScenarioDefinition,
  ScenarioLink,
  ScenarioNode,
  ScenarioParameter,
} from "../../domain/scenario";
import { formatDataRate, formatSimSeconds } from "../../domain/scenarioFormat";
import { EvidenceIdentityError, EvidenceSchemaError } from "../errors";
import { RC1_SOFTWARE_VERSION } from "./catalog";

/**
 * Lee research-alessi-baseline desde la evidence RC1 ya cargada.
 * No importa Python, no ejecuta la simulación y no copia las ventanas a mano.
 * La banda de generación usa la fórmula del perfil sobre campos congelados:
 * el evento n ocurre en start + n / tasa, y el último índice es max_events - 1
 * cuando duration_seconds es nulo.
 */

const BASELINE_ID = "research-alessi-baseline";
const NORMAL_WORKLOAD_ID = "alessi-normal-tm";

const NOTE_MARS_RELAY = "Intervalos Marte–relé: tiempo SOURCE_APPROXIMATED";
const NOTE_RELAY_EARTH = "Intervalos relé–Tierra: tiempo SOURCE_APPROXIMATED";
const NOTE_RETURN = "El camino de vuelta, en ambos tramos, es TFI_ASSUMPTION";
const NOTE_HORIZON = "Horizonte SOURCE_TRANSFORMED: 1440 s de figura por 60";
const NOTE_DELAY = "Retardo interplanetario SOURCE_TRANSFORMED: 23 min por 60";
const NOTE_STATIONS = "colapso de las estaciones";
const NOTE_RATES = "SOURCE_TRANSFORMED a bps";
const DESC_FIGURE = "reconstrucción de la figura 5";
const DESC_SCALE = "multiplicando por 60";
const DESC_LIMIT = "No reproduce la red de nueve nodos";

const LABEL_FORWARD = "Fuente aproximada / transformada";
const LABEL_FORWARD_EARTH =
  "Fuente aproximada / transformada. EARTH lógico reúne las estaciones.";
const LABEL_RETURN = "Supuesto TFI";

const ADOPTED_HORIZON_SECONDS = 86400;
const ADOPTED_LIGHT_TIME_SECONDS = 1380;

const LINK_ORDER = [
  ["MARS", "RELAY"],
  ["RELAY", "EARTH"],
  ["EARTH", "RELAY"],
  ["RELAY", "MARS"],
] as const;

const NODE_ORDER = ["MARS", "RELAY", "EARTH"] as const;

interface RawContact {
  contact_id: string;
  source: string;
  destination: string;
  start_time_sim: number;
  end_time_sim: number;
  data_rate_bps: number;
  propagation_delay_s: number;
}

interface RawScenario {
  scenario_id: string;
  horizon_seconds: number;
  description: string;
  notes: string;
  contacts: RawContact[];
}

interface RawWorkload {
  workload_id: string;
  start_time_sim: number;
  duration_seconds: number | null;
  max_events: number | null;
  rate_events_per_second: number;
}

interface RawRun {
  softwareVersion: string;
  scenario: RawScenario;
  workload: RawWorkload;
}

interface RawPackage {
  campaignId: string;
  logicalPath: string;
  runs: RawRun[];
}

export interface Rc1ScenarioInput {
  e1: unknown;
  e1Path: string;
  e2: unknown;
  e2Path: string;
  e3: unknown;
  e3Path: string;
}

export function mapRc1Scenario(input: Rc1ScenarioInput): ScenarioDefinition {
  const e1 = readPackage(input.e1, input.e1Path);
  const e2 = readPackage(input.e2, input.e2Path);
  const e3 = readPackage(input.e3, input.e3Path);
  const baseline = sharedScenario(e1);
  const baselineKey = scenarioKey(baseline);
  assertSameScenario(e2, baselineKey);
  assertSameScenario(e3, baselineKey);
  assertNotes(baseline, e1.logicalPath);

  const workload = sharedWorkload(e1);
  const e3Workload = sharedWorkload(e3);
  const generation = generationSpan(workload, sameWorkload(workload, e3Workload));
  const links = buildLinks(baseline.contacts);
  const nodes = buildNodes(baseline.contacts);

  return {
    scenarioId: baseline.scenario_id,
    sourcePath: e1.logicalPath,
    horizonSeconds: baseline.horizon_seconds,
    nodes,
    links,
    parameters: buildParameters(baseline, links),
    generation,
    provenance: buildProvenance(baseline),
    figureNote: baseline.description.includes(DESC_FIGURE)
      ? "La reconstrucción de Figura 5 es aproximada y documentada."
      : null,
    limitNote: baseline.description.includes(DESC_LIMIT)
      ? "No es la red original de nueve nodos."
      : null,
    sourceNote: `Contactos de ${baseline.scenario_id}, leídos de la evidence RC1.`,
  };
}

function readPackage(data: unknown, logicalPath: string): RawPackage {
  const root = record(data, logicalPath);
  const manifest = record(root.campaign_manifest, `${logicalPath}: campaign_manifest`);
  const campaignId = text(manifest.campaign_id, `${logicalPath}: campaign_id`);
  const runsValue = manifest.runs;
  if (!Array.isArray(runsValue) || runsValue.length === 0) {
    throw new EvidenceSchemaError(`${logicalPath}: la campaña no trae corridas`);
  }
  const runs = runsValue.map((run, index) => readRun(run, `${logicalPath}: runs[${index}]`));
  return { campaignId, logicalPath, runs };
}

function readRun(value: unknown, path: string): RawRun {
  const run = record(value, path);
  const manifest = record(run.manifest, `${path}.manifest`);
  const softwareVersion = text(manifest.software_version, `${path}.software_version`);
  if (softwareVersion !== RC1_SOFTWARE_VERSION) {
    throw new EvidenceIdentityError(
      `${path}: software_version ${softwareVersion} no es ${RC1_SOFTWARE_VERSION}`,
    );
  }
  const specification = record(manifest.specification, `${path}.specification`);
  return {
    softwareVersion,
    scenario: readScenario(specification.scenario, `${path}.scenario`),
    workload: readWorkload(specification.workload, `${path}.workload`),
  };
}

function readScenario(value: unknown, path: string): RawScenario {
  const scenario = record(value, path);
  const contactsValue = scenario.contacts;
  if (!Array.isArray(contactsValue) || contactsValue.length === 0) {
    throw new EvidenceSchemaError(`${path}: sin contactos`);
  }
  return {
    scenario_id: text(scenario.scenario_id, `${path}.scenario_id`),
    horizon_seconds: positive(scenario.horizon_seconds, `${path}.horizon_seconds`),
    description: text(scenario.description, `${path}.description`),
    notes: text(scenario.notes, `${path}.notes`),
    contacts: contactsValue.map((contact, index) => readContact(contact, `${path}.contacts[${index}]`)),
  };
}

function readContact(value: unknown, path: string): RawContact {
  const contact = record(value, path);
  const start = finite(contact.start_time_sim, `${path}.start_time_sim`);
  const end = finite(contact.end_time_sim, `${path}.end_time_sim`);
  if (end <= start) {
    throw new EvidenceSchemaError(`${path}: el fin debe ser posterior al inicio`);
  }
  const rate = finite(contact.data_rate_bps, `${path}.data_rate_bps`);
  if (!Number.isInteger(rate) || rate <= 0) {
    throw new EvidenceSchemaError(`${path}: data_rate_bps debe ser un entero mayor que 0`);
  }
  const delay = finite(contact.propagation_delay_s, `${path}.propagation_delay_s`);
  if (delay < 0) {
    throw new EvidenceSchemaError(`${path}: propagation_delay_s no puede ser negativo`);
  }
  return {
    contact_id: text(contact.contact_id, `${path}.contact_id`),
    source: text(contact.source, `${path}.source`),
    destination: text(contact.destination, `${path}.destination`),
    start_time_sim: start,
    end_time_sim: end,
    data_rate_bps: rate,
    propagation_delay_s: delay,
  };
}

function readWorkload(value: unknown, path: string): RawWorkload {
  const workload = record(value, path);
  const duration = workload.duration_seconds;
  const maxEvents = workload.max_events;
  return {
    workload_id: text(workload.workload_id, `${path}.workload_id`),
    start_time_sim: finite(workload.start_time_sim, `${path}.start_time_sim`),
    duration_seconds: duration === null ? null : positive(duration, `${path}.duration_seconds`),
    max_events:
      maxEvents === null ? null : positiveInteger(maxEvents, `${path}.max_events`),
    rate_events_per_second: positive(workload.rate_events_per_second, `${path}.rate_events_per_second`),
  };
}

function sharedScenario(pkg: RawPackage): RawScenario {
  const first = pkg.runs[0]?.scenario;
  if (!first) {
    throw new EvidenceSchemaError(`${pkg.logicalPath}: sin escenario`);
  }
  if (first.scenario_id !== BASELINE_ID) {
    throw new EvidenceSchemaError(
      `${pkg.logicalPath}: se esperaba ${BASELINE_ID} y llegó ${first.scenario_id}`,
    );
  }
  const key = scenarioKey(first);
  for (const run of pkg.runs) {
    if (scenarioKey(run.scenario) !== key) {
      throw new EvidenceSchemaError(`${pkg.logicalPath}: las corridas no comparten el escenario`);
    }
  }
  return first;
}

function assertSameScenario(pkg: RawPackage, key: string): void {
  for (const run of pkg.runs) {
    if (scenarioKey(run.scenario) !== key) {
      throw new EvidenceSchemaError(
        `${pkg.logicalPath}: el escenario no coincide con ${BASELINE_ID}`,
      );
    }
  }
}

function sharedWorkload(pkg: RawPackage): RawWorkload {
  const first = pkg.runs[0]?.workload;
  if (!first) {
    throw new EvidenceSchemaError(`${pkg.logicalPath}: sin workload`);
  }
  const key = workloadKey(first);
  for (const run of pkg.runs) {
    if (workloadKey(run.workload) !== key) {
      throw new EvidenceSchemaError(`${pkg.logicalPath}: las corridas no comparten el workload`);
    }
  }
  return first;
}

function sameWorkload(left: RawWorkload, right: RawWorkload): boolean {
  return workloadKey(left) === workloadKey(right);
}

function scenarioKey(scenario: RawScenario): string {
  const contacts = scenario.contacts
    .map((contact) =>
      [
        contact.contact_id,
        contact.source,
        contact.destination,
        contact.start_time_sim,
        contact.end_time_sim,
        contact.data_rate_bps,
        contact.propagation_delay_s,
      ].join("|"),
    )
    .sort();
  return JSON.stringify({
    id: scenario.scenario_id,
    horizon: scenario.horizon_seconds,
    notes: scenario.notes,
    description: scenario.description,
    contacts,
  });
}

function workloadKey(workload: RawWorkload): string {
  return JSON.stringify(workload);
}

function assertNotes(scenario: RawScenario, logicalPath: string): void {
  const required = [NOTE_MARS_RELAY, NOTE_RELAY_EARTH, NOTE_RETURN, NOTE_HORIZON, NOTE_DELAY, NOTE_STATIONS, NOTE_RATES];
  for (const fragment of required) {
    if (!scenario.notes.includes(fragment)) {
      throw new EvidenceSchemaError(`${logicalPath}: las notas no traen «${fragment}»`);
    }
  }
  if (!scenario.description.includes(DESC_FIGURE) || !scenario.description.includes(DESC_SCALE)) {
    throw new EvidenceSchemaError(`${logicalPath}: la descripción no documenta la figura ni la escala`);
  }
}

function generationSpan(workload: RawWorkload, sharedWithE3: boolean): GenerationSpan | null {
  if (workload.workload_id !== NORMAL_WORKLOAD_ID) {
    return null;
  }
  if (workload.duration_seconds !== null || workload.max_events === null) {
    return null;
  }
  const lastEventSeconds =
    workload.start_time_sim + (workload.max_events - 1) / workload.rate_events_per_second;
  const periodSeconds = 1 / workload.rate_events_per_second;
  if (!Number.isFinite(lastEventSeconds) || !Number.isFinite(periodSeconds)) {
    return null;
  }
  if (lastEventSeconds < workload.start_time_sim) {
    return null;
  }
  return {
    workloadId: workload.workload_id,
    campaignNote: sharedWithE3 ? "E1 y E3" : "E1",
    startSeconds: workload.start_time_sim,
    lastEventSeconds,
    periodSeconds,
    rateEventsPerSecond: workload.rate_events_per_second,
  };
}

function buildLinks(contacts: readonly RawContact[]): ScenarioLink[] {
  const groups = new Map<string, RawContact[]>();
  for (const contact of contacts) {
    const key = `${contact.source}->${contact.destination}`;
    const list = groups.get(key);
    if (list) {
      list.push(contact);
    } else {
      groups.set(key, [contact]);
    }
  }
  const ordered = LINK_ORDER.map(([source, destination]) => `${source}->${destination}`);
  for (const key of groups.keys()) {
    if (!ordered.includes(key)) {
      throw new EvidenceSchemaError(`contacto sin clasificación de procedencia: ${key}`);
    }
  }
  return ordered.flatMap((key) => {
    const list = groups.get(key);
    if (!list || list.length === 0) {
      return [];
    }
    const [source, destination] = key.split("->");
    if (!source || !destination) {
      return [];
    }
    const kind = classify(source, destination);
    const sorted = [...list].sort((a, b) => a.start_time_sim - b.start_time_sim || a.contact_id.localeCompare(b.contact_id));
    const directed = sorted.map((contact) => toDirected(contact, kind));
    return [
      {
        id: key,
        source,
        destination,
        direction: kind.direction,
        label: `${source} → ${destination}`,
        provenance: kind.provenance,
        provenanceLabel: kind.provenanceLabel,
        contacts: directed,
        dataRateBps: uniform(directed.map((item) => item.dataRateBps)),
        propagationDelaySeconds: uniform(directed.map((item) => item.propagationDelaySeconds)),
      },
    ];
  });
}

function classify(source: string, destination: string): {
  direction: ContactDirection;
  provenance: ContactProvenance;
  provenanceLabel: string;
} {
  if (source === "MARS" && destination === "RELAY") {
    return { direction: "forward", provenance: "approximated-transformed", provenanceLabel: LABEL_FORWARD };
  }
  if (source === "RELAY" && destination === "EARTH") {
    return {
      direction: "forward",
      provenance: "approximated-transformed",
      provenanceLabel: LABEL_FORWARD_EARTH,
    };
  }
  if (
    (source === "EARTH" && destination === "RELAY") ||
    (source === "RELAY" && destination === "MARS")
  ) {
    return { direction: "return", provenance: "tfi-assumption", provenanceLabel: LABEL_RETURN };
  }
  throw new EvidenceSchemaError(`par ${source} → ${destination} sin procedencia documentada`);
}

function toDirected(
  contact: RawContact,
  kind: { provenance: ContactProvenance; provenanceLabel: string },
): DirectedContact {
  return {
    id: contact.contact_id,
    source: contact.source,
    destination: contact.destination,
    startSeconds: contact.start_time_sim,
    endSeconds: contact.end_time_sim,
    dataRateBps: contact.data_rate_bps,
    propagationDelaySeconds: contact.propagation_delay_s,
    provenance: kind.provenance,
    provenanceLabel: kind.provenanceLabel,
  };
}

function buildNodes(contacts: readonly RawContact[]): ScenarioNode[] {
  const present = new Set<string>();
  for (const contact of contacts) {
    present.add(contact.source);
    present.add(contact.destination);
  }
  const ordered: ScenarioNode[] = [];
  for (const id of NODE_ORDER) {
    if (present.has(id)) {
      ordered.push({ id, label: id });
      present.delete(id);
    }
  }
  for (const id of [...present].sort()) {
    ordered.push({ id, label: id });
  }
  return ordered;
}

function buildParameters(scenario: RawScenario, links: readonly ScenarioLink[]): ScenarioParameter[] {
  const parameters: ScenarioParameter[] = [
    {
      id: "horizon",
      label: "Horizonte",
      value: formatSimSeconds(scenario.horizon_seconds),
      detail: scenario.scenario_id,
      sourceField: "scenario.horizon_seconds",
      rawValue: String(scenario.horizon_seconds),
    },
  ];
  if (scenario.horizon_seconds === ADOPTED_HORIZON_SECONDS && scenario.notes.includes(NOTE_HORIZON)) {
    parameters.push({
      id: "scale",
      label: "Escala",
      value: "24 h equivalentes",
      detail: "en la escala adoptada",
      sourceField: "scenario.notes",
      rawValue: NOTE_HORIZON,
    });
  }
  pushRate(parameters, links, "MARS->RELAY", "mars-relay", "Mars–relay", "tasa transformada");
  pushRate(parameters, links, "RELAY->EARTH", "relay-earth", "Relay–Earth", "tasa transformada");
  pushRate(parameters, links, "EARTH->RELAY", "earth-relay", "Earth–relay", "tasa transformada · retorno supuesto");
  pushLightTime(parameters, links, scenario);
  return parameters;
}

function pushRate(
  parameters: ScenarioParameter[],
  links: readonly ScenarioLink[],
  linkId: string,
  id: string,
  label: string,
  detail: string,
): void {
  const link = links.find((item) => item.id === linkId);
  if (!link || link.dataRateBps === null) {
    return;
  }
  parameters.push({
    id,
    label,
    value: formatDataRate(link.dataRateBps),
    detail,
    sourceField: `contacts.${link.source}->${link.destination}.data_rate_bps`,
    rawValue: String(link.dataRateBps),
  });
}

function pushLightTime(
  parameters: ScenarioParameter[],
  links: readonly ScenarioLink[],
  scenario: RawScenario,
): void {
  const forward = links.find((item) => item.id === "RELAY->EARTH");
  const back = links.find((item) => item.id === "EARTH->RELAY");
  const delay = forward?.propagationDelaySeconds;
  if (delay === null || delay === undefined || delay !== back?.propagationDelaySeconds) {
    return;
  }
  const adopted = delay === ADOPTED_LIGHT_TIME_SECONDS && scenario.notes.includes(NOTE_DELAY);
  parameters.push({
    id: "light-time",
    label: "Light time adoptado",
    value: adopted ? "≈ 23 min" : formatSimSeconds(delay),
    detail: adopted ? `${formatSimSeconds(delay)} · transformado ×60` : formatSimSeconds(delay),
    sourceField: "contacts.RELAY->EARTH.propagation_delay_s",
    rawValue: String(delay),
  });
}

function buildProvenance(scenario: RawScenario): ProvenanceEntry[] {
  const entries: ProvenanceEntry[] = [
    { id: "reference", term: "Alessi et al.", meaning: "referencia técnica" },
  ];
  if (scenario.description.includes(DESC_FIGURE)) {
    entries.push({
      id: "figure",
      term: "Figura 5",
      meaning: "reconstrucción aproximada documentada",
    });
  }
  if (scenario.notes.includes(NOTE_HORIZON) || scenario.description.includes(DESC_SCALE)) {
    entries.push({ id: "scale", term: "×60", meaning: "transformación temporal" });
  }
  if (scenario.notes.includes(NOTE_RETURN)) {
    entries.push({ id: "return", term: "Retorno", meaning: "supuesto TFI" });
  }
  if (scenario.notes.includes(NOTE_STATIONS)) {
    entries.push({ id: "ground", term: "Estaciones de tierra", meaning: "EARTH lógico" });
  }
  return entries;
}

function uniform(values: readonly number[]): number | null {
  const first = values[0];
  if (first === undefined) {
    return null;
  }
  return values.every((value) => value === first) ? first : null;
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new EvidenceSchemaError(`${path}: se esperaba un objeto`);
  }
  return value as Record<string, unknown>;
}

function text(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new EvidenceSchemaError(`${path}: se esperaba texto`);
  }
  return value;
}

function finite(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new EvidenceSchemaError(`${path}: se esperaba un número finito`);
  }
  return value;
}

function positive(value: unknown, path: string): number {
  const number = finite(value, path);
  if (number <= 0) {
    throw new EvidenceSchemaError(`${path}: se esperaba un número mayor que 0`);
  }
  return number;
}

function positiveInteger(value: unknown, path: string): number {
  const number = positive(value, path);
  if (!Number.isInteger(number)) {
    throw new EvidenceSchemaError(`${path}: se esperaba un entero`);
  }
  return number;
}
