import requests

def test_get_rooms(api_base_url):
    resp = requests.get(f"{api_base_url}/room/")
    assert resp.status_code == 200
    assert "rooms" in resp.json()
    assert isinstance(resp.json()["rooms"], list)
