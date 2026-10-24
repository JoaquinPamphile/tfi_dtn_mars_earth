/**
 * Identidades RC1 que el visor acepta.
 * Si un artefacto no coincide, no se presenta como evidence oficial.
 */
export const RC1_SOFTWARE_VERSION = "1.0.0-rc1";
export const RC1_RELEASE_LABEL = "v1.0.0-rc1";
export const RC1_SOURCE_REVISION = "86597493672d2ebd445993999e1940b5471222b2";

export interface Rc1Target {
  uiId: "e1" | "e2" | "e3" | "e3-sensitivity";
  code: string;
  name: string;
  campaignId: string;
  campaignIdentity: string;
  family: string;
  role: "official" | "sensitivity";
  runCount: number;
  packageLogicalPath: string;
  provenanceLogicalPath: string | null;
  evidenceFile: string | null;
}

export const RC1_TARGETS: readonly Rc1Target[] = [
  {
    uiId: "e1",
    code: "E1",
    name: "Granularidad de sincronización",
    campaignId: "e1-strategy-alessi-10k",
    campaignIdentity: "efe47dd9-61f4-50d5-a2ba-11144c800493",
    family: "e1",
    role: "official",
    runCount: 4,
    packageLogicalPath: "evidence/official/e1/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
    provenanceLogicalPath: "evidence/manifests/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
    evidenceFile: "official/e1/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
  },
  {
    uiId: "e2",
    code: "E2",
    name: "Carga ofrecida",
    campaignId: "e2-offered-load",
    campaignIdentity: "d66bf23b-6392-5e01-b9c5-c0531c098d9d",
    family: "e2",
    role: "official",
    runCount: 12,
    packageLogicalPath: "evidence/official/e2/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
    provenanceLogicalPath: "evidence/manifests/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
    evidenceFile: "official/e2/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
  },
  {
    uiId: "e3",
    code: "E3",
    name: "Recuperación ante pérdida silenciosa",
    campaignId: "e3-recovery-policy",
    campaignIdentity: "b0228a7c-cd9a-515a-b799-96aaed75841a",
    family: "e3",
    role: "official",
    runCount: 4,
    packageLogicalPath: "evidence/official/e3/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
    provenanceLogicalPath: "evidence/manifests/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
    evidenceFile: "official/e3/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
  },
  {
    uiId: "e3-sensitivity",
    code: "E3 Sensitivity",
    name: "Sensibilidad a posición de pérdida",
    campaignId: "e3-loss-position-sensitivity",
    campaignIdentity: "05409804-725d-5f2d-9994-bac39ea41974",
    family: "e3",
    role: "sensitivity",
    runCount: 6,
    packageLogicalPath: "evidence/manifests/05409804-725d-5f2d-9994-bac39ea41974.json",
    provenanceLogicalPath: null,
    evidenceFile: null,
  },
];

export function targetById(uiId: string): Rc1Target | undefined {
  return RC1_TARGETS.find((item) => item.uiId === uiId);
}
