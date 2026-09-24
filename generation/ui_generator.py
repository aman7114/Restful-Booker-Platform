"""
generation/ui_generator.py

Responsible ONLY for:
- Driving Playwright MCP to explore the application
- Collecting accessibility snapshots, screenshots, URLs, and controls
- Saving evidence to evidence/ui/
- Running all 6 UI exploration workflows

No test generation here. No Gemini calls here. Evidence collection ONLY.
"""

import asyncio
import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from generation.config import Config
from generation.mcp_client import MCPClient

logger = logging.getLogger(__name__)

EVIDENCE_DIR = Path("evidence/ui")


def _save_evidence(filename: str, data: Any) -> None:
    """Save evidence data to JSON file."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = EVIDENCE_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        if isinstance(data, str):
            f.write(data)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
    logger.debug(f"Evidence saved: {filepath}")


def _save_screenshot(filename: str, b64_data: str) -> None:
    """Save a base64 screenshot to PNG file."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = EVIDENCE_DIR / filename
    try:
        image_data = base64.b64decode(b64_data)
        with open(filepath, "wb") as f:
            f.write(image_data)
        logger.debug(f"Screenshot saved: {filepath}")
    except Exception as e:
        logger.warning(f"Could not save screenshot {filename}: {e}")


def _parse_snapshot_elements(snapshot: str) -> dict:
    """
    Extract structured element information from an accessibility snapshot.

    Returns a dict with:
      - headings: list of heading texts
      - buttons: list of {name, ref}
      - links: list of {name, ref, url}
      - textboxes: list of {name, ref}
      - landmarks: list of landmark roles
    """
    elements = {
        "headings": [],
        "buttons": [],
        "links": [],
        "textboxes": [],
        "landmarks": [],
        "raw_lines": [],
    }

    if not snapshot:
        return elements

    lines = snapshot.splitlines()
    elements["raw_lines"] = lines

    for line in lines:
        stripped = line.strip()

        # Headings
        heading_match = re.search(r'heading\s+"([^"]+)"', stripped, re.IGNORECASE)
        if heading_match:
            elements["headings"].append(heading_match.group(1))

        # Buttons with ref
        btn_match = re.search(
            r'button\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?', stripped, re.IGNORECASE
        )
        if btn_match:
            elements["buttons"].append(
                {"name": btn_match.group(1), "ref": btn_match.group(2) or ""}
            )

        # Links with optional ref
        link_match = re.search(
            r'link\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?(?:.*url=([^\s\]]+))?',
            stripped,
            re.IGNORECASE,
        )
        if link_match:
            elements["links"].append(
                {
                    "name": link_match.group(1),
                    "ref": link_match.group(2) or "",
                    "url": link_match.group(3) or "",
                }
            )

        # Text boxes / inputs
        tb_match = re.search(
            r'(?:textbox|input)\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?',
            stripped,
            re.IGNORECASE,
        )
        if tb_match:
            elements["textboxes"].append(
                {"name": tb_match.group(1), "ref": tb_match.group(2) or ""}
            )

        # Landmark regions
        if re.search(r'\b(navigation|main|footer|header|region|banner)\b', stripped, re.IGNORECASE):
            role_match = re.match(r'\s*(\w+)', stripped)
            if role_match and role_match.group(1).lower() in (
                "navigation", "main", "footer", "header", "region", "banner"
            ):
                elements["landmarks"].append(role_match.group(1))

    return elements


async def explore_ui(config: Config) -> dict:
    """
    Run all UI exploration workflows.

    Returns a summary dict of all collected evidence.
    """
    evidence_summary = {
        "ui_base_url": config.ui_base_url,
        "workflows": {},
        "evidence_files": [],
    }

    async with MCPClient(
        command=config.mcp_command,
        package=config.mcp_package,
        headless=config.headless,
    ) as client:

        # --------------------------------------------------------
        # WORKFLOW 1 — Home Page
        # --------------------------------------------------------
        logger.info("  [UI] Workflow 1: Home Page")
        home_evidence = await _explore_home_page(client, config)
        _save_evidence("workflow_01_home.json", home_evidence)
        evidence_summary["workflows"]["home"] = home_evidence
        evidence_summary["evidence_files"].append("workflow_01_home.json")

        # --------------------------------------------------------
        # WORKFLOW 2 — Primary Navigation
        # --------------------------------------------------------
        logger.info("  [UI] Workflow 2: Navigation")
        nav_evidence = await _explore_navigation(client, config, home_evidence)
        _save_evidence("workflow_02_navigation.json", nav_evidence)
        evidence_summary["workflows"]["navigation"] = nav_evidence
        evidence_summary["evidence_files"].append("workflow_02_navigation.json")

        # --------------------------------------------------------
        # WORKFLOW 3 — Rooms Workflow (Dynamic Discovery)
        # --------------------------------------------------------
        logger.info("  [UI] Workflow 3: Rooms Discovery")
        rooms_evidence = await _explore_rooms(client, config)
        _save_evidence("workflow_03_rooms.json", rooms_evidence)
        evidence_summary["workflows"]["rooms"] = rooms_evidence
        evidence_summary["evidence_files"].append("workflow_03_rooms.json")

        # --------------------------------------------------------
        # WORKFLOW 4 — Reservation Page
        # --------------------------------------------------------
        logger.info("  [UI] Workflow 4: Reservation")
        reservation_url = rooms_evidence.get("reservation_url", "")
        reservation_evidence = await _explore_reservation(
            client, config, reservation_url
        )
        _save_evidence("workflow_04_reservation.json", reservation_evidence)
        evidence_summary["workflows"]["reservation"] = reservation_evidence
        evidence_summary["evidence_files"].append("workflow_04_reservation.json")

        # --------------------------------------------------------
        # WORKFLOW 5 — Admin Login
        # --------------------------------------------------------
        logger.info("  [UI] Workflow 5: Admin Login")
        admin_evidence = await _explore_admin(client, config)
        _save_evidence("workflow_05_admin.json", admin_evidence)
        evidence_summary["workflows"]["admin"] = admin_evidence
        evidence_summary["evidence_files"].append("workflow_05_admin.json")

        # --------------------------------------------------------
        # WORKFLOW 6 — Booking Flow
        # --------------------------------------------------------
        logger.info("  [UI] Workflow 6: Booking Flow")
        booking_evidence = await _explore_booking_flow(
            client, config, rooms_evidence
        )
        _save_evidence("workflow_06_booking.json", booking_evidence)
        evidence_summary["workflows"]["booking"] = booking_evidence
        evidence_summary["evidence_files"].append("workflow_06_booking.json")

    # Save overall summary
    _save_evidence("ui_evidence_summary.json", evidence_summary)
    return evidence_summary


async def _explore_home_page(client: MCPClient, config: Config) -> dict:
    """Workflow 1: Navigate to home and collect page evidence."""
    evidence = {
        "workflow": "home_page",
        "url": config.ui_base_url,
        "snapshot": "",
        "elements": {},
        "screenshot_file": "",
    }

    try:
        await client.navigate(config.ui_base_url)
        await asyncio.sleep(2)

        snapshot = await client.snapshot()
        evidence["snapshot"] = snapshot
        evidence["elements"] = _parse_snapshot_elements(snapshot)

        # Screenshot
        try:
            screenshot_b64 = await client.screenshot()
            if screenshot_b64 and isinstance(screenshot_b64, str):
                _save_screenshot("home_page.png", screenshot_b64)
                evidence["screenshot_file"] = "home_page.png"
        except Exception:
            pass

    except Exception as e:
        evidence["error"] = str(e)
        logger.warning(f"Home page exploration error: {e}")

    return evidence


async def _explore_navigation(
    client: MCPClient, config: Config, home_evidence: dict
) -> dict:
    """Workflow 2: Discover and validate primary navigation links."""
    evidence = {
        "workflow": "navigation",
        "discovered_links": [],
        "navigation_items": [],
    }

    try:
        # Re-navigate to home to ensure clean state
        await client.navigate(config.ui_base_url)
        await asyncio.sleep(1)

        snapshot = await client.snapshot()
        elements = _parse_snapshot_elements(snapshot)

        # Extract navigation links from the snapshot
        nav_links = []
        lines = snapshot.splitlines()
        in_nav = False

        for line in lines:
            stripped = line.strip()
            if "navigation" in stripped.lower() and re.match(r"\s*navigation", line, re.IGNORECASE):
                in_nav = True
            if in_nav:
                link_match = re.search(
                    r'link\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?', stripped, re.IGNORECASE
                )
                if link_match:
                    nav_links.append(
                        {"name": link_match.group(1), "ref": link_match.group(2) or ""}
                    )
                # End of nav block (next landmark)
                if stripped and re.match(r"(main|header|footer|region|banner)\b", stripped, re.IGNORECASE):
                    if nav_links:
                        in_nav = False

        # If no nav links found in navigation landmark, fall back to all links
        if not nav_links:
            nav_links = elements.get("links", [])[:10]

        evidence["navigation_items"] = nav_links
        evidence["all_links"] = elements.get("links", [])
        evidence["snapshot_excerpt"] = snapshot[:3000]

    except Exception as e:
        evidence["error"] = str(e)
        logger.warning(f"Navigation exploration error: {e}")

    return evidence


async def _explore_rooms(client: MCPClient, config: Config) -> dict:
    """
    Workflow 3: Dynamically discover room cards and navigate to a booking page.

    Discovery rules:
    - Room cards must have BOTH a name/type AND a booking action
    - "Our Rooms" section heading must NOT be treated as a room
    - No hardcoded room names (Single, Double, Suite)
    """
    evidence = {
        "workflow": "rooms",
        "discovered_rooms": [],
        "selected_room": None,
        "book_now_ref": None,
        "reservation_url": "",
        "navigation_success": False,
        "snapshot": "",
    }

    try:
        await client.navigate(config.ui_base_url)
        await asyncio.sleep(2)

        snapshot = await client.snapshot()
        evidence["snapshot"] = snapshot

        # Parse the rooms section from the accessibility snapshot
        rooms = _discover_room_cards(snapshot)
        evidence["discovered_rooms"] = rooms

        if not rooms:
            logger.warning("No room cards discovered from accessibility snapshot")
            return evidence

        # Select the first room with a booking action
        selected = rooms[0]
        evidence["selected_room"] = selected

        # Click the booking action
        book_ref = selected.get("book_ref", "")
        book_name = selected.get("book_action_name", "Book Now")

        if book_ref:
            evidence["book_now_ref"] = book_ref
            await client.click(book_ref, book_name)
            await asyncio.sleep(2)

            # Capture the reservation page URL from snapshot
            reservation_snapshot = await client.snapshot()
            url_match = re.search(
                r"(?:Page URL|url):\s*(https?://[^\s\n]+)", reservation_snapshot
            )
            if url_match:
                evidence["reservation_url"] = url_match.group(1)
            else:
                # Try to get URL from the snapshot content
                for line in reservation_snapshot.splitlines():
                    if "automationintesting.online" in line and "/room" in line.lower():
                        url_part = re.search(r"https?://[^\s\]'\"]+", line)
                        if url_part:
                            evidence["reservation_url"] = url_part.group(0)
                            break

            evidence["navigation_success"] = bool(evidence["reservation_url"])
            evidence["reservation_snapshot_excerpt"] = reservation_snapshot[:2000]

            # Screenshot of reservation page
            try:
                screenshot_b64 = await client.screenshot()
                if screenshot_b64 and isinstance(screenshot_b64, str):
                    _save_screenshot("rooms_selected.png", screenshot_b64)
                    evidence["screenshot_file"] = "rooms_selected.png"
            except Exception:
                pass

    except Exception as e:
        evidence["error"] = str(e)
        logger.warning(f"Rooms exploration error: {e}")

    return evidence


def _discover_room_cards(snapshot: str) -> list[dict]:
    """
    Parse room cards from the accessibility snapshot.

    A room card is identified by the presence of BOTH:
    - A meaningful name (not a generic section heading like "Our Rooms")
    - A booking action element (button or link with booking intent)

    Returns a list of discovered room dicts.
    """
    rooms = []
    lines = snapshot.splitlines()

    # Generic headings to exclude (section titles, not rooms)
    SECTION_HEADINGS = {"our rooms", "rooms", "accommodations", "available rooms"}

    # Booking action keywords
    BOOKING_KEYWORDS = {"book", "reserve", "booking", "reservation"}

    # Find all heading-level elements and associated buttons/links
    current_heading = None
    current_heading_ref = None
    heading_buttons = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect heading
        h_match = re.search(r'heading\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?', stripped, re.IGNORECASE)
        if h_match:
            heading_text = h_match.group(1).strip()
            heading_ref = h_match.group(2) or ""

            # Don't treat generic section headings as rooms
            if heading_text.lower() not in SECTION_HEADINGS:
                # If previous heading had booking actions, record it
                if current_heading and heading_buttons:
                    rooms.append({
                        "name": current_heading,
                        "ref": current_heading_ref,
                        "book_ref": heading_buttons[0].get("ref", ""),
                        "book_action_name": heading_buttons[0].get("name", ""),
                        "booking_actions": heading_buttons,
                    })

                current_heading = heading_text
                current_heading_ref = heading_ref
                heading_buttons = []
            else:
                current_heading = None
                heading_buttons = []

        # Detect buttons/links within the current room context
        if current_heading:
            btn_match = re.search(
                r'(?:button|link)\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?', stripped, re.IGNORECASE
            )
            if btn_match:
                btn_name = btn_match.group(1).strip()
                btn_ref = btn_match.group(2) or ""
                if any(kw in btn_name.lower() for kw in BOOKING_KEYWORDS):
                    heading_buttons.append({"name": btn_name, "ref": btn_ref})

        i += 1

    # Add the last room if it has booking actions
    if current_heading and heading_buttons:
        rooms.append({
            "name": current_heading,
            "ref": current_heading_ref,
            "book_ref": heading_buttons[0].get("ref", ""),
            "book_action_name": heading_buttons[0].get("name", ""),
            "booking_actions": heading_buttons,
        })

    # Fallback: look for any link/button with booking keywords that follows an image or card
    if not rooms:
        rooms = _fallback_room_discovery(snapshot)

    return rooms


def _fallback_room_discovery(snapshot: str) -> list[dict]:
    """
    Fallback: scan for booking-action elements and try to associate context.
    Used if the structured heading-based discovery finds nothing.
    """
    BOOKING_KEYWORDS = {"book now", "reserve", "book this room", "view room"}
    rooms = []
    lines = snapshot.splitlines()

    for line in lines:
        stripped = line.strip()
        btn_match = re.search(
            r'(?:button|link)\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?', stripped, re.IGNORECASE
        )
        if btn_match:
            btn_name = btn_match.group(1).strip()
            if any(kw in btn_name.lower() for kw in BOOKING_KEYWORDS):
                rooms.append({
                    "name": f"Room (via {btn_name})",
                    "ref": "",
                    "book_ref": btn_match.group(2) or "",
                    "book_action_name": btn_name,
                    "booking_actions": [{"name": btn_name, "ref": btn_match.group(2) or ""}],
                })

    return rooms


async def _explore_reservation(
    client: MCPClient, config: Config, reservation_url: str
) -> dict:
    """Workflow 4: Explore the reservation/booking page."""
    evidence = {
        "workflow": "reservation",
        "url": reservation_url or config.ui_base_url,
        "snapshot": "",
        "booking_controls": [],
        "date_controls": [],
        "form_fields": [],
        "primary_action": None,
    }

    try:
        # Navigate to the reservation URL if we have one
        target_url = reservation_url if reservation_url else config.ui_base_url
        await client.navigate(target_url)
        await asyncio.sleep(2)

        snapshot = await client.snapshot()
        evidence["snapshot"] = snapshot
        elements = _parse_snapshot_elements(snapshot)

        # Identify booking-specific controls using semantic analysis
        evidence["booking_controls"] = _identify_booking_controls(snapshot)
        evidence["date_controls"] = _identify_date_controls(snapshot)
        evidence["form_fields"] = elements.get("textboxes", [])

        # Identify primary booking action (Reserve Now, Book, etc.)
        reserve_keywords = {"reserve now", "book now", "confirm", "reserve", "book"}
        for btn in elements.get("buttons", []):
            if any(kw in btn["name"].lower() for kw in reserve_keywords):
                evidence["primary_action"] = btn
                break

        evidence["all_buttons"] = elements.get("buttons", [])
        evidence["all_links"] = elements.get("links", [])
        evidence["headings"] = elements.get("headings", [])

        # Screenshot
        try:
            screenshot_b64 = await client.screenshot()
            if screenshot_b64 and isinstance(screenshot_b64, str):
                _save_screenshot("reservation_page.png", screenshot_b64)
                evidence["screenshot_file"] = "reservation_page.png"
        except Exception:
            pass

    except Exception as e:
        evidence["error"] = str(e)
        logger.warning(f"Reservation exploration error: {e}")

    return evidence


def _identify_booking_controls(snapshot: str) -> list[dict]:
    """
    Identify booking-specific controls from snapshot using semantic analysis.
    Distinguishes booking controls from global navigation and footer elements.
    """
    booking_controls = []
    lines = snapshot.splitlines()

    # Look for controls within what appears to be the booking/reservation section
    in_booking_section = False
    BOOKING_SECTION_INDICATORS = {
        "reserve", "booking", "reservation", "check-in", "check-out",
        "checkin", "checkout", "dates", "calendar"
    }
    GLOBAL_NAV_INDICATORS = {"navigation", "footer", "header", "banner"}

    for line in lines:
        stripped = line.strip()

        # Detect section context
        if any(kw in stripped.lower() for kw in GLOBAL_NAV_INDICATORS):
            continue  # Skip navigation/footer context

        if any(kw in stripped.lower() for kw in BOOKING_SECTION_INDICATORS):
            in_booking_section = True

        if in_booking_section:
            btn_match = re.search(
                r'(?:button|link)\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?',
                stripped, re.IGNORECASE
            )
            if btn_match:
                booking_controls.append({
                    "name": btn_match.group(1),
                    "ref": btn_match.group(2) or "",
                    "type": "button" if "button" in stripped.lower() else "link",
                })

    return booking_controls


def _identify_date_controls(snapshot: str) -> list[dict]:
    """Identify calendar/date controls from the snapshot."""
    date_controls = []
    lines = snapshot.splitlines()

    DATE_KEYWORDS = {
        "check-in", "check-out", "checkin", "checkout", "date",
        "calendar", "arrival", "departure", "start date", "end date"
    }

    for line in lines:
        stripped = line.strip()
        stripped_lower = stripped.lower()

        if any(kw in stripped_lower for kw in DATE_KEYWORDS):
            ctrl_match = re.search(
                r'(?:button|input|textbox|spinbutton)\s+"([^"]+)"(?:.*\[ref=([^\]]+)\])?',
                stripped, re.IGNORECASE
            )
            if ctrl_match:
                date_controls.append({
                    "name": ctrl_match.group(1),
                    "ref": ctrl_match.group(2) or "",
                    "context": stripped[:200],
                })

    return date_controls


async def _explore_admin(client: MCPClient, config: Config) -> dict:
    """Workflow 5: Explore admin login page and authentication."""
    evidence = {
        "workflow": "admin",
        "url": f"{config.ui_base_url}{config.admin_path}",
        "snapshot": "",
        "username_field": None,
        "password_field": None,
        "login_button": None,
        "login_success": False,
        "dashboard_elements": [],
    }

    try:
        admin_url = f"{config.ui_base_url}{config.admin_path}"
        await client.navigate(admin_url)
        await asyncio.sleep(2)

        snapshot = await client.snapshot()
        evidence["snapshot"] = snapshot
        elements = _parse_snapshot_elements(snapshot)

        # Find username field
        for tb in elements.get("textboxes", []):
            name_lower = tb["name"].lower()
            if "username" in name_lower or "user" in name_lower:
                evidence["username_field"] = tb
                break

        # Find password field
        for tb in elements.get("textboxes", []):
            if "password" in tb["name"].lower():
                evidence["password_field"] = tb
                break

        # If not found by name, look in raw lines for password type inputs
        if not evidence["password_field"]:
            for line in snapshot.splitlines():
                if "password" in line.lower():
                    ref_match = re.search(r'\[ref=([^\]]+)\]', line)
                    if ref_match:
                        evidence["password_field"] = {
                            "name": "Password",
                            "ref": ref_match.group(1)
                        }
                        break

        # Find login button
        for btn in elements.get("buttons", []):
            if "login" in btn["name"].lower() or "sign in" in btn["name"].lower():
                evidence["login_button"] = btn
                break

        # Perform login to capture dashboard evidence
        if (
            evidence["username_field"]
            and evidence["password_field"]
            and evidence["login_button"]
        ):
            # Fill username
            await client.fill(
                evidence["username_field"]["ref"],
                config.admin_username,
                "Username",
            )
            await asyncio.sleep(0.5)

            # Fill password
            await client.fill(
                evidence["password_field"]["ref"],
                config.admin_password,
                "Password",
            )
            await asyncio.sleep(0.5)

            # Click login
            await client.click(
                evidence["login_button"]["ref"], "Login"
            )
            await asyncio.sleep(2)

            # Capture dashboard
            dashboard_snapshot = await client.snapshot()
            dashboard_elements = _parse_snapshot_elements(dashboard_snapshot)
            evidence["dashboard_snapshot"] = dashboard_snapshot[:3000]
            evidence["dashboard_elements"] = dashboard_elements.get("headings", [])

            # Check if login was successful (login form should be gone)
            evidence["login_success"] = "login" not in dashboard_snapshot.lower() or len(
                dashboard_elements.get("headings", [])
            ) > 1

            # Screenshot of dashboard
            try:
                screenshot_b64 = await client.screenshot()
                if screenshot_b64 and isinstance(screenshot_b64, str):
                    _save_screenshot("admin_dashboard.png", screenshot_b64)
                    evidence["screenshot_file"] = "admin_dashboard.png"
            except Exception:
                pass

    except Exception as e:
        evidence["error"] = str(e)
        logger.warning(f"Admin exploration error: {e}")

    return evidence


async def _explore_booking_flow(
    client: MCPClient, config: Config, rooms_evidence: dict
) -> dict:
    """Workflow 6: Explore the complete booking form flow."""
    evidence = {
        "workflow": "booking_flow",
        "reservation_url": "",
        "form_structure": {},
        "date_picker_type": "unknown",
        "guest_fields": [],
        "submission_result": "",
    }

    try:
        reservation_url = rooms_evidence.get("reservation_url", "")
        if not reservation_url:
            # Try to navigate back to home and re-discover
            await client.navigate(config.ui_base_url)
            await asyncio.sleep(2)
            snapshot = await client.snapshot()
            rooms = _discover_room_cards(snapshot)
            if rooms and rooms[0].get("book_ref"):
                await client.click(rooms[0]["book_ref"], rooms[0]["book_action_name"])
                await asyncio.sleep(2)
                post_click_snapshot = await client.snapshot()
                url_match = re.search(
                    r"(?:Page URL|url):\s*(https?://[^\s\n]+)", post_click_snapshot
                )
                if url_match:
                    reservation_url = url_match.group(1)

        if reservation_url:
            await client.navigate(reservation_url)
        await asyncio.sleep(2)

        snapshot = await client.snapshot()
        evidence["reservation_url"] = reservation_url
        elements = _parse_snapshot_elements(snapshot)

        # Analyze date picker type from snapshot
        snapshot_lower = snapshot.lower()
        if "calendar" in snapshot_lower or "datepicker" in snapshot_lower:
            evidence["date_picker_type"] = "calendar_widget"
        elif "check-in" in snapshot_lower or "checkin" in snapshot_lower:
            evidence["date_picker_type"] = "checkin_checkout_inputs"
        elif "date" in snapshot_lower:
            evidence["date_picker_type"] = "date_inputs"

        evidence["guest_fields"] = elements.get("textboxes", [])
        evidence["all_buttons"] = elements.get("buttons", [])
        evidence["headings"] = elements.get("headings", [])
        evidence["snapshot_excerpt"] = snapshot[:4000]

        # Capture form structure
        evidence["form_structure"] = {
            "textboxes": elements.get("textboxes", []),
            "buttons": elements.get("buttons", []),
            "headings": elements.get("headings", []),
        }

        # Screenshot
        try:
            screenshot_b64 = await client.screenshot()
            if screenshot_b64 and isinstance(screenshot_b64, str):
                _save_screenshot("booking_flow.png", screenshot_b64)
                evidence["screenshot_file"] = "booking_flow.png"
        except Exception:
            pass

    except Exception as e:
        evidence["error"] = str(e)
        logger.warning(f"Booking flow exploration error: {e}")

    return evidence
