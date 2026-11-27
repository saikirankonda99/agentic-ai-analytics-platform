"""Review explicit CSV field mappings before replacing the active sales dataset."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from decimal import DecimalException
import re

import pandas as pd

from csv_analytics import (
    ALIASES,
    CSVAnalysisError,
    SUPPORTED_CURRENCIES,
    SUPPORTED_QUESTIONS,
    SalesAnalysis,
    _decimal,
    _normalize_column,
    _validate_size,
    analyze_sales,
)


MAPPING_FIELDS = ("revenue", "quantity", "unit_price", "product", "date", "country", "currency")
DATE_FORMATS = {"YYYY-MM-DD": "%Y-%m-%d", "MM/DD/YYYY": "%m/%d/%Y", "DD/MM/YYYY": "%d/%m/%Y"}
_DATE_PATTERNS = {
    "YYYY-MM-DD": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
    "MM/DD/YYYY": re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4}"),
    "DD/MM/YYYY": re.compile(r"[0-9]{2}/[0-9]{2}/[0-9]{4}"),
}
_SOURCE_RECORD_COLUMN = "__import_source_record_id"


@dataclass(frozen=True)
class SalesImportReview:
    frame: pd.DataFrame | None
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    analysis: SalesAnalysis | None
    available_questions: tuple[str, ...]


def suggest_sales_mapping(frame: pd.DataFrame) -> dict[str, str | None]:
    """Suggest only a single exact normalized alias; leave ambiguity to the user."""
    suggestions = {}
    for field in MAPPING_FIELDS:
        matches = [column for column in frame.columns if _normalize_column(column) in ALIASES[field]]
        suggestions[field] = matches[0] if len(matches) == 1 else None
    return suggestions


def _row_numbers(rows: list[int]) -> str:
    shown = ", ".join(str(row) for row in rows[:8])
    return shown + (f" (and {len(rows) - 8} more)" if len(rows) > 8 else "")


def _failed(errors: list[str], warnings: list[str] | None = None) -> SalesImportReview:
    return SalesImportReview(None, tuple(errors), tuple(warnings or ()), None, ())


def _available_questions(frame: pd.DataFrame) -> tuple[str, ...]:
    required = {
        "Total revenue": (),
        "Revenue by product": ("product",),
        "Revenue by month": ("date",),
        "Revenue by country": ("country",),
        "Units sold by product": ("product", "quantity"),
        "Sales summary": (),
    }
    return tuple(question for question in SUPPORTED_QUESTIONS if all(field in frame for field in required[question]))


def validate_sales_import(
    frame: pd.DataFrame,
    mapping: Mapping[str, str | None],
    *,
    revenue_mode: str = "column",
    date_format: str = "YYYY-MM-DD",
    default_currency: str | None = "USD",
) -> SalesImportReview:
    """Validate every selected field and return an all-or-nothing import review.

    Error row numbers count data rows from 1, excluding the CSV header. Numeric
    and label values remain unchanged; dates alone are converted to ISO format.
    An internal, non-alias column preserves exact raw-row identity for duplicate
    detection after unmapped fields are removed. It is not a business measure.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(frame, pd.DataFrame):
        return _failed(["Choose a readable CSV before mapping its columns."])
    try:
        _validate_size(frame)
    except CSVAnalysisError as exc:
        return _failed([str(exc)])
    if not frame.columns.is_unique:
        return _failed(["The source has duplicate column names. Rename them before choosing a mapping."])
    if not isinstance(mapping, Mapping):
        return _failed(["Provide a field-to-column mapping before applying this import."])
    if revenue_mode not in {"column", "quantity_price"}:
        errors.append("Choose revenue mode 'column' or 'quantity_price'.")
    if date_format not in DATE_FORMATS:
        errors.append("Choose a supported date format: " + ", ".join(DATE_FORMATS) + ".")
    for field, source in mapping.items():
        if field not in MAPPING_FIELDS:
            errors.append(f"Unknown sales field '{field}'. Choose one of: {', '.join(MAPPING_FIELDS)}.")
        elif source is not None and (not isinstance(source, str) or source not in frame.columns):
            errors.append(f"Mapped source column '{source}' for '{field}' does not exist in this CSV.")
    if errors:
        return _failed(errors)

    ignored_field = "unit_price" if revenue_mode == "column" else "revenue"
    selected = {
        field: mapping.get(field)
        for field in MAPPING_FIELDS
        if field != ignored_field and mapping.get(field) is not None
    }
    required = ("revenue",) if revenue_mode == "column" else ("quantity", "unit_price")
    for field in required:
        if field not in selected:
            errors.append(f"Map a '{field}' column for the selected revenue mode.")
    assigned: dict[str, str] = {}
    for field, source in selected.items():
        if source in assigned:
            errors.append(f"Source column '{source}' is mapped to both '{assigned[source]}' and '{field}'. Choose different source columns.")
        assigned[source] = field
    if errors:
        return _failed(errors)
    if mapping.get(ignored_field) is not None:
        warnings.append(f"The '{ignored_field}' mapping is ignored in '{revenue_mode}' revenue mode.")

    prepared = pd.DataFrame(index=frame.index)
    for field, source in selected.items():
        prepared[field] = frame[source].copy(deep=True)
        label = f"{field.replace('_', ' ').capitalize()} ('{source}')"
        if field in {"revenue", "quantity", "unit_price"}:
            invalid_rows = []
            for row, value in enumerate(frame[source], start=1):
                try:
                    _decimal(value, source)
                except (CSVAnalysisError, DecimalException, OverflowError):
                    invalid_rows.append(row)
            if invalid_rows:
                errors.append(f"{label} has invalid numbers at data rows: {_row_numbers(invalid_rows)}. Use plain finite numbers without currency symbols or blank cells, within the supported range of -1,000,000,000 to 1,000,000,000.")
        elif field in {"product", "country"}:
            invalid = frame[source].isna() | frame[source].astype(str).str.strip().eq("")
            invalid_rows = [row for row, missing in enumerate(invalid, start=1) if missing]
            if invalid_rows:
                errors.append(f"{label} has blank labels at data rows: {_row_numbers(invalid_rows)}. Fill these cells or leave this optional field unmapped.")
        elif field == "date":
            values = frame[source].astype("string")
            exact_format = values.str.fullmatch(_DATE_PATTERNS[date_format], na=False)
            dates = pd.to_datetime(values, format=DATE_FORMATS[date_format], errors="coerce")
            invalid_rows = [row for row, valid in enumerate(exact_format & dates.notna(), start=1) if not valid]
            if invalid_rows:
                errors.append(f"{label} has invalid dates at data rows: {_row_numbers(invalid_rows)}. Use valid dates exactly in {date_format} format, or select the format used by the file.")
            else:
                prepared[field] = dates.dt.strftime("%Y-%m-%d").to_numpy()
        elif field == "currency":
            currencies = frame[source].astype("string").str.strip().str.upper()
            valid_currency = currencies.isin(SUPPORTED_CURRENCIES)
            invalid_rows = [row for row, valid in enumerate(valid_currency, start=1) if not valid]
            if invalid_rows:
                errors.append(f"{label} has missing or unsupported currency codes at data rows: {_row_numbers(invalid_rows)}. Use one of: {', '.join(SUPPORTED_CURRENCIES)}. A default currency does not replace mapped blank cells.")
            distinct = list(currencies[valid_currency].unique())
            if len(distinct) > 1:
                errors.append(f"{label} contains mixed currencies ({', '.join(distinct)}). Import one currency at a time; currency conversion is not available.")

    if "currency" not in selected and default_currency is not None:
        currency = str(default_currency).strip().upper()
        if currency not in SUPPORTED_CURRENCIES:
            errors.append("Choose a supported default currency: " + ", ".join(SUPPORTED_CURRENCIES) + ", or leave it unspecified.")
        else:
            prepared["currency"] = currency
            warnings.append(f"No currency column is mapped; {currency} is assumed for every row. Confirm that this matches your file.")
    if errors:
        return _failed(errors, warnings)

    # Equal codes represent equal original rows, including IDs and unused values.
    # Unlike a unique row number, these codes retain genuine duplicate warnings.
    # Unlike copying every source column, they cannot reintroduce amount aliases
    # or push a valid 100-column upload beyond the analysis column limit.
    record_codes, _ = pd.factorize(pd.MultiIndex.from_frame(frame), sort=False)
    prepared[_SOURCE_RECORD_COLUMN] = [f"source-{code}" for code in record_codes]
    try:
        analysis = analyze_sales(prepared, "Sales summary")
    except (CSVAnalysisError, DecimalException, OverflowError) as exc:
        return _failed([f"The mapped sales data could not be calculated: {exc}"], warnings)
    combined_warnings = tuple(dict.fromkeys([*warnings, *analysis.warnings]))
    return SalesImportReview(
        prepared,
        (),
        combined_warnings,
        replace(analysis, warnings=combined_warnings),
        _available_questions(prepared),
    )
