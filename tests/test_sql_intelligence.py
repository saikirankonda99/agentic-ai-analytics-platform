from __future__ import annotations

from backend.sql_intelligence import (
    analyze_result_quality,
    build_schema_intelligence,
    explain_sql,
    validate_sql_against_schema,
)
from guardrails import is_safe_sql


SCHEMA = """
Table: Customer
CustomerId (INTEGER), FirstName (TEXT), LastName (TEXT), Email (TEXT), SupportRepId (INTEGER)

Table: Invoice
InvoiceId (INTEGER), CustomerId (INTEGER), InvoiceDate (TEXT), Total (REAL)
"""


def test_schema_intelligence_infers_relationships_and_compressed_context() -> None:
    intelligence = build_schema_intelligence(SCHEMA)

    assert intelligence["table_count"] == 2
    assert intelligence["confidence"] > 0.6
    assert any(item["from_table"] == "Invoice" for item in intelligence["relationships"])
    assert "Schema intelligence" in intelligence["compressed_prompt"]


def test_sql_validation_detects_unknown_table_and_column() -> None:
    table_result = validate_sql_against_schema("SELECT * FROM Customers", SCHEMA)
    column_result = validate_sql_against_schema("SELECT c.DoesNotExist FROM Customer c LIMIT 5", SCHEMA)

    assert table_result["status"] == "failed"
    assert "Unknown table: Customers." in table_result["errors"]
    assert column_result["status"] == "failed"
    assert "Unknown column: c.DoesNotExist." in column_result["errors"]


def test_sql_validation_scores_safe_query_and_explanation() -> None:
    sql = "SELECT c.CustomerId, c.Email, SUM(i.Total) AS revenue FROM Customer c JOIN Invoice i ON c.CustomerId = i.CustomerId GROUP BY c.CustomerId, c.Email LIMIT 10"
    validation = validate_sql_against_schema(sql, SCHEMA)
    explanation = explain_sql(sql, validation)

    assert validation["status"] == "passed"
    assert validation["risk_level"] == "low"
    assert validation["complexity"]["joins"] == 1
    assert explanation["intent_summary"].startswith("Aggregate")
    assert explanation["confidence"] == validation["confidence"]


def test_unsafe_query_detection_uses_word_boundaries() -> None:
    assert is_safe_sql("SELECT updated_at FROM events") is True
    assert is_safe_sql("UPDATE Customer SET FirstName = 'x'") is False
    assert validate_sql_against_schema("DROP TABLE Customer", SCHEMA)["status"] == "failed"


def test_result_quality_detects_empty_and_null_heavy_results() -> None:
    empty = analyze_result_quality(["id"], [])
    null_heavy = analyze_result_quality(["id", "email"], [(None, None), (1, None)])

    assert empty["status"] == "warning"
    assert "Query returned no rows." in empty["warnings"]
    assert null_heavy["status"] == "warning"
    assert "Result is null-heavy." in null_heavy["warnings"]
