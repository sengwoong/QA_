import json
import threading
import time
from contextlib import contextmanager

import httpx
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@contextmanager
def sse_client(room_id: int, to_user_id: int):
    with httpx.Client(timeout=None) as c:
        with c.stream('GET', f'http://testserver/sse/rooms/{room_id}', params={'toUserId': to_user_id}) as r:
            yield r


def test_message_triggers_notify_and_sse_filters():
    room_id = 999
    sender_id = 1
    target_user = 2

    # Start SSE listener in a thread
    events = []

    def listen():
        with sse_client(room_id, target_user) as r:
            for line in r.iter_lines():
                if line.startswith('data: '):
                    payload = json.loads(line[len('data: '):])
                    events.append(payload)
                    break

    th = threading.Thread(target=listen, daemon=True)
    th.start()

    time.sleep(0.5)

    # Publish message to DB via API
    resp = client.post('/messages', json={
        'roomId': room_id,
        'senderId': sender_id,
        'toUserId': target_user,
        'content': 'hello'
    })
    assert resp.status_code == 200

    # wait for event
    for _ in range(30):
        if events:
            break
        time.sleep(0.2)

    assert events, 'No SSE event received'
    evt = events[0]
    assert evt['roomId'] == room_id
    assert evt['senderId'] == sender_id
    assert evt['toUserId'] == target_user


