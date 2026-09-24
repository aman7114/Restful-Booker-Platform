"""
generation/executor.py

Responsible ONLY for:
- Running pytest against the generated/ directory
- Capturing stdout/stderr output
- Parsing JUnit XML results
- Producing execution.json

No test generation here. No Gemini calls here. Execution + result collection ONLY.
"""

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

GENERATED_DIR = Path("generated")
REPORTS_DIR = GENERATED_DIR / "reports"
JUNIT_XML = REPORTS_DIR / "junit.xml"
EXECUTION_JSON = REPORTS_DIR / "execution.json"


def run_tests() -> dict:
    """
    Execute pytest against the generated/ directory.

    Returns execution summary dict (also written to execution.json).
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "html").mkdir(parents=True, exist_ok=True)

    # Build pytest command
    pytest_cmd = [
        sys.executable, "-m", "pytest",
        "tests/",
        "--html=reports/html/report.html",
        "--self-contained-html",
        f"--junitxml=reports/junit.xml",
        "-v",
        "--tb=short",
        "--no-header",
    ]

    logger.info(f"  [EXEC] Running: {' '.join(pytest_cmd)}")
    logger.info(f"  [EXEC] Working directory: {GENERATED_DIR.resolve()}")

    start_time = time.time()
    result = subprocess.run(
        pytest_cmd,
        cwd=GENERATED_DIR.resolve(),
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout
    )
    duration = time.time() - start_time

    logger.info(f"  [EXEC] pytest exit code: {result.returncode}")

    # Save raw pytest output
    stdout_file = REPORTS_DIR / "pytest_stdout.txt"
    stderr_file = REPORTS_DIR / "pytest_stderr.txt"
    stdout_file.write_text(result.stdout or "", encoding="utf-8")
    stderr_file.write_text(result.stderr or "", encoding="utf-8")

    # Parse JUnit XML for structured results
    execution_data = _parse_junit_xml(JUNIT_XML, duration, result)

    # Write execution.json
    EXECUTION_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(EXECUTION_JSON, "w", encoding="utf-8") as f:
        json.dump(execution_data, f, indent=2, ensure_ascii=False, default=str)

    logger.info(
        f"  [EXEC] Results: "
        f"{execution_data['passed']} passed, "
        f"{execution_data['failed']} failed, "
        f"{execution_data['skipped']} skipped"
    )

    return execution_data


def _parse_junit_xml(
    junit_path: Path,
    duration: float,
    subprocess_result: subprocess.CompletedProcess,
) -> dict:
    """
    Parse JUnit XML file and build execution summary dict.
    Falls back to stdout parsing if XML is not available.
    """
    execution = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "errors": 0,
        "duration_seconds": round(duration, 2),
        "exit_code": subprocess_result.returncode,
        "tests": [],
        "stdout_summary": "",
    }

    if junit_path.exists():
        try:
            execution.update(_parse_xml_file(junit_path))
        except Exception as e:
            logger.warning(f"JUnit XML parse error: {e} — falling back to stdout parsing")
            execution.update(_parse_stdout(subprocess_result.stdout))
    else:
        logger.warning("JUnit XML not found — parsing stdout")
        execution.update(_parse_stdout(subprocess_result.stdout))

    # Add stdout summary for report generation
    stdout = subprocess_result.stdout or ""
    execution["stdout_summary"] = _extract_stdout_summary(stdout)

    return execution


def _parse_xml_file(junit_path: Path) -> dict:
    """Parse JUnit XML using xml.etree.ElementTree."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(junit_path)
    root = tree.getroot()

    # Handle both <testsuites> and <testsuite> root elements
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    else:
        suites = [root]

    total = 0
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    tests = []

    for suite in suites:
        for testcase in suite.findall("testcase"):
            total += 1
            name = testcase.get("name", "")
            classname = testcase.get("classname", "")
            test_duration = float(testcase.get("time", 0))

            failure = testcase.find("failure")
            error = testcase.find("error")
            skip = testcase.find("skipped")

            if failure is not None:
                status = "failed"
                failed += 1
                failure_message = failure.get("message", "")
                traceback = failure.text or ""
            elif error is not None:
                status = "error"
                errors += 1
                failure_message = error.get("message", "")
                traceback = error.text or ""
            elif skip is not None:
                status = "skipped"
                skipped += 1
                failure_message = skip.get("message", "")
                traceback = ""
            else:
                status = "passed"
                passed += 1
                failure_message = None
                traceback = ""

            tests.append({
                "name": name,
                "classname": classname,
                "status": status,
                "duration_seconds": round(test_duration, 3),
                "failure_message": failure_message,
                "traceback": traceback[:1000] if traceback else None,
            })

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "tests": tests,
    }


def _parse_stdout(stdout: str) -> dict:
    """
    Fallback: parse pytest stdout for pass/fail counts.
    Handles the '5 passed, 2 failed' summary line format.
    """
    import re

    lines = stdout.splitlines()
    tests = []

    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    for line in lines:
        # Match test result lines: "PASSED tests/api/test_auth.py::test_name"
        m = re.match(r"(PASSED|FAILED|SKIPPED|ERROR)\s+([\w/:. -]+)", line.strip())
        if m:
            status_str = m.group(1).lower()
            test_name = m.group(2).strip()

            if status_str == "passed":
                passed += 1
            elif status_str == "failed":
                failed += 1
            elif status_str == "skipped":
                skipped += 1
            elif status_str == "error":
                errors += 1

            tests.append({
                "name": test_name,
                "classname": "",
                "status": status_str,
                "duration_seconds": 0,
                "failure_message": None,
                "traceback": None,
            })

    # Also parse summary line: "3 passed, 1 failed in 5.23s"
    for line in reversed(lines):
        summary_m = re.search(
            r"(\d+) passed(?:.*?(\d+) failed)?(?:.*?(\d+) skipped)?(?:.*?(\d+) error)?",
            line,
        )
        if summary_m:
            if not tests:  # Only use if we got no individual test records
                passed = int(summary_m.group(1) or 0)
                failed = int(summary_m.group(2) or 0)
                skipped = int(summary_m.group(3) or 0)
                errors = int(summary_m.group(4) or 0)
            break

    total = passed + failed + skipped + errors
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "tests": tests,
    }


def _extract_stdout_summary(stdout: str) -> str:
    """Extract last N lines of stdout for inclusion in reports."""
    lines = stdout.splitlines()
    # Get last 100 lines or all if shorter
    summary_lines = lines[-100:] if len(lines) > 100 else lines
    return "\n".join(summary_lines)
