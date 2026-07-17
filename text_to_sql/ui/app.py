"""
app.py  —  Streamlit UI for Text-to-SQL (fully dynamic, zero hardcoding)
Run:  streamlit run ui/app.py
"""
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from core import config, schema, llm, executor

# ── Page setup ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Text to SQL",
    page_icon="🗄️",
    layout="wide",
)

st.title("🗄️ Text to SQL — Local LLM")
st.caption("Ask questions in plain English. SQL is generated and executed automatically.")

# ── Load config ─────────────────────────────────────────────────────────────
@st.cache_resource
def load_config():
    return config.load()

try:
    cfg = load_config()
except FileNotFoundError as e:
    st.error(f"**config.yaml not found.** {e}")
    st.stop()

# ── Sidebar: connection & model info ─────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    db_type = cfg["database"]["type"]
    base_url = cfg["llm"]["base_url"]

    # Database status
    st.subheader("Database")
    if db_type == "sqlite":
        db_path = cfg["database"]["path"]
        exists = Path(db_path).exists()
        if exists:
            st.success(f"✅ SQLite  ·  `{Path(db_path).name}`")
        else:
            st.error(f"❌ File not found: `{db_path}`")
            st.stop()
    else:
        st.info(f"🔌 {db_type.upper()}  ·  {cfg['database'].get('host')}:{cfg['database'].get('port')}/{cfg['database'].get('name')}")

    # LLM / Ollama status
    st.subheader("LLM (Ollama)")
    ollama_ok = llm.is_ollama_running(base_url)
    if ollama_ok:
        installed = llm.list_installed_models(base_url)
        if installed:
            selected_model = st.selectbox(
                "Model",
                options=installed,
                index=installed.index(cfg["llm"]["model"]) if cfg["llm"]["model"] in installed else 0,
            )
            st.success(f"✅ Ollama running  ·  {len(installed)} model(s)")
        else:
            st.warning("Ollama is running but no models found. Run `ollama pull llama3`.")
            st.stop()
    else:
        st.error("❌ Ollama not reachable. Start it with `ollama serve`.")
        selected_model = cfg["llm"]["model"]
        st.stop()

    # Schema overview
    st.subheader("Schema")
    try:
        tables = schema.discover(cfg)
        if tables:
            for t in tables:
                with st.expander(f"📋 {t.name}  ({len(t.columns)} cols)"):
                    for c in t.columns:
                        pk_badge = " 🔑" if c.primary_key else ""
                        st.markdown(f"`{c.name}` — *{c.dtype}*{pk_badge}")
        else:
            st.warning("No tables found in the database.")
    except Exception as e:
        st.error(f"Schema error: {e}")
        st.stop()

    st.divider()
    st.caption(f"readonly: `{cfg['app']['readonly']}`  ·  max rows: `{cfg['app']['max_rows']}`")

# ── Main: conversation ────────────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []   # list of {role, content, sql, df, error}

schema_context = schema.build_prompt_context(tables)

# Render past Q&A
for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        if turn.get("sql"):
            with st.expander("📝 Generated SQL"):
                st.code(turn["sql"], language="sql")
        if turn.get("df") is not None:
            if turn.get("note"):
                st.caption(turn["note"])
            st.dataframe(turn["df"], use_container_width=True)
        if turn.get("error"):
            st.error(turn["error"])

# Input
question = st.chat_input("Ask a question about your data…")

if question:
    # Show user message
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.history.append({"role": "user", "content": question})

    # Build conversation history for the LLM (only text turns)
    llm_history = [
        {"role": h["role"], "content": h["content"]}
        for h in st.session_state.history[:-1]  # exclude current question
        if h["role"] in ("user", "assistant")
    ]

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL…"):
            try:
                raw = llm.generate_sql(
                    question=question,
                    schema_context=schema_context,
                    db_type=db_type,
                    model=selected_model,
                    base_url=base_url,
                    history=llm_history,
                )
                sql = llm.extract_sql(raw)
            except Exception as e:
                st.error(f"LLM error: {e}")
                st.stop()

        with st.expander("📝 Generated SQL", expanded=True):
            st.code(sql, language="sql")

        df, err_or_note = executor.run_query(sql, cfg)

        note = None
        error = None
        if df is not None:
            # err_or_note here is a cap note, not a real error
            if err_or_note:
                note = err_or_note
                st.caption(note)
            st.dataframe(df, use_container_width=True)
            reply = f"Found **{len(df)} row(s)**."
        else:
            error = err_or_note
            st.error(error)
            reply = f"Query failed: {error}"

        st.markdown(reply)

    st.session_state.history.append({
        "role": "assistant",
        "content": reply,
        "sql": sql,
        "df": df,
        "note": note,
        "error": error,
    })
