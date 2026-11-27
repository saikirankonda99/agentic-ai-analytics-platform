from __future__ import annotations

from streamlit.testing.v1 import AppTest

from csv_analytics import DEMO_PATH


def _review_app(content: bytes) -> AppTest:
    script = f"""
import streamlit as st
from csv_analytics import read_sales_csv
from ui.views.data_import import render_sales_import_review

st.radio("Primary navigation", ["Overview", "Copilot"], index=1, key="top_navigation")
st.session_state.setdefault("applied_frame", None)
raw = read_sales_csv({content!r})
review = render_sales_import_review(raw, "ui-test.csv", "ui-test")
if review is not None:
    st.session_state.applied_frame = review.frame
    st.session_state.applied_summary = review.analysis.summary
"""
    app = AppTest.from_string(script, default_timeout=15).run()
    assert not app.exception, [error.message for error in app.exception]
    return app


def _button(app: AppTest, label: str):
    return next(button for button in app.button if button.label == label)


def _total(app: AppTest) -> str:
    return next(metric.value for metric in app.metric if metric.label == "Total revenue")


def test_standard_upload_preview_requires_apply_and_opens_overview():
    app = _review_app(DEMO_PATH.read_bytes())

    assert len(app.dataframe[0].value) == 10
    assert _total(app) == "352.00 USD"
    assert app.session_state["applied_frame"] is None
    assert app.session_state["top_navigation"] == "Copilot"
    assert not _button(app, "Use this data").disabled

    _button(app, "Use this data").click().run()

    assert not app.exception
    assert app.session_state["top_navigation"] == "Overview"
    assert app.session_state["workspace_route"] == "Overview"
    assert len(app.session_state["applied_frame"]) == 12
    assert "352.00 USD" in app.session_state["applied_summary"]


def test_custom_headers_and_us_dates_are_mapped_through_real_widgets():
    app = _review_app(
        b"Item description,Sold units,Each amount,Sold on\n"
        b"001,2,12.50,01/31/2026\n"
        b"Tea,3,7.00,02/01/2026\n"
        b"Mug,1,12.00,02/10/2026\n"
    )
    assert _button(app, "Use this data").disabled

    for field, source in {
        "quantity": "Sold units",
        "unit_price": "Each amount",
        "product": "Item description",
        "date": "Sold on",
    }.items():
        app.selectbox(key=f"csv_import_ui-test_{field}").set_value(source)
    app.run()
    assert not app.exception
    assert _button(app, "Use this data").disabled
    assert any("invalid dates" in error.value for error in app.error)

    app.selectbox(key="csv_import_ui-test_date_format").set_value("MM/DD/YYYY").run()
    assert not app.exception
    assert _total(app) == "58.00 USD"
    assert not _button(app, "Use this data").disabled
    _button(app, "Use this data").click().run()

    assert not app.exception
    prepared = app.session_state["applied_frame"]
    assert prepared["product"].tolist() == ["001", "Tea", "Mug"]
    assert prepared["date"].tolist() == ["2026-01-31", "2026-02-01", "2026-02-10"]
    assert "58.00 USD" in app.session_state["applied_summary"]


def test_invalid_row_beyond_preview_blocks_apply_until_mapping_is_fixed():
    content = (
        b"product,quantity,unit_price,currency,good_quantity\n"
        + b"Tea,1,2.00,USD,1\n" * 11
        + b"Tea,bad,2.00,USD,3\n"
    )
    app = _review_app(content)
    assert len(app.dataframe[0].value) == 10
    assert app.session_state["applied_frame"] is None
    assert _button(app, "Use this data").disabled
    assert any("Quantity" in error.value and "data rows: 12" in error.value for error in app.error)

    app.selectbox(key="csv_import_ui-test_quantity").set_value("good_quantity").run()
    assert not app.exception
    assert not app.error
    assert _total(app) == "28.00 USD"
    _button(app, "Use this data").click().run()
    assert not app.exception
    assert len(app.session_state["applied_frame"]) == 12
    assert app.session_state["applied_frame"]["quantity"].iloc[-1] == "3"


def test_cancel_requests_cleanup_and_opens_overview_without_applying():
    app = _review_app(b"product,revenue,currency\nTea,7.50,USD\n")
    assert _total(app) == "7.50 USD"
    _button(app, "Cancel upload").click().run()

    assert not app.exception
    assert app.session_state["csv_import_cancel_requested"] is True
    assert app.session_state["top_navigation"] == "Overview"
    assert app.session_state["workspace_route"] == "Overview"
    assert app.session_state["applied_frame"] is None
