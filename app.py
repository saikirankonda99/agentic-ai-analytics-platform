import streamlit as st
import pandas as pd
import time

from db import get_schema
from openai import OpenAI

try:
    from graph.workflow import run_workflow
except Exception:
    run_workflow = None

# ---------------- CONFIG ---------------- #
st.set_page_config(
    page_title="GenAI SQL Assistant",
    layout="wide",
    page_icon="📊"
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

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


def can_render_chart(df):
    if df.empty or len(df) < 2:
        return False

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    return bool((numeric_cols and cat_cols) or len(numeric_cols) >= 2)


def build_overview_chart(df):
    if not can_render_chart(df):
        return None

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    if numeric_cols and cat_cols:
        chart_df = df[[cat_cols[0], numeric_cols[0]]].dropna()
        if chart_df.empty:
            return None
        return chart_df.set_index(cat_cols[0])

    chart_df = df[numeric_cols].dropna()
    if chart_df.empty or len(chart_df.columns) < 2:
        return None

    return chart_df.set_index(numeric_cols[0])


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
            render_workflow_trace()
        else:
            if run_workflow is None:
                render_workflow_trace()
                st.error("❌ Workflow is unavailable.")
                st.stop()

            workflow_result = run_workflow(question)
            st.session_state.workflow_trace = workflow_result.get("trace", [])
            sql = (workflow_result.get("sql") or "").strip()
            workflow_error = workflow_result.get("error")

            if workflow_error:
                render_workflow_trace()
                st.error(f"❌ {workflow_error}")
                if sql:
                    st.code(sql, language="sql")
                st.stop()

            cols = workflow_result.get("columns", [])
            rows = workflow_result.get("rows", [])

            if not cols:
                render_workflow_trace()
                st.warning("⚠️ No columns returned or query failed")
                st.stop()

            df = pd.DataFrame(rows, columns=cols)

    render_workflow_trace()

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

                    all_cols = df.columns.tolist()
                    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                    cat_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

                    c1, c2, c3 = st.columns(3)

                    # X-axis
                    with c1:
                        x_col = st.selectbox(
                            "X-axis",
                            all_cols,
                            index=all_cols.index(st.session_state.x_col) if st.session_state.x_col in all_cols else 0
                        )
                        st.session_state.x_col = x_col

                    # Y-axis
                    with c2:
                        y_options = [c for c in numeric_cols if c != x_col]

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

                    # Handle single numeric column
                    if len(numeric_cols) == 1:
                        y_col = numeric_cols[0]

                    # FILTER
                    if x_col in cat_cols:
                        values = st.multiselect(
                            f"Filter {x_col}",
                            df[x_col].dropna().unique(),
                            default=df[x_col].dropna().unique()
                        )
                        filtered_df = df[df[x_col].isin(values)]
                    else:
                        filtered_df = df

                    # CHART
                    if y_col:
                        chart_df = filtered_df[[x_col, y_col]].dropna()

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
