import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import type { Plugin } from "vite";

/**
 * Lectura read-only de evidence/ en dev y en build.
 * No copia los JSON a frontend/ ni los escribe.
 * El navegador recibe un módulo virtual; no se sirven los archivos por /@fs/.
 */
export const RC1_VIRTUAL_ID = "virtual:rc1-evidence";
const RESOLVED_ID = "\0virtual:rc1-evidence";

const RELATIVE_FILES = {
  e1Package: "official/e1/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
  e1Provenance: "manifests/efe47dd9-61f4-50d5-a2ba-11144c800493.json",
  e2Package: "official/e2/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
  e2Provenance: "manifests/d66bf23b-6392-5e01-b9c5-c0531c098d9d.json",
  e3Package: "official/e3/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
  e3Provenance: "manifests/b0228a7c-cd9a-515a-b799-96aaed75841a.json",
  sensitivityPackage: "manifests/05409804-725d-5f2d-9994-bac39ea41974.json",
} as const;

type FileKey = keyof typeof RELATIVE_FILES;

export function rc1EvidencePlugin(evidenceRoot: string): Plugin {
  return {
    name: "rc1-evidence-readonly",
    resolveId(id) {
      if (id === RC1_VIRTUAL_ID) {
        return RESOLVED_ID;
      }
      return null;
    },
    load(id) {
      if (id !== RESOLVED_ID) {
        return null;
      }
      const files = {} as Record<
        FileKey,
        { logicalPath: string; data: unknown; error: string | null }
      >;
      for (const key of Object.keys(RELATIVE_FILES) as FileKey[]) {
        const relative = RELATIVE_FILES[key];
        const logicalPath = `evidence/${relative}`;
        const absolute = join(evidenceRoot, relative);
        this.addWatchFile(absolute);
        files[key] = readArtifact(absolute, logicalPath);
      }
      return `export const rc1Artifacts = ${JSON.stringify({ files })};`;
    },
  };
}

function readArtifact(
  absolute: string,
  logicalPath: string,
): { logicalPath: string; data: unknown; error: string | null } {
  if (!existsSync(absolute)) {
    return {
      logicalPath,
      data: null,
      error: `No se encontró ${logicalPath}`,
    };
  }
  try {
    const text = readFileSync(absolute, "utf8");
    return { logicalPath, data: JSON.parse(text) as unknown, error: null };
  } catch (error) {
    const detail = error instanceof Error ? error.message : "lectura fallida";
    return {
      logicalPath,
      data: null,
      error: `No se pudo leer ${logicalPath}: ${detail}`,
    };
  }
}
