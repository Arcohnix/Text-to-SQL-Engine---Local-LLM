"""
llm.py  —  Talk to Ollama. Auto-detects installed models.
"""
from __future__ import annotations
import requests


def list_installed_models(base_url: str) -> list[str]:
    """Return models currently installed in Ollama on this machine."""
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception as e:
        return []


def is_ollama_running(base_url: str) -> bool:
    try:
        requests.get(f"{base_url}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def generate_sql(
    question: str,
    schema_context: str,
    db_type: str,
    model: str,
    base_url: str,
    history: list[dict] | None = None,
) -> str:
    """
    Send the user question + live schema to the local LLM.
    Returns raw LLM output (SQL + maybe explanation).
    """
    dialect_hint = {
        "sqlite": "SQLite",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
    }.get(db_type, "SQL")

    system_prompt = f"""You are an expert {dialect_hint} query writer.
Given a database schema and a user question, write a correct {dialect_hint} SELECT query.

Rules:
- Return ONLY the SQL query, nothing else — no markdown, no explanation.
- Use only table and column names that exist in the schema.
- Never use DROP, DELETE, INSERT, UPDATE, ALTER, or TRUNCATE.
- Use proper JOINs when data spans multiple tables.
- For aggregations (totals, averages, counts), always use GROUP BY appropriately.
- Limit results to 100 rows unless the user specifies otherwise.

Schema:
{schema_context}"""

    messages = [{"role": "system", "content": system_prompt}]

    # Include conversation history for follow-up questions
    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": question})

    resp = requests.post(
        f"{base_url}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def extract_sql(raw_output: str) -> str:
    """
    Strip markdown fences and explanation text from LLM output,
    returning just the SQL query.
    """
    import re

    # Strip ```sql ... ``` or ``` ... ``` blocks
    fence = re.search(r"```(?:sql)?\s*(.*?)```", raw_output, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()

    # If no fence, take first SELECT statement found
    lines = raw_output.splitlines()
    sql_lines = []
    capturing = False
    for line in lines:
        upper = line.strip().upper()
        if upper.startswith("SELECT") or upper.startswith("WITH"):
            capturing = True
        if capturing:
            sql_lines.append(line)

    if sql_lines:
        return "\n".join(sql_lines).strip()

    # Fallback: return as-is
    return raw_output.strip()
