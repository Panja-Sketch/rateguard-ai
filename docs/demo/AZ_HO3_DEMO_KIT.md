# RateGuard AI — Sample Assets & Acceptance Test Kit

This directory contains clean, unencumbered synthetic demo assets and configuration templates for verifying RateGuard AI's **Assurance Mission V2** workflows without private carrier data.

---

## 1. Demo Asset Inventory (`data/demo/`)

| Asset File | Description | Purpose |
| :--- | :--- | :--- |
| [`data/demo/runtime_api_connector_example.json`](file:///c:/Users/chara/rateguard-ai/data/demo/runtime_api_connector_example.json) | Connector JSON template for external Black-Box Rating APIs | Test connection & Black-Box Runtime Verification mode |
| [`data/implementations/canonical/AZ_HO3_2026_09_ipir.json`](file:///c:/Users/chara/rateguard-ai/data/implementations/canonical/AZ_HO3_2026_09_ipir.json) | Authoritative Arizona Homeowners HO3 Pricing Intent AST | Canonical filing intent baseline |
| [`data/implementations/defective/AZ_HO3_2026_09_ipir.json`](file:///c:/Users/chara/rateguard-ai/data/implementations/defective/AZ_HO3_2026_09_ipir.json) | Defective Rating Engine Implementation AST | Multi-defect regression testing |
| [`data/portfolio/az_ho3_2026_synthetic_50k.csv`](file:///c:/Users/chara/rateguard-ai/data/portfolio/az_ho3_2026_synthetic_50k.csv) | 50,000 synthetic in-force Arizona policy risk records | Portfolio exposure & financial blast radius math |

> **Synthetic Notice**: All rates, factors, boundaries, and policy records are synthetic actuarial representations created exclusively for demonstration and software verification.

---

## 2. Modes Covered by Kit

1. **`EQUIVALENCE`**: Symmetric comparison of Source A $\leftrightarrow$ Source B ASTs.
2. **`RELEASE_CONFORMANCE`**: Compares Authoritative Intent against Target Rating Implementation.
3. **`RUNTIME_VERIFICATION`**: Compares Authoritative Intent against `POST /api/v1/demo-rating/quote` black-box API.

