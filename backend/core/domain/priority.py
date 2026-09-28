from enum import StrEnum

class TelemetryPriority(StrEnum):
    BULK = "bulk"
    NORMAL = "normal"
    EXPEDITED = "expedited"
