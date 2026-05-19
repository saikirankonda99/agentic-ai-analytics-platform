from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from guardrails import is_safe_sql
from semantic import infer_column_role, parse_schema_tables


ValidationStatus = Literal["passed", "failed", "warning"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class SQLValidationResult:
    status: ValidationStatus
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    risk_score: float = 0.0
    risk_level: RiskLevel = "low"
    confidence: float = 0.0
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    complexity: dict[str, Any] = field(default_factory=dict)
    repair_hint: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_schema_intelligence(schema: str) -> dict[str, Any]:
    tables = parse_schema_tables(schema)
    table_names = {table["name"] for table in tables}
    relationships = infer_relationships(tables)
    columns = [
        {
            **column,
            "table": table["name"],
            "category": column.get("role") or infer_column_role(column.get("name", ""), dtype=column.get("dtype")),
        }
        for table in tables
        for column in table.get("columns", [])
    ]
    confidence = schema_confidence(tables, relationships)
    return {
        "table_count": len(tables),
        "column_count": len(columns),
        "tables": tables,
        "table_names": sorted(table_names),
        "columns": columns,
        "relationships": relationships,
        "confidence": confidence,
        "business_summary": business_schema_summary(tables, relationships),
        "compressed_prompt": compressed_schema_context(tables, relationships),
    }


def infer_relationships(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_lookup = {table["name"].lower(): table for table in tables}
    relationships = []
    primary_like = {
        (table["name"].lower(), column["name"].lower())
        for table in tables
        for column in table.get("columns", [])
        if column["name"].lower() in {"id", f"{table['name'].lower()}id", f"{table['name'].lower()}_id"}
    }
    for table in tables:
        for column in table.get("columns", []):
            name = column["name"]
            lowered = name.lower()
            if not (lowered.endswith("id") or lowered.endswith("_id")):
                continue
            stem = lowered.removesuffix("_id").removesuffix("id")
            candidates = [stem, f"{stem}s", stem.rstrip("s")]
            target = next((table_lookup[item]["name"] for item in candidates if item in table_lookup and item != table["name"].lower()), None)
            if target or any(column_name == lowered for _, column_name in primary_like):
                relationships.append(
                    {
                        "from_table": table["name"],
                        "from_column": name,
                        "to_table": target or name.removesuffix("Id").removesuffix("_id"),
                        "confidence": 0.82 if target else 0.58,
                        "type": "many_to_one",
                    }
                )
    return relationships


def schema_confidence(tables: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> float:
    if not tables:
        return 0.0
    column_count = sum(len(table.get("columns", [])) for table in tables)
    base = 0.55 + min(len(tables), 8) * 0.03 + min(column_count, 80) * 0.002
    if relationships:
        base += min(len(relationships), 8) * 0.025
    return round(min(base, 0.96), 2)


def business_schema_summary(tables: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> str:
    table_text = ", ".join(table["name"] for table in tables[:8]) or "No tables detected"
    relation_text = f"{len(relationships)} inferred relationship(s)" if relationships else "no inferred relationships"
    return f"Schema contains {len(tables)} table(s): {table_text}. Relationship graph has {relation_text}."


def compressed_schema_context(tables: list[dict[str, Any]], relationships: list[dict[str, Any]], limit: int = 14) -> str:
    lines = []
    for table in tables[:limit]:
        metrics = [column["name"] for column in table.get("columns", []) if column.get("role") == "metric"][:5]
        dimensions = [column["name"] for column in table.get("columns", []) if column.get("role") in {"dimension", "categorical"}][:5]
        identifiers = [column["name"] for column in table.get("columns", []) if column.get("role") == "identifier"][:5]
        lines.append(
            f"- {table['name']}: ids={', '.join(identifiers) or 'none'}; metrics={', '.join(metrics) or 'none'}; dimensions={', '.join(dimensions) or 'none'}"
        )
    relation_lines = [
        f"- {item['from_table']}.{item['from_column']} -> {item['to_table']}"
        for item in relationships[:limit]
    ]
    return "Schema intelligence:\n" + "\n".join(lines) + ("\nRelationships:\n" + "\n".join(relation_lines) if relation_lines else "")


def validate_sql_against_schema(sql: str, schema: str) -> dict[str, Any]:
    sql = _strip_sql(sql)
    schema_info = build_schema_intelligence(schema)
    errors: list[str] = []
    warnings: list[str] = []
    if not sql:
        errors.append("SQL is empty.")
    if not is_safe_sql(sql):
        errors.append("SQL contains a blocked write or DDL operation.")
    if not re.match(r"^\s*(select|with)\b", sql, flags=re.IGNORECASE):
        errors.append("Only SELECT or WITH queries are allowed.")
    if sql.count("(") != sql.count(")"):
        errors.append("SQL has unbalanced parentheses.")
    if ";" in sql.rstrip(";"):
        errors.append("Multiple SQL statements are not allowed.")

    tables = extract_tables(sql)
    columns = extract_referenced_columns(sql)
    table_map = {table["name"].lower(): table for table in schema_info["tables"]}
    alias_map = extract_aliases(sql)
    missing_tables = [table for table in tables if table.lower() not in table_map]
    for table in missing_tables:
        errors.append(f"Unknown table: {table}.")

    missing_columns = []
    all_columns = {
        column["name"].lower(): column
        for table in schema_info["tables"]
        for column in table.get("columns", [])
    }
    for reference in columns:
        if "." in reference:
            alias, column_name = reference.split(".", 1)
            table_name = alias_map.get(alias.lower(), alias)
            table = table_map.get(table_name.lower())
            if table and column_name.lower() not in {column["name"].lower() for column in table.get("columns", [])}:
                missing_columns.append(reference)
        elif reference.lower() not in all_columns and reference != "*":
            warnings.append(f"Column could not be confidently resolved: {reference}.")
    for column in missing_columns:
        errors.append(f"Unknown column: {column}.")

    complexity = query_complexity(sql)
    if complexity["joins"] >= 4:
        warnings.append("Query has a high join count.")
    if not re.search(r"\blimit\b", sql, flags=re.IGNORECASE):
        warnings.append("Query has no LIMIT clause.")

    risk_score = query_risk_score(errors, warnings, complexity)
    status: ValidationStatus = "failed" if errors else "warning" if warnings else "passed"
    return SQLValidationResult(
        status=status,
        errors=errors,
        warnings=warnings,
        risk_score=risk_score,
        risk_level=risk_level(risk_score),
        confidence=validation_confidence(errors, warnings, schema_info["confidence"]),
        tables=tables,
        columns=columns,
        complexity=complexity,
        repair_hint=repair_hint(errors, warnings, schema_info),
    ).as_dict()


def explain_sql(sql: str, validation: dict[str, Any] | None = None) -> dict[str, Any]:
    validation = validation or {}
    tables = validation.get("tables") or extract_tables(sql)
    complexity = validation.get("complexity") or query_complexity(sql)
    intent = "Retrieve records"
    lowered = sql.lower()
    if " group by " in lowered:
        intent = "Aggregate results by grouped dimensions"
    elif " order by " in lowered:
        intent = "Rank or sort result rows"
    if " join " in lowered:
        intent += " across related tables"
    annotations = []
    if complexity.get("joins"):
        annotations.append(f"Uses {complexity['joins']} join(s).")
    if complexity.get("aggregations"):
        annotations.append("Uses aggregate calculations.")
    if not re.search(r"\blimit\b", sql, flags=re.IGNORECASE):
        annotations.append("No explicit row limit detected.")
    return {
        "intent_summary": intent,
        "tables_used": tables,
        "annotations": annotations,
        "confidence": validation.get("confidence", 0.5),
        "risk_level": validation.get("risk_level", "medium"),
        "reasoning_summary": f"Query references {', '.join(tables) if tables else 'no resolved tables'} and has {complexity.get('joins', 0)} join(s).",
    }


def analyze_result_quality(columns: list[str], rows: list[Any]) -> dict[str, Any]:
    row_count = len(rows)
    warnings = []
    if row_count == 0:
        warnings.append("Query returned no rows.")
    if row_count == 50:
        warnings.append("Result may be truncated by default row limit.")
    null_values = 0
    total_values = max(row_count * max(len(columns), 1), 1)
    for row in rows:
        values = row.values() if isinstance(row, dict) else row
        null_values += sum(1 for value in values if value is None)
    null_ratio = null_values / total_values
    if null_ratio > 0.4:
        warnings.append("Result is null-heavy.")
    confidence = max(0.2, 0.92 - len(warnings) * 0.18 - min(null_ratio, 0.5) * 0.3)
    return {
        "row_count": row_count,
        "column_count": len(columns),
        "warnings": warnings,
        "null_ratio": round(null_ratio, 3),
        "confidence": round(confidence, 2),
        "status": "warning" if warnings else "passed",
    }


def extract_tables(sql: str) -> list[str]:
    return list(dict.fromkeys(match.group(2) for match in re.finditer(r"\b(from|join)\s+([A-Za-z_][\w.]*)", sql, re.IGNORECASE)))


def extract_aliases(sql: str) -> dict[str, str]:
    aliases = {}
    for match in re.finditer(r"\b(from|join)\s+([A-Za-z_][\w.]*)\s+(?:as\s+)?([A-Za-z_][\w]*)", sql, re.IGNORECASE):
        table = match.group(2)
        alias = match.group(3)
        if alias.lower() not in {"where", "join", "on", "group", "order", "limit"}:
            aliases[alias.lower()] = table
    return aliases


def extract_referenced_columns(sql: str) -> list[str]:
    cleaned = re.sub(r"'[^']*'|\"[^\"]*\"", "", sql)
    references = set(re.findall(r"\b[A-Za-z_][\w]*\.[A-Za-z_][\w]*\b", cleaned))
    select_match = re.search(r"\bselect\b(.+?)\bfrom\b", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if select_match:
        for piece in select_match.group(1).split(","):
            token = re.sub(r"\b(sum|count|avg|min|max|round|cast)\s*\(", "", piece, flags=re.IGNORECASE)
            token = re.sub(r"\bas\b\s+[A-Za-z_][\w]*", "", token, flags=re.IGNORECASE)
            token = token.strip(" ()")
            if token and re.match(r"^[A-Za-z_][\w.]*$", token):
                references.add(token)
    return sorted(references)


def query_complexity(sql: str) -> dict[str, Any]:
    lowered = sql.lower()
    return {
        "joins": len(re.findall(r"\bjoin\b", lowered)),
        "subqueries": max(lowered.count("(select"), 0),
        "aggregations": len(re.findall(r"\b(sum|count|avg|min|max)\s*\(", lowered)),
        "has_group_by": " group by " in lowered,
        "has_order_by": " order by " in lowered,
        "has_limit": bool(re.search(r"\blimit\b", lowered)),
    }


def query_risk_score(errors: list[str], warnings: list[str], complexity: dict[str, Any]) -> float:
    score = len(errors) * 0.35 + len(warnings) * 0.08 + complexity.get("joins", 0) * 0.06 + complexity.get("subqueries", 0) * 0.1
    return round(min(score, 1.0), 2)


def risk_level(score: float) -> RiskLevel:
    if score >= 0.65:
        return "high"
    if score >= 0.3:
        return "medium"
    return "low"


def validation_confidence(errors: list[str], warnings: list[str], schema_confidence_value: float) -> float:
    return round(max(0.05, schema_confidence_value - len(errors) * 0.25 - len(warnings) * 0.06), 2)


def repair_hint(errors: list[str], warnings: list[str], schema_info: dict[str, Any]) -> str:
    if not errors and not warnings:
        return "No repair required."
    available = ", ".join(schema_info.get("table_names", [])[:12])
    return "Repair SQL using known tables and columns. Available tables: " + (available or "none detected")


def _strip_sql(sql: str) -> str:
    return sql.strip().replace("```sql", "").replace("```", "").strip()


__all__ = [
    "analyze_result_quality",
    "build_schema_intelligence",
    "compressed_schema_context",
    "explain_sql",
    "infer_relationships",
    "validate_sql_against_schema",
]
