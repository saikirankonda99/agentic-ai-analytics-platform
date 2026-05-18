from __future__ import annotations

from typing import Any

import pandas as pd


SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def empty_insight_state() -> dict[str, Any]:
    return {
        "findings": [],
        "severity": "info",
        "summary": "No autonomous insight scan has run yet.",
    }


def _severity(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "info"
    return max((item.get("severity", "info") for item in findings), key=lambda value: SEVERITY_RANK.get(value, 0))


def _format_value(value: Any) -> str:
    if pd.isna(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _numeric_columns(df: pd.DataFrame) -> list[str]:
    return [str(column) for column in df.columns if pd.api.types.is_numeric_dtype(df[column])]


def _time_columns(df: pd.DataFrame) -> list[str]:
    candidates = []
    for column in df.columns:
        series = df[column]
        name = str(column).lower()
        if pd.api.types.is_datetime64_any_dtype(series) or any(token in name for token in ("date", "time", "year", "month")):
            candidates.append(str(column))
    return candidates


def _categorical_columns(df: pd.DataFrame) -> list[str]:
    columns = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series) or series.nunique(dropna=True) <= 24:
            columns.append(str(column))
    return columns


def _add_trend_findings(df: pd.DataFrame, findings: list[dict[str, Any]]) -> None:
    time_columns = _time_columns(df)
    numeric_columns = _numeric_columns(df)
    if not time_columns or not numeric_columns or len(df) < 3:
        return

    time_col = time_columns[0]
    metric = numeric_columns[0]
    trend_df = df[[time_col, metric]].copy()
    trend_df[time_col] = pd.to_datetime(trend_df[time_col], errors="coerce")
    trend_df[metric] = pd.to_numeric(trend_df[metric], errors="coerce")
    trend_df = trend_df.dropna().sort_values(time_col)
    if len(trend_df) < 3:
        return

    first_value = float(trend_df[metric].iloc[0])
    last_value = float(trend_df[metric].iloc[-1])
    if first_value != 0:
        change_pct = ((last_value - first_value) / abs(first_value)) * 100
        if abs(change_pct) >= 15:
            direction = "upward trend" if change_pct > 0 else "downward trend"
            findings.append(
                {
                    "type": "trend",
                    "severity": "warning" if abs(change_pct) >= 35 else "info",
                    "title": f"{metric} shows a {direction}",
                    "detail": f"{metric} changed {change_pct:,.1f}% from {_format_value(first_value)} to {_format_value(last_value)} across {time_col}.",
                    "metric": metric,
                    "dimension": time_col,
                }
            )

    changes = trend_df[metric].pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
    if changes.empty:
        return
    largest_move = changes.abs().idxmax()
    change_pct = float(changes.loc[largest_move] * 100)
    if abs(change_pct) >= 25:
        movement = "spike" if change_pct > 0 else "drop"
        findings.append(
            {
                "type": movement,
                "severity": "critical" if abs(change_pct) >= 60 else "warning",
                "title": f"{metric} has a notable {movement}",
                "detail": f"The largest period change is {change_pct:,.1f}% near {_format_value(trend_df.loc[largest_move, time_col])}.",
                "metric": metric,
                "dimension": time_col,
            }
        )


def _add_outlier_findings(df: pd.DataFrame, findings: list[dict[str, Any]]) -> None:
    for metric in _numeric_columns(df)[:4]:
        series = pd.to_numeric(df[metric], errors="coerce").dropna()
        if len(series) < 6:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        high_threshold = q3 + 1.5 * iqr
        low_threshold = q1 - 1.5 * iqr
        outliers = series[(series > high_threshold) | (series < low_threshold)]
        if outliers.empty:
            continue
        extreme_value = outliers.iloc[outliers.abs().argmax()]
        findings.append(
            {
                "type": "outlier",
                "severity": "warning" if len(outliers) <= max(2, len(series) * 0.1) else "critical",
                "title": f"{metric} contains outlier values",
                "detail": f"Detected {len(outliers)} outlier row(s); most extreme observed value is {_format_value(extreme_value)}.",
                "metric": metric,
            }
        )


def _add_category_findings(df: pd.DataFrame, findings: list[dict[str, Any]]) -> None:
    numeric_columns = _numeric_columns(df)
    for dimension in _categorical_columns(df)[:4]:
        series = df[dimension].dropna()
        if series.empty:
            continue
        top_share = series.value_counts(normalize=True).iloc[0]
        top_value = series.value_counts().index[0]
        if top_share >= 0.45:
            findings.append(
                {
                    "type": "dominant_category",
                    "severity": "warning" if top_share >= 0.65 else "info",
                    "title": f"{dimension} is concentrated in one category",
                    "detail": f"{_format_value(top_value)} represents {top_share * 100:,.1f}% of rows.",
                    "dimension": dimension,
                }
            )

        if numeric_columns:
            metric = numeric_columns[0]
            grouped = df.groupby(dimension, dropna=True)[metric].sum().sort_values(ascending=False)
            if len(grouped) >= 2 and grouped.sum() != 0:
                contribution = float(grouped.iloc[0] / grouped.sum())
                if contribution >= 0.5:
                    findings.append(
                        {
                            "type": "dominant_category",
                            "severity": "critical" if contribution >= 0.75 else "warning",
                            "title": f"{dimension} dominates {metric}",
                            "detail": f"{_format_value(grouped.index[0])} contributes {contribution * 100:,.1f}% of total {metric}.",
                            "metric": metric,
                            "dimension": dimension,
                        }
                    )


def analyze_result_set(df: pd.DataFrame | None, question: str = "") -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "findings": [],
            "severity": "info",
            "summary": "Autonomous insight scan found no rows to analyze.",
            "question": question,
        }

    findings: list[dict[str, Any]] = []
    _add_trend_findings(df, findings)
    _add_outlier_findings(df, findings)
    _add_category_findings(df, findings)

    if not findings:
        findings.append(
            {
                "type": "baseline",
                "severity": "info",
                "title": "No major anomalies detected",
                "detail": f"Scanned {len(df):,} rows across {len(df.columns)} columns without detecting a strong spike, drop, outlier, or category concentration.",
            }
        )

    severity = _severity(findings)
    summary = f"Autonomous insight scan detected {len(findings)} finding(s); highest severity is {severity}."
    return {
        "findings": findings[:8],
        "severity": severity,
        "summary": summary,
        "question": question,
    }


def insight_prompt_block(insight_state: dict[str, Any] | None) -> str:
    if not insight_state:
        return ""
    findings = insight_state.get("findings", [])
    finding_text = "\n".join(
        f"- [{item.get('severity', 'info')}] {item.get('title', '')}: {item.get('detail', '')}" for item in findings
    )
    return (
        "\n\nAutonomous insight agent findings:\n"
        f"{insight_state.get('summary', '')}\n"
        f"{finding_text or '- No findings'}"
    )
