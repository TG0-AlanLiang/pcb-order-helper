"""All Orders - Admin dashboard showing all PCB orders."""
import json
from datetime import datetime, date

import streamlit as st

from utils.auth import require_role
from utils.google_client import get_gspread_client
from utils.orders_store import (
    fetch_all_orders, update_order,
    sync_order_to_delivery, ensure_delivery_for_order,
)
from utils.message_store import fetch_messages_for_order, send_message
from config import ORDER_STATUSES, STATUS_COLORS, CNY_TO_GBP


user = require_role("admin")

st.title("📊 All Orders")
st.caption("Delivered orders are moved to **Order History** — see sidebar.")

all_orders = fetch_all_orders()
# Exclude delivered orders (they're in Order History page)
orders = [o for o in all_orders if o.get("Status") != "delivered"]
if not orders:
    st.info("No active orders. Check Order History for delivered orders.")
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

# Sort: URGENT first, then newest first within same priority
filtered.sort(key=lambda o: (
    0 if o.get("Priority") == "URGENT" else 1,
    "9999" if not o.get("CreatedAt") else o.get("CreatedAt"),
), reverse=False)
# Within each priority group, reverse by date (newest first)
urgent = [o for o in filtered if o.get("Priority") == "URGENT"]
normal = [o for o in filtered if o.get("Priority") != "URGENT"]
urgent.sort(key=lambda o: o.get("CreatedAt", ""), reverse=True)
normal.sort(key=lambda o: o.get("CreatedAt", ""), reverse=True)
filtered = urgent + normal

st.markdown(f"**{len(filtered)} orders** shown")
st.markdown("---")

# --- Order cards ---
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

    with st.expander(header, expanded=False):
        # Info row (display only)
        info1, info2 = st.columns(2)
        with info1:
            st.markdown(f"**ID:** `{order_id}`")
            st.markdown(f"**Engineer:** {engineer}")
            reviewer_name = order.get("Reviewer", "")
            if reviewer_name:
                st.markdown(f"**Reviewer:** {reviewer_name}")
            st.markdown(f"**Recipient:** {order.get('Recipient', 'N/A')}")
            st.markdown(f"**Submitted:** {created}")
        with info2:
            st.markdown(f"**Layers:** {order.get('Layers', 'N/A')}")
            st.markdown(f"**Thickness:** {order.get('Thickness', 'N/A')}")
            st.markdown(f"**Solder Mask:** {order.get('SolderMask', 'N/A')}")
            st.markdown(f"**Needs SMT:** {'Yes' if needs_smt else 'No'}")

        # File link
        drive_link = order.get("DriveFileLink", "")
        if drive_link:
            st.markdown(f"📁 [View files on Drive]({drive_link})")

        # Cost display
        def _to_f(v):
            try: return float(str(v).strip()) if str(v).strip() else 0.0
            except (ValueError, TypeError): return 0.0
        bare_c = _to_f(order.get("BareBoardCostCNY", ""))
        bom_c = _to_f(order.get("BOMCostCNY", ""))
        smt_c = _to_f(order.get("SMTCostCNY", ""))
        total_cny = bare_c + bom_c + smt_c
        if total_cny > 0:
            total_gbp = total_cny * CNY_TO_GBP
            st.markdown(f"💰 **Cost:** Bare ¥{bare_c:.0f} + BOM ¥{bom_c:.0f} + SMT ¥{smt_c:.0f} = **¥{total_cny:,.2f} CNY (£{total_gbp:,.2f} GBP)**")

        st.progress(pct)

        # --- Edit form (no rerun until Save) ---
        current_eta = order.get("ETA", "")
        try:
            eta_default = datetime.strptime(current_eta, "%Y-%m-%d").date() if current_eta else None
        except ValueError:
            eta_default = None

        with st.form(f"editform_{order_id}"):
            ef1, ef2 = st.columns(2)
            with ef1:
                new_smt = st.text_input("SMT Route", value=order.get("SMTRoute", ""), key=f"smt_{order_id}")
                new_vendor = st.text_input("Vendor Order #", value=order.get("VendorOrderNum", ""), key=f"vendor_{order_id}")
                new_eta_date = st.date_input("ETA", value=eta_default, key=f"eta_{order_id}")
            with ef2:
                st.markdown("**Checklist:**")
                new_done = []
                for j, item in enumerate(checklist):
                    new_done.append(st.checkbox(
                        item.get("text", ""),
                        value=item.get("done", False),
                        key=f"chk_{order_id}_{item.get('id', j)}",
                    ))
            new_notes = st.text_area("Notes", value=order.get("Notes", ""), key=f"notes_{order_id}", height=160)
            saved = st.form_submit_button("💾 Save Changes", type="primary")

        if saved and client:
            new_eta = new_eta_date.strftime("%Y-%m-%d") if new_eta_date else ""
            payload = {}
            if new_smt != order.get("SMTRoute", ""):
                payload["SMTRoute"] = new_smt
            if new_vendor != order.get("VendorOrderNum", ""):
                payload["VendorOrderNum"] = new_vendor
            if new_eta != current_eta:
                payload["ETA"] = new_eta
            if new_notes != order.get("Notes", ""):
                payload["Notes"] = new_notes
            cl_changed = False
            for item, v in zip(checklist, new_done):
                if v != item.get("done", False):
                    item["done"] = v
                    cl_changed = True
            if cl_changed:
                payload["ChecklistJSON"] = json.dumps(checklist, ensure_ascii=False)
            if payload:
                update_order(client, order_id, payload)
                # Keep the linked PCB Delivery row in sync (ETA / vendor / SMT)
                if any(k in payload for k in ("ETA", "VendorOrderNum", "SMTRoute")):
                    try:
                        sync_order_to_delivery(client, order, new_vendor, new_smt, new_eta)
                    except Exception as e:
                        st.warning(f"Delivery sync failed: {e}")
                st.success("Saved!")
            st.rerun()

        # --- Messages ---
        st.markdown("**💬 Messages:**")
        messages = fetch_messages_for_order(order_id)
        if messages:
            for m in messages:
                author = m.get("Author", "")
                ts = m.get("Timestamp", "")
                content = m.get("Content", "")
                prefix = "🟢" if author == user["name"] else "🔵"
                st.markdown(f"{prefix} **{author}** ({ts}): {content}")
        else:
            st.caption("No messages.")

        with st.form(f"msgform_{order_id}", clear_on_submit=True):
            new_msg = st.text_input("Message", key=f"msg_{order_id}",
                                    placeholder="Ask engineer or leave note...",
                                    label_visibility="collapsed")
            sent = st.form_submit_button("Send")
        if sent and new_msg.strip() and client:
            send_message(client, order_id, user["name"], new_msg.strip())
            st.rerun()

        # --- Status action buttons (single-click, outside forms) ---
        st.markdown("**Actions:**")
        btn_col2, btn_col3 = st.columns(2)

        STATUS_ACTIONS = {
            "new": ("🔧 Start Processing", "processing"),
            "processing": ("📦 Mark as Ordered", "ordered"),
            "ordered": ("🚚 Mark as Shipped", "shipped"),
            "shipped": ("✅ Mark as Delivered", "delivered"),
        }

        if status in STATUS_ACTIONS:
            label, next_status = STATUS_ACTIONS[status]
            with btn_col2:
                if st.button(label, key=f"advance_{order_id}"):
                    if client:
                        if next_status == "ordered":
                            # Combine the status flip with the delivery linkage
                            # into one update_order write.
                            try:
                                num = ensure_delivery_for_order(
                                    client, order,
                                    order.get("VendorOrderNum", ""),
                                    order.get("SMTRoute", ""),
                                    order.get("ETA", ""),
                                    extra_order_updates={"Status": "ordered"},
                                )
                                st.toast(f"PCB Delivery #{num} ready!")
                            except Exception as e:
                                st.warning(f"PCB Delivery write failed: {e}")
                        else:
                            update_order(client, order_id, {"Status": next_status})

                        st.rerun()

        if status != "new":
            status_idx = ORDER_STATUSES.index(status) if status in ORDER_STATUSES else 0
            prev_status = ORDER_STATUSES[status_idx - 1]
            with btn_col3:
                if st.button(f"↩ Revert to {prev_status}", key=f"revert_{order_id}"):
                    if client:
                        update_order(client, order_id, {"Status": prev_status})
                        st.rerun()
