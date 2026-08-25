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


CANDIDATE_ORIGIN = "https://candidate---rateguard-web-iqofutwtva-uc.a.run.app"


def _report_with_cors_responses(get_response: tuple, preflight_response: tuple) -> vc.Report:
    """get_response/preflight_response are (status_code, headers_dict) pairs,
    matching what verify_candidate._http_with_origin returns."""
    report = vc.Report()
    responses = iter([get_response, preflight_response])
    with patch.object(vc, "_http_with_origin", side_effect=lambda *a, **k: next(responses)):
        vc.check_cors_from_candidate_web_origin(
            report, "https://candidate---rateguard-api-example.a.run.app", CANDIDATE_ORIGIN
        )
    return report


def test_cors_check_passes_when_both_get_and_preflight_allow_the_candidate_origin():
    report = _report_with_cors_responses(
        (200, {"Access-Control-Allow-Origin": CANDIDATE_ORIGIN}),
        (200, {"Access-Control-Allow-Origin": CANDIDATE_ORIGIN, "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}),
    )
    assert report.checks[-1].passed is True


def test_cors_check_fails_when_get_has_no_allow_origin_header():
    """Regression: this is exactly the candidate-origin bug's symptom -- a
    plain GET returns 200 (the API is reachable), but the response carries no
    Access-Control-Allow-Origin header because the origin was never
    allow-listed, so a real browser blocks the response from ever reaching
    the candidate frontend's JS."""
    report = _report_with_cors_responses(
        (200, {}),
        (200, {"Access-Control-Allow-Origin": CANDIDATE_ORIGIN, "Access-Control-Allow-Methods": "GET, POST, OPTIONS"}),
    )
    assert report.checks[-1].passed is False


def test_cors_check_fails_when_preflight_returns_400():
    """Regression: matches the exact bug-report symptom -- OPTIONS preflight
    for an unlisted origin returns HTTP 400 with no allow-origin header."""
    report = _report_with_cors_responses(
        (200, {"Access-Control-Allow-Origin": CANDIDATE_ORIGIN}),
        (400, {}),
    )
    assert report.checks[-1].passed is False


def test_cors_check_fails_when_preflight_does_not_allow_post():
    report = _report_with_cors_responses(
        (200, {"Access-Control-Allow-Origin": CANDIDATE_ORIGIN}),
        (200, {"Access-Control-Allow-Origin": CANDIDATE_ORIGIN, "Access-Control-Allow-Methods": "GET"}),
    )
    assert report.checks[-1].passed is False


def test_main_fails_the_cors_check_when_frontend_url_is_not_provided():
    """--frontend-url is optional at the CLI level, but omitting it must
    still surface as a FAILED postcondition -- never a silent skip -- since
    it is the one check that can catch a browser-facing CORS regression."""
    report = vc.Report()
    with patch.object(vc, "check_health_live"), patch.object(vc, "check_health_ready"), \
         patch.object(vc, "check_system_status"), patch.object(vc, "create_demo_mission", return_value=None), \
         patch.object(vc, "check_cancel_delete_lifecycle"), patch.object(vc, "check_invalid_mission_returns_structured_422"), \
         patch.object(vc, "check_missing_sources_no_arizona_fallback"), \
         patch.object(vc, "check_runtime_verification_no_localhost_fallback"), \
         patch.object(vc, "Report", return_value=report):
        vc.main(argv=["--yes-test-candidate", "--api-url", "https://example.com"])
    cors_checks = [c for c in report.checks if c.name == "cors_allows_candidate_web_origin"]
    assert len(cors_checks) == 1
    assert cors_checks[0].passed is False
