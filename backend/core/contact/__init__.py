"""Contactos dirigidos y plan de contactos en tiempo lógico de simulación."""

from core.contact.contact import Contact, LogicalNode
from core.contact.plan import ContactPlan, ContactPlanError

__all__ = [
    "Contact",
    "ContactPlan",
    "ContactPlanError",
    "LogicalNode",
]
