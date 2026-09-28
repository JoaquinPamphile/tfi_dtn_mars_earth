from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.contact import Contact

class FailurePlanError(ValueError):
    """El corte no cae dentro de la ventana o el contacto no está en el plan."""

class ContactCutFailure(BaseModel):
    """Cierre inesperado y determinista de una ventana de contacto.
    ``cut_at_sim`` está en segundos de simulación. La construcción solo exige
    que no sea negativo. La ventana estricta
    ``start_time_sim < cut_at_sim < end_time_sim`` se comprueba después, con
    ``validate_contact_cut`` o ``validate_failure_plan``.
    El objetivo es ``contact_id``. No hay semilla ni elección aleatoria.
    Cerrar la ventana queda para el motor.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")
    failure_id: str
    contact_id: str
    cut_at_sim: float = Field(ge=0)

    @field_validator("failure_id", "contact_id")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("no debe estar vacío")
        return value

def contact_cut_failure_id(contact_id: str) -> str:
    """Identificador determinista de un corte a partir del contacto."""
    return f"contact-cut-{contact_id}"

def validate_contact_cut(contact: Contact, cut_at_sim: float) -> None:
    """Exige ``start_time_sim < cut_at_sim < end_time_sim``."""
    if not (contact.start_time_sim < cut_at_sim < contact.end_time_sim):
        raise FailurePlanError(
            "cut_at_sim debe cumplir "
            "contact.start_time_sim < cut_at_sim < contact.end_time_sim"
        )
