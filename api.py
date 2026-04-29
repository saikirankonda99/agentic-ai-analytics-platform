from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
import os

from db import run_query, get_schema
from guardrails import is_safe_sql
from llm import generate_sql

app = FastAPI()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------- REQUEST MODEL ---------------- #
class QueryRequest(BaseModel):
    question: str


# ---------------- SAFE RUN ---------------- #
def safe_run(sql, schema):
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
        return run_query(fixed_sql)


# ---------------- MAIN ENDPOINT ---------------- #
@app.post("/query")
def query_data(req: QueryRequest):
    question = req.question

    schema = get_schema()
    sql = generate_sql(question, schema)

    if not is_safe_sql(sql):
        return {"error": "Unsafe SQL detected"}

    try:
        cols, rows = safe_run(sql, schema)

        return {
            "question": question,
            "sql": sql,
            "columns": cols,
            "rows": rows,
            "count": len(rows)
        }

    except Exception as e:
        return {"error": str(e)}


# ---------------- HEALTH CHECK ---------------- #
@app.get("/")
def root():
    return {"status": "API running"}