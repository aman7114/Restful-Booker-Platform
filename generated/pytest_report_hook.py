"""Generate local QA report artifacts after every pytest run."""

import json
from pathlib import Path


_RESULTS = {}


def pytest_runtest_logreport(report):
    """Keep one final result per test nodeid."""
    if report.when == "call":
        _RESULTS[report.nodeid] = report
    elif report.when == "setup" and report.failed:
        _RESULTS[report.nodeid] = report


def _status(report):
    if report.skipped:
        return "skipped"
    if report.failed:
        return "failed"
    return "passed"


def _group_for(nodeid):
    lowered = nodeid.lower()
    if "/api/" in lowered or "\\api\\" in lowered:
        return "API"
    return "UI"


def _test_label(nodeid):
    return nodeid.split("::")[-1]


def _build_execution(reports, exitstatus):
    statuses = [_status(report) for report in reports]
    return {
        "total": len(reports),
        "passed": statuses.count("passed"),
        "failed": statuses.count("failed"),
        "skipped": statuses.count("skipped"),
        "errors": 0,
        "duration_seconds": round(
            sum(getattr(report, "duration", 0.0) for report in reports), 2
        ),
        "exit_code": int(exitstatus),
        "tests": [
            {
                "name": _test_label(report.nodeid),
                "classname": report.nodeid.rsplit("::", 1)[0],
                "status": _status(report),
                "duration_seconds": round(getattr(report, "duration", 0.0), 3),
                "failure_message": (
                    str(getattr(report, "longrepr", ""))[:1000]
                    if report.failed else None
                ),
                "traceback": None,
            }
            for report in reports
        ],
    }


def _build_report(session):
    reports = list(_RESULTS.values())
    passed = sum(_status(report) == "passed" for report in reports)
    failed = sum(_status(report) == "failed" for report in reports)
    skipped = sum(_status(report) == "skipped" for report in reports)
    total = len(reports)
    duration = sum(getattr(report, "duration", 0.0) for report in reports)
    pass_rate = (passed / total * 100) if total else 0.0

    lines = [
        "# QA Automation Execution Report",
        "## Restful Booker Platform",
        "",
        "---",
        "",
        "## Executive Summary",
        (
            f"The automated test suite completed with a **{pass_rate:.2f}% pass rate**. "
            f"Out of {total} tests executed, {passed} passed, {failed} failed, "
            f"and {skipped} were skipped."
        ),
        "",
        "## Test Execution Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Tests | {total} |",
        f"| Passed | {passed} |",
        f"| Failed | {failed} |",
        f"| Skipped | {skipped} |",
        f"| Duration | {duration:.2f}s |",
        f"| Pass Rate | {pass_rate:.2f}% |",
        "",
    ]

    for group in ("UI", "API"):
        lines.extend([f"## {group} Test Results", ""])
        group_reports = [
            report for report in reports if _group_for(report.nodeid) == group
        ]
        if not group_reports:
            lines.append("No tests executed.")
        for report in group_reports:
            lines.append(
                f"* `{_test_label(report.nodeid)}` - **{_status(report).title()}**"
            )
        lines.append("")

    lines.extend(["## Failure Analysis", ""])
    failures = [report for report in reports if _status(report) == "failed"]
    if not failures:
        lines.append("All tests passed.")
    else:
        for report in failures:
            message = str(getattr(report, "longrepr", "")).replace("\n", " ")
            lines.extend([
                f"- **Test:** `{_test_label(report.nodeid)}`",
                "  **Status:** failed",
                f"  **Observed Error:** [FACT] {message[:1000]}",
                "",
            ])

    lines.extend([
        "## Test Artifacts",
        "",
        "| Artifact | Path |",
        "|----------|------|",
        "| HTML Report | generated/reports/html/report.html |",
        "| JUnit XML | generated/reports/junit.xml |",
        "| Execution JSON | generated/reports/execution.json |",
        "",
        "---",
        "",
        "*Report generated locally by pytest after this test run.*",
        "",
    ])
    return "\n".join(lines)


def pytest_sessionfinish(session, exitstatus):
    """Write report.md after pytest has collected and run all tests."""
    reports = list(_RESULTS.values())
    report_path = Path(__file__).parent / "reports" / "report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_build_report(session), encoding="utf-8")
    execution_path = report_path.parent / "execution.json"
    execution_path.write_text(
        json.dumps(_build_execution(reports, exitstatus), indent=2),
        encoding="utf-8",
    )
