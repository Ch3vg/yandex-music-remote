import pytest

from ym_remote.models.errors import RemoteError
from ym_remote.models.playback import QueueView
from ym_remote.services.gate import HeavyGate
from ym_remote.services.queue import QueueService
from ym_remote.services.texts import SKIP_FAILED, SKIP_TOO_FAR


class Adapter:
    def __init__(self) -> None:
        self.steps: list[int] = []

    async def skip(self, steps: int) -> tuple[bool, QueueView]:
        self.steps.append(steps)
        return True, QueueView.empty()

    async def read_queue(self) -> QueueView:
        return QueueView.empty()


async def test_skip_rejects_more_than_forty_steps_without_clicking():
    adapter = Adapter()
    service = QueueService(adapter, HeavyGate())
    with pytest.raises(RemoteError) as exc:
        await service.skip(41)
    assert exc.value.message == SKIP_TOO_FAR
    assert adapter.steps == []


async def test_skip_reports_failure_when_the_track_does_not_change():
    class Stuck(Adapter):
        async def skip(self, steps: int) -> tuple[bool, QueueView]:
            self.steps.append(steps)
            return False, QueueView.empty()

    adapter = Stuck()
    service = QueueService(adapter, HeavyGate())
    with pytest.raises(RemoteError) as exc:
        await service.skip(-3)
    assert exc.value.message == SKIP_FAILED
    assert adapter.steps == [-3]


async def test_skip_passes_signed_steps():
    adapter = Adapter()
    service = QueueService(adapter, HeavyGate())
    view = await service.skip(2)
    assert view.before == ()
    assert adapter.steps == [2]
