from __future__ import annotations

import json
import re
from pathlib import Path

from google import genai


ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = ROOT / "spec.md"
ARTIFACTS = ROOT / "reporting" / "artifacts"
EXECUTION_JSON = ARTIFACTS / "execution.json"

REPORT_MD = ARTIFACTS / "ai-qa-report.md"
REPORT_JSON = ARTIFACTS / "ai-qa-report.json"

MODEL = "gemini-3.1-flash-lite"


def read_api_key(spec_text: str) -> str:
    match = re.search(
        r'^\s*GEMINI_API_KEY\s*=\s*["\']([^"\']+)["\']\s*$',
        spec_text,
        re.MULTILINE,
    )
    if not match:
        raise RuntimeError("GEMINI_API_KEY was not found in spec.md.")
    return match.group(1).strip()


def build_prompt(execution: dict, spec_text: str) -> str:
    # Do not send the full specification blindly if it is huge.
    # The report should be grounded primarily in actual execution evidence.
    return f"""
You are an AI QA reporting assistant.

Generate a factual, professional QA execution report from the supplied
pytest execution evidence.

IMPORTANT RULES:
- Do not invent test results, failures, causes, timings, or recommendations.
- Treat execution.json as the authoritative source for test status.
- Clearly distinguish observed facts from reasonable investigation suggestions.
- If all tests passed, explicitly state that no test failures were observed.
- If tests failed, analyze only the supplied failure/error details.
- Do not claim that a root cause is proven unless the evidence proves it.
- Recommendations must be actionable but clearly framed as recommendations.
- Do not repeat secrets, API keys, passwords, tokens, cookies, or credentials.
- Do not include raw stdout unless it materially helps explain a failure.
- Use Markdown.
- Return ONLY the report content, without code fences.

REPORT STRUCTURE:
# AI QA Execution Report

## Executive Summary
Include total, passed, failed, errors, skipped, and duration.

## Test Results
Group tests by UI/API when the classname/nodeid makes that distinction clear.

## Execution Observations
Mention meaningful facts supported by the execution evidence.

## Failure Analysis
If there are failures/errors, analyze each one separately:
- Test
- Status
- Observed evidence
- Likely area to investigate
- Suggested next step

If there are no failures/errors, say so explicitly.

## Recommendations
Give only evidence-based or clearly labelled follow-up recommendations.

## Execution Metadata
Include execution duration and exit code.

SPECIFICATION CONTEXT:
{spec_text[:12000]}

EXECUTION EVIDENCE:
{json.dumps(execution, indent=2, ensure_ascii=False)}
""".strip()


def main() -> int:
    if not SPEC_FILE.exists():
        raise SystemExit(f"spec.md not found: {SPEC_FILE}")

    if not EXECUTION_JSON.exists():
        raise SystemExit(
            "execution.json not found. Run reporting/run_tests.py first."
        )

    spec_text = SPEC_FILE.read_text(encoding="utf-8")
    execution = json.loads(EXECUTION_JSON.read_text(encoding="utf-8"))

    api_key = read_api_key(spec_text)

    print("=" * 72)
    print("AI QA REPORT GENERATION")
    print("=" * 72)
    print(f"Model: {MODEL}")
    print("Gemini report requests: exactly ONE")
    print("The report is generated from local pytest evidence.")
    print()

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL,
        contents=build_prompt(execution, spec_text),
        config={
            "temperature": 0.2,
        },
    )

    report = (response.text or "").strip()
    if not report:
        raise RuntimeError("Gemini returned an empty QA report.")

    REPORT_MD.write_text(report + "\n", encoding="utf-8")

    # Keep a machine-readable envelope without trying to parse Gemini's
    # Markdown into artificial fields.
    report_json = {
        "schema_version": "1.0",
        "model": MODEL,
        "source": str(EXECUTION_JSON),
        "execution_summary": execution.get("summary", {}),
        "report_markdown_file": str(REPORT_MD),
        "report": report,
    }

    REPORT_JSON.write_text(
        json.dumps(report_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Report generated successfully.")
    print(f"Markdown report : {REPORT_MD}")
    print(f"JSON report     : {REPORT_JSON}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
