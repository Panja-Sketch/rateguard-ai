from unittest.mock import MagicMock

from app.engines.impact.models import ImpactPredicate, PredicateClause
from app.ipir.enums import ComparisonOperator
from app.storage.portfolio import (
    BigQueryPortfolioRepository,
    LocalPortfolioRepository,
    get_portfolio_repository,
    translate_predicates_to_bigquery_where,
)


def test_sql_translator_parameterized_query():
    """Verifies sql_translator builds safe parameterized SQL filters."""
    predicates = [
        ImpactPredicate(
            id="PRED-01",
            description="Roof age 21 to 30",
            clauses=[
                PredicateClause(field="roof_age", operator=ComparisonOperator.GTE, value=21),
                PredicateClause(field="roof_age", operator=ComparisonOperator.LTE, value=30),
            ],
        ),
        ImpactPredicate(
            id="PRED-02",
            description="Territory T17",
            clauses=[
                PredicateClause(field="territory", operator=ComparisonOperator.EQ, value="T17"),
            ],
        ),
    ]

    p_filter = translate_predicates_to_bigquery_where(predicates)

    assert "WHERE" in p_filter.where_clause
    assert "roof_age >= @p_1" in p_filter.where_clause
    assert "roof_age <= @p_2" in p_filter.where_clause
    assert "territory = @p_3" in p_filter.where_clause
    assert len(p_filter.query_params) == 3

    # Check parameters
    assert p_filter.query_params[0]["name"] == "p_1"
    assert p_filter.query_params[0]["value"] == 21
    assert p_filter.query_params[1]["name"] == "p_2"
    assert p_filter.query_params[1]["value"] == 30
    assert p_filter.query_params[2]["name"] == "p_3"
    assert p_filter.query_params[2]["value"] == "T17"


def test_sql_translator_ignores_unallowed_fields():
    """Verifies sql_translator ignores unallowed field names to prevent SQL injection."""
    predicates = [
        ImpactPredicate(
            id="PRED-INJECT",
            description="SQL Injection attempt",
            clauses=[
                PredicateClause(field="DROP TABLE synthetic_policies; --", operator=ComparisonOperator.EQ, value="test"),
            ],
        )
    ]

    p_filter = translate_predicates_to_bigquery_where(predicates)
    assert p_filter.where_clause == ""
    assert len(p_filter.query_params) == 0


def test_local_portfolio_repository():
    """Tests LocalPortfolioRepository loading and query filtering."""
    repo = LocalPortfolioRepository()
    policies = repo.load_policies(limit=10)
    assert len(policies) == 10
    assert policies[0].policy_id.startswith("POL-AZ-")

    summary = repo.get_portfolio_summary()
    assert summary.total_policies >= 1000


def test_bigquery_repository_mocked():
    """Tests BigQueryPortfolioRepository using a mocked BigQuery client."""
    mock_client = MagicMock()

    # Mock query result for load_policies
    mock_row = {
        "policy_id": "POL-AZ-000001",
        "product_id": "AZ_HO3",
        "state": "AZ",
        "form": "HO3",
        "transaction_type": "NEW_BUSINESS",
        "effective_date": "2026-09-15",
        "territory": "T01",
        "roof_age": 10,
        "deductible": 1000,
        "protection_class": 3,
        "construction_type": "FRAME",
        "dwelling_limit": 300000,
        "multi_policy": True,
        "claims_free": True,
        "claims_free_years": 5,
        "canonical_premium": "1200.50",
    }

    mock_row_obj = MagicMock()
    mock_row_obj.items.return_value = mock_row.items()
    mock_client.query.return_value.result.return_value = [mock_row_obj]

    repo = BigQueryPortfolioRepository(client=mock_client)
    policies = repo.load_policies(limit=1)

    assert len(policies) == 1
    assert policies[0].policy_id == "POL-AZ-000001"
    assert policies[0].canonical_premium == 1200.50


def test_factory_returns_local_by_default():
    """Verifies factory returns LocalPortfolioRepository when BigQuery disabled."""
    repo = get_portfolio_repository()
    assert isinstance(repo, LocalPortfolioRepository)

