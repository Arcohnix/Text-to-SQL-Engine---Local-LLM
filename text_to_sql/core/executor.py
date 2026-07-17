"""
executor.py  —  Safely run the generated SQL on any supported database.
"""
from __future__ import annotations
import re
import pandas as pd


_FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|INSERT|UPDATE|CREATE|REPLACE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _get_connection(cfg: dict):
    db_type = cfg["database"]["type"]

    if db_type == "sqlite":
        import sqlite3
        return sqlite3.connect(cfg["database"]["path"]), "sqlite"

    elif db_type == "postgresql":
        import psycopg2
        conn = psycopg2.connect(
            host=cfg["database"]["host"],
            port=cfg["database"].get("port", 5432),
            dbname=cfg["database"]["name"],
            user=cfg["database"]["user"],
            password=cfg["database"]["password"],
        )
        return conn, "postgresql"

    elif db_type == "mysql":
        import pymysql
        conn = pymysql.connect(
            host=cfg["database"]["host"],
            port=cfg["database"].get("port", 3306),
            database=cfg["database"]["name"],
            user=cfg["database"]["user"],
            password=cfg["database"]["password"],
        )
        return conn, "mysql"

    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def run_query(sql: str, cfg: dict) -> tuple[pd.DataFrame | None, str | None]:
    """
    Execute sql and return (DataFrame, None) on success,
    or (None, error_message) on failure.
    """
    readonly = cfg.get("app", {}).get("readonly", True)
    max_rows = cfg.get("app", {}).get("max_rows", 500)

    if readonly and _FORBIDDEN.search(sql):
        match = _FORBIDDEN.search(sql)
        return None, f"Query blocked: contains forbidden keyword '{match.group()}'. Only SELECT is allowed."

    if not re.search(r"\bSELECT\b", sql, re.IGNORECASE):
        return None, "Query does not appear to be a SELECT statement."

    try:
        conn, db_type = _get_connection(cfg)
        df = pd.read_sql_query(sql, conn)
        conn.close()

        if len(df) > max_rows:
            df = df.head(max_rows)
            note = f"(Results capped at {max_rows} rows)"
        else:
            note = None

        return df, note

    except Exception as e:
        return None, str(e)
