/**
 * Identidad única del visor.
 * La versión y la revisión no deben repetirse en los componentes.
 * El frontend no forma parte de la evidencia RC1.
 */
export const projectConfig = {
  projectName: "Laboratorio DTN",
  subtitle: "Sincronización de telemetría Marte–Tierra",
  releaseVersion: "v1.0.0-rc1",
  sourceRevision: "86597493672d2ebd445993999e1940b5471222b2",
  scientificMode: "read-only",
  readOnly: true,
  readOnlyLabel: "READ ONLY",
  readOnlyStateLabel: "SOLO LECTURA",
  homeBadge: "RC1 · SOLO LECTURA",
  headerBadge: "RC1 · READ ONLY",
  dataSourceLabel: "RC1 EVIDENCE",
  evidenceIntegrationNote: "Evidence RC1 cargada",
} as const;
