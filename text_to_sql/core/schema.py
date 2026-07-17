"""
schema.py  —  Auto-discover schema from any connected database.
Supports: SQLite · PostgreSQL · MySQL
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    dtype: str
    nullable: bool = True
    primary_key: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)

    def to_sql_ddl(self) -> str:
        """Return a CREATE TABLE statement for use in LLM prompts."""
        col_parts = []
        for c in self.columns:
            part = f"  {c.name} {c.dtype}"
            if c.primary_key:
                part += " PRIMARY KEY"
            if not c.nullable:
                part += " NOT NULL"
            col_parts.append(part)
        return f"CREATE TABLE {self.name} (\n" + ",\n".join(col_parts) + "\n);"


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


def discover(cfg: dict) -> list[Table]:
    """Return a list of Table objects describing the live database schema."""
    conn, db_type = _get_connection(cfg)
    cur = conn.cursor()
    tables = []

    if db_type == "sqlite":
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        table_names = [row[0] for row in cur.fetchall()]
        for tname in table_names:
            cur.execute(f"PRAGMA table_info({tname});")
            rows = cur.fetchall()
            # cid, name, type, notnull, dflt_value, pk
            cols = [
                Column(
                    name=r[1],
                    dtype=r[2] or "TEXT",
                    nullable=not r[3],
                    primary_key=bool(r[5]),
                )
                for r in rows
            ]
            tables.append(Table(name=tname, columns=cols))

    elif db_type == "postgresql":
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name;
        """)
        table_names = [row[0] for row in cur.fetchall()]
        for tname in table_names:
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = %s ORDER BY ordinal_position;
            """, (tname,))
            rows = cur.fetchall()
            # fetch primary keys
            cur.execute("""
                SELECT kcu.column_name FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY';
            """, (tname,))
            pks = {r[0] for r in cur.fetchall()}
            cols = [
                Column(name=r[0], dtype=r[1], nullable=(r[2] == "YES"), primary_key=r[0] in pks)
                for r in rows
            ]
            tables.append(Table(name=tname, columns=cols))

    elif db_type == "mysql":
        cur.execute("SELECT DATABASE();")
        db_name = cur.fetchone()[0]
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s ORDER BY table_name;
        """, (db_name,))
        table_names = [row[0] for row in cur.fetchall()]
        for tname in table_names:
            cur.execute("""
                SELECT column_name, column_type, is_nullable, column_key
                FROM information_schema.columns
                WHERE table_name = %s AND table_schema = %s
                ORDER BY ordinal_position;
            """, (tname, db_name))
            rows = cur.fetchall()
            cols = [
                Column(name=r[0], dtype=r[1], nullable=(r[2] == "YES"), primary_key=(r[3] == "PRI"))
                for r in rows
            ]
            tables.append(Table(name=tname, columns=cols))

    conn.close()
    return tables


def build_prompt_context(tables: list[Table]) -> str:
    """Return a compact schema string ready to paste into an LLM prompt."""
    return "\n\n".join(t.to_sql_ddl() for t in tables)


def get_table_names(tables: list[Table]) -> list[str]:
    return [t.name for t in tables]
