/** Fallo de lectura o de validación de evidence. No es un resultado científico. */
export class EvidenceAccessError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

/** El archivo no está, no se puede leer o el JSON no parsea. */
export class EvidenceLoadError extends EvidenceAccessError {}

/** El artefacto no es la identity RC1 esperada. */
export class EvidenceIdentityError extends EvidenceAccessError {}

/** El JSON parsea, pero no tiene la forma que el visor sabe leer. */
export class EvidenceSchemaError extends EvidenceAccessError {}
