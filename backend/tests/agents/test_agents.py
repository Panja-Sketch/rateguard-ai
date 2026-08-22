from pathlib import Path

from app.agents import AgenticAssuranceRunner
from app.ipir.package import IPIRPackage
from app.storage import InMemoryRunStore


def get_canonical_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"


def get_defective_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"


def load_canonical_package() -> IPIRPackage:
    with open(get_canonical_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def load_defective_package() -> IPIRPackage:
    with open(get_defective_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def test_01_agentic_assurance_defective_block_deployment() -> None:
    canonical = load_canonical_package()
    defective = load_defective_package()

    store = InMemoryRunStore()
    runner = AgenticAssuranceRunner(run_store=store)

    result = runner.run_assurance(
        left_package=canonical,
        right_package=defective,
        include_portfolio_analysis=False,
    )

    assert result.status == "BLOCK_DEPLOYMENT"
    assert "BLOCK DEPLOYMENT" in result.recommendation
    assert len(result.agent_steps) >= 5
    assert len(result.evidence_refs) >= 5

    record = store.get_run(result.run_id)
    assert record is not None
    assert record.status == "COMPLETED"


def test_02_agentic_assurance_identical_package_pass() -> None:
    canonical = load_canonical_package()

    store = InMemoryRunStore()
    runner = AgenticAssuranceRunner(run_store=store)

    result = runner.run_assurance(
        left_package=canonical,
        right_package=canonical,
        include_portfolio_analysis=False,
    )

    assert result.status == "PASS"
    assert "PASS" in result.recommendation
