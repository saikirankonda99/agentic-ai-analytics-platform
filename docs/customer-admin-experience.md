# Sales Studio: customer and administrator experience

This guide describes the implemented Streamlit interface and its exact screen text. It is a review and demonstration guide, not a claim that the changes are deployed or that production readiness has been established.

## Separate interfaces

The customer interface is the default. Accounts with the `analyst` or `viewer` role receive only this interface. An authenticated administrator sees an **Interface** selector with **Customer dashboard** and **Admin workspace**. The role comes from the validated login session; changing interface or navigation state does not grant administrator access.

The customer sidebar contains **Workspace settings** and **Account**. The settings include **Workspace scope** with **Personal** / **Shared team**, plus **Clear session**. Account provides **Logout**. Switching workspace or logging out clears the current uploaded data and analysis.

Administrator tools are grouped in the separate workspace. Its caption is **“Admin workspace · Platform settings, integrations, and diagnostics”**. Its navigation remains **Overview**, **Operations**, **Copilot**, **Investigations**, **Monitoring**, **Agents**, **API**, and **History**. Customers do not need these technical screens to review sales.

## Visual direction and components

| Purpose | Implemented color |
|---|---|
| Warm ivory page | `#FAF5ED` |
| Cream panel | `#FFF9F0` |
| Deep plum text | `#3D2939` |
| Plum primary button | `#563548` |
| Terracotta accent | `#9D4937` |
| Coral illustration face | `#C6755A` |
| Sage illustration face | `#82947A` |

The hero combines a warm gradient, layered cards, soft depth, and a decorative CSS 3D bar model. The illustration is not a representation of the customer's numbers. It has no interaction requirement, is hidden from assistive technology, stops moving when reduced motion is requested, and is hidden on narrow phone screens. Actual sales charts remain precise two-dimensional bar or line charts, using the calculated result values.

The page title is **“Sales Studio · Your sales, made clear”**. The hero reads:

> YOUR BUSINESS. A CLEARER PICTURE.
>
> Your sales, made clear.

Before a source is loaded, its supporting sentence is **“Bring your sales data. Find the answers that help you decide what to do next.”** With accepted data, it becomes **“Ask a sales question. Get a clear answer you can check against your data.”**

## Customer flow and exact screen text

| Step | Visible content and behavior |
|---|---|
| **Upload & review** | **“1 · Upload your sales file”**, the **“Upload your sales CSV”** control, **Try sample data**, and **Download sample CSV**. The upload caption states **“CSV only · Up to 10 MB and 50,000 rows · Review your columns before analysis.”** |
| **Ask a question** | **“Ask your business question”**, the example **“Which products generated the most revenue?”**, and **Get answer**. The collapsed **Common questions** section contains the six report shortcuts below. |
| **Answer & download** | **“YOUR ANSWER”**, the question, **“What this means”**, and a suitable chart or numeric result. **“See the numbers and how this was calculated”** reveals the result table and source. **Download results CSV** and **Download summary** export the current report. |

The empty-state heading is **“What would you like to know about your sales?”** Its explanation is **“Upload a CSV or try the retail sample. Review the columns once, then explore your sales.”** Once a file is accepted, the upload section becomes **“Your sales data · Change file”**.

The mapping screen is titled **“Review your sales file”**, followed by **“Match your columns and check the data before using it for analysis.”** It shows the first ten rows while validating every row. **Calculate revenue from** offers **Revenue column** or **Quantity × unit price**. Optional product, date, country, and currency mappings determine which reports are available. **Use this data** is enabled only after required checks pass; **Cancel upload** discards the candidate. Acceptance produces **“CSV ready for analysis.”** and an initial sales summary in customer mode.

Excel workbooks are not accepted directly. The screen says **“Sample data is fictional. For an Excel file, export the sheet as CSV first.”** Amounts are used as supplied; tax, discounts, and shipping are not automatically reconciled.

### Six supported reports

| Button | Calculation | Additional mapping |
|---|---|---|
| **Total Revenue** | Sum accepted sales amounts | Revenue or quantity × unit price |
| **Revenue by Product** | Aggregate revenue by product | Product |
| **Monthly Revenue** | Aggregate revenue by recorded month | Date, with explicit format |
| **Sales Summary** | Total revenue, source-row count, and units where available | Quantity for units |
| **Revenue by Country** | Aggregate revenue by country | Country |
| **Units Sold by Product** | Aggregate quantity by product | Product and quantity |

Missing mappings disable the corresponding shortcut and identify the needed columns. The question field recognizes these reports and supported equivalent phrases. It does not provide arbitrary filtering or a general conversational ChatGPT experience.

## What actually uses AI

The six reports use deterministic local calculations. Uploading a file, calculating totals, and drawing charts do not call a model.

The optional AI section is **“AI help · What should I check next?”** It provides **What would you like help with?** choices **Overview**, **Products**, **Monthly pattern**, and **Data checks**, followed by **Explain this result with AI**. AI reviews the currently calculated report; a product or monthly breakdown must exist to supply those detailed facts.

When explicitly requested, the server sends OpenAI calculated totals, counts, anonymous group statistics, and data-quality flags. Raw CSV rows, uploaded headers, product or customer names, and the file name are not included in this review prompt. The model chooses existing fact IDs and suggested-check IDs. The application validates the selection and renders the numerical statements locally. The model cannot write arbitrary factual prose, alter the report calculations, or execute code through this path.

Three status labels make the distinction visible:

- **Calculated reports**: **“Sales reports work now. AI is not connected in this session.”**
- **AI assistance available**: **“AI can review calculated findings and suggest checks. A live response has not been verified yet.”**
- **AI-assisted answer**: **“AI selected relevant findings and suggested checks; the figures were calculated from your data.”**

A configured API key establishes availability to attempt a request. Only a successful, validated model response establishes that AI assisted that review. Failures retain the calculated report and show a truthful unavailable message. There is no fabricated AI fallback.

This review does not establish why sales changed, calculate profit without costs, forecast future sales, or perform business actions. Monthly totals describe uploaded records and do not establish that reporting periods are complete.

## Demo with the provided 60-row file

Upload **synthetic_retail_sales_60_rows.csv**, use **Quantity × unit price**, retain the suggested mappings and `YYYY-MM-DD` format, then select **Use this data**. These values were independently recalculated with the repository's sales engine from that supplied synthetic file:

| Check | Expected result |
|---|---:|
| Source rows | 60 |
| Total Revenue | 2,584.00 USD |
| January 2026 | 647.00 USD |
| February 2026 | 867.00 USD |
| March 2026 | 1,070.00 USD |
| Leading product: Water Bottle | 880.00 USD |

The built-in **Try sample data** action uses a different, 12-row sample; its total is 352.00 USD. Use the uploaded 60-row file for the values above. Do not describe the synthetic figures as evidence of customer revenue or business improvement.

## Administrator implementation notes

The existing runtime reads `OPENAI_API_KEY` from the server environment or Streamlit secrets; local development also supports the project's `.env` file. Configure the secret on the server and restart the app when needed. Do not place a real key in customer forms, browser code, screenshots, or source control. OpenAI's [API authentication documentation](https://developers.openai.com/api/reference/overview#authentication) explains server-side credential handling. The current integration uses the existing model client in `llm.py`; setting a key is not a live connection test.

This customer workflow is on demand. Accepting data opens its initial summary, report actions calculate requested answers, and the explicit AI button requests a review. Scheduled CSV ingestion, automatic synchronization from accounting systems, unattended customer reports, and automatic business actions are not implemented. The administrator's existing scheduled database checks run while the page is active; they are not a customer background ingestion service.

The customer flow is implemented in `app.py`, `ui/views/customer_flow.py`, and `ui/views/customer.py`; appearance is in `styles/theme.py`; bounded AI selection is in `sales_copilot.py`. Deployment status, browser validation, model connectivity, and production access controls require their own verification and are not established by this guide.
