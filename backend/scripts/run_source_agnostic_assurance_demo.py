import sys
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.adapters import SourceDescriptor, SourceFormat, get_adapter_registry  # noqa: E402
from app.agents import AgenticAssuranceRunner  # noqa: E402
from app.storage import InMemoryRunStore  # noqa: E402


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    registry = get_adapter_registry()

    excel_path = root_dir / "data" / "actuarial" / "AZ_HO3_2026_09_rate_spec.xlsx"
    platform_defective_path = (
        root_dir / "data" / "implementations" / "platform_config" / "AZ_HO3_2026_09_defective_platform_config.json"
    )

    print("\n========================================================")
    print("  RateGuard AI -- Source-Agnostic Assurance Workflow    ")
    print("========================================================\n")
    print("Story: RateGuard compiles two distinct pricing source representations")
    print("(Excel Actuarial Spec -> Target Engine Platform Config) into IPIR and")
    print("executes autonomous multi-agent pricing assurance.\n")

    # 1. Compile Excel Actuarial Source
    print("1. Compiling Canonical Excel Actuarial Specification...")
    with open(excel_path, "rb") as f:
        excel_bytes = f.read()
    desc_excel = SourceDescriptor(
        source_id="SRC-EXCEL-CANONICAL",
        name="AZ_HO3_2026_09_rate_spec.xlsx",
        source_type=SourceFormat.EXCEL,
        format="xlsx",
        storage_uri=str(excel_path),
    )
    res_excel = registry.get_adapter(SourceFormat.EXCEL).to_ipir(desc_excel, excel_bytes)
    print(f"   [SUCCESS] Compiled IPIR Package: '{res_excel.ipir_package.id}' (Confidence: {res_excel.confidence})\n")

    # 2. Compile Defective Platform Configuration
    print("2. Compiling Defective Target Platform Configuration...")
    with open(platform_defective_path, "rb") as f:
        plat_bytes = f.read()
    desc_plat = SourceDescriptor(
        source_id="SRC-PLATFORM-DEFECTIVE",
        name="AZ_HO3_2026_09_defective_platform_config.json",
        source_type=SourceFormat.PLATFORM_CONFIG,
        format="json",
        storage_uri=str(platform_defective_path),
    )
    res_plat = registry.get_adapter(SourceFormat.PLATFORM_CONFIG).to_ipir(desc_plat, plat_bytes)
    print(f"   [SUCCESS] Compiled IPIR Package: '{res_plat.ipir_package.id}' (Confidence: {res_plat.confidence})\n")

    # 3. Trigger ADK Agentic Autonomous Assurance Workflow
    print("3. Executing Google ADK Multi-Agent Autonomous Assurance Workflow...")
    store = InMemoryRunStore()
    runner = AgenticAssuranceRunner(run_store=store)

    result = runner.run_assurance(
        left_package=res_excel.ipir_package,
        right_package=res_plat.ipir_package,
        include_portfolio_analysis=True,
    )

    print(f"\nRun ID:           {result.run_id}")
    print(f"Assurance Status: [{result.status}]\n")

    print("Agent Workflow Audit Steps:")
    for step in result.agent_steps:
        print(f"  Step {step.step_index}: [{step.agent_name}] -> {step.action}")
        print(f"         Summary: {step.summary}")

    print("\n--------------------------------------------------------")
    print("Evidence-Backed Executive Recommendation:")
    print(result.recommendation)
    print("--------------------------------------------------------\n")
    print(f"Evidence Lineage References: {len(result.evidence_refs)} total stored.")
    print("========================================================\n")


if __name__ == "__main__":
    main()

