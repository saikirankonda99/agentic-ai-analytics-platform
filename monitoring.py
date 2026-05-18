from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Callable

import pandas as pd

from autonomous_insights import analyze_result_set
from db import run_query as run_sql_query
from investigation import run_investigation, should_investigate


MonitoringCallback = Callable[[str, str, str], None]


TARGET_SQL = {
    "revenue": """
        SELECT strftime('%Y-%m', InvoiceDate) AS period, SUM(Total) AS revenue
        FROM Invoice
        GROUP BY period
        ORDER BY period
        LIMIT 24
    """,
    "customers": """
        SELECT Country AS segment, COUNT(CustomerId) AS customers
        FROM Customer
        GROUP BY Country
        ORDER BY customers DESC
        LIMIT 25
    """,
    "orders": """
        SELECT strftime('%Y-%m', InvoiceDate) AS period, COUNT(InvoiceId) AS orders, SUM(Total) AS revenue
        FROM Invoice
        GROUP BY period
        ORDER BY period
        LIMIT 24
    """,
    "growth": """
        SELECT strftime('%Y-%m', InvoiceDate) AS period, SUM(Total) AS revenue, COUNT(InvoiceId) AS orders
        FROM Invoice
        GROUP BY period
        ORDER BY period
        LIMIT 24
    """,
    "anomalies": """
        SELECT BillingCountry AS segment, SUM(Total) AS revenue, COUNT(InvoiceId) AS orders
        FROM Invoice
        GROUP BY BillingCountry
        ORDER BY revenue DESC
        LIMIT 25
    """,
}


def default_monitoring_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "targets": ["revenue", "customers", "orders", "growth", "anomalies"],
        "interval_minutes": 60,
        "last_run_at": None,
    }


def empty_monitoring_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "targets": [],
        "checks": [],
        "severity": "info",
        "summary": "No scheduled monitoring run has executed yet.",
        "telemetry": {
            "steps": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": 0,
            "model": "sqlite",
            "usage_available": False,
        },
    }


def empty_briefing_state() -> dict[str, Any]:
    return {
        "status": "idle",
        "severity": "info",
        "summary": "No executive briefing has been generated yet.",
        "sections": [],
        "generated_at": None,
    }


def monitoring_due(config: dict[str, Any], now: datetime | None = None) -> bool:
    if not config.get("enabled"):
        return False
    last_run_at = config.get("last_run_at")
    if not last_run_at:
        return True
    try:
        last_run = datetime.fromisoformat(last_run_at)
    except ValueError:
        return True
    now = now or datetime.now()
    return (now - last_run).total_seconds() >= int(config.get("interval_minutes", 60)) * 60


def _record_sql_step(telemetry: dict[str, Any], latency_ms: int) -> dict[str, Any]:
    steps = list(telemetry.get("steps", [])) + [
        {
            "step": "monitoring",
            "model": "sqlite",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": latency_ms,
            "usage_available": False,
        }
    ]
    telemetry.update(
        {
            "steps": steps,
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": "sqlite",
            "usage_available": False,
        }
    )
    return telemetry


def _merge_telemetry(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    steps = list(base.get("steps", [])) + list((extra or {}).get("steps", []))
    base.update(
        {
            "steps": steps,
            "prompt_tokens": sum(item.get("prompt_tokens", 0) for item in steps),
            "completion_tokens": sum(item.get("completion_tokens", 0) for item in steps),
            "total_tokens": sum(item.get("total_tokens", 0) for item in steps),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in steps),
            "latency_ms": sum(item.get("latency_ms", 0) for item in steps),
            "model": (extra or {}).get("model") or base.get("model") or "sqlite",
            "usage_available": any(item.get("usage_available", False) for item in steps),
        }
    )
    return base


def _severity(checks: list[dict[str, Any]]) -> str:
    rank = {"info": 0, "warning": 1, "critical": 2}
    return max((check.get("severity", "info") for check in checks), key=lambda item: rank.get(item, 0), default="info")


def generate_executive_briefing(monitoring_state: dict[str, Any]) -> dict[str, Any]:
    checks = monitoring_state.get("checks", [])
    sections = []
    for check in checks:
        insight = check.get("insight", {})
        investigation = check.get("investigation", {})
        findings = insight.get("findings", [])
        sections.append(
            {
                "target": check.get("target", "unknown"),
                "severity": check.get("severity", "info"),
                "kpi_status": check.get("status", "unknown"),
                "trend": findings[0].get("title", "No major trend detected") if findings else "No major trend detected",
                "anomalies": len([item for item in findings if item.get("severity") in {"warning", "critical"}]),
                "investigation": investigation.get("summary", "No investigation required."),
            }
        )
    severity = monitoring_state.get("severity", "info")
    warning_count = len([item for item in checks if item.get("severity") in {"warning", "critical"}])
    return {
        "status": "completed",
        "severity": severity,
        "summary": f"Executive briefing completed for {len(checks)} KPI target(s); {warning_count} target(s) require attention.",
        "sections": sections,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def run_monitoring_checks(
    targets: list[str],
    semantic_context: dict[str, Any] | None = None,
    *,
    callback: MonitoringCallback | None = None,
    max_investigations: int = 2,
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected_targets = [target for target in targets if target in TARGET_SQL]
    state = {
        **empty_monitoring_state(),
        "status": "running",
        "targets": selected_targets,
        "summary": "Scheduled monitoring run is active.",
    }
    investigations_run = 0

    for target in selected_targets:
        if callback:
            callback("active", "monitoring", f"Checking {target} KPI target.")
        started = time.perf_counter()
        columns, rows = run_sql_query(TARGET_SQL[target])
        latency_ms = int((time.perf_counter() - started) * 1000)
        state["telemetry"] = _record_sql_step(state["telemetry"], latency_ms)
        df = pd.DataFrame(rows, columns=columns)
        insight = analyze_result_set(df, f"Scheduled monitoring check for {target}")
        investigation = {"status": "skipped", "summary": "No investigation required for this target."}

        if should_investigate(insight) and investigations_run < max_investigations:
            investigations_run += 1
            if callback:
                callback("active", "investigation", f"Investigating {target} monitoring signal.")
            investigation = run_investigation(
                f"Scheduled monitoring check for {target}",
                TARGET_SQL[target],
                insight,
                semantic_context,
                max_queries=1,
                callback=callback,
            )
            state["telemetry"] = _merge_telemetry(state["telemetry"], investigation.get("telemetry", {}))

        check = {
            "target": target,
            "status": "completed",
            "row_count": len(df),
            "severity": insight.get("severity", "info"),
            "insight": insight,
            "investigation": investigation,
        }
        state["checks"].append(check)
        if callback:
            callback("completed", "monitoring", f"{target} monitoring completed with {check['severity']} severity.")

    state["severity"] = _severity(state["checks"])
    state["status"] = "completed"
    state["summary"] = f"Scheduled monitoring completed for {len(state['checks'])} target(s). Highest severity: {state['severity']}."
    briefing = generate_executive_briefing(state)
    return state, briefing
