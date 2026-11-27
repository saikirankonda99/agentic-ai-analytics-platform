# Small-business sales milestone

## What this milestone delivers

The first business use case is a sales review for a small retailer: load transaction data, calculate product and monthly totals, inspect a chart, and export an explainable report. It runs locally without sending the uploaded CSV to a model.

This is an in-development prototype. The sales demo demonstrates a specific useful workflow. It does not establish production readiness, real customer savings, or the accuracy of the separate model-generated SQL workflow.

## Try the demo

Use Python 3.11 and install `requirements-lock.txt` in a virtual environment, then run:

```bash
python -m streamlit run app.py --server.port 8501
```

In development mode, log in using `admin` and `admin123`, or your configured development password. Select **Load retail demo** in the sidebar, then **Revenue by Product**. The active data caption identifies the synthetic file and its row count. Select **Monthly Revenue** or **Total Revenue** to change the view. Download the full CSV and executive summary below the result.

The file `data/demo/retail_sales.csv` contains 12 synthetic transactions. Its expected answers are:

| Question | Expected answer |
|---|---|
| Total revenue | 352.00 USD |
| Revenue by product | Coffee Beans 180.00; Tea 100.00; Mug 72.00 |
| Revenue by month | 2026-01: 144.00; 2026-02: 117.00; 2026-03: 91.00 |
| Revenue by country | USA 256.00; Canada 74.00; Germany 22.00 |
| Units sold by product | Coffee Beans 12; Tea 10; Mug 6 |

Monthly sales totals are descriptive. They do not adjust for incomplete reporting periods or explain why sales changed. The example contains no costs, so it cannot calculate profit or margin.

## CSV contract

Use one transaction or line item per row. Provide an amount column such as `revenue`, or both `quantity` and `unit_price`. The sample CSV is a reusable format and can be downloaded from the sidebar.

| Field | Requirement |
|---|---|
| `revenue` | Numeric line amount; used when supplied. Otherwise calculated from quantity × unit price |
| `quantity`, `unit_price` | Both required when revenue is absent; quantity also needed for units by product |
| `product` | Needed for product questions |
| `date` | Needed for monthly revenue; use YYYY-MM-DD |
| `country` | Needed for country questions |
| `currency` | Optional single code: USD, CAD, EUR, GBP, AUD, or NZD; no currency conversion |

Supported questions are **Total revenue**, **Revenue by product**, **Revenue by month**, **Revenue by country**, **Units sold by product**, and **Sales summary**. Some equivalent phrases are recognized. Arbitrary filters, forecasts, profit questions, and causal explanations are not supported by this CSV calculation path. It reports an unsupported question instead of guessing.

Limits are 10 MB, 50,000 rows, and 100 columns. Money is calculated from original numeric text, rounded to two decimal places per line using half-up rounding, and aggregated as integer cents. Product codes retain leading zeros. Duplicate or ambiguous headers and malformed rows are rejected. Invalid amounts, missing required group fields, and mixed currencies are rejected. An absent currency produces an explicit same-currency assumption. Duplicate rows are retained with a warning because repeated sales may be legitimate. Negative amounts remain in totals and are flagged as possible returns or adjustments. Values such as `$1,000` must be cleaned to plain numeric values.

The supplied revenue column is authoritative when present. Users should make clear whether it includes discounts, tax, or shipping. The demo does not reconcile multiple amount definitions or automatically identify duplicate orders.

The active dataset stays selected until a replacement is uploaded or **Use example database** is selected. Switching workspace or logging out clears the uploaded data and current results. Unsupported or failed questions clear the previous answer so it is not displayed as the new result.

## Engineering corrections

- CSV questions now aggregate the entire source rather than returning an unchanged input table or a small preview.
- UI identity comes from the login session; editable user/team/role fields were removed. Private APIs validate session tokens and check workflow/workspace access. Diagnostics and connector endpoints require admin access.
- Logout and session expiry clear uploaded data and cached UI results. Workspace switching clears the previous workspace's active analysis.
- Authentication reads and revokes individual stored tokens. An in-flight validation cannot write a stale session snapshot back after logout; database failures deny authentication instead of using an old JSON copy.
- SQL execution uses read-only SQLite connections and an authorizer, bounded results/time, and read-only PostgreSQL transactions. Guardrails remain an additional check.
- Linear SQL retries execute and revalidate the reflected correction instead of overwriting it with another initial generation. The selected evaluation model reaches both workflow paths.
- Semantic roles distinguish IDs and dates from actual measures, including common CamelCase names. Insight scanning no longer treats order IDs as revenue-like numeric signals.
- The evaluation harness uses the actual Chinook schema and compares result values, duplicate counts, and ordering where required. Matching row counts alone no longer count as correctness.
- Authentication tests use isolated explicit credentials. Startup checks exercise FastAPI lifespan and use authenticated diagnostics. CI and Docker builds install the same dependency lock.
- API lifecycle responses identify simulation and synthetic usage. The unimplemented pgvector backend is no longer selected by default in Compose.

## Verification

The original checkout passed 84 tests with 10 browser tests skipped. Its auth tests failed under the passwords configured by CI (3 failures), which was reproduced before changing them. The updated suite uses explicit fixtures to remove that dependency.

The completed milestone passed **196 offline tests in 13.35 seconds**, including the Streamlit application test, using CI-style passwords and an empty API key. Ruff and whitespace validation passed. All **20 reference SQL queries** validated against the bundled database without model calls. These results describe the local implementation checks; a remote CI result is a separate check.

Run the offline suite and reference checks:

```bash
OPENAI_API_KEY='' python -m pytest tests --ignore=tests/e2e
python -m ruff check .
python evals/run_evals.py --validate-only
```

The CSV unit tests check exact monetary results, raw numeric precision, product codes, input validation, and full-dataset aggregation. `tests/test_sales_demo_app.py` exercises the real Streamlit app without a browser: login, demo selection, calculated results, unsupported questions, workspace changes, and logout. Security and evaluation regressions use isolated test data.

The browser suite has assertions for raw CSV upload and the exact downloaded result/report values. A browser executable is required. In the implementation workspace the browser download returned HTTP 403 and the advertised system Chromium executable was unavailable, so browser E2E and visual validation were not completed there. API health/authentication smoke checks and Streamlit application tests are separate evidence.

No paid model calls, real PostgreSQL integration tests, Docker builds, load tests, or live deployment changes were performed for this milestone. Validating the 20 reference queries establishes a working evaluation dataset; it is not a model accuracy score.

## Remaining work before a customer pilot

1. Pick one pilot business and define its export format and one useful decision, such as which products contributed most to this month's sales. Reconcile totals with the business's existing report before using the output.
2. Add an upload preview and column-mapping step for real exports, with explicit treatment of returns, tax, discounts, missing dates, and duplicates. Add period comparison only after reporting-window completeness is defined.
3. Run browser upload/download tests, package the demo, and verify the deployment from a clean environment. Exercise PostgreSQL with a real service if it will be used.
4. Connect the FastAPI execution endpoint to the actual SQL/analysis pipeline if an API-backed product is needed. Add failure handling and observed execution telemetry; its current lifecycle simulation is not customer analytics.
5. Separate every customer's database credentials, uploaded files, vector/retrieval history, and reports. The bundled Chinook connector and historical retrieval paths are still shared demonstration infrastructure.
6. Run the repaired golden evaluation against the selected model with a budget and review wrong answers. Add durable jobs and monitoring only when the product needs them; Redis and pgvector scaffolding alone do not provide those features.
7. Record pilot evidence: task time before and after, accuracy against the trusted report, owner feedback, and permission to share the case study. Use those measured outcomes in a portfolio or application; describe this sample as synthetic until then.
