from __future__ import annotations

import pandas as pd
import pytest

from csv_analytics import SUPPORTED_QUESTIONS, analyze_sales, read_sales_csv
from csv_import import DATE_FORMATS, MAPPING_FIELDS, suggest_sales_mapping, validate_sales_import


def assert_rejected(review, *messages):
    assert review.frame is None
    assert review.analysis is None
    assert review.available_questions == ()
    assert review.errors
    for message in messages:
        assert any(message in error for error in review.errors), review.errors


def test_suggestions_use_only_unambiguous_existing_aliases():
    frame = pd.DataFrame(columns=["Revenue", "total", " Qty ", "Unit Price", "Product Name", "Order Date", "Billing Country", "Currency Code", "Net Receipts"])
    assert suggest_sales_mapping(frame) == {
        "revenue": None, "quantity": " Qty ", "unit_price": "Unit Price", "product": "Product Name",
        "date": "Order Date", "country": "Billing Country", "currency": "Currency Code",
    }
    assert all(value is None for value in suggest_sales_mapping(pd.DataFrame(columns=["Net Receipts", "Sold on", "SKU"])).values())
    assert tuple(suggest_sales_mapping(frame)) == MAPPING_FIELDS


def test_arbitrary_headers_preserve_precision_codes_and_original_frame():
    raw = read_sales_csv(b"SKU,Net receipts,Sold on,Ship to,Money\n001,123456789.1549999999,01/02/2026,NA,USD\n1,0.10,02/03/2026,US,USD\n")
    raw.index = [10, 30]
    original = raw.copy(deep=True)
    review = validate_sales_import(raw, {"product": "SKU", "revenue": "Net receipts", "date": "Sold on", "country": "Ship to", "currency": "Money"}, date_format="MM/DD/YYYY")

    assert not review.errors
    assert review.frame["revenue"].tolist() == ["123456789.1549999999", "0.10"]
    assert review.frame["product"].tolist() == ["001", "1"]
    assert review.frame["country"].tolist() == ["NA", "US"]
    assert review.frame["date"].tolist() == ["2026-01-02", "2026-02-03"]
    assert review.analysis.total_revenue == 123456789.25
    assert analyze_sales(review.frame, "Revenue by product").result.to_dict("records") == [
        {"product": "001", "revenue": 123456789.15}, {"product": "1", "revenue": 0.1},
    ]
    pd.testing.assert_frame_equal(raw, original)


def test_column_mode_uses_mapped_revenue_and_ignores_bad_unit_price():
    raw = pd.DataFrame({"Net": ["25.00"], "Units": ["2"], "Price": ["bad"], "total": ["999"]})
    review = validate_sales_import(raw, {"revenue": "Net", "quantity": "Units", "unit_price": "Price"})
    assert not review.errors
    assert "unit_price" not in review.frame
    assert review.analysis.total_revenue == 25.0
    assert review.analysis.result.iloc[0]["units"] == 2.0
    assert "Sum of 'revenue'" in review.analysis.summary


def test_quantity_price_mode_ignores_mapped_and_unmapped_revenue_aliases():
    raw = pd.DataFrame({"Net": ["bad"], "Units": ["2"], "Price": ["3.125"], "revenue": ["999"]})
    review = validate_sales_import(raw, {"revenue": "Net", "quantity": "Units", "unit_price": "Price"}, revenue_mode="quantity_price")
    assert not review.errors
    assert "revenue" not in review.frame
    assert review.analysis.total_revenue == 6.25
    assert "'quantity' × 'unit_price'" in review.analysis.summary


@pytest.mark.parametrize("mapping,kwargs,message", [
    ({}, {}, "Map a 'revenue'"),
    ({"quantity": "Amount"}, {"revenue_mode": "quantity_price"}, "Map a 'unit_price'"),
    ({"revenue": "Amount", "profit": None}, {}, "Unknown sales field 'profit'"),
    ({"revenue": "missing"}, {}, "does not exist"),
    ({"revenue": "Amount", "unit_price": "missing"}, {}, "does not exist"),
    ({"revenue": "Amount", "quantity": "Amount"}, {}, "mapped to both"),
    ({"quantity": "Amount", "unit_price": "Amount"}, {"revenue_mode": "quantity_price"}, "mapped to both"),
    ({"revenue": "Amount"}, {"revenue_mode": "guess"}, "Choose revenue mode"),
    ({"revenue": "Amount"}, {"date_format": "automatic"}, "supported date format"),
])
def test_invalid_mapping_configuration_returns_no_partial_result(mapping, kwargs, message):
    assert_rejected(validate_sales_import(pd.DataFrame({"Amount": ["10"]}), mapping, **kwargs), message)


def test_duplicate_assignment_to_an_inactive_field_does_not_change_mode():
    review = validate_sales_import(pd.DataFrame({"Amount": ["10"]}), {"revenue": "Amount", "unit_price": "Amount"})
    assert not review.errors
    assert review.analysis.total_revenue == 10.0


@pytest.mark.parametrize("value", ["", None, pd.NA, "NaN", "Infinity", "-Infinity", "$10", "1,000", "1000000001"])
def test_bad_numeric_cells_are_rejected_with_data_row_numbers(value):
    raw = pd.DataFrame({"Net": ["10", value]}, index=[100, 200])
    assert_rejected(validate_sales_import(raw, {"revenue": "Net"}), "Revenue ('Net')", "data rows: 2")


@pytest.mark.parametrize("field,mode", [("revenue", "column"), ("quantity", "column"), ("unit_price", "quantity_price")])
def test_all_rows_and_optional_numeric_fields_are_validated_beyond_preview(field, mode):
    raw = pd.DataFrame({"revenue": ["10"] * 12, "quantity": ["2"] * 12, "unit_price": ["5"] * 12})
    raw.loc[11, field] = "invalid"
    original = raw.copy(deep=True)
    review = validate_sales_import(raw, {column: column for column in raw}, revenue_mode=mode)
    assert_rejected(review, f"('{field}')", "data rows: 12")
    pd.testing.assert_frame_equal(raw, original)


@pytest.mark.parametrize("format_label,date,expected", [
    ("YYYY-MM-DD", "2026-01-02", "2026-01-02"),
    ("MM/DD/YYYY", "01/02/2026", "2026-01-02"),
    ("DD/MM/YYYY", "01/02/2026", "2026-02-01"),
])
def test_date_format_is_explicit_and_normalizes_to_iso(format_label, date, expected):
    review = validate_sales_import(pd.DataFrame({"Amount": ["10"], "Sold on": [date]}), {"revenue": "Amount", "date": "Sold on"}, date_format=format_label)
    assert not review.errors
    assert format_label in DATE_FORMATS
    assert review.frame["date"].tolist() == [expected]
    assert analyze_sales(review.frame, "Revenue by month").result.iloc[0]["month"] == expected[:7]


@pytest.mark.parametrize("date,format_label", [
    ("2026-1-02", "YYYY-MM-DD"), ("2026-02-30", "YYYY-MM-DD"),
    ("2026-01-02T12:00:00", "YYYY-MM-DD"), ("01/02/2026", "YYYY-MM-DD"),
    ("13/02/2026", "MM/DD/YYYY"), ("02/13/2026", "DD/MM/YYYY"),
    (" 01/02/2026 ", "MM/DD/YYYY"), (None, "YYYY-MM-DD"),
])
def test_selected_dates_must_all_match_the_exact_valid_format(date, format_label):
    review = validate_sales_import(pd.DataFrame({"Amount": ["10"], "When": [date]}), {"revenue": "Amount", "date": "When"}, date_format=format_label)
    assert_rejected(review, "Date ('When')", "data rows: 1", format_label)


@pytest.mark.parametrize("field", ["product", "country"])
@pytest.mark.parametrize("value", ["", "  ", None])
def test_blank_optional_dimensions_block_apply_when_mapped(field, value):
    raw = pd.DataFrame({"Amount": ["10"], "Label": [value]})
    assert_rejected(validate_sales_import(raw, {"revenue": "Amount", field: "Label"}), "blank labels", "data rows: 1")
    assert not validate_sales_import(raw, {"revenue": "Amount"}).errors


@pytest.mark.parametrize("currency", ["", None, "JPY", "KWD", "unknown"])
def test_mapped_bad_currency_is_never_filled_from_default(currency):
    raw = pd.DataFrame({"Amount": ["10"], "Money": [currency]})
    assert_rejected(validate_sales_import(raw, {"revenue": "Amount", "currency": "Money"}, default_currency="USD"), "Currency ('Money')", "data rows: 1")


def test_mixed_currencies_block_apply_and_valid_mapped_currency_overrides_default():
    raw = pd.DataFrame({"Amount": ["10", "20"], "Money": ["USD", "CAD"]})
    assert_rejected(validate_sales_import(raw, {"revenue": "Amount", "currency": "Money"}), "mixed currencies")
    raw["Money"] = [" cad ", "CAD"]
    review = validate_sales_import(raw, {"revenue": "Amount", "currency": "Money"}, default_currency="invalid")
    assert not review.errors
    assert review.analysis.currency == "CAD"
    assert not any("assumed" in warning for warning in review.warnings)


def test_default_currency_is_explicitly_warned_or_left_unspecified():
    raw = pd.DataFrame({"Amount": ["10"]})
    review = validate_sales_import(raw, {"revenue": "Amount"}, default_currency="CAD")
    assert not review.errors
    assert review.analysis.currency == "CAD"
    assert any("CAD is assumed" in warning for warning in review.warnings)
    assert review.analysis.warnings == review.warnings
    unspecified = validate_sales_import(raw, {"revenue": "Amount"}, default_currency=None)
    assert not unspecified.errors
    assert "currency" not in unspecified.frame
    assert any("No currency column" in warning for warning in unspecified.warnings)
    assert_rejected(validate_sales_import(raw, {"revenue": "Amount"}, default_currency="JPY"), "default currency")


def test_original_ids_preserve_only_exact_raw_duplicates_and_negative_returns():
    raw = pd.DataFrame({"Order ID": ["0001", "0002", "0001", "0003"], "SKU": ["001"] * 4, "Amount": ["10", "10", "10", "-2"]})
    review = validate_sales_import(raw, {"product": "SKU", "revenue": "Amount"})
    assert not review.errors
    assert len(review.frame) == review.analysis.source_rows == 4
    assert review.analysis.total_revenue == 28.0
    assert any("1 exact duplicate row(s)" in warning for warning in review.warnings)
    assert any("Negative" in warning for warning in review.warnings)
    result = analyze_sales(review.frame, "Revenue by product")
    assert result.result.to_dict("records") == [{"product": "001", "revenue": 28.0}]
    assert any("1 exact duplicate row(s)" in warning for warning in result.warnings)


def test_same_sales_values_with_distinct_unused_fields_are_not_exact_duplicates():
    raw = pd.DataFrame({"ID": ["A", "B"], "Amount": ["10", "10"]})
    review = validate_sales_import(raw, {"revenue": "Amount"})
    assert not review.errors
    assert not any("duplicate" in warning for warning in review.warnings)


def test_available_questions_require_mapped_valid_dimensions_and_quantity():
    raw = pd.DataFrame({"revenue": ["10"], "quantity": ["2"], "product": ["Tea"], "date": ["2026-01-02"], "country": ["US"], "currency": ["USD"]})
    all_fields = validate_sales_import(raw, suggest_sales_mapping(raw))
    assert not all_fields.errors
    assert all_fields.available_questions == SUPPORTED_QUESTIONS
    amount_only = validate_sales_import(raw, {"revenue": "revenue"})
    assert amount_only.available_questions == ("Total revenue", "Sales summary")
    product_only = validate_sales_import(raw, {"revenue": "revenue", "product": "product"})
    assert product_only.available_questions == ("Total revenue", "Revenue by product", "Sales summary")


def test_provenance_does_not_make_a_valid_hundred_column_file_too_wide():
    raw = pd.DataFrame({f"column {column}": [str(column)] for column in range(100)})
    review = validate_sales_import(raw, {"revenue": "column 1"})
    assert not review.errors
    assert review.analysis.total_revenue == 1.0


def test_empty_and_duplicate_column_frames_are_rejected():
    assert_rejected(validate_sales_import(pd.DataFrame(columns=["Amount"]), {"revenue": "Amount"}), "no sales rows")
    assert_rejected(validate_sales_import(pd.DataFrame([[10, 20]], columns=["Amount", "Amount"]), {"revenue": "Amount"}), "duplicate column names")
