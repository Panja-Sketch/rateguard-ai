from typing import Any

from app.ipir.package import IPIRPackage


def generate_ipir_json_schema() -> dict[str, Any]:
    """Generates the JSON Schema for the root IPIRPackage model."""
    return IPIRPackage.model_json_schema()

