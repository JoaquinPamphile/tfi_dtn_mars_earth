"""Definición documental de un plan de contactos, independiente del runtime.

``ContactPlanDefinition`` no entra en ``Scenario``, ``ScientificRunSpec``
ni en la identidad de dataset. La conversión al plan que ya consume el
motor es ``to_runtime_contact_plan``: los mismos ``Contact``, sin
escalar, redondear, fusionar, recortar, renombrar ni inventar el enlace
inverso.

Hay dos huellas SHA-256. Ninguna se incluye a sí misma. Las dos usan
``canonical_json`` —claves ordenadas, separadores compactos,
``ensure_ascii=True`` y ``allow_nan=False``— y codifican ese texto en
UTF-8. No usan ``repr``, ``hash``, UUID4, el reloj de pared ni un
redondeo adicional.

``contact_plan_fingerprint`` resume el payload operacional. Lleva
``payload_version``, la versión de ese documento, y los siete campos de
cada ``Contact`` en el orden de ``ContactPlan``:
``(start_time_sim, contact_id)``. ``contact_id`` es operacional porque
desempata contactos que empiezan juntos. Quedan afuera
``contact_plan_id``, ``schema_version``, ``source_type``, las notas, los
nodos declarados y la provenance. Un nodo declarado que no aparece en
ningún contacto no participa del runtime actual; lo cubre la huella
documental.

``contact_plan_definition_fingerprint`` resume la definición completa:
identidad documental, ``source_type``, nodos, contactos y provenance.
Los nodos y las atribuciones se ordenan porque contractualmente son
conjuntos. El orden de los contactos es el del runtime, que sí tiene
significado. El orden de ``references`` y de ``assumptions`` se
conserva.

Números. El codificador es el de ``canonical_json``, el mismo JSON de la
biblioteca estándar, sin otro formato. Un entero aceptado por un campo
``float`` queda almacenado como ``float``: ``1`` y ``1.0`` se serializan
``1.0`` y no cambian el contacto entregado al runtime. ``data_rate_bps``
sigue el contrato de ``Contact`` y es ``int``. El cero con signo no se
normaliza: ``-0.0`` y ``0.0`` siguen distintos en el modelo, en el JSON
canónico y en el ``Contact`` que recibe ``ContactPlan``.
"""

from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from math import isfinite
from typing import Self

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlan
from core.domain.provenance import ProvenanceClassification

from experiments.canonical import HASH_ALGORITHM, canonical_json

# Versión de este documento. No es una versión de generador, ni un epoch,
# ni un hash publicado.
CONTACT_PLAN_DEFINITION_SCHEMA_VERSION = 1

# Versión del payload operacional. Es independiente de schema_version:
# cambia solo si cambia la forma en que se hashean los contactos.
CONTACT_PLAN_OPERATIONAL_PAYLOAD_VERSION = 1

_CONTACT_FIELDS = (
    "contact_id",
    "source",
    "destination",
    "start_time_sim",
    "end_time_sim",
    "data_rate_bps",
    "propagation_delay_s",
)

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}\Z")


class ContactPlanDefinitionError(ValueError):
    """La definición no cumple el contrato documental o el del runtime."""


class ContactPlanSourceType(StrEnum):
    """Origen declarado del plan. No describe un archivo de diseñador."""

    STATIC_DOCUMENTED = "STATIC_DOCUMENTED"
    ORBIT_DERIVED = "ORBIT_DERIVED"


class ContactPlanParameter(StrEnum):
    """Aspecto al que se aplica una clasificación de provenance."""

    TIME = "TIME"
    RATE = "RATE"
    DELAY = "DELAY"
    TOPOLOGY = "TOPOLOGY"
    RETURN = "RETURN"


# Tiempo, tasa y retardo describen un contacto concreto. Topología y
# retorno pueden atribuirse al plan o a un contacto.
_CONTACT_SCOPED_PARAMETERS = frozenset(
    {
        ContactPlanParameter.TIME,
        ContactPlanParameter.RATE,
        ContactPlanParameter.DELAY,
    }
)


class ContactPlanSourceArtifact(BaseModel):
    """Fuente citada y, cuando existen, el artefacto y su SHA-256.

    El hash no se calcula aquí. Solo se conserva el que aporta quien
    arma la definición, y solo si ya es un SHA-256 hexadecimal en
    minúsculas. No se reescribe la caja ni se inventa un valor ausente.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_ref: str
    artifact_ref: str | None = None
    artifact_sha256: str | None = None

    @field_validator("source_ref")
    @classmethod
    def source_ref_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("source_ref no debe estar vacío")
        return value

    @field_validator("artifact_ref")
    @classmethod
    def artifact_ref_must_not_be_blank(cls, value: str | None) -> str | None:
        return _optional_text(value, "artifact_ref")

    @field_validator("artifact_sha256")
    @classmethod
    def artifact_sha256_must_be_literal(cls, value: str | None) -> str | None:
        return _optional_sha256(value)

    @model_validator(mode="after")
    def hash_requires_artifact(self) -> Self:
        if self.artifact_sha256 is not None and self.artifact_ref is None:
            raise ValueError("artifact_sha256 requiere artifact_ref")
        return self


class ContactProvenanceStatement(BaseModel):
    """Atribución de un parámetro, del plan o de un contacto.

    No es un mapa libre. ``contact_id`` vacío no se admite: el alcance
    del plan se indica con ``None``. El identificador, si está, se
    conserva literalmente.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter: ContactPlanParameter
    classification: ProvenanceClassification
    contact_id: str | None = None
    source_ref: str = ""
    artifact_ref: str | None = None
    artifact_sha256: str | None = None
    assumption: str | None = None

    @field_validator("contact_id")
    @classmethod
    def contact_id_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.strip() == "":
            raise ValueError("contact_id no debe estar vacío")
        return value

    @field_validator("source_ref")
    @classmethod
    def source_ref_keeps_blank_only_when_empty(cls, value: str) -> str:
        if value != "" and value.strip() == "":
            raise ValueError("source_ref no debe ser solo espacios")
        return value

    @field_validator("artifact_ref")
    @classmethod
    def artifact_ref_must_not_be_blank(cls, value: str | None) -> str | None:
        return _optional_text(value, "artifact_ref")

    @field_validator("artifact_sha256")
    @classmethod
    def artifact_sha256_must_be_literal(cls, value: str | None) -> str | None:
        return _optional_sha256(value)

    @field_validator("assumption")
    @classmethod
    def assumption_must_not_be_blank(cls, value: str | None) -> str | None:
        return _optional_text(value, "assumption")

    @model_validator(mode="after")
    def scope_and_artifact(self) -> Self:
        if self.parameter in _CONTACT_SCOPED_PARAMETERS and self.contact_id is None:
            raise ValueError("tiempo, tasa y delay se atribuyen a un contacto")
        if self.artifact_sha256 is not None and self.artifact_ref is None:
            raise ValueError("artifact_sha256 requiere artifact_ref")
        return self


class ContactPlanProvenance(BaseModel):
    """Provenance estructurada. No admite diccionarios arbitrarios.

    ``statements`` es un conjunto: una pareja ``(contact_id, parameter)``
    no puede repetirse. ``references`` y ``assumptions`` son secuencias;
    su orden forma parte del documento.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: ContactPlanSourceArtifact | None = None
    statements: tuple[ContactProvenanceStatement, ...] = ()
    references: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()

    @field_validator("references", "assumptions")
    @classmethod
    def items_must_not_be_blank(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if item.strip() == "":
                raise ValueError("no debe estar vacío")
        return value


class ContactPlanDefinition(BaseModel):
    """Plan documental inmutable, con sus contactos y su provenance.

    Los identificadores válidos se conservan tal como llegan, incluidos
    los espacios internos. Solo se rechaza el texto vacío o hecho de
    espacios. Las reglas de identidad, solape, contigüidad y sentidos
    inversos las aplica ``ContactPlan``. Esta frontera agrega el rechazo
    de magnitudes no finitas, que ``Contact`` todavía permite en el fin
    de la ventana y en el retardo infinito.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    contact_plan_id: str
    schema_version: int
    source_type: ContactPlanSourceType
    declared_nodes: tuple[LogicalNode, ...]
    contacts: tuple[Contact, ...]
    provenance: ContactPlanProvenance
    notes: str = ""

    @field_validator("contact_plan_id")
    @classmethod
    def contact_plan_id_must_not_be_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

    @field_validator("schema_version")
    @classmethod
    def schema_version_must_be_known(cls, value: int) -> int:
        if isinstance(value, bool) or value != CONTACT_PLAN_DEFINITION_SCHEMA_VERSION:
            raise ValueError(
                "schema_version debe ser "
                f"{CONTACT_PLAN_DEFINITION_SCHEMA_VERSION}"
            )
        return value

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        if len(set(self.declared_nodes)) != len(self.declared_nodes):
            raise ContactPlanDefinitionError("hay nodos lógicos declarados repetidos")
        declared = set(self.declared_nodes)
        for contact in self.contacts:
            _require_finite(contact)
            if contact.source not in declared or contact.destination not in declared:
                raise ContactPlanDefinitionError(
                    f"un extremo de {contact.contact_id} no está entre los nodos declarados"
                )
        # Identificadores únicos, solapes, contigüidad y sentidos independientes.
        ContactPlan(self.contacts)
        _require_provenance_contacts(self.provenance, self.contacts)
        return self

    def to_runtime_contact_plan(self) -> ContactPlan:
        """El ``ContactPlan`` que ya programa el motor.

        El orden queda ``(start_time_sim, contact_id)``. No se agregan
        contactos de vuelta ni se modifican los campos.
        """
        return ContactPlan(self.contacts)


def operational_payload(definition: ContactPlanDefinition) -> dict[str, object]:
    """Documento operacional versionado. No incluye la huella."""
    return {
        "payload_version": CONTACT_PLAN_OPERATIONAL_PAYLOAD_VERSION,
        "contacts": [_contact_payload(contact) for contact in _runtime_contacts(definition)],
    }


def definition_payload(definition: ContactPlanDefinition) -> dict[str, object]:
    """Documento documental normalizado. No incluye la huella.

    Los nodos siguen el orden de ``LogicalNode`` (MARS, RELAY, EARTH),
    no el orden en que fueron declarados. Las atribuciones se ordenan
    por su clave canónica. Contactos, referencias y supuestos no se
    reordenan más allá de esa regla: los contactos ya vienen en orden
    de runtime y las dos secuencias conservan el orden declarado.
    """
    return {
        "schema_version": definition.schema_version,
        "contact_plan_id": definition.contact_plan_id,
        "source_type": definition.source_type.value,
        "notes": definition.notes,
        "declared_nodes": _declared_nodes_payload(definition.declared_nodes),
        "contacts": [_contact_payload(contact) for contact in _runtime_contacts(definition)],
        "provenance": _provenance_payload(definition.provenance),
    }


def contact_plan_fingerprint(definition: ContactPlanDefinition) -> str:
    """SHA-256 hexadecimal del payload operacional."""
    return _sha256_canonical(operational_payload(definition))


def contact_plan_definition_fingerprint(definition: ContactPlanDefinition) -> str:
    """SHA-256 hexadecimal de la definición normalizada."""
    return _sha256_canonical(definition_payload(definition))


def _runtime_contacts(definition: ContactPlanDefinition) -> tuple[Contact, ...]:
    return definition.to_runtime_contact_plan().contacts


def _contact_payload(contact: Contact) -> dict[str, object]:
    """Los campos persistidos de ``Contact``, sin capacidad ni duración."""
    payload = {
        "contact_id": contact.contact_id,
        "source": contact.source.value,
        "destination": contact.destination.value,
        "start_time_sim": contact.start_time_sim,
        "end_time_sim": contact.end_time_sim,
        "data_rate_bps": contact.data_rate_bps,
        "propagation_delay_s": contact.propagation_delay_s,
    }
    if tuple(payload) != _CONTACT_FIELDS:
        raise RuntimeError("el payload del contacto no tiene los campos contractuales")
    return payload


def _declared_nodes_payload(nodes: tuple[LogicalNode, ...]) -> list[str]:
    present = set(nodes)
    return [node.value for node in LogicalNode if node in present]


def _provenance_payload(provenance: ContactPlanProvenance) -> dict[str, object]:
    ordered = tuple(sorted(provenance.statements, key=_statement_sort_key))
    return {
        "source": None if provenance.source is None else _source_payload(provenance.source),
        "statements": [_statement_payload(statement) for statement in ordered],
        "references": list(provenance.references),
        "assumptions": list(provenance.assumptions),
    }


def _source_payload(source: ContactPlanSourceArtifact) -> dict[str, object]:
    return {
        "source_ref": source.source_ref,
        "artifact_ref": source.artifact_ref,
        "artifact_sha256": source.artifact_sha256,
    }


def _statement_payload(statement: ContactProvenanceStatement) -> dict[str, object]:
    return {
        "parameter": statement.parameter.value,
        "classification": statement.classification.value,
        "contact_id": statement.contact_id,
        "source_ref": statement.source_ref,
        "artifact_ref": statement.artifact_ref,
        "artifact_sha256": statement.artifact_sha256,
        "assumption": statement.assumption,
    }


def _statement_sort_key(
    statement: ContactProvenanceStatement,
) -> tuple[str, str, str, str, str, str, str]:
    """Clave del conjunto de atribuciones. No sustituye a ``contact_id``."""
    return (
        "" if statement.contact_id is None else statement.contact_id,
        statement.parameter.value,
        statement.classification.value,
        statement.source_ref,
        "" if statement.artifact_ref is None else statement.artifact_ref,
        "" if statement.artifact_sha256 is None else statement.artifact_sha256,
        "" if statement.assumption is None else statement.assumption,
    )


def _sha256_canonical(payload: dict[str, object]) -> str:
    if HASH_ALGORITHM != "sha256":
        raise RuntimeError("el algoritmo contractual de la huella es sha256")
    encoded = canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_finite(contact: Contact) -> None:
    for name in ("start_time_sim", "end_time_sim", "propagation_delay_s"):
        value = getattr(contact, name)
        if not isfinite(value):
            raise ContactPlanDefinitionError(f"{contact.contact_id}: {name} debe ser finito")


def _require_provenance_contacts(
    provenance: ContactPlanProvenance,
    contacts: tuple[Contact, ...],
) -> None:
    known = {contact.contact_id for contact in contacts}
    seen: set[tuple[str | None, ContactPlanParameter]] = set()
    for statement in provenance.statements:
        if statement.contact_id is not None and statement.contact_id not in known:
            raise ContactPlanDefinitionError(
                f"la provenance nombra un contacto inexistente: {statement.contact_id}"
            )
        key = (statement.contact_id, statement.parameter)
        if key in seen:
            scope = "plan" if statement.contact_id is None else statement.contact_id
            raise ContactPlanDefinitionError(
                f"provenance duplicada para {scope}/{statement.parameter.value}"
            )
        seen.add(key)


def _optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    if value.strip() == "":
        raise ValueError(f"{field_name} no debe estar vacío")
    return value


def _optional_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    if _SHA256_HEX.fullmatch(value) is None:
        raise ValueError(
            "artifact_sha256 debe ser un SHA-256 hexadecimal en minúsculas"
        )
    return value

