"""All Orders - Admin dashboard showing all PCB orders."""
import json

import streamlit as st

from utils.auth import require_role
from utils.google_client import get_gspread_client
from utils.orders_store import fetch_all_orders, update_order, update_checklist
from config import ORDER_STATUSES, STATUS_COLORS


user = require_role("admin")

st.title("📊 All Orders")

orders = fetch_all_orders()
if not orders:
    st.info("No orders yet.")
    st.stop()

# --- Summary metrics ---
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
for col, status in zip([col_m1, col_m2, col_m3, col_m4, col_m5], ORDER_STATUSES):
    count = sum(1 for o in orders if o.get("Status") == status)
    col.metric(status.upper(), count)

st.markdown("---")

# --- Filters ---
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    status_filter = st.selectbox("Status", ["all"] + ORDER_STATUSES, index=0)
with col_f2:
    priority_filter = st.selectbox("Priority", ["all", "URGENT", "Normal"])
with col_f3:
    engineers = sorted(set(o.get("EngineerName", "") for o in orders if o.get("EngineerName")))
    engineer_filter = st.selectbox("Engineer", ["all"] + engineers)

# Filter
filtered = orders
if status_filter != "all":
    filtered = [o for o in filtered if o.get("Status") == status_filter]
if priority_filter != "all":
    filtered = [o for o in filtered if o.get("Priority") == priority_filter]
if engineer_filter != "all":
    filtered = [o for o in filtered if o.get("EngineerName") == engineer_filter]

# Sort: URGENT first, then by date
filtered.sort(key=lambda o: (
    0 if o.get("Priority") == "URGENT" else 1,
    o.get("CreatedAt", ""),
))
filtered.reverse()

st.markdown(f"**{len(filtered)} orders** shown")
st.markdown("---")

# --- Order cards ---
changed = False
client = get_gspread_client()

for order in filtered:
    order_id = order.get("OrderID", "?")
    pcb_name = order.get("PCBName", "Unknown")
    status = order.get("Status", "new")
    priority = order.get("Priority", "Normal")
    engineer = order.get("EngineerName", "")
    pcb_type = order.get("PCBType", "Rigid")
    quantity = order.get("Quantity", "")
    created = order.get("CreatedAt", "")
    needs_smt = order.get("NeedsSMT", "No") == "Yes"

    # Parse checklist
    try:
        checklist = json.loads(order.get("ChecklistJSON", "[]"))
    except (json.JSONDecodeError, TypeError):
        checklist = []

    done_count = sum(1 for c in checklist if c.get("done"))
    total_count = len(checklist) or 1
    pct = done_count / total_count

    priority_icon = "🔴" if priority == "URGENT" else "🟢"
    type_icon = "🔵 FPC" if pcb_type == "FPC" else "⬜ Rigid"
    status_color = STATUS_COLORS.get(status, "gray")

    header = (
        f"{priority_icon} **{pcb_name}** | {type_icon} | Qty: {quantity} | "
        f"👤 {engineer} | :{status_color}[{status.upper()}] | {pct:.0%} done"
    )

    with st.expander(header, expanded=(status not in ["delivered", "shipped"])):
        # Info row
        info1, info2, info3 = st.columns(3)
        with info1:
            st.markdown(f"**ID:** `{order_id}`")
            st.markdown(f"**Engineer:** {engineer}")
            st.markdown(f"**Recipient:** {order.get('Recipient', 'N/A')}")
            st.markdown(f"**Submitted:** {created}")
        with info2:
            st.markdown(f"**Layers:** {order.get('Layers', 'N/A')}")
            st.markdown(f"**Thickness:** {order.get('Thickness', 'N/A')}")
            st.markdown(f"**Solder Mask:** {order.get('SolderMask', 'N/A')}")
            st.markdown(f"**Needs SMT:** {'Yes' if needs_smt else 'No'}")
        with info3:
            # Editable fields
            new_smt = st.text_input("SMT Route", value=order.get("SMTRoute", ""), key=f"smt_{order_id}")
            new_vendor = st.text_input("Vendor Order #", value=order.get("VendorOrderNum", ""), key=f"vendor_{order_id}")
            new_eta = st.text_input("ETA", value=order.get("ETA", ""), key=f"eta_{order_id}")

        # File link
        drive_link = order.get("DriveFileLink", "")
        if drive_link:
            st.markdown(f"📁 [View files on Drive]({drive_link})")

        # Progress bar
        st.progress(pct)

        # Checklist
        st.markdown("**Checklist:**")
        checklist_changed = False
        for j, item in enumerate(checklist):
            new_val = st.checkbox(
                item.get("text", ""),
                value=item.get("done", False),
                key=f"chk_{order_id}_{item.get('id', j)}",
            )
            if new_val != item.get("done", False):
                item["done"] = new_val
                checklist_changed = True

        # Notes
        new_notes = st.text_area("Notes", value=order.get("Notes", ""), key=f"notes_{order_id}", height=80)

        # Save changes button
        updates_pending = {}
        if new_smt != order.get("SMTRoute", ""):
            updates_pending["SMTRoute"] = new_smt
        if new_vendor != order.get("VendorOrderNum", ""):
            updates_pending["VendorOrderNum"] = new_vendor
        if new_eta != order.get("ETA", ""):
            updates_pending["ETA"] = new_eta
        if new_notes != order.get("Notes", ""):
            updates_pending["Notes"] = new_notes

        # Action buttons
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

        if updates_pending or checklist_changed:
            with btn_col1:
                if st.button("💾 Save Changes", key=f"save_{order_id}", type="primary"):
                    if client and updates_pending:
                        update_order(client, order_id, updates_pending)
                    if client and checklist_changed:
                        update_checklist(client, order_id, checklist)
                    st.success("Saved!")
                    st.rerun()

        # Status transition buttons
        status_idx = ORDER_STATUSES.index(status) if status in ORDER_STATUSES else 0
        if status_idx < len(ORDER_STATUSES) - 1:
            next_status = ORDER_STATUSES[status_idx + 1]
            with btn_col2:
                if st.button(f"→ {next_status.upper()}", key=f"next_{order_id}"):
                    if client:
                        update_order(client, order_id, {"Status": next_status})
                        st.rerun()

        if status_idx > 0:
            prev_status = ORDER_STATUSES[status_idx - 1]
            with btn_col3:
                if st.button(f"← {prev_status.upper()}", key=f"prev_{order_id}"):
                    if client:
                        update_order(client, order_id, {"Status": prev_status})
                        st.rerun()
