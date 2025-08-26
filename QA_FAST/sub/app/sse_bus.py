from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, Set


class RoomEventBus:
    def __init__(self) -> None:
        self._room_id_to_queues: Dict[int, Set[asyncio.Queue]] = defaultdict(set)

    def add_subscriber(self, room_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._room_id_to_queues[room_id].add(queue)
        return queue

    def remove_subscriber(self, room_id: int, queue: asyncio.Queue) -> None:
        try:
            self._room_id_to_queues[room_id].discard(queue)
            if not self._room_id_to_queues[room_id]:
                self._room_id_to_queues.pop(room_id, None)
        except KeyError:
            pass

    def publish(self, room_id: int, payload: dict) -> None:
        for q in list(self._room_id_to_queues.get(room_id, set())):
            try:
                q.put_nowait(payload)
            except Exception:
                # Drop if queue is closed or full
                pass


bus = RoomEventBus()


