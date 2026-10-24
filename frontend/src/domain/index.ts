export type {
  AuditRow,
  DesignBlock,
  LabExperiment,
  LabRun,
  LabStored,
  MetricGroup,
  UiReferenceKind,
} from "./lab";

export {
  GLOSSARY,
  GROUP_LABEL,
  GROUP_ORDER,
  LAB_METRICS,
  catalogStoredCount,
  defenseHref,
  findLabRun,
  loadLabel,
  presentStored,
  runJsonDocument,
  storedNumber,
  strategyLabel,
} from "./lab";

export type {
  EvidenceIdentity,
  EvidenceLocator,
  EvidencePresentation,
  EvidenceSource,
  EvidenceSourceKind,
  ExperimentDetail,
  ExperimentSummary,
  LabDataset,
  RunSummary,
  ScientificRelease,
} from "./types";

export type { E3RecoveryPresentation } from "./recovery";

export type {
  E1PresentationMetrics,
  E1SharedFinalState,
  E1TreatmentMetrics,
  E2ObservedPattern,
  E2PointMetrics,
  E2PresentationMetrics,
  E2StrategyPanel,
  MetricGap,
  RunContactMetrics,
  RunConvergenceMetrics,
  RunFreshnessMetrics,
  RunMeasurement,
  RunStateMetrics,
  RunTrafficMetrics,
  ScientificValue,
  StoredRunMetrics,
} from "./metrics";

export { isStoredNumber } from "./metrics";

export {
  DECIMAL_MEGABYTE,
  decimalMegabytes,
  formatAxisNumber,
  formatBytes,
  formatCount,
  formatMegabytes,
  formatOfferedLoad,
  formatOriginalNumber,
  formatPercent,
  formatRawNumber,
  formatSeconds,
  formatSecondsDetail,
} from "./metricFormat";

export { presentationLabel, presentationTone } from "./presentation";

export {
  abbreviateHash,
  formatBatch,
  formatFailure,
  formatLoad,
  formatOptional,
  formatSequences,
} from "./format";

export type {
  ContactDirection,
  ContactProvenance,
  DirectedContact,
  GenerationSpan,
  ProvenanceEntry,
  ScenarioDefinition,
  ScenarioLink,
  ScenarioNode,
  ScenarioParameter,
} from "./scenario";

export { formatDataRate, formatSimSeconds } from "./scenarioFormat";
