import pytest
import requests
import datetime
import uuid


@pytest.mark.api
def test_create_booking(config, authenticated_api_session, booking_payload):
    """POST /booking creates a booking; response is FLAT (no nested 'booking' key)."""
    r = authenticated_api_session.post(
        f"{config['API_BASE_URL']}/booking", json=booking_payload
    )
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    body = r.json()
    # Response is flat: bookingid and firstname are at root level
    assert "bookingid" in body, f"bookingid missing. Got: {body}"
    assert isinstance(body["bookingid"], int)
    assert body.get("firstname") == booking_payload["firstname"], (
        f"firstname mismatch. Got: {body}"
    )
    pytest.created_booking_id = body["bookingid"]


@pytest.mark.api
def test_get_created_booking(config, authenticated_api_session):
    """GET /booking/{id} returns the created booking (flat structure)."""
    if not hasattr(pytest, "created_booking_id"):
        pytest.skip("Booking ID not available")
    r = authenticated_api_session.get(
        f"{config['API_BASE_URL']}/booking/{pytest.created_booking_id}"
    )
    assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
    body = r.json()
    assert body.get("bookingid") == pytest.created_booking_id


@pytest.mark.api
def test_update_booking(config, authenticated_api_session, booking_payload):
    """PUT /booking/{id} updates; response is NESTED under 'booking' key."""
    if not hasattr(pytest, "created_booking_id"):
        pytest.skip("Booking ID not available")
    updated = booking_payload.copy()
    updated["firstname"] = f"Updated{uuid.uuid4().hex[:4]}"
    # Use dates 500+ days ahead to avoid date-conflict 409
    far = datetime.date.today() + datetime.timedelta(days=500)
    updated["bookingdates"] = {
        "checkin": str(far),
        "checkout": str(far + datetime.timedelta(days=2)),
    }
    r = authenticated_api_session.put(
        f"{config['API_BASE_URL']}/booking/{pytest.created_booking_id}",
        json=updated,
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    # PUT response wraps booking under a "booking" key
    booking_data = body.get("booking", body)
    assert booking_data.get("firstname") == updated["firstname"], (
        f"firstname not updated. Got: {body}"
    )


@pytest.mark.api
def test_delete_booking(config, authenticated_api_session):
    """DELETE /booking/{id} removes the booking."""
    if not hasattr(pytest, "created_booking_id"):
        pytest.skip("Booking ID not available")
    r = authenticated_api_session.delete(
        f"{config['API_BASE_URL']}/booking/{pytest.created_booking_id}"
    )
    assert r.status_code in [202, 204], f"Expected 202/204, got {r.status_code}"


@pytest.mark.api
def test_get_deleted_booking(config, authenticated_api_session):
    """GET after delete returns 404."""
    if not hasattr(pytest, "created_booking_id"):
        pytest.skip("Booking ID not available")
    r = authenticated_api_session.get(
        f"{config['API_BASE_URL']}/booking/{pytest.created_booking_id}"
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


@pytest.mark.api
def test_create_booking_missing_field(config, authenticated_api_session, booking_payload):
    """POST without required field returns 4xx."""
    bad = booking_payload.copy()
    bad.pop("firstname")
    r = authenticated_api_session.post(
        f"{config['API_BASE_URL']}/booking", json=bad
    )
    assert 400 <= r.status_code < 500, f"Expected 4xx, got {r.status_code}"


@pytest.mark.api
def test_create_booking_no_auth(config, booking_payload):
    """POST /booking without auth returns 201 (public booking allowed by design)."""
    r = requests.post(f"{config['API_BASE_URL']}/booking", json=booking_payload)
    assert r.status_code == 201, (
        f"Expected 201 for public booking, got {r.status_code}: {r.text}"
    )
    assert "bookingid" in r.json(), "bookingid missing from public booking response"


@pytest.mark.api
def test_delete_without_auth(config, booking_payload):
    """DELETE /booking/{id} without auth returns 403."""
    # First create a booking to delete
    r_create = requests.post(
        f"{config['API_BASE_URL']}/booking", json=booking_payload
    )
    assert r_create.status_code == 201, f"Setup failed: {r_create.text}"
    bid = r_create.json()["bookingid"]
    # Attempt unauthenticated delete
    r_del = requests.delete(f"{config['API_BASE_URL']}/booking/{bid}")
    assert r_del.status_code == 403, f"Expected 403, got {r_del.status_code}"
