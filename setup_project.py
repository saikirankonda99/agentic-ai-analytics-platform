import os

base = "genai-sql-assistant"

folders = [
    "evals",
    "logs",
    "data"
]

files = {
    "app.py": """import streamlit as st
from llm import generate_sql
from db import run_query
from guardrails import validate_sql

st.title("GenAI SQL Assistant")

question = st.text_input("Ask a question")

if question:
    sql = generate_sql(question)
    st.subheader("Generated SQL")
    st.code(sql, language="sql")

    try:
        validate_sql(sql)
        result = run_query(sql)
        st.subheader("Result")
        st.write(result)
    except Exception as e:
        st.error(f"Error: {e}")
""",

    "llm.py": """import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SCHEMA = "Tables will be added later"

def generate_sql(question):
    prompt = f\"\"\"
You are a SQL expert.

Schema:
{SCHEMA}

Rules:
- Only return SQL
- No explanation

Question:
{question}
\"\"\"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()
""",

    "db.py": """import sqlite3

DB_PATH = "data/chinook.db"

def run_query(sql):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(sql)
    rows = cursor.fetchall()
    conn.close()
    return rows
""",

    "guardrails.py": """FORBIDDEN = ["DROP", "DELETE", "UPDATE", "INSERT"]

def validate_sql(sql):
    sql_upper = sql.upper()
    for word in FORBIDDEN:
        if word in sql_upper:
            raise ValueError("Unsafe query detected")
    return True
""",

    "evals/eval.py": """print("Eval script placeholder")""",

    "evals/dataset.json": "[]",

    "logs/query_logs.json": "",

    ".env": "OPENAI_API_KEY=your_key_here",

    "requirements.txt": """streamlit
openai
pandas
python-dotenv
sqlite-utils
""",

    "README.md": """# GenAI SQL Assistant

Production-grade Text-to-SQL system with evaluation pipeline.
"""
}

# Create base directory
os.makedirs(base, exist_ok=True)

# Create folders
for folder in folders:
    os.makedirs(os.path.join(base, folder), exist_ok=True)

# Create files
for path, content in files.items():
    full_path = os.path.join(base, path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

print("✅ Project structure created successfully!")