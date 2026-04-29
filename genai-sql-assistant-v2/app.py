import streamlit as st
import pandas as pd
import time

from llm import generate_sql
from db import run_query, get_schema
from guardrails import is_safe_sql
from openai import OpenAI

# ---------------- CONFIG ---------------- #
st.set_page_config(
    page_title="GenAI SQL Assistant",
    layout="wide",
    page_icon="📊"
)

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------------- STYLE ---------------- #
st.markdown("""
<style>
.stMetric {
    background-color: #0e1117;
    padding: 12px;
    border-radius: 10px;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ---------------- #
st.markdown("# 📊 GenAI SQL Assistant")
st.caption("🚀 AI-powered Data Analyst")
st.divider()

# ---------------- SIDEBAR ---------------- #
with st.sidebar:
    st.title("⚙️ Settings")

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
user_input = st.chat_input("Ask your data question...")
# ✅ ADD HERE (EXACT)
st.markdown("### 💡 Try these:")

c1, c2, c3 = st.columns(3)

if c1.button("Top customers"):
    user_input = "Top customers by spending"

if c2.button("Invoices summary"):
    user_input = "Show total invoices by country"

if c3.button("Track analysis"):
    user_input = "Top tracks by sales"
# ---------------- SAFE RUN ---------------- #
def safe_run(sql, question, schema):
    try:
        return run_query(sql)
    except Exception as e:
        fix_prompt = f"""
Fix this SQL query.

Schema:
{schema}

Broken SQL:
{sql}

Error:
{str(e)}

Return ONLY corrected SQL.
"""
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": fix_prompt}],
            temperature=0
        )

        fixed_sql = response.choices[0].message.content.strip()
        fixed_sql = fixed_sql.replace("```sql", "").replace("```", "").strip()

        return run_query(fixed_sql)

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
    schema = get_schema()

    # Stage 1: Generate SQL
    with st.spinner("🧠 Generating SQL..."):

        history_text = "\n".join([
            f"{m['role']}: {m['content']}"
            for m in st.session_state.messages[-5:]
        ])

        prompt = f"""
    You are an expert SQL assistant.

    Conversation:
    {history_text}

    User Question:
    {question}

    Database Schema:
    {schema}

    Generate ONLY SQL query.
    """

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        sql = response.choices[0].message.content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

    # Stage 2
    with st.spinner("🗄️ Running query..."):

        # ✅ USE CSV IF UPLOADED
        if "uploaded_df" in st.session_state:
            df = st.session_state.uploaded_df.query(sql)
            cols = df.columns
            rows = df.values
        else:
            cols, rows = safe_run(sql, question, schema)

    # ✅ Stage 3: Prepare Data
    with st.spinner("📊 Preparing results..."):
        df = pd.DataFrame(rows, columns=cols)

    # ✅ AFTER SPINNER (EXACT PLACE)
    st.success(f"✅ Query returned {len(df)} rows")
    st.session_state.messages.append({
    "role": "assistant",
    "content": f"📊 Found {len(df)} rows. Check dashboard for insights."
    })

    st.divider()
    st.subheader("📊 Quick Visualization")

    if not df.empty:
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        cat_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

        if numeric_cols and cat_cols:
            chart_df = df[[cat_cols[0], numeric_cols[0]]].dropna().set_index(cat_cols[0])
            st.bar_chart(chart_df)
        else:
            st.info("No suitable columns for visualization")

    # ✅ safety check OUTSIDE
    if not is_safe_sql(sql):
        st.error("Unsafe query blocked")

    # ✅ NOW TRY BLOCK (correct position)
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
                        st.warning("⚠️ Query returned no data")
                    else:
                        st.dataframe(df, width="stretch")

                # KPI CARDS
                c1, c2, c3 = st.columns(3)
                c1.metric("Rows", len(df))
                c2.metric("Columns", len(df.columns))
                c3.metric("Execution Time", f"{exec_time:.2f}s")
                st.caption("📌 Tip: Change X and Y to explore insights")

                # CHART
                numeric_cols = df.select_dtypes(include=["number"]).columns
                cat_cols = df.select_dtypes(include=["object", "string"]).columns

                if not df.empty:
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
                            chart_df = chart_df.set_index(x_col)

                            st.caption(f"Using: {x_col} vs {y_col}")

                            if chart_type == "Bar":
                                st.bar_chart(chart_df)
                            elif chart_type == "Line":
                                st.line_chart(chart_df)
                            else:
                                st.area_chart(chart_df)
                        else:
                            st.info("No data for selected columns")
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