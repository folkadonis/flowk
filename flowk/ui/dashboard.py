import streamlit as st
import sqlite3
import json
import os

st.set_page_config(page_title="Flowk Dashboard", page_icon="🌊", layout="wide")

st.title("🌊 Flowk Observability Dashboard")
st.markdown("Monitor your autonomous agents and workflows locally. Zero vendor lock-in.")

# Connect to the local SQLite memory store
db_path = os.getenv("FLOWK_DB_PATH", "flowk_memory.db")

st.sidebar.header("Configuration")
db_input = st.sidebar.text_input("Database Path", db_path)

try:
    with sqlite3.connect(db_input) as conn:
        sessions = conn.execute("SELECT id, state FROM sessions").fetchall()
        
    if not sessions:
        st.info("No recorded storage sessions found. Run a Flowk Graph with `checkpoint_db` configured.")
    else:
        st.sidebar.subheader("Active Sessions")
        session_id = st.sidebar.selectbox("Select Session to Debug", [s[0] for s in sessions])
        
        # Find selected state
        selected_state = next(json.loads(s[1]) for s in sessions if s[0] == session_id)
        
        st.header(f"Session Trace: `{session_id}`")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Global Graph State")
            st.json(selected_state)
            
        with col2:
            st.subheader("Time Machine Actions")
            if st.button("🗑️ Delete Session"):
                with sqlite3.connect(db_input) as c:
                    c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                st.success("Session deleted successfully.")
                st.rerun()
                
            st.markdown("*(Future functionality: Re-run node from specific state modification)*")

except sqlite3.OperationalError:
    st.warning(f"Could not connect to `{db_input}`. Ensure your Flowk agents are running and saving to this path.")
except Exception as e:
    st.error(f"Error reading local state: {e}")
