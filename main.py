"""
main.py — AI QA Automation Orchestrator

This is the ONLY entry point. Run with:

    python main.py

The complete workflow executes automatically:
1.  Load configuration
2.  Explore UI (Playwright MCP)
3.  Explore API (requests)
4.  Generate tests (Gemini)
5.  Validate generated project
6.  Run pytest
7.  Generate execution evidence
8.  Generate AI QA report (Gemini)
9.  Display final summary
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows (avoids cp1252 encoding errors)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# LOGGING SETUP — Simple, professional console output
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Suppress noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("playwright").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(text)
    print("=" * 60)


def _step(number: int, total: int, text: str) -> None:
    print(f"\n[{number}/{total}] {text}")


def _success(text: str) -> None:
    print(f"  [OK] {text}")


def _warning(text: str) -> None:
    print(f"  [!!] {text}")


def _error(text: str) -> None:
    print(f"  [ERR] {text}")


# ============================================================
# VALIDATION — Verify generated project is sane before running
# ============================================================

def validate_generated_project() -> tuple[bool, list[str]]:
    """
    Check that key generated files exist before running pytest.

    Returns (is_valid, list_of_issues).
    """
    generated_dir = Path("generated")
    required_paths = [
        "conftest.py",
        "pytest.ini",
        "tests",
        "pages",
    ]

    issues = []
    for rel_path in required_paths:
        full_path = generated_dir / rel_path
        if not full_path.exists():
            issues.append(f"Missing: generated/{rel_path}")

    return len(issues) == 0, issues


# ============================================================
# SUMMARY DISPLAY
# ============================================================

def _display_summary(execution: dict, report_path: str) -> None:
    """Display the final execution summary."""
    _header("EXECUTION SUMMARY")

    tests = execution.get("tests", [])
    ui_tests = [t for t in tests if "ui" in t.get("classname", "").lower() or
                "ui" in t.get("name", "").lower()]
    api_tests = [t for t in tests if "api" in t.get("classname", "").lower() or
                 "api" in t.get("name", "").lower()]

    ui_passed = sum(1 for t in ui_tests if t.get("status") == "passed")
    api_passed = sum(1 for t in api_tests if t.get("status") == "passed")

    print(f"\n  UI tests    : {len(ui_tests)} total, {ui_passed} passed")
    print(f"  API tests   : {len(api_tests)} total, {api_passed} passed")
    print(f"  Passed      : {execution.get('passed', 0)}")
    print(f"  Failed      : {execution.get('failed', 0)}")
    print(f"  Skipped     : {execution.get('skipped', 0)}")
    print(f"  Duration    : {execution.get('duration_seconds', 0)}s")
    print(f"\n  Generated project : generated/")
    print(f"  Report            : {report_path}")
    print(f"  HTML report       : generated/reports/html/report.html")
    print(f"  JUnit XML         : generated/reports/junit.xml")
    print(f"  Execution JSON    : generated/reports/execution.json")
    print()


# ============================================================
# MAIN WORKFLOW
# ============================================================

async def main() -> None:
    _header("AI QA AUTOMATION")
    print("  Restful Booker Platform")
    print("  Evidence-driven | AI-generated | Automated reporting")

    TOTAL_STEPS = 8

    # --------------------------------------------------------
    # STEP 1: Load Configuration
    # --------------------------------------------------------
    _step(1, TOTAL_STEPS, "Loading configuration...")
    try:
        from generation.config import load_config
        config = load_config()
        _success(f"Configuration loaded")
        _success(f"UI: {config.ui_base_url}")
        _success(f"API: {config.api_base_url}")
        _success(f"Gemini model: {config.gemini_model}")
    except EnvironmentError as e:
        _error(str(e))
        sys.exit(1)

    # --------------------------------------------------------
    # STEP 2: Explore UI
    # --------------------------------------------------------
    _step(2, TOTAL_STEPS, "Exploring UI with Playwright MCP...")
    ui_evidence = {}
    try:
        from generation.ui_generator import explore_ui
        ui_evidence = await explore_ui(config)
        workflows_found = len(ui_evidence.get("workflows", {}))
        _success(f"UI exploration complete ({workflows_found} workflows captured)")

        # Report key findings
        rooms = ui_evidence.get("workflows", {}).get("rooms", {})
        discovered_rooms = rooms.get("discovered_rooms", [])
        reservation_url = rooms.get("reservation_url", "")
        _success(f"Rooms discovered: {len(discovered_rooms)}")
        if reservation_url:
            _success(f"Reservation URL: {reservation_url}")

        admin = ui_evidence.get("workflows", {}).get("admin", {})
        if admin.get("login_success"):
            _success("Admin login: verified")
        else:
            _warning("Admin login: could not verify (evidence collected)")

    except Exception as e:
        _error(f"UI exploration failed: {e}")
        logger.exception("UI exploration traceback:")
        # Continue — evidence might be partial but we can still generate
        _warning("Continuing with partial UI evidence...")

    # --------------------------------------------------------
    # STEP 3: Explore API
    # --------------------------------------------------------
    _step(3, TOTAL_STEPS, "Exploring API with requests...")
    api_evidence = {}
    try:
        from generation.api_generator import explore_api
        api_evidence = explore_api(config)
        workflows_found = len(api_evidence.get("workflows", {}))
        _success(f"API exploration complete ({workflows_found} workflows captured)")

        auth = api_evidence.get("workflows", {}).get("auth", {})
        if auth.get("token"):
            _success("Auth token: obtained")
        else:
            _warning("Auth token: not obtained")

        rooms = api_evidence.get("workflows", {}).get("rooms", {})
        room_count = len(rooms.get("discovered_rooms", []))
        _success(f"Rooms via API: {room_count} found")

        bookings = api_evidence.get("workflows", {}).get("bookings", {})
        if bookings.get("created_booking_id"):
            _success(f"Test booking created: ID={bookings['created_booking_id']}")

    except Exception as e:
        _error(f"API exploration failed: {e}")
        logger.exception("API exploration traceback:")
        _warning("Continuing with partial API evidence...")

    # --------------------------------------------------------
    # STEP 4: Generate Tests with Gemini
    # --------------------------------------------------------
    _step(4, TOTAL_STEPS, "Generating tests with Gemini...")
    try:
        from generation.test_generator import generate_tests
        written_files = generate_tests(config)
        _success(f"Test generation complete ({len(written_files)} files generated)")

        # List key generated files
        for f in written_files[:5]:
            _success(f"  → {Path(f).relative_to(Path('generated').resolve()) if Path(f).is_absolute() else f}")
        if len(written_files) > 5:
            print(f"       ... and {len(written_files) - 5} more files")

    except Exception as e:
        _error(f"Test generation failed: {e}")
        logger.exception("Test generation traceback:")
        sys.exit(1)

    # --------------------------------------------------------
    # STEP 5: Validate Generated Project
    # --------------------------------------------------------
    _step(5, TOTAL_STEPS, "Validating generated project...")
    is_valid, issues = validate_generated_project()
    if is_valid:
        _success("Generated project structure is valid")
    else:
        for issue in issues:
            _warning(issue)
        _warning("Project validation had warnings — attempting to run tests anyway")

    # --------------------------------------------------------
    # STEP 6: Run pytest
    # --------------------------------------------------------
    _step(6, TOTAL_STEPS, "Running pytest...")
    execution = {}
    try:
        from generation.executor import run_tests
        execution = run_tests()

        passed = execution.get("passed", 0)
        failed = execution.get("failed", 0)
        total = execution.get("total", 0)

        if failed == 0 and total > 0:
            _success(f"All {total} tests passed!")
        elif total == 0:
            _warning("No tests were collected/executed")
        else:
            _warning(f"{passed}/{total} tests passed ({failed} failed)")

        _success("junit.xml generated")
        _success("HTML report generated")

    except Exception as e:
        _error(f"Test execution error: {e}")
        logger.exception("Executor traceback:")
        # Always continue to report generation
        _warning("Continuing to report generation...")
        execution = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "tests": []}

    # --------------------------------------------------------
    # STEP 7: Generate Execution Evidence (execution.json)
    # --------------------------------------------------------
    _step(7, TOTAL_STEPS, "Generating execution evidence...")
    execution_path = Path("generated/reports/execution.json")
    if execution_path.exists():
        _success(f"execution.json written ({execution_path.stat().st_size} bytes)")
    else:
        # Write it manually if executor didn't create it
        execution_path.parent.mkdir(parents=True, exist_ok=True)
        execution_path.write_text(
            json.dumps(execution, indent=2, default=str), encoding="utf-8"
        )
        _success("execution.json created from runtime data")

    # --------------------------------------------------------
    # STEP 8: Generate AI QA Report
    # --------------------------------------------------------
    _step(8, TOTAL_STEPS, "Generating AI QA report...")
    report_path = "generated/reports/report.md"
    try:
        from generation.report_generator import generate_report
        report_path = generate_report(config)
        report_size = Path(report_path).stat().st_size
        _success(f"report.md generated ({report_size} bytes)")
    except Exception as e:
        _error(f"Report generation failed: {e}")
        logger.exception("Report generation traceback:")
        # Create minimal fallback report
        _create_fallback_report(execution)
        _warning("Fallback report created")

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------
    _display_summary(execution, report_path)


def _create_fallback_report(execution: dict) -> None:
    """Create a minimal report if Gemini report generation fails."""
    reports_dir = Path("generated/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    content = f"""# QA Automation Execution Report

## Execution Summary

| Metric | Value |
|--------|-------|
| Total | {execution.get('total', 0)} |
| Passed | {execution.get('passed', 0)} |
| Failed | {execution.get('failed', 0)} |
| Skipped | {execution.get('skipped', 0)} |
| Duration | {execution.get('duration_seconds', 0)}s |

## Note
AI report generation was unavailable. See execution.json for full details.

## Test Results

"""
    for test in execution.get("tests", []):
        status_icon = "✓" if test.get("status") == "passed" else "✗"
        content += f"- {status_icon} {test.get('name', 'unknown')}: {test.get('status', 'unknown')}\n"

    (reports_dir / "report.md").write_text(content, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
