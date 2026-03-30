"""Sheet Update page - Auto-generate and write Google Sheet entries."""
import streamlit as st
import pandas as pd
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_role
from utils.google_client import get_gspread_client
from utils.sheet_handler import (
    get_next_component_id,
    get_next_delivery_number,
    add_component_rows,
    add_delivery_row,
    add_stock_entry,
)
from utils.orders_store import fetch_all_orders

require_role("admin")

st.title("📝 Google Sheet Update")

# Check connection
client = get_gspread_client()
if not client:
    st.error("Google Sheets not configured. Check service_account.json.")
    st.stop()

# --- Select order ---
st.header("1. Select Order")
all_orders = fetch_all_orders()
active_orders = [o for o in all_orders if o.get("Status") not in ["delivered", ""]]

if not active_orders:
    st.info("No active orders. Create one in **New Order** or **Submit Order** first.")
    st.stop()

order_labels = [f"{o.get('PCBName', '?')} ({o.get('OrderID', '?')}) - {o.get('EngineerName', '')}" for o in active_orders]
selected_idx = st.selectbox("Order", range(len(order_labels)), format_func=lambda i: order_labels[i])
order_record = active_orders[selected_idx]

# Map order record fields to the names used below
order = {
    "pcb_name": order_record.get("PCBName", ""),
    "quantity": int(order_record.get("Quantity", 0) or 0),
    "priority": order_record.get("Priority", "Normal"),
    "recipient": order_record.get("Recipient", ""),
    "engineer": order_record.get("EngineerName", ""),
}
project = {
    "vendor_order_number": order_record.get("VendorOrderNum", ""),
    "eta": order_record.get("ETA", ""),
}

st.markdown(f"**PCB:** {order.get('pcb_name')} | **Qty:** {order.get('quantity')} | **Priority:** {order.get('priority')}")

# === PCB Delivery Tab ===
st.header("2. PCB Delivery Entry")

try:
    next_num = get_next_delivery_number(client)
except Exception as e:
    st.warning(f"Could not fetch next delivery number: {e}")
    next_num = 1

with st.form("delivery_form"):
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        d_number = st.number_input("Number", value=next_num)
        d_order_date = st.date_input("Order Date", value=datetime.now())
        d_priority = st.text_input("Priority", value=order.get("priority", "Normal"))
        d_pcb_name = st.text_input("PCB Name", value=order.get("pcb_name", ""))
    with d_col2:
        d_vendor_order = st.text_input("Vendor Order Number", value=project.get("vendor_order_number", ""))
        d_recipient = st.text_input("Recipient", value=order.get("recipient", ""))
        d_eta = st.text_input("ETA (UK)", value=project.get("eta", ""))

    # Preview
    delivery_row = [
        d_number,
        d_order_date.strftime("%Y-%m-%d"),
        d_priority,
        d_pcb_name,
        d_vendor_order,
        "",  # Photo
        d_recipient,
        "",  # Jimmy received
        "",  # Jimmy ship remark
        d_eta,
    ]

    st.markdown("**Preview:**")
    preview_df = pd.DataFrame([delivery_row], columns=[
        "Number", "Order Date", "Priority", "PCB Name", "Vendor Order #",
        "Photo", "Recipient", "Jimmy Received", "Jimmy Ship Remark", "ETA (UK)",
    ])
    st.dataframe(preview_df, width="stretch")

    if st.form_submit_button("Write to PCB Delivery", type="primary"):
        try:
            add_delivery_row(client, delivery_row)
            st.success("Written to PCB Delivery tab!")
            st.warning("Remember: Please paste the PCB photo manually in Google Sheet (Photo column)")
        except Exception as e:
            st.error(f"Failed to write: {e}")

# === AllComponents Tab ===
st.header("3. AllComponents Entries")
st.markdown("Add component rows for this order. Fill in one row at a time or upload from BOM Check.")

try:
    next_id = get_next_component_id(client)
except Exception as e:
    st.warning(f"Could not fetch next ID: {e}")
    next_id = 1

with st.form("component_form"):
    c_col1, c_col2, c_col3 = st.columns(3)
    with c_col1:
        c_id = st.number_input("ID", value=next_id)
        c_date = st.date_input("Record Date", value=datetime.now(), key="comp_date")
        c_priority = st.text_input("Priority", value=order.get("priority", "Normal"), key="comp_priority")
        c_pcb_name = st.text_input("PCB Name", value=order.get("pcb_name", ""), key="comp_pcb")
    with c_col2:
        c_component = st.text_input("Component", key="comp_name")
        c_count = st.number_input("Count (designator count)", value=1, min_value=1, key="comp_count")
        c_mpn = st.text_input("MPN", key="comp_mpn")
        c_bom_qty = st.number_input("BOM Quantity", value=0, key="comp_bom_qty")
    with c_col3:
        c_order_qty = st.number_input("Order Quantity", value=0, key="comp_order_qty")
        c_price = st.text_input("Unit Price (CNY)", key="comp_price")
        c_supplier = st.text_input("Supplier", key="comp_supplier")
        c_status = st.selectbox("Status", [
            "To Order", "Ordered", "DeliveredToVendor", "From Stock",
            "Delivered", "In Transit", "Pending",
        ], key="comp_status")

    component_row = [
        c_id,
        c_date.strftime("%Y-%m-%d"),
        c_priority,
        c_pcb_name,
        c_component,
        c_count,
        c_mpn,
        c_bom_qty,
        c_order_qty,
        c_price,
        "",  # Category
        "",  # JLC SMT Order
        order.get("quantity", 0),  # PCB Quantity
        c_supplier,
        "",  # Component source
        c_status,
        c_date.strftime("%Y-%m-%d"),  # Order date
        "",  # ETD
        order.get("engineer", ""),  # Point of contact
        "",  # Notes
    ]

    st.markdown("**Preview:**")
    st.json({
        "ID": c_id, "Date": c_date.strftime("%Y-%m-%d"), "Priority": c_priority,
        "PCB": c_pcb_name, "Component": c_component, "MPN": c_mpn,
        "BOM Qty": c_bom_qty, "Order Qty": c_order_qty, "Status": c_status,
    })

    if st.form_submit_button("Write to AllComponents", type="primary"):
        try:
            add_component_rows(client, [component_row])
            st.success("Written to AllComponents tab!")
        except Exception as e:
            st.error(f"Failed to write: {e}")

# === Stock Tab (Special Sourcing Only) ===
st.header("4. Stock - New MPN (Special Sourcing Only)")
st.markdown("Only add MPNs that need special sourcing/ordering. LCSC-available or supplier-sourced parts don't need to be added.")

with st.form("stock_form"):
    s_col1, s_col2 = st.columns(2)
    with s_col1:
        s_mpn = st.text_input("Component MPN", key="stock_mpn")
        s_specs = st.text_input("Specs/Description", key="stock_specs")
    with s_col2:
        s_project = st.text_input("Project", value=order.get("pcb_name", ""), key="stock_project")
        s_note = st.text_input("Note", key="stock_note")

    if st.form_submit_button("Add to Stock"):
        if s_mpn:
            try:
                add_stock_entry(client, s_mpn, s_specs, s_project, s_note)
                st.success(f"Added MPN `{s_mpn}` to Stock tab!")
            except Exception as e:
                st.error(f"Failed to write: {e}")
        else:
            st.warning("Please enter an MPN.")
