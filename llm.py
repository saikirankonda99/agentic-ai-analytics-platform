from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def generate_sql(question, schema):
    prompt = f"""
You are an expert SQL generator.

Database schema:
{schema}

Rules:
- Return ONLY raw SQL
- Do NOT use markdown (no ```sql)
- Do NOT explain anything
- Use correct column names
- Limit results to 50

User question:
{question}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )

        return response.choices[0].message.content.strip().replace("```sql", "").replace("```", "")

    except Exception as e:
        return f"ERROR: {str(e)}"