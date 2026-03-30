"""Process Order - Admin detailed view for processing a single order."""
import json

import streamlit as st

from utils.auth import require_role
from utils.google_client import get_gspread_client
from utils.orders_store import fetch_all_orders, update_order, update_checklist
from utils.drive_handler import download_file_bytes, download_to_local
from config import ORDER_STATUSES, STATUS_COLORS, IS_LOCAL


user = require_role("admin")

st.title("🔧 Process Order")

orders = fetch_all_orders()
if not orders:
    st.info("No orders to process.")
    st.stop()

# Filter to non-delivered orders by default
active_orders = [o for o in orders if o.get("Status") != "delivered"]

if not active_orders:
    st.success("All orders have been delivered!")
    st.stop()

# --- Visual overview list ---
st.subheader("Active Orders Overview")

status_icons = {"new": "⚪", "processing": "🔵", "ordered": "🟠", "shipped": "🟣", "delivered": "🟢"}
selected_order_id = None

for o in active_orders:
    oid = o.get("OrderID", "?")
    pcb = o.get("PCBName", "?")
    eng = o.get("EngineerName", "")
    s = o.get("Status", "new")
    pri = o.get("Priority", "Normal")
    eta = o.get("ETA", "")
    smt = o.get("SMTRoute", "")
    icon = status_icons.get(s, "⚪")
    pri_icon = "🔴" if pri == "URGENT" else ""

    cols = st.columns([0.5, 3, 1.5, 1.5, 1.5, 1])
    with cols[0]:
        st.markdown(f"{icon}")
    with cols[1]:
        st.markdown(f"**{pcb}** — {eng} {pri_icon}")
    with cols[2]:
        st.markdown(f"`{s.upper()}`")
    with cols[3]:
        st.markdown(f"{smt or '-'}")
    with cols[4]:
        st.markdown(f"ETA: {eta or '-'}")
    with cols[5]:
        if st.button("Open", key=f"open_{oid}"):
            selected_order_id = oid

# Check session state for selected order
if selected_order_id:
    st.session_state["process_order_id"] = selected_order_id

sel_id = st.session_state.get("process_order_id")
if not sel_id:
    st.info("Click **Open** on an order above to process it.")
    st.stop()

# Find the selected order
order = next((o for o in active_orders if o.get("OrderID") == sel_id), None)
if not order:
    st.warning("Selected order not found. It may have been delivered.")
    if st.button("Clear selection"):
        del st.session_state["process_order_id"]
        st.rerun()
    st.stop()

st.markdown("---")
if st.button("⬆ Close Details", key="collapse_btn"):
    del st.session_state["process_order_id"]
    st.rerun()

order_id = order.get("OrderID", "?")
status = order.get("Status", "new")
status_idx = ORDER_STATUSES.index(status) if status in ORDER_STATUSES else 0
status_color = STATUS_COLORS.get(status, "gray")

st.markdown(f"### :{status_color}[{status.upper()}] — {order.get('PCBName', '')}")
st.progress(status_idx / (len(ORDER_STATUSES) - 1))

# --- Status transition ---
st.subheader("Status")
scol1, scol2, scol3 = st.columns(3)
client = get_gspread_client()

if status_idx > 0:
    with scol1:
        prev_status = ORDER_STATUSES[status_idx - 1]
        if st.button(f"⬅ Back to {prev_status.upper()}", width="stretch"):
            if client:
                update_order(client, order_id, {"Status": prev_status})
                st.rerun()

with scol2:
    st.markdown(f"**Current: {status.upper()}**")

if status_idx < len(ORDER_STATUSES) - 1:
    with scol3:
        next_status = ORDER_STATUSES[status_idx + 1]
        if st.button(f"Advance to {next_status.upper()} ➡", type="primary", width="stretch"):
            if client:
                update_order(client, order_id, {"Status": next_status})
                st.rerun()

st.markdown("---")

# --- Order details ---
st.subheader("Order Details")
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**Order ID:** `{order_id}`")
    st.markdown(f"**Engineer:** {order.get('EngineerName', '')} ({order.get('EngineerEmail', '')})")
    st.markdown(f"**Submitted:** {order.get('CreatedAt', '')}")
    st.markdown(f"**PCB Name:** {order.get('PCBName', '')}")
    st.markdown(f"**PCB Type:** {order.get('PCBType', '')}")
    st.markdown(f"**Layers:** {order.get('Layers', '')}")
with col2:
    st.markdown(f"**Thickness:** {order.get('Thickness', '')}")
    st.markdown(f"**Solder Mask:** {order.get('SolderMask', '')}")
    st.markdown(f"**Quantity:** {order.get('Quantity', '')}")
    st.markdown(f"**Priority:** {order.get('Priority', '')}")
    st.markdown(f"**Recipient:** {order.get('Recipient', '')}")
    st.markdown(f"**Needs SMT:** {order.get('NeedsSMT', 'No')}")
    st.markdown(f"**Test by Engineer:** {order.get('TestByEngineer', 'No')}")

st.markdown("---")

# --- File download ---
drive_link = order.get("DriveFileLink", "")
if drive_link:
    st.subheader("📁 Files")
    st.markdown(f"[Open in Google Drive]({drive_link})")

    dcol1, dcol2 = st.columns(2)
    with dcol1:
        if st.button("⬇ Download (Browser)", key="dl_browser"):
            try:
                file_bytes, filename = download_file_bytes(drive_link)
                st.download_button(
                    label=f"Save {filename}",
                    data=file_bytes,
                    file_name=filename,
                    key="dl_btn",
                )
            except Exception as e:
                st.error(f"Download failed: {e}")

    if IS_LOCAL:
        with dcol2:
            if st.button("⬇ Download to Local Folder", key="dl_local"):
                try:
                    created = order.get("CreatedAt", "")
                    order_date = created.split(" ")[0] if created else ""
                    if order_date:
                        local_path = download_to_local(
                            drive_link,
                            order.get("PCBName", "Unknown"),
                            order_date,
                        )
                        st.success(f"Saved to: `{local_path}`")
                    else:
                        st.error("Cannot determine order date for folder path")
                except Exception as e:
                    st.error(f"Local download failed: {e}")

st.markdown("---")

# --- Admin editable fields ---
st.subheader("Processing")
with st.form("process_form"):
    pcol1, pcol2 = st.columns(2)
    with pcol1:
        smt_route = st.selectbox(
            "SMT Route",
            ["", "JLC", "Xinhai (新海)", "Ausinter (奥兴达)", "N/A - Bare Board"],
            index=["", "JLC", "Xinhai (新海)", "Ausinter (奥兴达)", "N/A - Bare Board"].index(
                order.get("SMTRoute", "")
            ) if order.get("SMTRoute", "") in ["", "JLC", "Xinhai (新海)", "Ausinter (奥兴达)", "N/A - Bare Board"] else 0,
        )
        vendor_order = st.text_input("Vendor Order #", value=order.get("VendorOrderNum", ""))
    with pcol2:
        current_eta = order.get("ETA", "")
        try:
            from datetime import datetime
            eta_default = datetime.strptime(current_eta, "%Y-%m-%d").date() if current_eta else None
        except ValueError:
            eta_default = None
        eta_date = st.date_input("ETA (UK)", value=eta_default, key="proc_eta")
        eta = eta_date.strftime("%Y-%m-%d") if eta_date else ""
        notes = st.text_area("Notes", value=order.get("Notes", ""), height=100)

    if st.form_submit_button("Save Processing Info", type="primary"):
        if client:
            updates = {}
            if smt_route != order.get("SMTRoute", ""):
                updates["SMTRoute"] = smt_route
            if vendor_order != order.get("VendorOrderNum", ""):
                updates["VendorOrderNum"] = vendor_order
            if eta != order.get("ETA", ""):
                updates["ETA"] = eta
            if notes != order.get("Notes", ""):
                updates["Notes"] = notes
            if updates:
                update_order(client, order_id, updates)
                st.success("Saved!")
                st.rerun()
            else:
                st.info("No changes to save.")

st.markdown("---")

# --- Checklist ---
st.subheader("Checklist")
try:
    checklist = json.loads(order.get("ChecklistJSON", "[]"))
except (json.JSONDecodeError, TypeError):
    checklist = []

if checklist:
    checklist_changed = False
    for item in checklist:
        new_val = st.checkbox(
            item.get("text", ""),
            value=item.get("done", False),
            key=f"proc_chk_{order_id}_{item.get('id', '')}",
        )
        if new_val != item.get("done", False):
            item["done"] = new_val
            checklist_changed = True

    if checklist_changed:
        if st.button("💾 Save Checklist", type="primary"):
            if client:
                update_checklist(client, order_id, checklist)
                st.success("Checklist saved!")
                st.rerun()
else:
    st.info("No checklist items.")
