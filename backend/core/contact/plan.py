from collections import defaultdict
from collections.abc import Sequence
from core.contact.contact import Contact, LogicalNode

class ContactPlanError(ValueError):
    """El plan repite un ``contact_id`` o solapa ventanas del mismo sentido."""

class ContactPlan:
    """Colección inmutable de contactos dirigidos, ordenada de forma determinista.
    El orden es ``(start_time_sim, contact_id)``.
    En un mismo sentido, dos ventanas no pueden solaparse: el inicio de la
    siguiente debe ser mayor o igual que el fin de la anterior.
    Ventanas contiguas, con el fin de una igual al inicio de la otra, son válidas
    porque la ventana es semiabierta.
    Cada sentido es independiente. El plan no crea el contacto inverso.
    """
    def __init__(self, contacts: Sequence[Contact]) -> None:
        ordered = tuple(
            sorted(contacts, key=lambda contact: (contact.start_time_sim, contact.contact_id))
        )
        self._validate(ordered)
        self._contacts = ordered

    @property
    def contacts(self) -> tuple[Contact, ...]:
        """Contactos en orden ``(start_time_sim, contact_id)``."""
        return self._contacts

    def all_contacts(self) -> tuple[Contact, ...]:
        """Los mismos contactos que ``contacts``, en el mismo orden."""
        return self._contacts

    def get(self, contact_id: str) -> Contact:
        """Devuelve el contacto con ese identificador.

        Lanza ``KeyError`` si no existe.
        """
        for contact in self._contacts:
            if contact.contact_id == contact_id:
                return contact
        raise KeyError(contact_id)

    def active_at(self, time_sim: float) -> tuple[Contact, ...]:
        """Contactos cuya ventana semiabierta contiene el instante ``time_sim``."""
        return tuple(contact for contact in self._contacts if contact.is_active_at(time_sim))

    def next_contact_after(
        self,
        time_sim: float,
        source: LogicalNode,
        destination: LogicalNode,
    ) -> Contact | None:
        """Primer contacto del sentido cuyo inicio es estrictamente posterior a ``time_sim``.

        El desempate es ``(start_time_sim, contact_id)``.
        Un contacto ya iniciado no se devuelve.
        """
        return self._next_contact(time_sim, source, destination, inclusive_start=False)

    def next_contact_on_or_after(
        self,
        time_sim: float,
        source: LogicalNode,
        destination: LogicalNode,
    ) -> Contact | None:
        """Primer contacto del sentido cuyo inicio es mayor o igual que ``time_sim``.

        El desempate es ``(start_time_sim, contact_id)``.
        Un contacto ya iniciado, con inicio anterior a ``time_sim``, no se devuelve.
        """
        return self._next_contact(time_sim, source, destination, inclusive_start=True)

    def _next_contact(
        self,
        time_sim: float,
        source: LogicalNode,
        destination: LogicalNode,
        *,
        inclusive_start: bool,
    ) -> Contact | None:
        candidates = [
            contact
            for contact in self._contacts
            if contact.source == source
            and contact.destination == destination
            and (
                contact.start_time_sim >= time_sim
                if inclusive_start
                else contact.start_time_sim > time_sim
            )
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda contact: (contact.start_time_sim, contact.contact_id))

    @staticmethod
    def _validate(contacts: tuple[Contact, ...]) -> None:
        seen_ids: set[str] = set()
        for contact in contacts:
            if contact.contact_id in seen_ids:
                raise ContactPlanError(f"contact_id duplicado: {contact.contact_id}")
            seen_ids.add(contact.contact_id)

        by_link: dict[tuple[LogicalNode, LogicalNode], list[Contact]] = defaultdict(list)
        for contact in contacts:
            by_link[(contact.source, contact.destination)].append(contact)

        for (source, destination), group in by_link.items():
            group.sort(key=lambda contact: (contact.start_time_sim, contact.contact_id))
            for previous, current in zip(group, group[1:]):
                if current.start_time_sim < previous.end_time_sim:
                    raise ContactPlanError(
                        "contactos solapados en "
                        f"{source.value}->{destination.value}: "
                        f"{previous.contact_id} y {current.contact_id}"
                    )
