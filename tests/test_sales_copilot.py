import json

import pandas as pd
import pytest

from csv_analytics import DEMO_PATH, analyze_sales, read_sales_csv
import sales_copilot


@pytest.fixture
def products():
    return analyze_sales(read_sales_csv(DEMO_PATH.read_bytes()), "Revenue by product")


def _model(monkeypatch, selection, captured=None):
    monkeypatch.setattr(sales_copilot, "get_openai_api_key", lambda: "test-key-not-a-real-secret")

    def generate(prompt, **kwargs):
        if captured is not None:
            captured.append(prompt)
        return {"text": json.dumps(selection), "telemetry": {"model": "test-model", "total_tokens": 123}}

    monkeypatch.setattr(sales_copilot, "stream_text_with_telemetry", generate)


def test_ai_is_opt_in_and_no_key_does_not_call_provider(monkeypatch, products):
    def never(*args, **kwargs):
        pytest.fail("The model must not be called.")

    monkeypatch.setattr(sales_copilot, "stream_text_with_telemetry", never)
    assert sales_copilot.explain_sales_report(products)["status"] == "disabled"
    monkeypatch.setattr(sales_copilot, "get_openai_api_key", lambda: None)
    reply = sales_copilot.explain_sales_report(products, enabled=True)
    assert reply["status"] == "not_connected"
    assert reply["ai_used"] is False
    assert reply["findings"] == []


def test_model_prioritises_facts_but_all_visible_numbers_are_local(monkeypatch, products):
    calls = []
    _model(monkeypatch, {
        "headline": "concentration",
        "fact_ids": ["leading_group", "leading_share", "total_revenue"],
        "action_ids": ["product_check", "cost_check"],
    }, calls)
    reply = sales_copilot.explain_sales_report(products, enabled=True)
    assert reply["status"] == "success"
    assert reply["ai_used"] is True
    assert reply["model"] == "test-model"
    assert "Coffee Beans (180.00 USD)" in reply["findings"][0]
    assert "51.1%" in reply["findings"][1]
    assert "352.00 USD" in reply["findings"][2]
    assert len(calls) == 1
    assert "Coffee Beans" not in calls[0]
    assert "Tea" not in calls[0]
    assert "Mug" not in calls[0]
    assert '"total_revenue"' in calls[0]


def test_mapping_contract_uses_current_result_and_never_sends_raw_metadata(monkeypatch, products):
    calls = []
    _model(monkeypatch, {
        "headline": "overview", "fact_ids": ["total_revenue", "source_rows"], "action_ids": ["reconcile"],
    }, calls)
    metadata = {
        "source_rows": products.source_rows, "total_revenue": products.total_revenue,
        "currency": products.currency, "warnings": [],
        "summary": "Private Customer alice@example.test; confidential raw order 123",
        "filename": "private-alice.csv",
    }
    reply = sales_copilot.explain_sales_report(metadata, products.result, enabled=True)
    assert reply["ai_used"]
    assert "alice" not in calls[0]
    assert "Private" not in calls[0]


@pytest.mark.parametrize("selection", [
    {"headline": "overview", "fact_ids": ["total_revenue", "profit"], "action_ids": ["reconcile"]},
    {"headline": "overview", "fact_ids": ["total_revenue", "source_rows"], "action_ids": ["buy_more_stock"]},
    {"headline": "overview", "fact_ids": ["total_revenue", "total_revenue"], "action_ids": ["reconcile"]},
    {"headline": "overview", "fact_ids": ["total_revenue", "leading_share"], "action_ids": ["reconcile"]},
    {"headline": "monthly", "fact_ids": ["total_revenue", "source_rows"], "action_ids": ["reconcile"]},
    {"headline": "overview", "fact_ids": ["total_revenue", "source_rows"], "action_ids": ["reconcile"], "text": "Profit is 999"},
    {"headline": "Sales fell because customers left", "fact_ids": ["total_revenue", "source_rows"], "action_ids": ["reconcile"]},
])
def test_invented_numbers_causes_actions_or_schema_are_never_rendered(monkeypatch, products, selection):
    _model(monkeypatch, selection)
    reply = sales_copilot.explain_sales_report(products, enabled=True)
    assert reply["status"] == "unavailable"
    assert not reply["ai_used"]
    assert reply["findings"] == []
    assert reply["next_steps"] == []


def test_month_observation_requires_completeness_caveat(monkeypatch):
    months = analyze_sales(read_sales_csv(DEMO_PATH.read_bytes()), "Revenue by month")
    selection = {"headline": "monthly", "fact_ids": ["highest_month", "recorded_months"], "action_ids": ["reconcile"]}
    _model(monkeypatch, selection)
    assert sales_copilot.explain_sales_report(months, enabled=True)["status"] == "unavailable"
    selection["action_ids"] = ["period_check"]
    _model(monkeypatch, selection)
    reply = sales_copilot.explain_sales_report(months, enabled=True)
    assert reply["ai_used"]
    assert "2026-01 (144.00 USD)" in reply["findings"][0]
    assert any("incomplete" in text for text in reply["limitations"])


def test_negative_revenue_does_not_produce_misleading_share(monkeypatch):
    analysis = analyze_sales(pd.DataFrame({"product": ["A", "B"], "revenue": [100, -50]}), "Revenue by product")
    calls = []
    _model(monkeypatch, {
        "headline": "quality", "fact_ids": ["total_revenue", "negative_amounts"], "action_ids": ["returns_check"],
    }, calls)
    reply = sales_copilot.explain_sales_report(analysis, enabled=True)
    assert reply["ai_used"]
    assert '"id": "leading_share"' not in calls[0]


def test_provider_failure_keeps_report_and_does_not_expose_error(monkeypatch, products):
    original = products.result.copy(deep=True)
    monkeypatch.setattr(sales_copilot, "get_openai_api_key", lambda: "test-key")

    def broken(*args, **kwargs):
        raise RuntimeError("secret endpoint https://private.example/?token=secret")

    monkeypatch.setattr(sales_copilot, "stream_text_with_telemetry", broken)
    reply = sales_copilot.explain_sales_report(products, enabled=True)
    assert reply["status"] == "unavailable"
    assert "secret" not in json.dumps(reply)
    pd.testing.assert_frame_equal(products.result, original)


def test_corrupt_or_unsupported_data_never_reaches_the_model(monkeypatch, products):
    def never(*args, **kwargs):
        pytest.fail("The model must not be called.")

    monkeypatch.setattr(sales_copilot, "stream_text_with_telemetry", never)
    metadata = {"source_rows": 12, "total_revenue": 999, "currency": "USD", "warnings": []}
    assert sales_copilot.explain_sales_report(metadata, products.result, enabled=True)["status"] == "unsupported"
    assert sales_copilot.explain_sales_report(products, focus="Forecast next month", enabled=True)["status"] == "unsupported"
