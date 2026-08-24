from decimal import Decimal

from app.adapters.runtime_connector import BlackBoxRatingApiAdapter
from app.agents.supervisor import AssuranceSupervisor
from app.api.assurance import resolve_demo_package
from app.models.mission import (
    AssuranceMission,
    ComparisonMode,
    MissionObjective,
    PricingSourceRef,
)
from app.models.mission import (
    RuntimeConnectorConfig as ConfigModel,
)
from app.services.remediation_service import RemediationService
from app.services.validation_service import MissionValidationService
from app.storage.memory_store import InMemoryRunStore


def test_mission_validation_rules():
    # Valid mission
    mission = AssuranceMission(
        mission_id="MIS-TEST-01",
        name="Valid Mission",
        mode=ComparisonMode.RELEASE_CONFORMANCE,
        objective=MissionObjective(product="AZ_HO3", jurisdiction="Arizona", effective_period_start="2026-09-01"),
        source_a=PricingSourceRef(source_id="AZ_HO3_2026_09", source_type="SAMPLE_RELEASE", name="Intent"),
        source_b=PricingSourceRef(source_id="AZ_HO3_2026_09_DEFECTIVE", source_type="SAMPLE_RELEASE", name="Target"),
    )

    issues = MissionValidationService.validate_mission(mission)
    assert len(issues) == 0


def test_rating_api_connector_validation():
    # Invalid URL & missing connector name
    bad_config = ConfigModel(
        connector_name="",
        base_url="not_a_url",
        expected_premium_field="premium",
    )
    issues = MissionValidationService.validate_runtime_connector(bad_config)
    assert len(issues) >= 2


def test_blackbox_rating_adapter_payload_mapping():
    config = ConfigModel(
        connector_name="Test API",
        base_url="http://localhost:8000/quote",
        request_template={"product": "AZ_HO3"},
        expected_premium_field="premium",
    )
    adapter = BlackBoxRatingApiAdapter(config)
    payload = adapter.map_inputs_to_payload({"dwelling_limit": Decimal("350000"), "roof_age": 10})

    assert payload["product"] == "AZ_HO3"
    assert payload["dwelling_limit"] == 350000.0
    assert payload["roof_age"] == 10


def test_blackbox_rating_adapter_premium_extraction():
    config = ConfigModel(
        connector_name="Test API",
        base_url="http://localhost:8000/quote",
        expected_premium_field="data.quote.final_premium",
    )
    adapter = BlackBoxRatingApiAdapter(config)
    res_data = {"data": {"quote": {"final_premium": "$1,250.50"}}}
    prem = adapter.extract_premium(res_data)

    assert prem == Decimal("1250.50")


def test_supervisor_clean_equivalence():
    store = InMemoryRunStore()
    supervisor = AssuranceSupervisor(store)

    left_pkg = resolve_demo_package("AZ_HO3_2026_09")
    right_pkg = resolve_demo_package("AZ_HO3_2026_09_CLEAN")

    mission = AssuranceMission(
        mission_id="MIS-CLEAN-01",
        name="Clean Equivalence Mission",
        mode=ComparisonMode.EQUIVALENCE,
        objective=MissionObjective(product="AZ_HO3", jurisdiction="Arizona", effective_period_start="2026-09-01"),
        source_a=PricingSourceRef(source_id="AZ_HO3_2026_09", source_type="SAMPLE_RELEASE", name="Intent"),
        source_b=PricingSourceRef(source_id="AZ_HO3_2026_09_CLEAN", source_type="SAMPLE_RELEASE", name="Clean Target"),
    )

    res = supervisor.run_mission(mission, left_pkg, right_pkg)
    assert res.release_decision.data.status == "PASS"
    assert res.semantic_analysis.data.difference_count == 0


def test_supervisor_defective_conformance_and_remediation():
    store = InMemoryRunStore()
    supervisor = AssuranceSupervisor(store)

    left_pkg = resolve_demo_package("AZ_HO3_2026_09")
    right_pkg = resolve_demo_package("AZ_HO3_2026_09_DEFECTIVE")

    mission = AssuranceMission(
        mission_id="MIS-DEFECTIVE-01",
        name="Defective Conformance Mission",
        mode=ComparisonMode.RELEASE_CONFORMANCE,
        objective=MissionObjective(product="AZ_HO3", jurisdiction="Arizona", effective_period_start="2026-09-01"),
        source_a=PricingSourceRef(source_id="AZ_HO3_2026_09", source_type="SAMPLE_RELEASE", name="Intent"),
        source_b=PricingSourceRef(source_id="AZ_HO3_2026_09_DEFECTIVE", source_type="SAMPLE_RELEASE", name="Defective Target"),
    )

    res = supervisor.run_mission(mission, left_pkg, right_pkg)
    assert res.release_decision.data.status == "BLOCK_DEPLOYMENT"
    assert res.semantic_analysis.data.difference_count > 0
    assert res.remediation.data is not None
    assert res.revalidation.data is not None
    assert res.revalidation.data.exposure_eliminated_pct == 100.0


def test_remediation_service_derived_package():
    rem_service = RemediationService()
    intent = resolve_demo_package("AZ_HO3_2026_09")
    defective = resolve_demo_package("AZ_HO3_2026_09_DEFECTIVE")

    proposal = rem_service.generate_remediation_proposal(intent, defective, [])
    assert proposal.derived_package_id.startswith("IPIR_PATCHED_")

    reval = rem_service.revalidate_remediation(intent, defective, proposal)
    assert reval.new_release_decision == "PASS"
    assert reval.exposure_eliminated_pct == 100.0

