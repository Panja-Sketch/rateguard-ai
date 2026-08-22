import sys
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from google.cloud import bigquery  # noqa: E402
from google.cloud.exceptions import NotFound  # noqa: E402

from app.core.config import get_settings  # noqa: E402


def setup_bigquery() -> None:
    """Idempotently provisions BigQuery dataset and tables for RateGuard AI."""
    settings = get_settings()
    project_id = settings.google_cloud_project
    dataset_id = settings.bigquery_dataset
    location = settings.bigquery_location

    client = bigquery.Client(project=project_id)

    # 1. Dataset setup
    dataset_ref = bigquery.DatasetReference(project_id, dataset_id)
    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset '{project_id}.{dataset_id}' already exists.")
    except NotFound:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location
        dataset.description = "RateGuard AI portfolio analytics dataset"
        client.create_dataset(dataset, timeout=30)
        print(f"Successfully created dataset '{project_id}.{dataset_id}' in location {location}.")

    # 2. Portfolio Table setup (`synthetic_policies`)
    portfolio_table_id = f"{project_id}.{dataset_id}.{settings.bigquery_portfolio_table}"
    try:
        client.get_table(portfolio_table_id)
        print(f"Table '{portfolio_table_id}' already exists.")
    except NotFound:
        schema = [
            bigquery.SchemaField("policy_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("product_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("state", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("form", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("transaction_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("effective_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("territory", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("roof_age", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("deductible", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("protection_class", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("construction_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("dwelling_limit", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("multi_policy", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("claims_free", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("claims_free_years", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("canonical_premium", "NUMERIC", mode="REQUIRED"),
        ]
        table = bigquery.Table(portfolio_table_id, schema=schema)
        table.description = "Deterministic synthetic portfolio policies for RateGuard analysis"
        client.create_table(table)
        print(f"Successfully created table '{portfolio_table_id}'.")

    # 3. Results Table setup (`portfolio_exposure_results`)
    results_table_id = f"{project_id}.{dataset_id}.{settings.bigquery_results_table}"
    try:
        client.get_table(results_table_id)
        print(f"Table '{results_table_id}' already exists.")
    except NotFound:
        results_schema = [
            bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
            bigquery.SchemaField("total_policies", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("exposed_policies", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("behaviorally_affected", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("financially_affected", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("expected_premium", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("target_premium", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("signed_variance", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("absolute_variance", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("decision", "STRING", mode="REQUIRED"),
        ]
        results_table = bigquery.Table(results_table_id, schema=results_schema)
        results_table.description = "Summary financial exposure results for RateGuard assurance runs"
        client.create_table(results_table)
        print(f"Successfully created table '{results_table_id}'.")


if __name__ == "__main__":
    setup_bigquery()

