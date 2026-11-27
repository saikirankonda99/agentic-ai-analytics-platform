"""Opt-in AI prioritisation of verified sales facts, with local rendering.

The model receives a small aggregate fact catalogue and chooses what to highlight.
It cannot change calculations, execute code, invent numbers, or supply factual prose.
Raw transactions, category labels, uploaded headers and file names stay local.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import math
from typing import Any, Mapping

import pandas as pd

from csv_analytics import SalesAnalysis, SUPPORTED_CURRENCIES
from llm import DEFAULT_SQL_MODEL, get_openai_api_key, stream_text_with_telemetry


FOCUS_OPTIONS = ("overview", "products", "trend", "data_quality")
AI_DATA_DISCLOSURE = (
    "AI receives calculated totals, counts and anonymous group statistics. "
    "Your raw rows, product names and file name stay in this app. "
    "The model chooses which verified facts and next checks to highlight."
)
BASE_LIMITATIONS = [
    "This review describes the uploaded data; it does not establish why sales changed.",
    "Profit, forecasts and automatic business actions are not included.",
]
_ACTIONS = {
    "reconcile": "Compare the total with your original sales report before making a decision.",
    "product_check": "Review stock availability for the leading product before changing purchasing.",
    "country_check": "Review the country breakdown alongside your business costs before changing your focus.",
    "period_check": "Check that each month contains the same reporting coverage before comparing performance.",
    "returns_check": "Check that negative amounts represent the returns or adjustments you expect.",
    "duplicate_check": "Confirm that repeated rows are separate sales before removing any of them.",
    "currency_check": "Confirm that all sales use the same currency.",
    "cost_check": "Add product costs to a separate review if you need to understand profit.",
    "volume_check": "Review the units sold alongside revenue before deciding which products to prioritise.",
}
_HEADLINES = {
    "overview": "A closer look at your sales",
    "concentration": "Where your sales are concentrated",
    "monthly": "What your recorded months show",
    "quality": "Checks to make before acting",
    "volume": "What your sales volumes show",
}


@dataclass(frozen=True)
class _Fact:
    key: str
    text: str
    aggregate: dict[str, Any]


def _reply(status: str, headline: str, *, limitations: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "ai_used": False,
        "headline": headline,
        "findings": [],
        "next_steps": [],
        "limitations": limitations or [],
        "model": None,
        "telemetry": {},
    }


def _number(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("A boolean is not a sales amount.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Sales amounts must be numeric.") from exc
    if not math.isfinite(number):
        raise ValueError("Sales amounts must be finite.")
    return number


def _money(value: Any) -> str:
    return f"{_number(value):,.2f}"


def _local_label(value: Any) -> str:
    # Labels are used only when rendering local verified facts, never in a prompt.
    return " ".join(str(value).split())[:160]


def _catalogue(
    analysis: SalesAnalysis | Mapping[str, Any], result: pd.DataFrame | None,
) -> tuple[list[_Fact], list[str], list[str], list[str]]:
    if isinstance(analysis, SalesAnalysis):
        result = analysis.result
        metadata = {
            "source_rows": analysis.source_rows,
            "total_revenue": analysis.total_revenue,
            "currency": analysis.currency,
            "warnings": analysis.warnings,
        }
    else:
        metadata = dict(analysis)
    if not isinstance(result, pd.DataFrame) or result.empty:
        raise ValueError("A calculated result is required.")
    currency = metadata.get("currency")
    if currency not in (*SUPPORTED_CURRENCIES, "CSV currency"):
        raise ValueError("The currency is not supported.")
    source_rows = metadata.get("source_rows")
    if isinstance(source_rows, bool) or not isinstance(source_rows, int) or not 0 < source_rows <= 50_000:
        raise ValueError("The source row count is invalid.")
    total = _number(metadata.get("total_revenue"))
    columns = set(result.columns)
    permitted = [
        {"revenue"}, {"revenue", "sales_rows"}, {"revenue", "sales_rows", "units"},
        {"product", "revenue"}, {"country", "revenue"}, {"month", "revenue"}, {"product", "units"},
    ]
    if columns not in permitted or len(result.columns) != len(columns):
        raise ValueError("The result is not a supported sales calculation.")
    if "revenue" in result:
        amounts = [_number(value) for value in result["revenue"]]
        # The source engine sums exact cents; tolerate only float representation noise.
        rounded_sum = sum(Decimal(str(value)).quantize(Decimal("0.01")) for value in amounts)
        if abs(rounded_sum - Decimal(str(total))) > Decimal("0.000001"):
            raise ValueError("The result does not reconcile with the calculated total.")
    facts = [
        _Fact("total_revenue", f"The uploaded sales total is {_money(total)} {currency}.",
              {"measure": "total_revenue", "value": total, "currency": currency}),
        _Fact("source_rows", f"The calculation includes all {source_rows:,} uploaded sales rows.",
              {"measure": "source_row_count", "value": source_rows}),
    ]
    actions = ["reconcile", "cost_check"]
    headlines = ["overview", "quality"]
    limitations = list(BASE_LIMITATIONS)
    for dimension in ("product", "country"):
        if dimension not in result:
            continue
        measure = "units" if "units" in result else "revenue"
        values = [_number(value) for value in result[measure]]
        largest_index = max(range(len(values)), key=lambda index: values[index])
        leading = result.iloc[largest_index]
        value = values[largest_index]
        tied = sum(item == value for item in values) > 1
        leader_text = "Joint highest" if tied else "Highest"
        unit = currency if measure == "revenue" else "units"
        facts.append(_Fact(
            "leading_group",
            f"{leader_text} {measure} in this breakdown: {_local_label(leading[dimension])} "
            f"({_money(value)} {unit}).",
            {"measure": f"highest_{dimension}_{measure}", "value": value, "tied": tied,
             "group_count": len(values), "unit": unit},
        ))
        if measure == "revenue" and total > 0 and all(item >= 0 for item in values):
            share = round(value / total * 100, 1)
            facts.append(_Fact(
                "leading_share",
                f"That leading {dimension} accounts for {share:.1f}% of the uploaded revenue.",
                {"measure": f"highest_{dimension}_share_percent", "value": share},
            ))
        actions.append("product_check" if dimension == "product" else "country_check")
        headlines.append("concentration" if measure == "revenue" else "volume")
        if measure == "units":
            actions.append("volume_check")
    if "month" in result:
        dates = pd.to_datetime(result["month"], format="%Y-%m", errors="coerce")
        if dates.isna().any() or result["month"].duplicated().any():
            raise ValueError("The month breakdown is invalid.")
        values = [_number(value) for value in result["revenue"]]
        largest_index = max(range(len(values)), key=lambda index: values[index])
        leading = result.iloc[largest_index]
        tied = sum(value == values[largest_index] for value in values) > 1
        facts.append(_Fact(
            "recorded_months", f"The upload contains sales in {len(result):,} distinct month(s).",
            {"measure": "recorded_month_count", "value": len(result)},
        ))
        facts.append(_Fact(
            "highest_month",
            f"{'Joint highest' if tied else 'Highest'} recorded monthly total: "
            f"{_local_label(leading['month'])} ({_money(leading['revenue'])} {currency}).",
            {"measure": "highest_recorded_month_revenue", "value": values[largest_index], "tied": tied,
             "currency": currency},
        ))
        actions.append("period_check")
        headlines.append("monthly")
        limitations.append("Months may be incomplete; missing months are not assumed to have zero sales.")
    warning_text = " ".join(str(item) for item in metadata.get("warnings", ()))
    for marker, key, text, action in (
        ("Negative amounts", "negative_amounts", "Negative amounts are included in the total.", "returns_check"),
        ("exact duplicate", "duplicates", "Exact duplicate rows were retained in the calculation.", "duplicate_check"),
        ("No currency column", "currency_assumed", "The calculation assumes that all rows use one currency.", "currency_check"),
    ):
        if marker in warning_text:
            facts.append(_Fact(key, text, {"check": key, "flagged": True}))
            actions.append(action)
    return facts, actions, headlines, limitations


def explain_sales_report(
    analysis: SalesAnalysis | Mapping[str, Any], result: pd.DataFrame | None = None,
    *, focus: str = "overview", enabled: bool = False,
) -> dict[str, Any]:
    """Ask AI to prioritise verified findings after an explicit UI action.

    No credentials means no model call. A successful reply means a model actually
    returned a validated selection, not simply that a key exists. All visible
    factual sentences and actions come from the verified local catalogue.
    """
    if not enabled:
        return _reply("disabled", "AI review has not been requested.")
    if focus not in FOCUS_OPTIONS:
        return _reply("unsupported", "Choose an available review focus.")
    try:
        facts, actions, headlines, limitations = _catalogue(analysis, result)
    except (ValueError, TypeError, KeyError, InvalidOperation):
        return _reply("unsupported", "Calculate a supported sales report before asking for an AI review.")
    if not get_openai_api_key():
        return _reply("not_connected", "AI is not connected yet.", limitations=[
            "Your calculated report is still available. An administrator can connect the AI service in server settings.",
        ])
    payload = {
        "review_focus": focus,
        "facts": [{"id": fact.key, **fact.aggregate} for fact in facts],
        "allowed_headlines": headlines,
        "allowed_actions": {key: _ACTIONS[key] for key in actions},
    }
    prompt = (
        "You help a small-business owner prioritise a verified sales review. "
        "The anonymous aggregate facts below were calculated by trusted code. "
        "Choose the most useful facts and practical next checks for the review focus. "
        "Never infer causes, profit, forecasts, period completeness or guaranteed business outcomes. "
        "Return ONLY a JSON object with exactly these keys: headline, fact_ids, action_ids. "
        "headline must be one allowed headline. fact_ids must be 2 to 4 distinct existing fact IDs. "
        "action_ids must be 1 to 3 distinct allowed action IDs. "
        "If you select leading_share, also select leading_group first. "
        "If recorded-month facts are available and selected, include period_check. "
        "Prefer data-quality checks when their flags are present. "
        "Do not include prose, labels, numbers, SQL or code in your response.\n"
        + json.dumps(payload, ensure_ascii=True, allow_nan=False)
    )
    try:
        response = stream_text_with_telemetry(prompt, model=DEFAULT_SQL_MODEL, temperature=0)
        telemetry = response.get("telemetry") or {}
        if telemetry.get("error_type") or not isinstance(response.get("text"), str):
            raise ValueError("The model request failed.")
        raw = response["text"].strip()
        if len(raw) > 4000:
            raise ValueError("The model response is too long.")
        selection = json.loads(raw)
        if not isinstance(selection, dict) or set(selection) != {"headline", "fact_ids", "action_ids"}:
            raise ValueError("The model response schema is invalid.")
        fact_ids, action_ids = selection["fact_ids"], selection["action_ids"]
        by_id = {fact.key: fact for fact in facts}
        for choices, minimum, maximum, allowed in (
            (fact_ids, 2, 4, by_id), (action_ids, 1, 3, actions),
        ):
            if not isinstance(choices, list) or not minimum <= len(choices) <= maximum:
                raise ValueError("The model selection length is invalid.")
            if any(not isinstance(choice, str) or choice not in allowed for choice in choices):
                raise ValueError("The model selected an unverified item.")
            if len(set(choices)) != len(choices):
                raise ValueError("The model selected duplicate items.")
        if not isinstance(selection["headline"], str) or selection["headline"] not in headlines:
            raise ValueError("The model selected an unsupported headline.")
        if "leading_share" in fact_ids and (
            "leading_group" not in fact_ids or fact_ids.index("leading_group") > fact_ids.index("leading_share")
        ):
            raise ValueError("A share requires its group context.")
        if {"recorded_months", "highest_month"}.intersection(fact_ids) and "period_check" not in action_ids:
            raise ValueError("A month observation requires a completeness check.")
    except Exception:
        # Never display raw provider errors, partial generated text or a fabricated AI answer.
        return _reply("unavailable", "The AI review could not be verified.", limitations=[
            "Your calculated report is unchanged. Try the AI review again later.",
        ])
    return {
        "status": "success",
        "ai_used": True,
        "headline": _HEADLINES[selection["headline"]],
        "findings": [by_id[key].text for key in fact_ids],
        "next_steps": [_ACTIONS[key] for key in action_ids],
        "limitations": limitations,
        "model": telemetry.get("model") or DEFAULT_SQL_MODEL,
        "telemetry": {
            key: telemetry[key] for key in ("model", "latency_ms", "usage_available", "total_tokens", "cost_usd")
            if key in telemetry
        },
    }
