import streamlit as st
import sqlite3

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "chinook.db")


# ---------------- RUN QUERY ---------------- #
@st.cache_data(show_spinner=False)
@st.cache_data(ttl=600)
def run_query(sql):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(sql)

            rows = cursor.fetchall()
            cols = [desc[0] for desc in cursor.description]

        return cols, rows

    except Exception as e:
        raise Exception(f"Database error: {e}")


# ---------------- GET SCHEMA ---------------- #
@st.cache_data(show_spinner=False)
def get_schema():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            )
            tables = cursor.fetchall()

            schema = []

            for table in tables:
                table_name = table[0]

                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()

                col_defs = ", ".join(
                    [f"{col[1]} ({col[2]})" for col in columns]
                )

                schema.append(f"Table: {table_name}\n{col_defs}")

        return "\n\n".join(schema)

    except Exception as e:
        return f"Schema error: {e}"