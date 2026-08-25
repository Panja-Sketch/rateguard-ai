"""Focused, offline tests for verify_candidate.check_system_status's
verifier contract: it must validate the structured `gemini` fields
individually (exact model id, provider, framework, auth mode, effective
location, endpoint_probe_invoked) rather than a loose substring match over
the whole response body, which previously passed even when the reported
values were wrong (e.g. a stale 'us-central1' location).

No network calls: verify_candidate._http is monkeypatched in every test.
"""

import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import verify_candidate as vc  # noqa: E402

VALID_GEMINI_BODY = {
    "gemini": {
        "configured_model_id": "gemini-3.7-flash",
        "provider": "Google Vertex AI",
        "framework": "Google GenAI SDK (google-genai structured output)",
        "auth_mode": "VERTEX_AI",
        "configured_location": "global",
        "agent_enabled": True,
        "endpoint_probe_invoked": False,
        "note": "Configuration only.",
    }
}


def _report_with_status(body: dict, status_code: int = 200) -> vc.Report:
    report = vc.Report()
    with patch.object(vc, "_http", return_value=(status_code, body)):
        vc.check_system_status(report, "https://candidate---rateguard-api-example.a.run.app")
    return report


def test_system_status_check_passes_on_the_correct_contract():
    report = _report_with_status(VALID_GEMINI_BODY)
    assert report.checks[-1].passed is True


def test_system_status_check_fails_on_stale_deployment_region_as_location():
    """Regression: the exact defect this repair fixes -- reporting the
    general Cloud Run/GCP deployment region ('us-central1') as the Gemini
    location, and omitting provider/auth_mode/framework entirely, is
    exactly the pre-fix response shape and must fail the verifier."""
    body = {"gemini": {"configured_model_id": "gemini-3.7-flash", "location": "us-central1", "invoked": False}}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_on_wrong_model_id():
    body = {**VALID_GEMINI_BODY, "gemini": {**VALID_GEMINI_BODY["gemini"], "configured_model_id": "gemini-1.5-pro"}}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_on_wrong_provider():
    body = {**VALID_GEMINI_BODY, "gemini": {**VALID_GEMINI_BODY["gemini"], "provider": "OpenAI"}}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_on_wrong_auth_mode():
    body = {**VALID_GEMINI_BODY, "gemini": {**VALID_GEMINI_BODY["gemini"], "auth_mode": "API_KEY"}}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_on_wrong_location():
    body = {**VALID_GEMINI_BODY, "gemini": {**VALID_GEMINI_BODY["gemini"], "configured_location": "us-central1"}}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_when_endpoint_probe_invoked_is_true():
    body = {**VALID_GEMINI_BODY, "gemini": {**VALID_GEMINI_BODY["gemini"], "endpoint_probe_invoked": True}}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_on_secret_shaped_data_anywhere_in_body():
    body = {**VALID_GEMINI_BODY, "leaked": "AIzaSyFAKESECRETVALUE0000000000000"}
    report = _report_with_status(body)
    assert report.checks[-1].passed is False


def test_system_status_check_fails_on_non_200():
    report = _report_with_status(VALID_GEMINI_BODY, status_code=500)
    assert report.checks[-1].passed is False
