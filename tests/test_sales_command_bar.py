from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _button(app: AppTest, label: str):
    return next(button for button in app.button if button.label == label)


def test_limited_upload_explains_missing_columns_and_keeps_summary_available():
    app = AppTest.from_string('''
import streamlit as st
from csv_analytics import read_sales_csv, analyze_sales
from csv_import import validate_sales_import
from ui.dashboard import render_command_bar

review = validate_sales_import(
    read_sales_csv(b"product,revenue,currency\\nTea,7.50,USD\\n"),
    {"product": "product", "revenue": "revenue", "currency": "currency"},
)
st.session_state.uploaded_df = review.frame
st.session_state.csv_import_available_questions = review.available_questions
st.session_state.setdefault("command_input", "")
question = render_command_bar()
if question:
    st.session_state.result = analyze_sales(review.frame, question).result
''', default_timeout=15).run()
    assert not app.exception
    assert not _button(app, "Total Revenue").disabled
    assert not _button(app, "Sales Summary").disabled
    assert not _button(app, "Revenue by Product").disabled
    for label, field in [("Monthly Revenue", "date"), ("Revenue by Country", "country"), ("Units Sold by Product", "quantity")]:
        button = _button(app, label)
        assert button.disabled
        assert f"map {field} during review" in button.help
        assert any(f"{label} ({field})" in caption.value for caption in app.caption)

    _button(app, "Sales Summary").click().run()
    assert not app.exception
    assert app.session_state["command_input"] == "Sales summary"
    assert app.session_state["result"].to_dict("records") == [{"revenue": 7.5, "sales_rows": 1}]


def test_database_actions_remain_available_without_csv_fields():
    app = AppTest.from_string('''
import streamlit as st
from ui.dashboard import render_command_bar
st.session_state.setdefault("command_input", "")
st.session_state.question = render_command_bar()
''', default_timeout=15).run()
    assert not app.exception
    assert {button.label for button in app.button} == {"Run", "Top Customers", "Revenue by Country", "Top Tracks"}
    assert all(not button.disabled for button in app.button)
    _button(app, "Revenue by Country").click().run()
    assert not app.exception
    assert app.session_state["question"] == "Revenue by country"
    assert app.session_state["command_input"] == "Revenue by country"
