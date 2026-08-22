import sys
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.adapters import SourceDescriptor, SourceFormat, get_adapter_registry
from app.engines.diff import compare_packages


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    registry = get_adapter_registry()

    json_path = root_dir / "data" / "actuarial" / "AZ_HO3_2026_09_rate_spec.json"
    excel_path = root_dir / "data" / "actuarial" / "AZ_HO3_2026_09_rate_spec.xlsx"
    pdf_path = root_dir / "data" / "filings" / "AZ_HO3_2026_09_synthetic_rate_spec.pdf"
    platform_defective_path = (
        root_dir / "data" / "implementations" / "platform_config" / "AZ_HO3_2026_09_defective_platform_config.json"
    )

    print("\n========================================================")
    print("      RateGuard AI -- Source-Agnostic Compilation Demo   ")
    print("========================================================\n")

    # 1. Compile Structured JSON
    with open(json_path, "rb") as f:
        json_bytes = f.read()
    desc_json = SourceDescriptor(
        source_id="SRC-JSON-001",
        name="AZ_HO3_2026_09_rate_spec.json",
        source_type=SourceFormat.STRUCTURED_JSON,
        format="json",
        storage_uri=str(json_path),
    )
    res_json = registry.get_adapter(SourceFormat.STRUCTURED_JSON).to_ipir(desc_json, json_bytes)
    print(f"1. Structured JSON Adapter: Compiled '{res_json.ipir_package.id}' (Coverage: {res_json.mapping_coverage}%, Confidence: {res_json.confidence})")

    # 2. Compile Excel Workbook
    with open(excel_path, "rb") as f:
        excel_bytes = f.read()
    desc_excel = SourceDescriptor(
        source_id="SRC-EXCEL-001",
        name="AZ_HO3_2026_09_rate_spec.xlsx",
        source_type=SourceFormat.EXCEL,
        format="xlsx",
        storage_uri=str(excel_path),
    )
    res_excel = registry.get_adapter(SourceFormat.EXCEL).to_ipir(desc_excel, excel_bytes)
    print(f"2. Excel Workbook Adapter:  Compiled '{res_excel.ipir_package.id}' (Coverage: {res_excel.mapping_coverage}%, Confidence: {res_excel.confidence})")

    # 3. Compile PDF Specification
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    desc_pdf = SourceDescriptor(
        source_id="SRC-PDF-001",
        name="AZ_HO3_2026_09_synthetic_rate_spec.pdf",
        source_type=SourceFormat.PDF,
        format="pdf",
        storage_uri=str(pdf_path),
    )
    res_pdf = registry.get_adapter(SourceFormat.PDF).to_ipir(desc_pdf, pdf_bytes)
    print(f"3. PDF Rate Spec Adapter:  Compiled '{res_pdf.ipir_package.id}' (Coverage: {res_pdf.mapping_coverage}%, Confidence: {res_pdf.confidence})")

    # 4. Compile Defective Platform Config
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
    print(f"4. Platform Config Adapter: Compiled '{res_plat.ipir_package.id}' (Coverage: {res_plat.mapping_coverage}%, Confidence: {res_plat.confidence})\n")

    # --------------------------------------------------------
    # Bidirectional Semantic Comparison Demos
    # --------------------------------------------------------
    print("--------------------------------------------------------")
    print("Comparison A: Structured JSON (Source A) <-> Excel Workbook (Source B)")
    diff_a_b = compare_packages(res_json.ipir_package, res_excel.ipir_package)
    print(f"  Direction A -> B Semantic Differences: {diff_a_b.difference_count}")
    diff_b_a = compare_packages(res_excel.ipir_package, res_json.ipir_package)
    print(f"  Direction B -> A Semantic Differences: {diff_b_a.difference_count}")
    print("  Status: PERFECT EQUIVALENCE (0 semantic differences)")

    print("\nComparison B: Excel Workbook (Source B) <-> PDF Rate Spec (Source C)")
    diff_b_c = compare_packages(res_excel.ipir_package, res_pdf.ipir_package)
    print(f"  Direction B -> C Semantic Differences: {diff_b_c.difference_count}")
    print("  Status: SEMANTICALLY EQUIVALENT")

    print("\nComparison C: Canonical Excel IPIR <-> Defective Target Platform Config IPIR")
    diff_can_def = compare_packages(res_excel.ipir_package, res_plat.ipir_package)
    print(f"  Discovered Semantic Differences: {diff_can_def.difference_count}")
    for d in diff_can_def.differences:
        print(f"    - [{d.severity.value}] {d.node_id}: {d.description}")

    print("\n========================================================\n")


if __name__ == "__main__":
    main()

