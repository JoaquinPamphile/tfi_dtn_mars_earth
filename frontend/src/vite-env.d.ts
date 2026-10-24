/// <reference types="vite/client" />

declare module "virtual:rc1-evidence" {
  export interface Rc1ArtifactFile {
    logicalPath: string;
    data: unknown;
    error: string | null;
  }

  export const rc1Artifacts: {
    files: {
      e1Package: Rc1ArtifactFile;
      e1Provenance: Rc1ArtifactFile;
      e2Package: Rc1ArtifactFile;
      e2Provenance: Rc1ArtifactFile;
      e3Package: Rc1ArtifactFile;
      e3Provenance: Rc1ArtifactFile;
      sensitivityPackage: Rc1ArtifactFile;
    };
  };
}
