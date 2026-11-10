from __future__ import annotations


class HeavyGate:
    """Пока глубина больше нуля, монитор пропускает ход и спит, а не встаёт в очередь CDP."""

    def __init__(self) -> None:
        self._depth = 0

    @property
    def active(self) -> bool:
        return self._depth > 0

    async def __aenter__(self) -> HeavyGate:
        self._depth += 1
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._depth = max(0, self._depth - 1)

    def hold(self):
        return self
