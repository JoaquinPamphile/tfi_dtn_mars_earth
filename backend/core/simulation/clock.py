class SimulationClock:
    """
    Tiempo lógico de simulación, en segundos.
    """
    def __init__(self) -> None:
        self._now = 0.0

    @property
    def now(self) -> float:
        return self._now

    def advance_to(self, time: float) -> None:
        if time < self._now:
            raise ValueError("el tiempo de simulación nunca retrocede")
        self._now = time