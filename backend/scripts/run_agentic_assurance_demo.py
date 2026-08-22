import sys
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agents import AgenticAssuranceRunner  # noqa: E402
from app.ipir.package import IPIRPackage  # noqa: E402
from app.storage import get_run_store  # noqa: E402


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    canonical_file = (
        root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"
    )
    defective_file = (
        root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"
    )

    if not canonical_file.exists() or not defective_file.exists():
        print("Error: IPIR package files not found.")
        sys.exit(1)

    with open(canonical_file, encoding="utf-8") as f:
        canonical_pkg = IPIRPackage.model_validate_json(f.read())

    with open(defective_file, encoding="utf-8") as f:
        defective_pkg = IPIRPackage.model_validate_json(f.read())

    store = get_run_store()
    runner = AgenticAssuranceRunner(run_store=store)

    print("\n========================================================")
    print("      Starting RateGuard Agentic Autonomous Assurance   ")
    print("========================================================\n")

    result = runner.run_assurance(
        left_package=canonical_pkg,
        right_package=defective_pkg,
        include_portfolio_analysis=True,
    )

    print(f"Run ID:                    {result.run_id}")
    print(f"Assurance Status:          [{result.status}]\n")

    print("Subagent Activity & Audit Steps")
    print("--------------------------------------------------------")
    for step in result.agent_steps:
        print(f"Step {step.step_index}: [{step.agent_name}] ({step.role})")
        print(f"       Action:  {step.action}")
        print(f"       Summary: {step.summary}\n")

    print("Evidence-Backed Executive Decision & Recommendation")
    print("--------------------------------------------------------")
    print(f"Executive Summary:\n{result.executive_summary}\n")
    print(f"Technical Recommendation:\n{result.recommendation}\n")

    print(f"Evidence Lineage Record References ({len(result.evidence_refs)} Total):")
    for ref in result.evidence_refs:
        print(f"  - {ref}")

    print("========================================================\n")


if __name__ == "__main__":
    main()

