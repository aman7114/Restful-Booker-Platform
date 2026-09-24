"""
generation/api_generator.py

Responsible ONLY for:
- Exploring API endpoints using requests
- Collecting response evidence (status, headers, body structure)
- Covering auth, rooms, and booking CRUD + negative scenarios
- Saving evidence to evidence/api/

No test generation here. No Gemini calls. Evidence collection ONLY.
All test data is generated at runtime (no hardcoded values).
"""

import json
import logging
import random
import string
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import requests

from generation.config import Config

logger = logging.getLogger(__name__)

EVIDENCE_DIR = Path("evidence/api")


def _save_evidence(filename: str, data: Any) -> None:
    """Save API evidence as JSON."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = EVIDENCE_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.debug(f"API evidence saved: {filepath}")


def _random_name() -> str:
    """Generate a random realistic-ish first name."""
    names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn"]
    suffix = "".join(random.choices(string.digits, k=4))
    return f"{random.choice(names)}{suffix}"


def _random_email() -> str:
    """Generate a random email address."""
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


def _random_phone() -> str:
    """Generate a valid 11-digit phone string."""
    return "07" + "".join(random.choices(string.digits, k=9))


def _future_dates(days_from_now: int = 30, stay_length: int = 2) -> tuple[str, str]:
    """Generate future check-in/check-out dates relative to today."""
    checkin = date.today() + timedelta(days=days_from_now)
    checkout = checkin + timedelta(days=stay_length)
    return checkin.isoformat(), checkout.isoformat()


def _record_request(
    method: str,
    url: str,
    payload: Any,
    response: requests.Response,
    scenario: str,
) -> dict:
    """Build a structured evidence record for one HTTP interaction."""
    try:
        body = response.json()
    except Exception:
        body = response.text[:500]

    return {
        "scenario": scenario,
        "method": method,
        "url": url,
        "request_payload": payload,
        "response_status": response.status_code,
        "response_headers": dict(response.headers),
        "response_body": body,
    }


def explore_api(config: Config) -> dict:
    """
    Run all API exploration workflows.

    Returns a summary dict of all collected evidence.
    """
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    timeout = config.api_timeout

    evidence_summary = {
        "api_base_url": config.api_base_url,
        "workflows": {},
        "evidence_files": [],
    }

    # --------------------------------------------------------
    # AUTH EXPLORATION
    # --------------------------------------------------------
    logger.info("  [API] Exploring: Auth")
    auth_evidence = _explore_auth(session, config, timeout)
    _save_evidence("auth_evidence.json", auth_evidence)
    evidence_summary["workflows"]["auth"] = auth_evidence
    evidence_summary["evidence_files"].append("auth_evidence.json")

    # Get the token for authenticated calls
    token = auth_evidence.get("token", "")

    # --------------------------------------------------------
    # ROOMS EXPLORATION
    # --------------------------------------------------------
    logger.info("  [API] Exploring: Rooms")
    rooms_evidence = _explore_rooms(session, config, timeout)
    _save_evidence("rooms_evidence.json", rooms_evidence)
    evidence_summary["workflows"]["rooms"] = rooms_evidence
    evidence_summary["evidence_files"].append("rooms_evidence.json")

    # Get a real room ID for booking tests
    room_id = rooms_evidence.get("first_room_id")

    # --------------------------------------------------------
    # BOOKINGS EXPLORATION
    # --------------------------------------------------------
    logger.info("  [API] Exploring: Bookings")
    bookings_evidence = _explore_bookings(session, config, timeout, token, room_id)
    _save_evidence("bookings_evidence.json", bookings_evidence)
    evidence_summary["workflows"]["bookings"] = bookings_evidence
    evidence_summary["evidence_files"].append("bookings_evidence.json")

    # Save overall summary
    _save_evidence("api_evidence_summary.json", evidence_summary)
    return evidence_summary


def _explore_auth(
    session: requests.Session, config: Config, timeout: int
) -> dict:
    """Explore POST /auth/login — positive and negative scenarios."""
    base = config.api_base_url
    evidence = {
        "endpoint": f"{base}/auth/login",
        "method": "POST",
        "scenarios": [],
        "token": "",
    }

    # Positive: valid credentials
    payload = {
        "username": config.admin_username,
        "password": config.admin_password,
    }
    try:
        resp = session.post(f"{base}/auth/login", json=payload, timeout=timeout)
        rec = _record_request("POST", f"{base}/auth/login", payload, resp, "valid_credentials")
        evidence["scenarios"].append(rec)

        if resp.status_code == 200:
            body = resp.json()
            token = body.get("token", "")
            evidence["token"] = token
            # Set token cookie for subsequent authenticated requests
            session.cookies.set("token", token)
            logger.info(f"  [API] Auth token obtained: {token[:10]}...")
    except Exception as e:
        evidence["scenarios"].append({"scenario": "valid_credentials", "error": str(e)})

    # Negative: invalid password
    bad_payload = {
        "username": config.admin_username,
        "password": "wrong_password_xyz",
    }
    try:
        resp = session.post(
            f"{base}/auth/login", json=bad_payload, timeout=timeout
        )
        evidence["scenarios"].append(
            _record_request("POST", f"{base}/auth/login", bad_payload, resp, "invalid_password")
        )
    except Exception as e:
        evidence["scenarios"].append({"scenario": "invalid_password", "error": str(e)})

    # Negative: empty credentials
    empty_payload = {"username": "", "password": ""}
    try:
        resp = session.post(
            f"{base}/auth/login", json=empty_payload, timeout=timeout
        )
        evidence["scenarios"].append(
            _record_request("POST", f"{base}/auth/login", empty_payload, resp, "empty_credentials")
        )
    except Exception as e:
        evidence["scenarios"].append({"scenario": "empty_credentials", "error": str(e)})

    return evidence


def _explore_rooms(
    session: requests.Session, config: Config, timeout: int
) -> dict:
    """Explore GET /room and GET /room/{id} endpoints."""
    base = config.api_base_url
    evidence = {
        "endpoint": f"{base}/room",
        "scenarios": [],
        "first_room_id": None,
        "discovered_rooms": [],
    }

    # GET all rooms
    try:
        resp = session.get(f"{base}/room", timeout=timeout)
        rec = _record_request("GET", f"{base}/room", None, resp, "get_all_rooms")
        evidence["scenarios"].append(rec)

        if resp.status_code == 200:
            body = resp.json()
            rooms = body.get("rooms", [])
            evidence["discovered_rooms"] = [
                {
                    "roomid": r.get("roomid"),
                    "roomName": r.get("roomName"),
                    "type": r.get("type"),
                    "roomPrice": r.get("roomPrice"),
                    "accessible": r.get("accessible"),
                    "features": r.get("features", []),
                }
                for r in rooms
            ]
            if rooms:
                evidence["first_room_id"] = rooms[0].get("roomid")
    except Exception as e:
        evidence["scenarios"].append({"scenario": "get_all_rooms", "error": str(e)})

    # GET single room by ID
    room_id = evidence.get("first_room_id")
    if room_id:
        try:
            resp = session.get(f"{base}/room/{room_id}", timeout=timeout)
            evidence["scenarios"].append(
                _record_request(
                    "GET", f"{base}/room/{room_id}", None, resp, f"get_room_{room_id}"
                )
            )
        except Exception as e:
            evidence["scenarios"].append(
                {"scenario": f"get_room_{room_id}", "error": str(e)}
            )

    # GET non-existent room
    try:
        resp = session.get(f"{base}/room/99999", timeout=timeout)
        evidence["scenarios"].append(
            _record_request("GET", f"{base}/room/99999", None, resp, "get_invalid_room")
        )
    except Exception as e:
        evidence["scenarios"].append({"scenario": "get_invalid_room", "error": str(e)})

    return evidence


def _explore_bookings(
    session: requests.Session,
    config: Config,
    timeout: int,
    token: str,
    room_id: int | None,
) -> dict:
    """
    Explore booking CRUD endpoints + negative scenarios.

    All test data is generated at runtime.
    """
    base = config.api_base_url
    evidence = {
        "endpoint": f"{base}/booking",
        "scenarios": [],
        "created_booking_id": None,
        "booking_payload": None,
    }

    if not room_id:
        evidence["warning"] = "No room_id available — skipping booking exploration"
        return evidence

    # Generate fresh booking data
    checkin, checkout = _future_dates(days_from_now=30, stay_length=2)
    firstname = _random_name()
    lastname = _random_name()
    email = _random_email()
    phone = _random_phone()

    booking_payload = {
        "roomid": room_id,
        "firstname": firstname,
        "lastname": lastname,
        "depositpaid": True,
        "email": email,
        "phone": phone,
        "bookingdates": {
            "checkin": checkin,
            "checkout": checkout,
        },
    }
    evidence["booking_payload"] = booking_payload

    # POST /booking — create
    try:
        resp = session.post(f"{base}/booking", json=booking_payload, timeout=timeout)
        rec = _record_request("POST", f"{base}/booking", booking_payload, resp, "create_booking")
        evidence["scenarios"].append(rec)

        if resp.status_code == 201:
            body = resp.json()
            evidence["created_booking_id"] = body.get("bookingid")
            logger.info(f"  [API] Booking created: ID={evidence['created_booking_id']}")
    except Exception as e:
        evidence["scenarios"].append({"scenario": "create_booking", "error": str(e)})

    booking_id = evidence.get("created_booking_id")

    # GET /booking — list all
    try:
        resp = session.get(f"{base}/booking", timeout=timeout)
        evidence["scenarios"].append(
            _record_request("GET", f"{base}/booking", None, resp, "get_all_bookings")
        )
    except Exception as e:
        evidence["scenarios"].append({"scenario": "get_all_bookings", "error": str(e)})

    # GET /booking/{id} — retrieve created
    if booking_id:
        try:
            resp = session.get(f"{base}/booking/{booking_id}", timeout=timeout)
            evidence["scenarios"].append(
                _record_request(
                    "GET", f"{base}/booking/{booking_id}",
                    None, resp, f"get_booking_{booking_id}"
                )
            )
        except Exception as e:
            evidence["scenarios"].append(
                {"scenario": f"get_booking_{booking_id}", "error": str(e)}
            )

    # PUT /booking/{id} — update
    if booking_id:
        checkin2, checkout2 = _future_dates(days_from_now=60, stay_length=3)
        update_payload = {
            **booking_payload,
            "firstname": _random_name(),
            "bookingdates": {"checkin": checkin2, "checkout": checkout2},
        }
        try:
            resp = session.put(
                f"{base}/booking/{booking_id}", json=update_payload, timeout=timeout
            )
            evidence["scenarios"].append(
                _record_request(
                    "PUT", f"{base}/booking/{booking_id}",
                    update_payload, resp, f"update_booking_{booking_id}"
                )
            )
        except Exception as e:
            evidence["scenarios"].append(
                {"scenario": f"update_booking_{booking_id}", "error": str(e)}
            )

    # DELETE /booking/{id} — cleanup
    if booking_id:
        try:
            resp = session.delete(f"{base}/booking/{booking_id}", timeout=timeout)
            evidence["scenarios"].append(
                _record_request(
                    "DELETE", f"{base}/booking/{booking_id}",
                    None, resp, f"delete_booking_{booking_id}"
                )
            )
        except Exception as e:
            evidence["scenarios"].append(
                {"scenario": f"delete_booking_{booking_id}", "error": str(e)}
            )

    # ---- NEGATIVE SCENARIOS ----

    # Create booking without auth token
    no_auth_session = requests.Session()
    no_auth_session.headers.update({"Content-Type": "application/json"})
    try:
        resp = no_auth_session.post(
            f"{base}/booking", json=booking_payload, timeout=timeout
        )
        evidence["scenarios"].append(
            _record_request(
                "POST", f"{base}/booking", booking_payload, resp, "create_booking_no_auth"
            )
        )
    except Exception as e:
        evidence["scenarios"].append(
            {"scenario": "create_booking_no_auth", "error": str(e)}
        )

    # Create booking with missing required field
    incomplete_payload = {"roomid": room_id, "firstname": "Test"}
    try:
        resp = session.post(
            f"{base}/booking", json=incomplete_payload, timeout=timeout
        )
        evidence["scenarios"].append(
            _record_request(
                "POST", f"{base}/booking", incomplete_payload,
                resp, "create_booking_missing_fields"
            )
        )
    except Exception as e:
        evidence["scenarios"].append(
            {"scenario": "create_booking_missing_fields", "error": str(e)}
        )

    # GET non-existent booking
    try:
        resp = session.get(f"{base}/booking/999999", timeout=timeout)
        evidence["scenarios"].append(
            _record_request("GET", f"{base}/booking/999999", None, resp, "get_invalid_booking")
        )
    except Exception as e:
        evidence["scenarios"].append({"scenario": "get_invalid_booking", "error": str(e)})

    # DELETE without auth
    if booking_id:
        try:
            resp = no_auth_session.delete(
                f"{base}/booking/{booking_id}", timeout=timeout
            )
            evidence["scenarios"].append(
                _record_request(
                    "DELETE", f"{base}/booking/{booking_id}",
                    None, resp, "delete_booking_no_auth"
                )
            )
        except Exception as e:
            evidence["scenarios"].append(
                {"scenario": "delete_booking_no_auth", "error": str(e)}
            )

    return evidence
