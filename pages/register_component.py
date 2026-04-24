"""Register Component - Quick form for anyone to log a component to AllComponents."""
import streamlit as st
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import get_next_component_id, add_component_rows, fetch_stock_data, add_stock_entry


user = require_auth()

st.title("📋 Register Component")
st.markdown(f"Logged in as: **{user['name']}**")
st.markdown("Register a component that needs to be sourced, ordered, or forwarded through Jimmy.")

client = get_gspread_client()
if not client:
    st.error("Cannot connect to Google Sheets.")
    st.stop()

try:
    next_id = get_next_component_id(client)
except Exception:
    next_id = 1

with st.form("register_component"):
    st.subheader("Component Details")

    col1, col2 = st.columns(2)
    with col1:
        pcb_name = st.text_input("PCB Name *", placeholder="e.g. EZ1_Main_revC")
        component = st.text_input("Component (Designator)", placeholder="e.g. U2, M1, C5")
        mpn = st.text_input("MPN *", placeholder="e.g. IQS7222C101QNR")
        bom_qty = st.number_input("BOM Quantity", min_value=0, value=0)

    with col2:
        order_qty = st.number_input("Order Quantity", min_value=0, value=0)
        priority = st.selectbox("Priority", ["Normal", "URGENT"])
        category = st.selectbox("Category", ["IC", "Mechanical", "Connector", "Passive", "Other"])
        supplier = st.text_input("Supplier & Destination",
                                 placeholder="e.g. Send to Xinhai, Keep in stock, Send all to JLC")

    st.subheader("Source & Notes")
    col3, col4 = st.columns(2)
    with col3:
        component_source = st.selectbox("Component Source", [
            "From Stock",
            "From UK",
            "From JLC",
            "To Order",
        ], help="Where is this component coming from?")
    with col4:
        notes = st.text_input("Notes (optional)", placeholder="e.g. Order from DigiKey, Lead time 2 weeks")

    submitted = st.form_submit_button("Register Component", type="primary")

if submitted:
    if not pcb_name.strip() or not mpn.strip():
        st.error("PCB Name and MPN are required!")
        st.stop()

    # Build AllComponents row (21 columns A-U)
    row = [
        next_id,                                    # A: ID
        datetime.now().strftime("%Y-%m-%d"),         # B: Record Date
        priority,                                   # C: Priority
        pcb_name.strip(),                           # D: PCB Name
        component.strip(),                          # E: Components
        "",                                         # F: Count
        mpn.strip(),                                # G: MPN
        bom_qty,                                    # H: BOM Quantity
        order_qty,                                  # I: Order Quantity
        "",                                         # J: Unit Price
        category,                                   # K: Category
        "",                                         # L: JLC SMT Order
        "",                                         # M: PCB Quantity
        supplier.strip(),                           # N: Supplier & Obj
        component_source,                           # O: Component source
        "To Order",                                 # P: Status (default, Jimmy changes this)
        datetime.now().strftime("%Y-%m-%d"),         # Q: Order date
        "",                                         # R: ETD
        user["name"],                               # S: Point of contact
        notes.strip(),                              # T: Notes (Jimmy fills tracking/storage)
        user["name"],                               # U: Registor
    ]

    try:
        add_component_rows(client, [row])
        st.success(f"Component registered! ID: **{next_id}** — {mpn.strip()} for {pcb_name.strip()}")

        # Auto-add MPN to Stock tab if not already there
        try:
            stock_data = fetch_stock_data(client)
            existing_mpns = set()
            for s in stock_data:
                stock_mpn = str(s.get("Component MPN", "") or s.get(list(s.keys())[0] if s else "", "")).strip()
                if stock_mpn:
                    existing_mpns.add(stock_mpn.upper())

            mpn_clean = mpn.strip()
            if mpn_clean.upper() not in existing_mpns:
                add_stock_entry(client, mpn_clean, specs=component.strip(),
                                project=pcb_name.strip(), note=f"Auto-added by {user['name']}")
                st.info(f"MPN `{mpn_clean}` was not in Stock tab — auto-added!")
            else:
                st.caption(f"MPN `{mpn_clean}` already exists in Stock tab.")
        except Exception as e:
            st.warning(f"Component registered but Stock check failed: {e}")

        st.balloons()
    except Exception as e:
        st.error(f"Failed to register: {e}")
