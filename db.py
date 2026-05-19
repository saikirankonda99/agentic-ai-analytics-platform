import streamlit as st

from backend.connectors import get_connector_registry


# ---------------- RUN QUERY ---------------- #
@st.cache_data(show_spinner=False)
@st.cache_data(ttl=600)
def run_query(sql):
    try:
        return get_connector_registry().get("sqlite").execute_read(sql)

    except Exception as e:
        raise Exception(f"Database error: {e}")


# ---------------- GET SCHEMA ---------------- #
@st.cache_data(show_spinner=False)
def get_schema():
    try:
        return get_connector_registry().get("sqlite").inspect_schema().get("schema_text", "")

    except Exception as e:
        return f"Schema error: {e}"
