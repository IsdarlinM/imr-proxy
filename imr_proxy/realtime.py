from __future__ import annotations

import asyncio
import itertools
import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrafficSubscription:
    id: int
    queue: asyncio.Queue[int]


class TrafficEventBus:
    """Thread-safe in-process fan-out for committed traffic revisions.

    The proxy engine and Web UI run in different threads. Flow persistence can
    therefore publish from the proxy thread while each WebSocket receives the
    newest committed revision on its own asyncio event loop.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._subscribers: dict[int, tuple[asyncio.AbstractEventLoop, asyncio.Queue[int]]] = {}

    def subscribe(self) -> TrafficSubscription:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[int] = asyncio.Queue(maxsize=1)
        subscription_id = next(self._counter)
        with self._lock:
            self._subscribers[subscription_id] = (loop, queue)
        return TrafficSubscription(subscription_id, queue)

    def unsubscribe(self, subscription: TrafficSubscription) -> None:
        with self._lock:
            self._subscribers.pop(subscription.id, None)

    @staticmethod
    def _offer(queue: asyncio.Queue[int], revision: int) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(revision)

    def publish(self, revision: int) -> None:
        with self._lock:
            subscribers = list(self._subscribers.items())
        stale: list[int] = []
        for subscription_id, (loop, queue) in subscribers:
            if loop.is_closed():
                stale.append(subscription_id)
                continue
            try:
                loop.call_soon_threadsafe(self._offer, queue, revision)
            except RuntimeError:
                stale.append(subscription_id)
        if stale:
            with self._lock:
                for subscription_id in stale:
                    self._subscribers.pop(subscription_id, None)


traffic_events = TrafficEventBus()
