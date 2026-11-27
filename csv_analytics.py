"""Deterministic sales calculations for the supported CSV demo questions.

Questions outside this explicit set are rejected rather than silently returning
unrelated rows. Calculations use the full upload and never call a model.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import StringIO
from pathlib import Path
import re

import pandas as pd


MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_CSV_ROWS = 50_000
SUPPORTED_CURRENCIES = ("USD", "CAD", "EUR", "GBP", "AUD", "NZD")
DEMO_PATH = Path(__file__).resolve().parent / "data" / "demo" / "retail_sales.csv"
SUPPORTED_QUESTIONS = (
    "Total revenue", "Revenue by product", "Revenue by month",
    "Revenue by country", "Units sold by product", "Sales summary",
)
ALIASES = {
    "revenue": {"revenue", "sales", "sales_amount", "line_total", "total"},
    "quantity": {"quantity", "qty", "units", "units_sold"},
    "unit_price": {"unit_price", "price"},
    "product": {"product", "product_name", "item", "item_name"},
    "country": {"country", "billing_country"},
    "date": {"date", "order_date", "sale_date", "invoice_date"},
    "currency": {"currency", "currency_code"},
}


class CSVAnalysisError(ValueError):
    """A data issue or unsupported question that the user can correct."""


@dataclass(frozen=True)
class SalesAnalysis:
    result: pd.DataFrame
    question: str
    summary: str
    source_rows: int
    total_revenue: float
    currency: str
    warnings: tuple[str, ...]


def read_sales_csv(content: bytes) -> pd.DataFrame:
    if len(content) > MAX_CSV_BYTES:
        raise CSVAnalysisError("Please upload a CSV smaller than 10 MB.")
    try:
        source = content.decode("utf-8-sig")
        # Inspect the original header before pandas silently renames duplicates.
        reader = csv.reader(StringIO(source), strict=True)
        header = next(
            (row for row in reader if row and (len(row) > 1 or row[0].strip())),
            [],
        )
        if len(header) > 100:
            raise CSVAnalysisError("This demo accepts up to 100 columns per CSV.")
        normalized_headers = [_normalize_column(column) for column in header]
        if len(set(normalized_headers)) != len(normalized_headers):
            raise CSVAnalysisError("The CSV contains duplicate column names. Give every column a unique name, ignoring capitalization and separators.")
        row_count = 0
        for row in reader:
            if not row or (len(row) == 1 and not row[0].strip()):
                continue
            row_count += 1
            if row_count > MAX_CSV_ROWS:
                raise CSVAnalysisError("This demo accepts up to 50,000 rows per CSV.")
            # Otherwise pandas can silently consume surplus fields as an index,
            # shifting values into different columns and changing the answer.
            if len(row) != len(header):
                raise CSVAnalysisError(f"The CSV row ending at line {reader.line_num} has {len(row)} fields; the header has {len(header)}. Make every row match the header.")
        # Inference can merge codes such as 001 and 1, treat NA as missing, and
        # round money through a float before Decimal receives the original value.
        frame = pd.read_csv(StringIO(source), dtype=str, keep_default_na=False, nrows=MAX_CSV_ROWS + 1)
    except (csv.Error, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise CSVAnalysisError("The file could not be read. Use a UTF-8 CSV with a header row.") from exc
    _validate_size(frame)
    return frame


def _validate_size(frame: pd.DataFrame) -> None:
    if frame.empty:
        raise CSVAnalysisError("The CSV has no sales rows.")
    if len(frame) > MAX_CSV_ROWS:
        raise CSVAnalysisError("This demo accepts up to 50,000 rows per CSV.")
    if len(frame.columns) > 100:
        raise CSVAnalysisError("This demo accepts up to 100 columns per CSV.")


def _normalize_column(column: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(column).strip().lower())


def _column(frame: pd.DataFrame, field: str, *, required: bool = False) -> str | None:
    matches = [column for column in frame.columns if _normalize_column(column) in ALIASES[field]]
    if len(matches) > 1:
        raise CSVAnalysisError(f"Several columns could mean {field}: {', '.join(map(str, matches))}. Keep one unambiguous column.")
    if not matches and required:
        raise CSVAnalysisError(f"This question needs a '{field}' column.")
    return matches[0] if matches else None


def _decimal(value: object, column: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CSVAnalysisError(f"Column '{column}' must contain numbers without currency symbols or blank cells.") from exc
    if not result.is_finite() or abs(result) > Decimal("1000000000"):
        raise CSVAnalysisError(f"Column '{column}' contains a missing, non-finite, or excessively large value.")
    return result


def _intent(question: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", question.lower())
    normalized = " ".join(normalized.split())
    normalized = re.sub(r"^(?:please )?(?:show me |show |calculate |summarize uploaded |summarise uploaded |what is (?:the )?)", "", normalized)
    aliases = {
        "total revenue": "total", "revenue": "total", "total sales": "total",
        "revenue by product": "product", "sales by product": "product",
        "top products by revenue": "product", "which products generated the most revenue": "product",
        "revenue by month": "month", "monthly revenue": "month", "monthly sales": "month",
        "revenue by country": "country", "sales by country": "country",
        "units sold by product": "units", "quantity by product": "units",
        "sales summary": "summary", "revenue summary": "summary",
    }
    if normalized not in aliases:
        raise CSVAnalysisError("This CSV demo supports: " + "; ".join(SUPPORTED_QUESTIONS) + ". Filters, forecasts, and causal questions are not supported yet.")
    return aliases[normalized]


def analyze_sales(frame: pd.DataFrame, question: str) -> SalesAnalysis:
    """Calculate one supported sales answer; retain returns and duplicate rows."""
    _validate_size(frame)
    intent = _intent(question)
    revenue_column = _column(frame, "revenue")
    quantity_column = _column(frame, "quantity")
    price_column = _column(frame, "unit_price")
    currency_column = _column(frame, "currency")
    currency = "CSV currency"
    if currency_column:
        if frame[currency_column].isna().any() or frame[currency_column].astype(str).str.strip().eq("").any():
            raise CSVAnalysisError("Every sales row must specify a currency when a currency column is supplied.")
        currencies = frame[currency_column].astype(str).str.strip().str.upper().unique()
        if len(currencies) != 1:
            raise CSVAnalysisError("Mixed currencies cannot be added. Upload one currency at a time.")
        currency = str(currencies[0])
        if currency not in SUPPORTED_CURRENCIES:
            raise CSVAnalysisError(
                "This demo rounds money to two decimal places and supports these currency codes: "
                + ", ".join(SUPPORTED_CURRENCIES)
                + ". Use a file in a supported currency; currency conversion is not available."
            )
    quantities = [_decimal(value, str(quantity_column)) for value in frame[quantity_column]] if quantity_column else None
    if revenue_column:
        amounts = [_decimal(value, str(revenue_column)) for value in frame[revenue_column]]
        calculation = f"Sum of '{revenue_column}' across all uploaded rows."
    elif quantities is not None and price_column:
        prices = [_decimal(value, str(price_column)) for value in frame[price_column]]
        amounts = [quantity * price for quantity, price in zip(quantities, prices)]
        calculation = f"Revenue calculated as '{quantity_column}' × '{price_column}' for each row."
    else:
        raise CSVAnalysisError("Add a 'revenue' column, or both 'quantity' and 'unit_price' columns.")
    if any(abs(amount) > Decimal("1000000000") for amount in amounts):
        raise CSVAnalysisError("A sales amount exceeds the supported range.")
    cents = [int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) for amount in amounts]
    total_cents = sum(cents)
    work = pd.DataFrame({"revenue_cents": cents})
    warnings = []
    duplicates = int(frame.duplicated().sum())
    if duplicates:
        warnings.append(f"{duplicates} exact duplicate row(s) were retained; confirm that they represent separate sales.")
    if any(amount < 0 for amount in amounts):
        warnings.append("Negative amounts are included in the total; confirm how your export represents returns.")
    if any(amount * 100 != Decimal(value) for amount, value in zip(amounts, cents)):
        warnings.append("Each row was rounded to two decimal places before summing.")
    if not currency_column:
        warnings.append("No currency column supplied. Confirm that all rows use the same currency.")

    if intent in {"product", "country", "units"}:
        dimension = "product" if intent in {"product", "units"} else "country"
        column = _column(frame, dimension, required=True)
        labels = frame[column].reset_index(drop=True).astype("string").str.strip()
        if labels.isna().any() or labels.eq("").any():
            raise CSVAnalysisError(f"Column '{column}' contains blank labels; fill them before grouping.")
        work[dimension] = labels
        if intent == "units":
            if quantities is None:
                raise CSVAnalysisError("Units sold by product needs a 'quantity' column.")
            work["units"] = quantities
            result = work.groupby(dimension, as_index=False, sort=True)["units"].sum().sort_values("units", ascending=False, kind="stable").reset_index(drop=True)
            result["units"] = result["units"].map(float)
        else:
            result = work.groupby(dimension, as_index=False, sort=True)["revenue_cents"].sum().sort_values("revenue_cents", ascending=False, kind="stable").reset_index(drop=True)
            result["revenue"] = result.pop("revenue_cents") / 100
    elif intent == "month":
        column = _column(frame, "date", required=True)
        dates = pd.to_datetime(frame[column], format="%Y-%m-%d", errors="coerce")
        if dates.isna().any():
            raise CSVAnalysisError(f"Column '{column}' must contain valid dates in YYYY-MM-DD format.")
        work["month"] = dates.dt.strftime("%Y-%m").to_numpy()
        result = work.groupby("month", as_index=False, sort=True)["revenue_cents"].sum()
        result["revenue"] = result.pop("revenue_cents") / 100
    elif intent == "total":
        result = pd.DataFrame({"revenue": [total_cents / 100]})
    else:
        result = pd.DataFrame({"revenue": [total_cents / 100], "sales_rows": [len(frame)]})
        if quantities is not None:
            result["units"] = [float(sum(quantities))]

    summary = f"Analyzed all {len(frame):,} uploaded sales rows. Total revenue: {total_cents / 100:,.2f} {currency}. {calculation}"
    if intent in {"product", "country", "units"}:
        measure = "units" if intent == "units" else "revenue"
        dimension = result.columns[0]
        lead = result.iloc[0]
        summary += f" Highest {measure}: {lead[dimension]} ({lead[measure]:,.2f})."
    elif intent == "month":
        summary += f" Monthly totals cover {result['month'].iloc[0]} through {result['month'].iloc[-1]}; missing months are not assumed to be zero."
    summary += " These are calculated results, not AI predictions."
    return SalesAnalysis(result, question, summary, len(frame), total_cents / 100, currency, tuple(warnings))
