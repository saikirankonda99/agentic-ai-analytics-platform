from __future__ import annotations

import pandas as pd
import streamlit as st

from csv_analytics import SUPPORTED_CURRENCIES
from csv_import import DATE_FORMATS, MAPPING_FIELDS, SalesImportReview, suggest_sales_mapping, validate_sales_import


def _open_overview() -> None:
    st.session_state.top_navigation = "Overview"
    st.session_state.workspace_route = "Overview"


def _request_cancel() -> None:
    _open_overview()
    st.session_state.csv_import_cancel_requested = True


def _select_column(
    label: str,
    field: str,
    columns: list[str],
    suggestions: dict[str, str | None],
    key_prefix: str,
    *,
    help_text: str,
) -> str | None:
    options = [None, *columns]
    suggested = suggestions.get(field)
    return st.selectbox(
        label,
        options,
        index=options.index(suggested) if suggested in options else 0,
        format_func=lambda value: "Not selected" if value is None else str(value),
        key=f"{key_prefix}{field}",
        help=help_text,
    )


def render_sales_import_review(
    raw_frame: pd.DataFrame,
    filename: str,
    import_key: str,
) -> SalesImportReview | None:
    """Preview and validate a pending upload; return data only after explicit use."""
    if st.session_state.get("csv_import_cancel_requested"):
        return None

    key_prefix = f"csv_import_{import_key}_"
    columns = list(raw_frame.columns)
    suggestions = suggest_sales_mapping(raw_frame)
    mapping = {field: None for field in MAPPING_FIELDS}

    st.markdown(
        """
        <div class="workspace-shell compact-shell" data-testid="csv-import-review">
            <div class="section-title">Review your sales file</div>
            <div class="section-subtitle">Match your columns and check the data before using it for analysis.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"File: {filename} · {len(raw_frame):,} sales rows · {len(columns):,} columns")
    st.dataframe(raw_frame.head(10), width="stretch", height=290, hide_index=True)
    st.caption("Preview shows up to the first 10 rows. Validation and calculations use every uploaded row.")

    st.markdown("#### Match your columns")
    st.caption("Recognized column names are suggested. Choose the matching columns for this file.")
    revenue_choice = st.radio(
        "Calculate revenue from",
        ["Revenue column", "Quantity × unit price"],
        index=0 if suggestions.get("revenue") else 1,
        horizontal=True,
        key=f"{key_prefix}revenue_mode",
    )
    revenue_mode = "column" if revenue_choice == "Revenue column" else "quantity_price"
    money_left, money_right = st.columns(2, gap="small")
    if revenue_mode == "column":
        with money_left:
            mapping["revenue"] = _select_column(
                "Revenue column", "revenue", columns, suggestions, key_prefix,
                help_text="Required. Select the total sales amount for each row, such as a line total.",
            )
        with money_right:
            mapping["quantity"] = _select_column(
                "Quantity column", "quantity", columns, suggestions, key_prefix,
                help_text="Optional. Select units sold to enable units-by-product questions.",
            )
    else:
        with money_left:
            mapping["quantity"] = _select_column(
                "Quantity column", "quantity", columns, suggestions, key_prefix,
                help_text="Required. Select the units sold on each row.",
            )
        with money_right:
            mapping["unit_price"] = _select_column(
                "Unit price column", "unit_price", columns, suggestions, key_prefix,
                help_text="Required. Select the price of one unit. Revenue is quantity multiplied by unit price.",
            )
    st.caption("Amounts are used as supplied. Tax, discounts, and shipping are not adjusted.")

    product_col, date_col = st.columns(2, gap="small")
    with product_col:
        mapping["product"] = _select_column(
            "Product column", "product", columns, suggestions, key_prefix,
            help_text="Optional. Select a product name or code to compare products.",
        )
    with date_col:
        mapping["date"] = _select_column(
            "Date column", "date", columns, suggestions, key_prefix,
            help_text="Optional. Select the sale date to calculate monthly revenue.",
        )
    country_col, currency_col = st.columns(2, gap="small")
    with country_col:
        mapping["country"] = _select_column(
            "Country column", "country", columns, suggestions, key_prefix,
            help_text="Optional. Select the country to compare sales by country.",
        )
    with currency_col:
        mapping["currency"] = _select_column(
            "Currency column", "currency", columns, suggestions, key_prefix,
            help_text="Optional. A currency column must contain one supported currency across all rows.",
        )

    date_format = "YYYY-MM-DD"
    default_currency = None
    if mapping["date"] is not None or mapping["currency"] is None:
        date_settings, currency_settings = st.columns(2, gap="small")
        if mapping["date"] is not None:
            with date_settings:
                date_format = st.selectbox(
                    "Date format",
                    list(DATE_FORMATS),
                    key=f"{key_prefix}date_format",
                    help="Choose the format used by every date in the selected column. Dates are not guessed.",
                )
        if mapping["currency"] is None:
            with currency_settings:
                default_currency = st.selectbox(
                    "Currency for all rows",
                    list(SUPPORTED_CURRENCIES),
                    key=f"{key_prefix}default_currency",
                    help="Applied to every row when no currency column is selected. Currency conversion is not available.",
                )

    review = validate_sales_import(
        raw_frame,
        mapping,
        revenue_mode=revenue_mode,
        date_format=date_format,
        default_currency=default_currency,
    )
    st.markdown("#### Data checks")
    if review.errors:
        st.error("Fix the issues below before using this file.")
        for error in review.errors:
            st.error(error)
        st.caption("Data-row numbers start at 1 after the header. Correct the file and upload it again, or change the selected columns.")
    for warning in review.warnings:
        st.warning(warning)

    ready = not review.errors and review.frame is not None and review.analysis is not None
    if ready:
        st.success(f"All {review.analysis.source_rows:,} rows passed the required checks.")
        row_metric, revenue_metric = st.columns(2, gap="small")
        row_metric.metric("Sales rows", f"{review.analysis.source_rows:,}")
        revenue_metric.metric("Total revenue", f"{review.analysis.total_revenue:,.2f} {review.analysis.currency}")
        st.caption("Available questions: " + "; ".join(review.available_questions) + ".")

    use_col, cancel_col = st.columns(2, gap="small")
    use_data = use_col.button(
        "Use this data",
        disabled=not ready,
        width="stretch",
        key=f"{key_prefix}apply",
        on_click=_open_overview,
    )
    cancel_col.button(
        "Cancel upload",
        width="stretch",
        key=f"{key_prefix}cancel",
        on_click=_request_cancel,
    )
    return review if use_data and ready else None
