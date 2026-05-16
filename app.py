import os
import streamlit as st
import pandas as pd
import time

from db import get_schema
from openai import OpenAI

try:
    from graph.workflow import run_workflow
except Exception:
    run_workflow = None


def get_openai_api_key():
    return st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

# ---------------- CONFIG ---------------- #
st.set_page_config(
    page_title="GenAI SQL Assistant",
    layout="wide",
    page_icon="📊"
)

client = OpenAI(api_key=get_openai_api_key())

# ---------------- STYLE ---------------- #
# ---------------- STYLE ---------------- #
st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.stButton > button {
    border-radius: 10px;
    padding: 0.6rem 1rem;
    font-weight: 500;
}

.stTextInput > div > div > input {
    border-radius: 10px;
}

[data-testid="stMetricValue"] {
    font-size: 28px;
}

.stMetric {
    background-color: #0e1117;
    padding: 12px;
    border-radius: 10px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ---------------- #
st.markdown("""
# 📊 GenAI SQL Assistant  
### Turn natural language into SQL + insights instantly
""")

st.divider()
st.markdown("<br>", unsafe_allow_html=True)

if "workflow_trace" not in st.session_state:
    st.session_state.workflow_trace = []

if "workflow_telemetry" not in st.session_state:
    st.session_state.workflow_telemetry = {}

# ---------------- SIDEBAR ---------------- #
with st.sidebar:
    st.markdown("## ⚙️ Settings")

    if st.button("🧹 Clear Chat"):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()
    st.markdown("### 💡 Sample Queries")
    st.markdown("""
    - List all customers  
    - Top customers by spending  
    - Tracks with album and artist  
    """)

    show_schema = st.toggle("Show Schema", False)
    # ✅ ADD HERE (INSIDE SIDEBAR)
    st.markdown("### 📂 Upload Data")

    uploaded_file = st.file_uploader("Upload CSV")

    if uploaded_file:
        df_uploaded = pd.read_csv(uploaded_file)
        st.session_state.uploaded_df = df_uploaded
        st.success("CSV uploaded successfully!")


def render_workflow_trace():
    with st.sidebar:
        st.markdown("### 🔎 Workflow Trace")
        trace = st.session_state.get("workflow_trace", [])
        if not trace:
            st.caption("Run a database query to see workflow steps.")
            return

        latest_by_step = {}
        for item in trace:
            latest_by_step[item["step"]] = item

        ordered_steps = [
            "planner",
            "schema retrieval",
            "memory retrieval",
            "sql generation",
            "validation",
            "reflection",
            "execution",
        ]
        icons = {
            "success": "✅",
            "error": "❌",
            "retry": "🔄",
            "pending": "⏳",
        }

        for step in ordered_steps:
            item = latest_by_step.get(
                step,
                {"status": "pending", "detail": "Not started."},
            )
            icon = icons.get(item["status"], "⏳")
            st.markdown(f"**{icon} {step.title()}**")
            st.caption(item["detail"])


def render_workflow_telemetry():
    with st.sidebar:
        st.markdown("### 📈 Telemetry")
        telemetry = st.session_state.get("workflow_telemetry", {})
        if not telemetry:
            st.caption("Run a database query to see telemetry.")
            return

        st.caption(f"Model: {telemetry.get('model') or 'Unavailable'}")
        st.caption(f"Prompt tokens: {telemetry.get('prompt_tokens', 0)}")
        st.caption(f"Completion tokens: {telemetry.get('completion_tokens', 0)}")
        st.caption(f"Total tokens: {telemetry.get('total_tokens', 0)}")
        st.caption(f"Estimated cost: ${telemetry.get('cost_usd', 0.0):.6f}")
        st.caption(f"Workflow latency: {telemetry.get('latency_ms', 0)} ms")
        if not telemetry.get("usage_available", False):
            st.caption("Token usage metadata unavailable for one or more steps.")

if show_schema:
    st.code(get_schema())

# ---------------- SESSION ---------------- #
if "messages" not in st.session_state:
    st.session_state.messages = []

if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- TABS ---------------- #
tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Dashboard", "🧠 History"])

# ---------------- INPUT ---------------- #
col1, col2, col3 = st.columns([1,2,1])

with col2:
    user_input = st.chat_input("Ask your data question...")

st.markdown("### 💡 Try these:")

c1, c2, c3 = st.columns(3)

if c1.button("📌 Top Customers", use_container_width=True):
    user_input = "Top 10 customers by invoices"

if c2.button("📊 Revenue by Country", use_container_width=True):
    user_input = "Revenue by country"

if c3.button("🎵 Top Tracks", use_container_width=True):
    user_input = "Top 10 tracks"


def is_scalar_result(df):
    return not df.empty and len(df) == 1 and len(df.columns) == 1


def build_column_options(df):
    seen = {}
    options = []

    for idx, col in enumerate(df.columns.tolist()):
        seen[col] = seen.get(col, 0) + 1
        label = col if seen[col] == 1 else f"{col} ({seen[col]})"
        options.append({"label": label, "index": idx, "name": col})

    return options


def get_numeric_column_options(df):
    return [
        option for option in build_column_options(df)
        if pd.api.types.is_numeric_dtype(df.iloc[:, option["index"]])
    ]


def get_categorical_column_options(df):
    return [
        option for option in build_column_options(df)
        if pd.api.types.is_object_dtype(df.iloc[:, option["index"]])
        or pd.api.types.is_string_dtype(df.iloc[:, option["index"]])
    ]


def can_render_chart(df):
    if df.empty or len(df) < 2:
        return False

    numeric_options = get_numeric_column_options(df)
    categorical_options = get_categorical_column_options(df)

    return bool(categorical_options and numeric_options)


def build_overview_chart(df):
    if not can_render_chart(df):
        return None

    x_option = get_categorical_column_options(df)[0]
    y_option = get_numeric_column_options(df)[0]

    chart_df = pd.DataFrame(
        {
            x_option["label"]: df.iloc[:, x_option["index"]],
            y_option["label"]: df.iloc[:, y_option["index"]],
        }
    ).dropna()

    if chart_df.empty:
        return None

    return chart_df.set_index(x_option["label"])


# ---------------- SAFE RUN ---------------- #
# ---------------- CHAT TAB ---------------- #
with tab1:
    st.subheader("💬 Chat")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# ---------------- MAIN LOGIC ---------------- #
if user_input:
    question = user_input
    st.session_state.messages.append({"role": "user", "content": question})

    start = time.time()
    sql = ""

    workflow_result = None

    # Stage 1 + 2
    with st.spinner("🧠 Running SQL workflow..."):
        # ✅ USE CSV IF UPLOADED
        if "uploaded_df" in st.session_state:
            st.warning("⚠️ CSV mode: showing raw data (SQL not applied)")
            df = st.session_state.uploaded_df
            cols = df.columns
            rows = df.values
            st.session_state.workflow_trace = []
            st.session_state.workflow_telemetry = {}
            render_workflow_trace()
            render_workflow_telemetry()
        else:
            if run_workflow is None:
                render_workflow_trace()
                render_workflow_telemetry()
                st.error("❌ Workflow is unavailable.")
                st.stop()

            workflow_result = run_workflow(question)
            st.session_state.workflow_trace = workflow_result.get("trace", [])
            st.session_state.workflow_telemetry = workflow_result.get("telemetry", {})
            sql = (workflow_result.get("sql") or "").strip()
            workflow_error = workflow_result.get("error")

            if workflow_error:
                render_workflow_trace()
                render_workflow_telemetry()
                st.error(f"❌ {workflow_error}")
                if sql:
                    st.code(sql, language="sql")
                st.stop()

            cols = workflow_result.get("columns", [])
            rows = workflow_result.get("rows", [])

            if not cols:
                render_workflow_trace()
                render_workflow_telemetry()
                st.warning("⚠️ No columns returned or query failed")
                st.stop()

            df = pd.DataFrame(rows, columns=cols)

    render_workflow_trace()
    render_workflow_telemetry()

    st.success(f"📊 Found {len(df)} rows")

    st.divider()
    st.markdown("### 📊 Insights Dashboard")
    if is_scalar_result(df):
        scalar_col = df.columns[0]
        st.metric(scalar_col, df.iloc[0, 0])
    else:
        overview_chart_df = build_overview_chart(df)
        if overview_chart_df is not None:
            st.bar_chart(overview_chart_df, height=400)
        elif not df.empty:
            st.info("No suitable columns for visualization")
    try:
            exec_time = time.time() - start
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ Query executed successfully. Returned {len(df)} rows."
            })
            # ---------------- DASHBOARD TAB ---------------- #
            with tab2:
                st.subheader("📊 Data Insights")

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("🧾 Generated SQL")
                    st.code(sql, language="sql")

                with col2:
                    st.subheader("📋 Result")

                    # ✅ FIX 5: Debug SQL
                    st.caption("🔍 Debug SQL")
                    st.code(sql, language="sql")

                    # ✅ FIX 3 + 4: Handle empty data safely
                    if df.empty:
                        st.warning("⚠️ No data found for this query")
                    else:
                        st.dataframe(df, use_container_width=True)
                        st.caption(f"Showing {len(df)} rows")
                # KPI CARDS
                c1, c2, c3 = st.columns(3)
                c1.metric("Rows", len(df))
                c2.metric("Columns", len(df.columns))
                c3.metric("Execution Time", f"{exec_time:.2f}s")
                st.caption("📌 Tip: Change X and Y to explore insights")

                # CHART
                numeric_cols = df.select_dtypes(include=["number"]).columns
                cat_cols = df.select_dtypes(include=["object", "string"]).columns

                if is_scalar_result(df):
                    st.subheader("📊 Visualization")
                    st.info("Single-value results are shown as a metric instead of a chart.")
                elif can_render_chart(df):

                    # ✅ KEEP SELECTION STATE
                    if "x_col" not in st.session_state:
                        st.session_state.x_col = None

                    if "y_col" not in st.session_state:
                        st.session_state.y_col = None

                    if "chart_type" not in st.session_state:
                        st.session_state.chart_type = "Bar"

                    st.subheader("📊 Visualization")

                    all_options = build_column_options(df)
                    numeric_options = get_numeric_column_options(df)
                    categorical_options = get_categorical_column_options(df)
                    all_labels = [option["label"] for option in all_options]
                    numeric_labels = [option["label"] for option in numeric_options]
                    option_lookup = {option["label"]: option for option in all_options}

                    c1, c2, c3 = st.columns(3)

                    # X-axis
                    with c1:
                        x_col = st.selectbox(
                            "X-axis",
                            all_labels,
                            index=all_labels.index(st.session_state.x_col) if st.session_state.x_col in all_labels else 0
                        )
                        st.session_state.x_col = x_col

                    # Y-axis
                    with c2:
                        y_options = [label for label in numeric_labels if label != x_col]

                        if y_options:
                            y_col = st.selectbox(
                                "Y-axis",
                                y_options,
                                index=y_options.index(st.session_state.y_col) if st.session_state.y_col in y_options else 0
                            )
                            st.session_state.y_col = y_col
                        else:
                            y_col = None

                    # Chart type
                    with c3:
                        chart_type = st.selectbox(
                            "Chart Type",
                            ["Bar", "Line", "Area"],
                            index=["Bar", "Line", "Area"].index(st.session_state.chart_type)
                        )
                        st.session_state.chart_type = chart_type

                    x_option = option_lookup[x_col]
                    y_option = option_lookup[y_col] if y_col else None

                    # FILTER
                    x_series = df.iloc[:, x_option["index"]]
                    if (
                        pd.api.types.is_object_dtype(x_series)
                        or pd.api.types.is_string_dtype(x_series)
                    ):
                        values = st.multiselect(
                            f"Filter {x_col}",
                            x_series.dropna().unique(),
                            default=x_series.dropna().unique()
                        )
                        filtered_df = df[x_series.isin(values)]
                    else:
                        filtered_df = df

                    # CHART
                    if y_option is not None:
                        chart_df = pd.DataFrame(
                            {
                                x_col: filtered_df.iloc[:, x_option["index"]],
                                y_col: filtered_df.iloc[:, y_option["index"]],
                            }
                        ).dropna()

                        if not chart_df.empty:
                            st.caption(f"Using: {x_col} vs {y_col}")

                            if chart_df[x_col].nunique() == len(chart_df):
                                chart_df = chart_df.set_index(x_col)

                            if chart_type == "Bar":
                                st.bar_chart(chart_df, height=400)
                            elif chart_type == "Line":
                                st.line_chart(chart_df)
                            else:
                                st.area_chart(chart_df)
                        else:
                            st.info("No data for selected columns")
                    else:
                        st.info("No numeric columns available for charting")
                elif not df.empty:
                    st.subheader("📊 Visualization")
                    st.info("This result shape is better viewed as a table.")
            # AI EXPLANATION
                def explain_result():
                    sample = df.head(5).to_string()

                    prompt = f"""
Explain this SQL result in simple terms.

Question:
{question}

Sample:
{sample}
"""
                    res = client.chat.completions.create(
                        model="gpt-4.1-mini",
                        messages=[{"role": "user", "content": prompt}]
                    )
                    return res.choices[0].message.content

                with st.expander("🧠 AI Explanation"):
                    if not df.empty:
                         st.write(explain_result())
                    else:
                        st.info("No data to explain")
                # DOWNLOAD
                st.download_button(
                    "⬇️ Download CSV",
                    df.to_csv(index=False).encode(),
                    "result.csv",
                    "text/csv"
                )

            # ---------------- HISTORY ---------------- #
            st.session_state.history.append({
                "question": question,
                "sql": sql,
                "rows": len(df) if not df.empty else 0
            })

    except Exception as e:
        st.error("Query failed. Try rephrasing.")
        st.code(str(e))
        st.code(sql)  # show failed SQL

# ---------------- HISTORY TAB ---------------- #
with tab3:
    st.subheader("🧠 Query History")

    for h in reversed(st.session_state.history[-10:]):
        st.markdown(f"""
- **Q:** {h['question']}  
- **SQL:** `{h['sql']}`  
- Rows: {h['rows']}
""")

st.markdown("---")

st.markdown("""
<div style='text-align:center; color:gray; font-size:14px;'>
Built with ❤️ using Streamlit + OpenAI <br>
GenAI SQL Assistant • 2026
</div>
""", unsafe_allow_html=True)
