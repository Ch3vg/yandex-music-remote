"""Одно соединение CDP и одна очередь транзакций на процесс.

Транзакция — весь публичный метод адаптера команды. Пока она выполняется,
следующая команда ждёт в этой очереди и не вклинивает evaluate между шагами.
Опрос монитора в очередь не встаёт: он вызывает evaluate напрямую и, пока
поднят флаг тяжёлой команды, не делает даже этого.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
import urllib.request
from collections.abc import Awaitable, Callable
from typing import TypeVar

import websocket

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CdpUnavailable(Exception):
    """Список страниц или сокет отладчика недоступны."""


class CdpError(Exception):
    """Выражение в странице завершилось ошибкой или таймаутом."""


def score_page(url: str) -> int:
    score = 0
    if "music-application" in url:
        score += 1000
    if "album/track" in url or "/track" in url:
        score += 200
    if "user-id" in url or "passport" in url:
        score -= 800
    return score


class CdpSession:
    def __init__(self, port: int = 9222) -> None:
        self.port = port
        self._queue: asyncio.Queue | None = None
        self._worker: asyncio.Task | None = None
        self._eval_lock = asyncio.Lock()
        self._owner: asyncio.Task | None = None
        self._ws = None
        self._ws_url: str | None = None
        self._page_url: str | None = None
        self._msg_id = 0
        self._socket_guard = threading.Lock()

    async def start(self) -> None:
        if self._worker is not None and not self._worker.done():
            return
        self._queue = asyncio.Queue()
        self._worker = asyncio.create_task(self._worker_loop(), name="cdp-transactions")

    async def stop(self) -> None:
        worker = self._worker
        queue = self._queue
        self._worker = None
        self._queue = None
        if worker is not None and queue is not None:
            await queue.put(None)
            try:
                await worker
            except asyncio.CancelledError:
                pass
        await asyncio.to_thread(self._close_ws)

    async def run(self, work: Callable[[], Awaitable[T]]) -> T:
        """Выполнить одну транзакцию целиком, строго после предыдущей."""
        if self._queue is None:
            await self.start()
        assert self._queue is not None
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((work, future))
        return await future

    async def evaluate(self, expression: str, timeout: float = 3.0):
        task = asyncio.current_task()
        if self._owner is task:
            return await asyncio.to_thread(self._evaluate_sync, expression, timeout)
        async with self._eval_lock:
            self._owner = task
            try:
                return await asyncio.to_thread(self._evaluate_sync, expression, timeout)
            finally:
                self._owner = None

    async def _worker_loop(self) -> None:
        assert self._queue is not None
        while True:
            item = await self._queue.get()
            if item is None:
                return
            work, future = item
            try:
                async with self._eval_lock:
                    self._owner = asyncio.current_task()
                    try:
                        result = await work()
                    finally:
                        self._owner = None
            except asyncio.CancelledError:
                if not future.done():
                    future.cancel()
                raise
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
            else:
                if not future.done():
                    future.set_result(result)

    def _evaluate_sync(self, expression: str, timeout: float):
        with self._socket_guard:
            self._ensure_connected()
            assert self._ws is not None
            self._msg_id += 1
            message_id = self._msg_id
            payload = {
                "id": message_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expression,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
            }
            try:
                self._ws.send(json.dumps(payload))
            except Exception as exc:
                self._close_ws()
                raise CdpUnavailable("сокет CDP закрыт") from exc
            end = time.monotonic() + timeout
            while True:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    raise CdpError("таймаут CDP")
                self._ws.settimeout(remaining)
                try:
                    raw = self._ws.recv()
                except Exception as exc:
                    self._close_ws()
                    raise CdpError("сокет CDP оборвался") from exc
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if data.get("id") != message_id:
                    continue
                if data.get("error"):
                    raise CdpError(str(data["error"]))
                result = data.get("result") or {}
                if result.get("exceptionDetails"):
                    details = result["exceptionDetails"]
                    text = details.get("text") or details.get("exception", {}).get("description") or "js"
                    raise CdpError(str(text))
                remote = result.get("result") or {}
                if remote.get("subtype") == "error":
                    raise CdpError(str(remote.get("description") or "error"))
                return remote.get("value")

    def _ensure_connected(self) -> None:
        ws_url, page_url = self._pick_page()
        if self._ws is not None and self._ws_url == ws_url and self._page_url == page_url:
            return
        self._close_ws()
        try:
            connection = websocket.create_connection(ws_url, timeout=3, suppress_origin=True)
        except Exception as exc:
            raise CdpUnavailable("не удалось открыть сокет CDP") from exc
        self._ws = connection
        self._ws_url = ws_url
        self._page_url = page_url
        self._msg_id += 1
        enable_id = self._msg_id
        try:
            connection.send(json.dumps({"id": enable_id, "method": "Runtime.enable"}))
            connection.settimeout(3)
            while True:
                raw = connection.recv()
                data = json.loads(raw)
                if data.get("id") == enable_id:
                    break
        except Exception as exc:
            self._close_ws()
            raise CdpUnavailable("Runtime.enable не подтверждён") from exc

    def _pick_page(self) -> tuple[str, str]:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/json")
        try:
            with opener.open(request, timeout=2) as response:
                pages = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise CdpUnavailable("список страниц CDP недоступен") from exc
        candidates = [page for page in pages if page.get("type") == "page" and page.get("webSocketDebuggerUrl")]
        if not candidates:
            raise CdpUnavailable("в CDP нет страницы")
        best = max(candidates, key=lambda page: score_page(str(page.get("url") or "")))
        return str(best["webSocketDebuggerUrl"]), str(best.get("url") or "")

    def _close_ws(self) -> None:
        connection = self._ws
        self._ws = None
        self._ws_url = None
        self._page_url = None
        if connection is not None:
            try:
                connection.close()
            except Exception:
                logger.debug("не удалось закрыть сокет CDP", exc_info=True)
