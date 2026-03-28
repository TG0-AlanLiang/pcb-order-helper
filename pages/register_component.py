"""Register Component - Quick form for anyone to log a component to AllComponents."""
import streamlit as st
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import get_next_component_id, add_component_rows


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
        supplier = st.text_input("Supplier", placeholder="e.g. Mouser, DigiKey, Taobao")

    st.subheader("Forwarding Info")
    col3, col4 = st.columns(2)
    with col3:
        status = st.selectbox("Status", [
            "To Order",
            "Ordered",
            "In Transit",
            "Delivered to Jimmy",
            "Forwarded to Vendor",
            "From Stock",
        ])
    with col4:
        notes = st.text_input("Notes", placeholder="e.g. Forward to Xinhai after received")

    submitted = st.form_submit_button("Register Component", type="primary")

if submitted:
    if not pcb_name.strip() or not mpn.strip():
        st.error("PCB Name and MPN are required!")
        st.stop()

    # Build AllComponents row (20 columns A-T)
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
        supplier.strip(),                           # N: Supplier
        "",                                         # O: Component source
        status,                                     # P: Status
        datetime.now().strftime("%Y-%m-%d"),         # Q: Order date
        "",                                         # R: ETD
        user["name"],                               # S: Point of contact
        notes.strip(),                              # T: Notes
    ]

    try:
        add_component_rows(client, [row])
        st.success(f"Component registered! ID: **{next_id}** — {mpn.strip()} for {pcb_name.strip()}")
        st.balloons()
    except Exception as e:
        st.error(f"Failed to register: {e}")
