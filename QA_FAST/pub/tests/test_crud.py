from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_user_crud_and_update():
    # create user
    r = client.post('/crud/users', json={'username': 'alice'})
    assert r.status_code == 200
    user = r.json()
    user_id = user['id']

    # list with pagination
    r = client.get('/crud/users', params={'page': 1, 'size': 10})
    assert r.status_code == 200
    data = r.json()
    assert 'items' in data and len(data['items']) >= 1

    # update
    r = client.patch(f'/crud/users/{user_id}', json={'username': 'alice2', 'status': 'inactive'})
    assert r.status_code == 200
    updated = r.json()
    assert updated['username'] == 'alice2'
    assert updated['status'] == 'inactive'


def test_room_and_messages_pagination():
    # create user and room
    u = client.post('/crud/users', json={'username': 'bob'}).json()
    room = client.post('/crud/rooms', json={'type': 'dm', 'title': 't'}).json()
    # add member
    client.post('/crud/room-members', json={'roomId': room['id'], 'userId': u['id']})

    # create messages
    for i in range(30):
        client.post('/crud/messages', json={'roomId': room['id'], 'senderId': u['id'], 'content': f'm{i}'})

    # list page 1
    r = client.get(f"/crud/rooms/{room['id']}/messages", params={'page': 1, 'size': 10})
    assert r.status_code == 200
    p1 = r.json()
    assert len(p1['items']) == 10

    # list page 2
    r = client.get(f"/crud/rooms/{room['id']}/messages", params={'page': 2, 'size': 10})
    assert r.status_code == 200
    p2 = r.json()
    assert len(p2['items']) == 10


