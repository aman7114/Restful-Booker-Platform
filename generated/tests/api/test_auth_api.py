import requests


def test_login_success(api_base_url):
    response = requests.post(
        f"{api_base_url}/auth/login",
        json={"username": "admin", "password": "password"},
        timeout=30,
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("token")


def test_login_negative(api_base_url):
    response = requests.post(
        f"{api_base_url}/auth/login",
        json={"username": "admin", "password": "wrong"},
        timeout=30,
    )
    assert response.status_code == 401
