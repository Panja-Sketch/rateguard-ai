#!/usr/bin/env python3
"""Non-destructive acceptance verification script for RateGuard AI deployments."""

import argparse
import sys
import httpx


def run_smoke_tests(base_url: str) -> bool:
    print(f"[*] Running smoke acceptance checks against {base_url}...")
    success = True

    # 1. Health Probe
    try:
        r = httpx.get(f"{base_url}/health", timeout=10.0)
        if r.status_code == 200:
            print("  [✓] /health returned 200 OK")
        else:
            print(f"  [✗] /health returned {r.status_code}")
            success = False
    except Exception as e:
        print(f"  [✗] /health failed: {e}")
        success = False

    # 2. System Info Probe
    try:
        r = httpx.get(f"{base_url}/api/v1/system/info", timeout=10.0)
        if r.status_code == 200:
            info = r.json()
            model_id = info.get("gemini_model")
            print(f"  [✓] /api/v1/system/info returned 200 OK (Model: {model_id})")
            if model_id != "gemini-3.7-flash":
                print(f"  [✗] Configured model is '{model_id}', expected 'gemini-3.7-flash'")
                success = False
        else:
            print(f"  [✗] /api/v1/system/info returned {r.status_code}")
            success = False
    except Exception as e:
        print(f"  [✗] /api/v1/system/info failed: {e}")
        success = False

    # 3. Test Connector Liveness
    try:
        connector_payload = {
            "connector_name": "Synthetic Demo Connector",
            "base_url": f"{base_url}/api/v1/demo-rating/quote",
            "http_method": "POST",
            "expected_premium_field": "premium",
            "timeout_seconds": 10.0,
        }
        r = httpx.post(f"{base_url}/api/v1/connectors/test", json=connector_payload, timeout=10.0)
        if r.status_code == 200:
            print("  [✓] /api/v1/connectors/test returned 200 OK")
        else:
            print(f"  [✗] /api/v1/connectors/test returned {r.status_code}: {r.text[:150]}")
            success = False
    except Exception as e:
        print(f"  [✗] Connector test failed: {e}")
        success = False

    # 4. List Missions
    try:
        r = httpx.get(f"{base_url}/api/v1/missions?limit=5", timeout=10.0)
        if r.status_code == 200:
            print("  [✓] /api/v1/missions returned 200 OK")
        else:
            print(f"  [✗] /api/v1/missions returned {r.status_code}")
            success = False
    except Exception as e:
        print(f"  [✗] List missions failed: {e}")
        success = False

    return success


def run_full_tests(base_url: str) -> bool:
    if not run_smoke_tests(base_url):
        return False

    print("\n[*] Running full end-to-end mission verification tests...")
    success = True

    # 1. Clean PASS Mission
    try:
        clean_req = {
            "name": "Acceptance Test Clean Mission",
            "mode": "RELEASE_CONFORMANCE",
            "product": "AZ_HO3",
            "jurisdiction": "Arizona",
            "source_a": {"source_id": "AZ_HO3_2026_09", "source_type": "SAMPLE_RELEASE", "name": "Intent"},
            "source_b": {"source_id": "AZ_HO3_2026_09_CLEAN", "source_type": "SAMPLE_RELEASE", "name": "Clean Target"},
            "disposable_sample_run": True,
        }
        r = httpx.post(f"{base_url}/api/v1/missions", json=clean_req, timeout=30.0)
        if r.status_code == 200:
            res = r.json()
            dec = res.get("decision")
            print(f"  [✓] Clean PASS mission executed (Decision: {dec})")
            if dec != "PASS":
                print(f"  [✗] Expected PASS, got {dec}")
                success = False
        else:
            print(f"  [✗] Clean mission returned HTTP {r.status_code}")
            success = False
    except Exception as e:
        print(f"  [✗] Clean mission failed: {e}")
        success = False

    # 2. Defective BLOCK Mission
    try:
        block_req = {
            "name": "Acceptance Test Block Mission",
            "mode": "RELEASE_CONFORMANCE",
            "product": "AZ_HO3",
            "jurisdiction": "Arizona",
            "source_a": {"source_id": "AZ_HO3_2026_09", "source_type": "SAMPLE_RELEASE", "name": "Intent"},
            "source_b": {"source_id": "AZ_HO3_2026_09_DEFECTIVE", "source_type": "SAMPLE_RELEASE", "name": "Defective Target"},
            "disposable_sample_run": True,
        }
        r = httpx.post(f"{base_url}/api/v1/missions", json=block_req, timeout=30.0)
        if r.status_code == 200:
            res = r.json()
            dec = res.get("decision")
            print(f"  [✓] Defective BLOCK mission executed (Decision: {dec})")
            if dec != "BLOCK_DEPLOYMENT":
                print(f"  [✗] Expected BLOCK_DEPLOYMENT, got {dec}")
                success = False
        else:
            print(f"  [✗] Defective mission returned HTTP {r.status_code}")
            success = False
    except Exception as e:
        print(f"  [✗] Defective mission failed: {e}")
        success = False

    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify deployed RateGuard AI instance.")
    parser.add_argument("--api-url", default="http://localhost:8000", help="Base RateGuard API URL")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke", help="Verification mode")

    args = parser.parse_args()

    base_url = args.api_url.rstrip("/")

    if args.mode == "smoke":
        ok = run_smoke_tests(base_url)
    else:
        ok = run_full_tests(base_url)

    if ok:
        print("\n[✓] All acceptance verification checks PASSED!")
        sys.exit(0)
    else:
        print("\n[✗] Acceptance verification checks FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()

