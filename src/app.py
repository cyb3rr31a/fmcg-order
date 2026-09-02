import os
import sys
from pathlib import Path
import pandas as pd
import streamlit as st

st.sidebar.header("Active Delivery Policies")

current_dir = Path(__file__).parent
root_dir = current_dir.parent 
policy_path = root_dir / "data" / "delivery_policies.txt"

if policy_path.exists():
    with st.sidebar.expander("View Current RAG Knowledge Base"):
        with open(policy_path, "r", encoding="utf-8") as f:
            st.write(f.read())
else:
    st.sidebar.error(f"Policy file not found at {policy_path.absolute()}")

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from database import SessionLocal
from models import Product, PaymentLedger
from agent_graph import app_graph, AgentState

st.set_page_config(page_title="FMCG WhatsApp Agent", layout="wide")

# --- SIDEBAR: LIVE DATABASE MONITOR ---
st.sidebar.header("Live SQLite Database")

def get_db_data():
    with SessionLocal() as db:
        products = db.query(Product).all()
        ledgers = db.query(PaymentLedger).all()
        
        prod_df = pd.DataFrame([{
            "SKU": p.sku, "Name": p.name, "Stock": p.stock, "Price (KES)": p.price
        } for p in products])
        
        ledger_df = pd.DataFrame([{
            "Code": l.transaction_code, "Amount": l.amount, "Status": l.status
        } for l in ledgers])
        
    return prod_df, ledger_df

prod_df, ledger_df = get_db_data()
st.sidebar.subheader("Inventory Stock")
st.sidebar.dataframe(prod_df, use_container_width=True, hide_index=True)

st.sidebar.subheader("M-Pesa Ledger (Test Codes)")
st.sidebar.dataframe(ledger_df, use_container_width=True, hide_index=True)

# --- CHAT STATE MANAGEMENT ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent_state" not in st.session_state:
    st.session_state.agent_state = AgentState(
        messages=[],
        intent="",
        order=None,
        payment_status="",
        response=""
    )

st.title("FMCG B2B Ordering Agent")
st.caption("Local GLiNER + LangGraph + Daraja M-Pesa Reconciliation")

# Display conversation history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("E.g., 'Nitumie 6 packets of milk' or 'Code is QWE123RTY4'"):
    # Render user prompt
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Prepare LangGraph state
    current_state = st.session_state.agent_state
    current_state["messages"].append(prompt)

    # Process through LangGraph
    with st.spinner("Processing..."):
        result = app_graph.invoke(current_state)

    # Update session state with returned graph state (preserving active order)
    st.session_state.agent_state = result
    bot_reply = result["response"]

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    with st.chat_message("assistant"):
        st.markdown(bot_reply)
        
    # Re-run so the sidebar reflects the new stock immediately
    st.rerun()