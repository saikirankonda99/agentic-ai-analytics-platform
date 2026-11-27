from __future__ import annotations

import pandas as pd
import pytest

from autonomous_insights import analyze_result_set
from semantic import infer_column_role, profile_dataframe, recommend_chart_fields


@pytest.mark.parametrize("name", ["revenue", "unit_cost", "total_sales", "quantity", "unitPrice", "InvoiceTotal"])
def test_named_integer_measures_remain_metrics_when_values_are_unique(name):
    assert infer_column_role(name, pd.Series([300, 200, 100])) == "metric"


@pytest.mark.parametrize("name", ["order_id", "CustomerId", "revenue_id", "product_code", "invoice_number"])
def test_identifiers_remain_identifiers_even_with_metric_words(name):
    assert infer_column_role(name, pd.Series([1, 2, 3])) == "identifier"


def test_revenue_chart_uses_named_measure_with_unique_integer_values():
    data = pd.DataFrame({"product": ["Coffee", "Tea", "Cake"], "revenue": [300, 200, 100]})

    assert recommend_chart_fields(data, profile_dataframe(data)) == ("product", "revenue")


def test_constant_revenue_does_not_raise_alerts_about_order_ids_or_dates():
    data = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "order_id": [1, 2, 3],
            "revenue": [100.0, 100.0, 100.0],
        }
    )

    result = analyze_result_set(data, "How is revenue trending?")

    assert result["severity"] == "info"
    assert [finding["type"] for finding in result["findings"]] == ["baseline"]


def test_revenue_trend_ignores_leading_identifier_and_numeric_year():
    data = pd.DataFrame(
        {
            "OrderId": [101, 102, 103],
            "OrderDate": ["2026-01-01", "2026-02-01", "2026-03-01"],
            "year": [2026, 2026, 2026],
            "revenue": [100, 150, 200],
        }
    )

    result = analyze_result_set(data, "How is revenue trending?")
    trend = next(finding for finding in result["findings"] if finding["type"] == "trend")

    assert trend["metric"] == "revenue"
    assert trend["dimension"] == "OrderDate"
    assert "100.0%" in trend["detail"]
    assert all(finding.get("metric") not in {"OrderId", "year"} for finding in result["findings"])
    assert all(finding.get("dimension") != "revenue" for finding in result["findings"])


def test_concentration_uses_product_and_revenue_without_numeric_self_grouping():
    data = pd.DataFrame(
        {
            "order_id": [1, 2, 3, 4],
            "product": ["Coffee", "Coffee", "Tea", "Cake"],
            "revenue": [400, 400, 100, 100],
        }
    )

    result = analyze_result_set(data, "Which product accounts for most revenue?")
    contribution = next(finding for finding in result["findings"] if "dominates" in finding["title"])

    assert contribution["dimension"] == "product"
    assert contribution["metric"] == "revenue"
    assert "80.0%" in contribution["detail"]
    assert all(finding.get("dimension") not in {"revenue", "order_id"} for finding in result["findings"])


def test_identifier_only_dataset_does_not_report_numeric_trends():
    data = pd.DataFrame({"OrderId": [1, 10, 100], "year": [2024, 2025, 2026]})

    result = analyze_result_set(data)

    assert [finding["type"] for finding in result["findings"]] == ["baseline"]
