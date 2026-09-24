import pytest
import requests


@pytest.mark.api
def test_login_valid_credentials(config):
    """POST /auth/login with valid creds returns 200 and a token."""
    r = requests.post(
        f"{config['API_BASE_URL']}/auth/login",
        json={"username": config["ADMIN_USERNAME"], "password": config["ADMIN_PASSWORD"]},
    )
    assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
    body = r.json()
    assert "token" in body and body["token"], "Token missing or empty"


@pytest.mark.api
def test_login_invalid_password(config):
    """POST /auth/login with wrong password returns 4xx."""
    r = requests.post(
        f"{config['API_BASE_URL']}/auth/login",
        json={"username": config["ADMIN_USERNAME"], "password": "wrong_xyz"},
    )
    # Platform returns 403 with {"error": "Invalid credentials"}
    assert r.status_code in [400, 401, 403], f"Expected 4xx, got {r.status_code}"
    body = r.json()
    assert "error" in body or "reason" in body, f"Expected error key, got: {body}"


@pytest.mark.api
def test_login_empty_credentials(config):
    """POST /auth/login with empty creds returns 4xx."""
    r = requests.post(
        f"{config['API_BASE_URL']}/auth/login",
        json={"username": "", "password": ""},
    )
    assert r.status_code in [400, 401, 403], f"Expected 4xx, got {r.status_code}"
    body = r.json()
    assert "error" in body or "reason" in body, f"Expected error key, got: {body}"
