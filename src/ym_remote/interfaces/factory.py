from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ym_remote.interfaces.http.routes import router
from ym_remote.interfaces.settings import Settings
from ym_remote.interfaces.ws.handler import CommandHandler
from ym_remote.interfaces.ws.hub import Hub
from ym_remote.net.addresses import choose_network, discover_ips
from ym_remote.services.build import build_services
from ym_remote.services.gate import HeavyGate
from ym_remote.yandex.client import YandexLibrary


def create_app(
    settings: Settings,
    *,
    discovered: list[str] | None = None,
    background: bool = True,
) -> FastAPI:
    network = choose_network(
        discovered if discovered is not None else discover_ips(),
        local_ip=settings.local_ip,
        port=settings.port,
    )
    gate = HeavyGate()
    catalog = YandexLibrary(settings.token)
    hub = Hub()
    services = build_services(settings.cdp_port, gate, catalog, hub)
    session = services.session

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.background:
            await app.state.session.start()
            await app.state.catalog.start()
            app.state.services.monitor.start()
            others = [ip for ip in app.state.network.all if ip != app.state.network.chosen]
            print(f"YM Remote: {app.state.network.url}")
            print(f"Прочие адреса: {', '.join(others) if others else '—'}")
            print(f"CDP: {app.state.settings.cdp_port}")
        try:
            yield
        finally:
            if app.state.background:
                await app.state.services.monitor.stop()
                await app.state.catalog.close()
                await app.state.session.stop()

    app = FastAPI(title="YM Remote", lifespan=lifespan)
    app.state.settings = settings
    app.state.network = network
    app.state.session = session
    app.state.catalog = catalog
    app.state.hub = hub
    app.state.services = services
    app.state.handler = CommandHandler(services.transport, services.queue, services.monitor, hub)
    app.state.background = background
    app.include_router(router)
    return app
