from __future__ import annotations

from ym_remote.cdp.scripts import script
from ym_remote.cdp.session import CdpSession


class CdpAdapter:
    """Общая сессия, клик, ввод, ожидание, поиск и чтение бара.

    Наследники не открывают соединение: его держит только CdpSession.
    """

    def __init__(self, session: CdpSession) -> None:
        self.session = session

    async def evaluate(self, expression: str, timeout: float = 3.0):
        return await self.session.evaluate(expression, timeout)

    async def wait(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    async def find(self, test_id: str) -> bool:
        import json

        body = f"return !!ymById({json.dumps(test_id)});"
        return bool(await self.evaluate(script(body)))

    async def click(self, test_id: str) -> bool:
        import json

        body = f"return ymClick(ymById({json.dumps(test_id)}));"
        return bool(await self.evaluate(script(body)))

    async def fill(self, test_id: str, value: str) -> bool:
        import json

        body = (
            "const el = ymById("
            + json.dumps(test_id)
            + ");"
            + f"return ymSetNativeValue(el, {json.dumps(value)});"
        )
        return bool(await self.evaluate(script(body)))

    async def read_bar(self) -> dict | None:
        from ym_remote.cdp.scripts import read_bar_script

        raw = await self.evaluate(read_bar_script(), timeout=3)
        return raw if isinstance(raw, dict) else None
