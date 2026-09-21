import requests
from datetime import datetime, timedelta


def test_create_and_get_booking(api_base_url):
    session = requests.Session()

    auth_response = session.post(
        f"{api_base_url}/auth/login",
        json={"username": "admin", "password": "password"},
        timeout=30,
    )
    assert auth_response.status_code == 200
    token = auth_response.json().get("token")
    assert token
    session.cookies.set("token", token)

    rooms_response = session.get(
        f"{api_base_url}/room/",
        timeout=30,
    )
    assert rooms_response.status_code == 200

    rooms = rooms_response.json().get("rooms", [])
    assert rooms, "No rooms returned by the API"

    # Use a future window and a few candidate rooms/dates. The deployed
    # platform resets its seeded database periodically, so the test must not
    # depend on a fixed room/date combination.
    start = datetime.now() + timedelta(days=30)
    created_booking = None
    last_conflict = None

    for room in rooms:
        room_id = room.get("roomid")
        if room_id is None:
            continue

        for offset in range(0, 60, 2):
            checkin = start + timedelta(days=offset)
            checkout = checkin + timedelta(days=1)
            payload = {
                "bookingdates": {
                    "checkin": checkin.strftime("%Y-%m-%d"),
                    "checkout": checkout.strftime("%Y-%m-%d"),
                },
                "depositpaid": True,
                "firstname": "Test",
                "lastname": "User",
                "roomid": room_id,
            }

            response = session.post(
                f"{api_base_url}/booking/",
                json=payload,
                timeout=30,
            )

            if response.status_code == 201:
                created_booking = response.json()
                break

            if response.status_code == 409:
                last_conflict = response.text
                continue

            raise AssertionError(
                f"Unexpected booking creation status {response.status_code}: {response.text}"
            )

        if created_booking is not None:
            break

    assert created_booking is not None, (
        "Could not create a booking for returned rooms/date combinations. "
        f"Last conflict: {last_conflict}"
    )

    booking_id = created_booking.get("bookingid")
    assert booking_id is not None

    get_response = session.get(
        f"{api_base_url}/booking/{booking_id}",
        timeout=30,
    )
    assert get_response.status_code == 200

    booking = get_response.json()
    assert booking.get("bookingid") == booking_id
    assert booking.get("roomid") == created_booking.get("roomid")
    assert booking.get("firstname") == "Test"
    assert booking.get("lastname") == "User"
