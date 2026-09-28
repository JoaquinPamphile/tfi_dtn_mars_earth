from enum import StrEnum

class ProvenanceClassification(StrEnum):
    """Origen legible por máquina de un parámetro del simulador.

    Un valor publicado en un artículo y un supuesto de modelado del TFI no
    deben compartir una cadena indiferenciada. Cada parámetro de
    investigación usa exactamente una de estas clases.
    """
    SOURCE_DIRECT = "SOURCE_DIRECT"
    SOURCE_TRANSFORMED = "SOURCE_TRANSFORMED"
    SOURCE_APPROXIMATED = "SOURCE_APPROXIMATED"
    TFI_ASSUMPTION = "TFI_ASSUMPTION"
    TFI_SENSITIVITY = "TFI_SENSITIVITY"
    DEVELOPMENT_ONLY = "DEVELOPMENT_ONLY"
    EXTERNAL_PHYSICAL_CONSTANT = "EXTERNAL_PHYSICAL_CONSTANT"
