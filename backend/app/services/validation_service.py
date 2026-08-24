from urllib.parse import urlparse

from app.models.mission import (
    AssuranceMission,
    ComparisonMode,
    RuntimeConnectorConfig,
    ValidationIssue,
)


class MissionValidationService:
    """Production-grade validator for sources, rating API connectors, and assurance missions."""

    @staticmethod
    def validate_runtime_connector(config: RuntimeConnectorConfig) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not config.connector_name.strip():
            issues.append(
                ValidationIssue(
                    field="connector_name",
                    code="REQUIRED",
                    message="Connector name is required.",
                )
            )

        if not config.base_url.strip():
            issues.append(
                ValidationIssue(
                    field="base_url",
                    code="REQUIRED",
                    message="Rating API base URL is required.",
                )
            )
        else:
            try:
                parsed = urlparse(config.base_url)
                if not parsed.scheme or not parsed.netloc:
                    issues.append(
                        ValidationIssue(
                            field="base_url",
                            code="INVALID_URL",
                            message="Base URL must be a valid HTTP or HTTPS URL.",
                        )
                    )
                elif parsed.scheme.lower() != "https" and parsed.hostname not in ("localhost", "127.0.0.1", "testserver"):
                    issues.append(
                        ValidationIssue(
                            field="base_url",
                            code="INSECURE_HTTP",
                            message="HTTPS is strictly required for external Rating API endpoints outside localhost.",
                        )
                    )
            except Exception:
                issues.append(
                    ValidationIssue(
                        field="base_url",
                        code="INVALID_URL",
                        message="Base URL failed parsing.",
                    )
                )

        if not config.expected_premium_field.strip():
            issues.append(
                ValidationIssue(
                    field="expected_premium_field",
                    code="REQUIRED",
                    message="Expected premium field mapping is required.",
                )
            )

        if config.timeout_seconds <= 0 or config.timeout_seconds > 60:
            issues.append(
                ValidationIssue(
                    field="timeout_seconds",
                    code="OUT_OF_RANGE",
                    message="Timeout seconds must be between 0.1 and 60.0 seconds.",
                )
            )

        return issues

    @staticmethod
    def validate_mission(mission: AssuranceMission) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        if not mission.name.strip():
            issues.append(
                ValidationIssue(
                    field="name",
                    code="REQUIRED",
                    message="Mission name is required.",
                )
            )

        if not mission.objective.product.strip():
            issues.append(
                ValidationIssue(
                    field="product",
                    code="REQUIRED",
                    message="Target insurance product is required.",
                )
            )

        if not mission.objective.jurisdiction.strip():
            issues.append(
                ValidationIssue(
                    field="jurisdiction",
                    code="REQUIRED",
                    message="Target jurisdiction is required.",
                )
            )

        # Mode-specific source requirements
        if mission.mode == ComparisonMode.RELEASE_CONFORMANCE:
            if not mission.source_a or not mission.source_a.source_id:
                issues.append(
                    ValidationIssue(
                        field="source_a",
                        code="REQUIRED",
                        message="Authoritative Pricing Intent (Source A) is required for Release Conformance mode.",
                    )
                )
            if not mission.source_b or not mission.source_b.source_id:
                issues.append(
                    ValidationIssue(
                        field="source_b",
                        code="REQUIRED",
                        message="Target Rating Implementation (Source B) is required for Release Conformance mode.",
                    )
                )

        elif mission.mode == ComparisonMode.EQUIVALENCE:
            if not mission.source_a or not mission.source_b:
                issues.append(
                    ValidationIssue(
                        field="sources",
                        code="REQUIRED",
                        message="Both Source A and Source B are required for Equivalence comparison mode.",
                    )
                )

        elif mission.mode == ComparisonMode.RUNTIME_VERIFICATION:
            if not mission.source_a or not mission.source_a.source_id:
                issues.append(
                    ValidationIssue(
                        field="source_a",
                        code="REQUIRED",
                        message="Authoritative Pricing Intent (Source A) is required for Runtime Verification mode.",
                    )
                )
            if not mission.runtime_connector:
                issues.append(
                    ValidationIssue(
                        field="runtime_connector",
                        code="REQUIRED",
                        message="Rating API Connector configuration is required for Runtime Verification mode.",
                    )
                )
            else:
                conn_issues = MissionValidationService.validate_runtime_connector(
                    mission.runtime_connector
                )
                issues.extend(conn_issues)

        return issues

