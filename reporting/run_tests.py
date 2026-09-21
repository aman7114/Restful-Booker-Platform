from __future__ import annotations

import json
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "generated"
REPORTING = ROOT / "reporting"
ARTIFACTS = REPORTING / "artifacts"

JUNIT_FILE = ARTIFACTS / "pytest-results.xml"
EXECUTION_LOG = ARTIFACTS / "execution.log"
EXECUTION_JSON = ARTIFACTS / "execution.json"


def parse_junit(path: Path) -> dict:
    """Convert pytest's JUnit XML into a compact, stable JSON structure."""
    if not path.exists():
        return {
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
            },
            "tests": [],
        }

    root = ET.parse(path).getroot()

    summary = {
        "total": int(root.attrib.get("tests", 0)),
        "passed": 0,
        "failed": int(root.attrib.get("failures", 0)),
        "errors": int(root.attrib.get("errors", 0)),
        "skipped": int(root.attrib.get("skipped", 0)),
    }

    tests = []

    for testcase in root.iter("testcase"):
        classname = testcase.attrib.get("classname", "")
        name = testcase.attrib.get("name", "")
        duration = float(testcase.attrib.get("time", 0) or 0)

        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")

        if failure is not None:
            status = "failed"
            detail = failure.attrib.get("message", "") or (failure.text or "")
        elif error is not None:
            status = "error"
            detail = error.attrib.get("message", "") or (error.text or "")
        elif skipped is not None:
            status = "skipped"
            detail = skipped.attrib.get("message", "") or (skipped.text or "")
        else:
            status = "passed"
            detail = ""
            summary["passed"] += 1

        tests.append(
            {
                "nodeid": f"{classname}::{name}" if classname else name,
                "name": name,
                "classname": classname,
                "status": status,
                "duration_seconds": round(duration, 3),
                "detail": detail.strip(),
            }
        )

    return {"summary": summary, "tests": tests}


def main() -> int:
    if not GENERATED.exists():
        raise SystemExit(f"Generated project not found: {GENERATED}")

    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("AI QA TEST EXECUTION")
    print("=" * 72)
    print(f"Project : {GENERATED}")
    print(f"Started : {datetime.now().astimezone().isoformat()}")
    print()

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--headed",
        f"--junitxml={JUNIT_FILE}",
    ]

    print("Running:")
    print(" ".join(command))
    print()

    started = time.perf_counter()

    process = subprocess.run(
        command,
        cwd=GENERATED,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    duration = time.perf_counter() - started

    stdout = process.stdout or ""
    stderr = process.stderr or ""

    # Keep the terminal useful while also persisting the complete execution log.
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")

    results = parse_junit(JUNIT_FILE)

    execution = {
        "schema_version": "1.0",
        "started_at": datetime.now().astimezone().isoformat(),
        "duration_seconds": round(duration, 3),
        "exit_code": process.returncode,
        "command": command,
        "project": str(GENERATED),
        "summary": results["summary"],
        "tests": results["tests"],
        "stdout": stdout,
        "stderr": stderr,
    }

    EXECUTION_JSON.write_text(
        json.dumps(execution, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    EXECUTION_LOG.write_text(
        stdout
        + ("\n\n[STDERR]\n" + stderr if stderr else ""),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("EXECUTION SUMMARY")
    print("=" * 72)
    print(json.dumps(results["summary"], indent=2))
    print()
    print(f"Structured results : {EXECUTION_JSON}")
    print(f"Execution log      : {EXECUTION_LOG}")
    print(f"JUnit XML          : {JUNIT_FILE}")

    # pytest's exit code is intentionally preserved.
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
