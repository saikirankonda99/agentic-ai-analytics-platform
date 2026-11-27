from io import StringIO

import pandas as pd
import pytest

from csv_analytics import CSVAnalysisError, DEMO_PATH, MAX_CSV_BYTES, MAX_CSV_ROWS, SUPPORTED_CURRENCIES, analyze_sales, read_sales_csv


def test_raw_transactions_produce_different_exact_answers():
    frame = read_sales_csv(DEMO_PATH.read_bytes())
    assert len(frame) == 12
    assert analyze_sales(frame, "Total revenue").result.to_dict("records") == [{"revenue": 352.0}]
    products = analyze_sales(frame, "Revenue by product")
    assert products.result.to_dict("records") == [
        {"product": "Coffee Beans", "revenue": 180.0},
        {"product": "Tea", "revenue": 100.0},
        {"product": "Mug", "revenue": 72.0},
    ]
    assert analyze_sales(frame, "Revenue by month").result.to_dict("records") == [
        {"month": "2026-01", "revenue": 144.0},
        {"month": "2026-02", "revenue": 117.0},
        {"month": "2026-03", "revenue": 91.0},
    ]
    assert analyze_sales(frame, "Units sold by product").result.to_dict("records") == [
        {"product": "Coffee Beans", "units": 12.0}, {"product": "Tea", "units": 10.0}, {"product": "Mug", "units": 6.0},
    ]
    assert analyze_sales(frame, "Summarize uploaded revenue by country").result.to_dict("records") == [
        {"country": "USA", "revenue": 256.0}, {"country": "Canada", "revenue": 74.0}, {"country": "Germany", "revenue": 22.0},
    ]
    pd.testing.assert_frame_equal(pd.read_csv(StringIO(products.result.to_csv(index=False))), products.result, check_dtype=False)
    assert products.currency == "USD"
    assert products.source_rows == 12


def test_money_is_summed_in_cents_and_negative_returns_are_visible():
    result = analyze_sales(pd.DataFrame({"revenue": ["0.10", "0.20", "-0.10"]}), "What is total revenue?")
    assert result.total_revenue == 0.2
    assert result.result.iloc[0, 0] == 0.2
    assert any("Negative" in warning for warning in result.warnings)


@pytest.mark.parametrize("question", ["Revenue by product for Canada", "Why did sales fall?", "Forecast next month", "Revenue by product and month", "Total profit"])
def test_unsupported_questions_do_not_silently_analyze_all_rows(question):
    with pytest.raises(CSVAnalysisError, match="supports"):
        analyze_sales(pd.DataFrame({"revenue": [100]}), question)


@pytest.mark.parametrize("value", [None, "not-a-number", float("inf"), float("nan"), "$100"])
def test_invalid_amounts_are_rejected_without_dropping_rows(value):
    with pytest.raises(CSVAnalysisError):
        analyze_sales(pd.DataFrame({"revenue": [10, value]}), "Total revenue")


def test_mixed_currencies_and_ambiguous_amount_columns_are_rejected():
    with pytest.raises(CSVAnalysisError, match="Mixed currencies"):
        analyze_sales(pd.DataFrame({"revenue": [10, 20], "currency": ["USD", "CAD"]}), "Total revenue")
    with pytest.raises(CSVAnalysisError, match="Several columns"):
        analyze_sales(pd.DataFrame({"revenue": [10], "total": [20]}), "Total revenue")


def test_invalid_dates_missing_dimensions_and_empty_files_are_actionable():
    with pytest.raises(CSVAnalysisError, match="YYYY-MM-DD"):
        analyze_sales(pd.DataFrame({"revenue": [10], "date": ["not-a-date"]}), "Revenue by month")
    with pytest.raises(CSVAnalysisError, match="product"):
        analyze_sales(pd.DataFrame({"revenue": [10]}), "Revenue by product")
    with pytest.raises(CSVAnalysisError):
        read_sales_csv(b"")


def test_non_default_dataframe_index_and_duplicates_are_preserved():
    frame = pd.DataFrame({"revenue": [10, 10, 5], "product": ["Tea", "Tea", "Mug"]}, index=[5, 6, 9])
    analysis = analyze_sales(frame, "Revenue by product")
    assert analysis.total_revenue == 25
    assert analysis.result.to_dict("records") == [{"product": "Tea", "revenue": 20.0}, {"product": "Mug", "revenue": 5.0}]
    assert any("duplicate" in warning for warning in analysis.warnings)


def test_csv_ingestion_preserves_product_codes_and_country_na():
    frame = read_sales_csv(b"product,country,revenue\n001,NA,10\n1,US,20\n")

    assert analyze_sales(frame, "Revenue by product").result.to_dict("records") == [
        {"product": "1", "revenue": 20.0}, {"product": "001", "revenue": 10.0},
    ]
    assert analyze_sales(frame, "Revenue by country").result.to_dict("records") == [
        {"country": "US", "revenue": 20.0}, {"country": "NA", "revenue": 10.0},
    ]


@pytest.mark.parametrize("header", ["product,revenue", "product,quantity,unit_price"])
def test_csv_money_reaches_decimal_without_float_rounding(header):
    values = "Tea,123456789.1549999999" if "quantity" not in header else "Tea,1,123456789.1549999999"
    frame = read_sales_csv(f"{header}\n{values}\n".encode())

    assert analyze_sales(frame, "Total revenue").total_revenue == 123456789.15


@pytest.mark.parametrize("header", [
    "product,revenue,revenue",
    "product, Revenue ,REVENUE",
    "product,sales amount,sales_amount",
])
def test_csv_rejects_original_duplicate_headers_before_pandas_renames_them(header):
    with pytest.raises(CSVAnalysisError, match="duplicate column"):
        read_sales_csv(f"{header}\nTea,10,999\n".encode())


def test_csv_keeps_exact_duplicates_and_distinct_numeric_looking_codes():
    frame = read_sales_csv(b"product,revenue\n001,10\n1,10\n001,10\n")
    analysis = analyze_sales(frame, "Revenue by product")

    assert analysis.source_rows == 3
    assert analysis.total_revenue == 30.0
    assert analysis.result.to_dict("records") == [
        {"product": "001", "revenue": 20.0}, {"product": "1", "revenue": 10.0},
    ]
    assert any("1 exact duplicate row(s)" in warning for warning in analysis.warnings)


def test_csv_utf8_bom_and_blank_lines_before_header_are_supported():
    frame = read_sales_csv("\ufeff\n\nproduct,revenue\nTea,0.10\n".encode("utf-8"))
    assert analyze_sales(frame, "Revenue by product").result.to_dict("records") == [{"product": "Tea", "revenue": 0.1}]


def test_csv_limits_count_all_accepted_rows_and_reject_truncation():
    content = b"revenue\n" + b"0.01\n" * (MAX_CSV_ROWS - 1) + b"1.01\n"
    analysis = analyze_sales(read_sales_csv(content), "Total revenue")
    assert analysis.source_rows == MAX_CSV_ROWS
    assert analysis.total_revenue == 501.0

    with pytest.raises(CSVAnalysisError, match="50,000 rows"):
        read_sales_csv(content + b"0.01\n")
    with pytest.raises(CSVAnalysisError, match="10 MB"):
        read_sales_csv(b" " * (MAX_CSV_BYTES + 1))
    with pytest.raises(CSVAnalysisError, match="100 columns"):
        read_sales_csv((",".join(f"column_{index}" for index in range(101)) + "\n" + ",".join("1" for _ in range(101))).encode())


@pytest.mark.parametrize("row", ["Tea,10,999", "Tea"])
def test_csv_rejects_rows_that_do_not_match_header_width(row):
    with pytest.raises(CSVAnalysisError, match="Make every row match the header"):
        read_sales_csv(f"product,revenue\n{row}\n".encode())


@pytest.mark.parametrize("currency", ["JPY", "KWD", "not-a-currency"])
def test_csv_rejects_currencies_outside_the_two_decimal_demo_contract(currency):
    frame = read_sales_csv(f"revenue,currency\n1.005,{currency}\n".encode())
    with pytest.raises(CSVAnalysisError, match="two decimal places") as error:
        analyze_sales(frame, "Total revenue")
    assert ", ".join(SUPPORTED_CURRENCIES) in str(error.value)


@pytest.mark.parametrize("currency", SUPPORTED_CURRENCIES)
def test_csv_supported_currencies_are_normalized_and_rounded_per_row(currency):
    frame = read_sales_csv(f"revenue,currency\n1.005, {currency.lower()} \n0.005,{currency}\n".encode())
    analysis = analyze_sales(frame, "Total revenue")
    assert analysis.currency == currency
    assert analysis.total_revenue == 1.02
    assert any("rounded to two decimal places" in warning for warning in analysis.warnings)
