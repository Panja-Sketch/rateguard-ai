# Source-Agnostic Pricing Adapters Architecture

## Executive Summary

RateGuard AI enforces strict source-agnostic compilation. Insurers maintain rating logic in heterogeneous sources (actuarial Excel workbooks, regulatory filings in PDF format, structured JSON rate specifications, and legacy core system configurations).

RateGuard's Adapter Layer parses these diverse formats into a single, strongly typed, vendor-neutral **Insurance Pricing Intermediate Representation (IPIR 0.1)** without loss of precision or auditability.

---

## Supported Source Formats

| Format Identifier | Source Type | Adapter Implementation Class | Key Capabilities |
| :--- | :--- | :--- | :--- |
| `STRUCTURED_JSON` | Structured Actuarial JSON Spec | `StructuredJSONPricingAdapter` | Direct 1:1 mapping, 100% deterministic compilation |
| `EXCEL` | Actuarial Workbook (`.xlsx`) | `ExcelPricingAdapter` | Openpyxl sheet/row parser, cell range mapping, table structure extraction |
| `PDF` | Rate Filing Specification (`.pdf`) | `PDFPricingAdapter` | Hybrid ReportLab/PyPDF text extraction + Gemini 3.5+ schema validation |
| `PLATFORM_CONFIG` | Synthetic Rating Engine Config | `PlatformConfigAdapter` | Vendor-neutral engine configuration parser |

---

## Adapter Architecture Principles

1. **Vendor Neutrality**: No vendor-specific constructs in IPIR. Vendor details are isolated inside `Provenance.sources`.
2. **Deterministic Computation**: Gemini 3.5+ handles schema structuring and semantic classification; deterministic Python code computes factor lookup arrays and formula trees.
3. **Traceable Provenance**: Every extracted element links directly back to its source location (e.g. `Sheet: RoofAgeFactors, Row: 5` or `PDF Page 1 Section 2`).
4. **Bidirectional Equivalence**: Compiling Source A (`.xlsx`) and Source B (`.json`) representing the same rate plan yields **0 semantic differences** when compared via `compare_packages()`.

---

## Verification & Execution

To run the source adapter comparison demo script:

```bash
cd backend
python scripts/run_adapter_comparison_demo.py
```

