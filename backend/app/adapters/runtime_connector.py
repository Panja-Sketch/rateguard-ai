import os
from decimal import Decimal
from typing import Any

import httpx

from app.models.mission import AuthType, RuntimeConnectorConfig


class RatingApiConnectionError(Exception):
    """Exception raised when rating API connection or payload validation fails."""
    pass


class BlackBoxRatingApiAdapter:
    """Vendor-neutral rating API runtime connector adapter for black-box rating verification."""

    def __init__(self, config: RuntimeConnectorConfig):
        self.config = config

    def _resolve_secret(self) -> str | None:
        if not self.config.secret_ref:
            return None
        # Check environment variable first (e.g. Secret Manager injected env)
        val = os.getenv(self.config.secret_ref)
        if val:
            return val
        return self.config.secret_ref

    def build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        secret = self._resolve_secret()

        if self.config.auth_type == AuthType.API_KEY and secret:
            header_name = self.config.auth_header_name or "X-API-Key"
            headers[header_name] = secret
        elif self.config.auth_type == AuthType.BEARER and secret:
            headers["Authorization"] = f"Bearer {secret}"

        return headers

    def map_inputs_to_payload(self, risk_inputs: dict[str, Any]) -> dict[str, Any]:
        """Maps standard rating risk inputs to the API payload template."""
        payload = dict(self.config.request_template) if self.config.request_template else {}
        
        # Override payload fields with risk_inputs
        for k, v in risk_inputs.items():
            if isinstance(v, Decimal):
                payload[k] = float(v)
            else:
                payload[k] = v

        if self.config.correlation_id:
            payload["correlation_id"] = self.config.correlation_id

        return payload

    def extract_premium(self, response_data: dict[str, Any]) -> Decimal:
        """Extracts and parses numeric Decimal premium from API response."""
        field_path = self.config.expected_premium_field.split(".")
        curr: Any = response_data

        for part in field_path:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                raise RatingApiConnectionError(
                    f"Expected premium field '{self.config.expected_premium_field}' not found in API response."
                )

        try:
            # Parse exact Decimal string or float
            str_val = str(curr).replace("$", "").replace(",", "").strip()
            return Decimal(str_val)
        except Exception as err:
            raise RatingApiConnectionError(
                f"Failed to parse numeric premium from value '{curr}': {err}"
            ) from err

    def test_connection(self) -> dict[str, Any]:
        """Executes a non-destructive liveness test against the configured rating API endpoint."""
        test_payload = self.map_inputs_to_payload(
            {
                "product": "AZ_HO3",
                "dwelling_limit": 350000,
                "roof_age": 10,
                "deductible": 1000,
                "territory": "T01",
                "protection_class": 3,
                "construction_type": "FRAME",
                "claims_free": True,
                "effective_date": "2026-09-01",
            }
        )

        headers = self.build_headers()

        try:
            with httpx.Client(timeout=self.config.timeout_seconds) as client:
                res = client.request(
                    method=self.config.http_method,
                    url=self.config.base_url,
                    json=test_payload,
                    headers=headers,
                )

            if res.status_code != 200:
                raise RatingApiConnectionError(
                    f"Rating API returned HTTP {res.status_code}: {res.text[:200]}"
                )

            res_json = res.json()
            premium = self.extract_premium(res_json)

            return {
                "status": "SUCCESS",
                "http_status": res.status_code,
                "parsed_premium": str(premium),
                "response_sample": res_json,
            }
        except RatingApiConnectionError:
            raise
        except Exception as e:
            raise RatingApiConnectionError(
                f"Failed to reach Rating API endpoint '{self.config.base_url}': {e}"
            ) from e

    def execute_quote(self, risk_inputs: dict[str, Any]) -> Decimal:
        """Executes a rating request against the external API endpoint and returns parsed Decimal premium."""
        payload = self.map_inputs_to_payload(risk_inputs)
        headers = self.build_headers()

        last_err: Exception | None = None
        retries = max(1, self.config.max_retries)

        for _attempt in range(retries):
            try:
                with httpx.Client(timeout=self.config.timeout_seconds) as client:
                    res = client.request(
                        method=self.config.http_method,
                        url=self.config.base_url,
                        json=payload,
                        headers=headers,
                    )

                if res.status_code == 200:
                    res_json = res.json()
                    return self.extract_premium(res_json)

                last_err = RatingApiConnectionError(
                    f"Rating API HTTP {res.status_code}: {res.text[:200]}"
                )
            except Exception as e:
                last_err = e

        raise RatingApiConnectionError(
            f"Rating API call failed after {retries} attempts. Last error: {last_err}"
        )
