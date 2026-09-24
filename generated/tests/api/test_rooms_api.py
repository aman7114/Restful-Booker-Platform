import pytest
import requests


@pytest.mark.api
def test_get_all_rooms(config):
    """GET /room returns list of rooms."""
    r = requests.get(f"{config['API_BASE_URL']}/room")
    assert r.status_code == 200
    body = r.json()
    assert "rooms" in body
    assert len(body["rooms"]) > 0


@pytest.mark.api
def test_rooms_have_required_fields(config):
    """Each room has roomid, type, and accessible fields."""
    r = requests.get(f"{config['API_BASE_URL']}/room")
    rooms = r.json()["rooms"]
    for room in rooms:
        assert "roomid" in room
        assert "type" in room
        assert "accessible" in room


@pytest.mark.api
def test_get_single_room(config, room_id):
    """GET /room/{id} returns the specific room."""
    r = requests.get(f"{config['API_BASE_URL']}/room/{room_id}")
    assert r.status_code == 200
    body = r.json()
    assert body.get("roomid") == room_id


@pytest.mark.api
def test_get_invalid_room(config):
    """GET /room/99999 returns non-200 (platform returns 404 or 500)."""
    r = requests.get(f"{config['API_BASE_URL']}/room/99999")
    # Platform returns 500 Internal Server Error for non-existent room IDs
    assert r.status_code in [404, 500], f"Expected 404 or 500, got {r.status_code}"
