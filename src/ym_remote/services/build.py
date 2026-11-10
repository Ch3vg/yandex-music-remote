"""Сборка сервисов. Маршруты этот модуль не импортируют."""

from __future__ import annotations

from dataclasses import dataclass

from ym_remote.cdp.monitor import MonitorCdpAdapter
from ym_remote.cdp.queue import QueueCdpAdapter
from ym_remote.cdp.search import SearchCdpAdapter
from ym_remote.cdp.session import CdpSession
from ym_remote.cdp.transport import TransportCdpAdapter
from ym_remote.services.gate import HeavyGate
from ym_remote.services.library import LibraryService
from ym_remote.services.monitor import MonitorService
from ym_remote.services.queue import QueueService
from ym_remote.services.search import SearchService
from ym_remote.services.transport import TransportService
from ym_remote.yandex.client import YandexLibrary


@dataclass
class Services:
    library: LibraryService
    search: SearchService
    transport: TransportService
    queue: QueueService
    monitor: MonitorService
    session: CdpSession
    catalog: YandexLibrary
    gate: HeavyGate


def build_services(cdp_port: int, gate: HeavyGate, catalog: YandexLibrary, hub) -> Services:
    session = CdpSession(cdp_port)
    library = LibraryService(catalog)
    return Services(
        library=library,
        search=SearchService(SearchCdpAdapter(session), gate, library),
        transport=TransportService(TransportCdpAdapter(session), library, gate),
        queue=QueueService(QueueCdpAdapter(session), gate),
        monitor=MonitorService(MonitorCdpAdapter(session), gate, hub),
        session=session,
        catalog=catalog,
        gate=gate,
    )
