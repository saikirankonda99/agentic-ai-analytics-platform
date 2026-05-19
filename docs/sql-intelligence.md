# SQL Intelligence and Analytics Reliability

The SQL intelligence layer strengthens analytics reliability without replacing the existing orchestration runtime. It provides deterministic schema reasoning, validation, explainability, risk scoring, and result-quality checks around the LLM-generated SQL path.

## Schema Reasoning

`backend.sql_intelligence` builds schema intelligence from connector schema text:

- table inventory
- column role categorization
- inferred table relationships
- schema confidence score
- business-oriented schema summary
- compressed prompt context

Relationship inference uses identifier-style columns such as `CustomerId`, `customer_id`, and table-name-derived primary keys. The output is intentionally heuristic and expressed with confidence metadata rather than treated as authoritative database lineage.

## Validation Pipeline

Generated SQL is validated before execution:

1. normalize SQL fences and whitespace
2. enforce read-only `SELECT` or `WITH`
3. block write, DDL, attach, detach, and destructive operations
4. reject multiple statements
5. validate balanced parentheses
6. extract referenced tables
7. validate table existence against schema metadata
8. validate qualified column references
9. emit warnings for unresolved unqualified columns
10. score query complexity and risk

Validation returns:

- `status`
- `errors`
- `warnings`
- `risk_score`
- `risk_level`
- `confidence`
- referenced tables and columns
- complexity metrics
- repair hint

Failed validation routes through the existing reflection path when retry budget remains.

## Retry and Repair

The reflection prompt now includes compressed schema intelligence and validation repair hints. This gives the model specific recovery context for:

- invalid tables
- invalid columns
- unsafe SQL
- syntax-like structural issues
- missing row limits

Retry telemetry is preserved through existing workflow telemetry and execution graph metadata.

## Query Explainability

The workflow now produces a deterministic SQL explanation object:

- intent summary
- referenced tables
- query annotations
- reasoning summary
- risk level
- validation confidence

This is designed for operator review and dashboard display, not as a substitute for the SQL itself.

## Result Quality

After execution, result quality checks detect:

- empty result sets
- potentially truncated default-limit results
- null-heavy outputs
- low-confidence result posture

Quality signals are attached to workflow results, execution graph metadata, and execution telemetry.

## Streamlit Surface

The Agents workspace includes a SQL Intelligence panel with:

- validation status
- query risk
- validation confidence
- schema confidence
- intent summary
- result quality
- validation and quality warnings

## Engineering Boundaries

This layer deliberately avoids a heavyweight SQL parser. It is a deterministic reliability pass that catches common failure modes before execution and improves recovery context. Ambiguous SQL is warned on rather than aggressively blocked unless it violates safety or known schema constraints.
