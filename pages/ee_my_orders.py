"""My Orders - EE view of their own submitted orders."""
import json

import streamlit as st

from utils.auth import require_auth, is_admin
from utils.orders_store import fetch_all_orders, fetch_orders_by_engineer
from config import ORDER_STATUSES, STATUS_COLORS


user = require_auth()

st.title("📦 My Orders")
st.markdown(f"Viewing orders for: **{user['name']}** ({user['email']})")

# Admin can see all orders here too (filtered by dropdown)
if is_admin(user):
    orders = fetch_all_orders()
    st.info(f"Admin view - showing all {len(orders)} orders")
else:
    orders = fetch_orders_by_engineer(user["email"])

if not orders:
    st.info("No orders found. Go to **Submit Order** to create one.")
    st.stop()

# Sort: non-delivered first, then by creation date descending
def sort_key(o):
    status = o.get("Status", "new")
    is_done = 1 if status == "delivered" else 0
    return (is_done, o.get("CreatedAt", ""))

orders.sort(key=sort_key)
orders.reverse()  # Most recent first within each group, but delivered at bottom
# Fix: delivered should be at the bottom
delivered = [o for o in orders if o.get("Status") == "delivered"]
active = [o for o in orders if o.get("Status") != "delivered"]
orders = active + delivered

for order in orders:
    order_id = order.get("OrderID", "?")
    pcb_name = order.get("PCBName", "Unknown")
    status = order.get("Status", "new")
    priority = order.get("Priority", "Normal")
    created = order.get("CreatedAt", "")
    pcb_type = order.get("PCBType", "Rigid")
    quantity = order.get("Quantity", "")
    engineer = order.get("EngineerName", "")

    # Status badge
    status_idx = ORDER_STATUSES.index(status) if status in ORDER_STATUSES else 0
    progress_pct = status_idx / (len(ORDER_STATUSES) - 1)

    priority_icon = "🔴" if priority == "URGENT" else "🟢"
    type_icon = "🔵 FPC" if pcb_type == "FPC" else "⬜ Rigid"

    header = f"{priority_icon} **{pcb_name}** | {type_icon} | Qty: {quantity} | :{STATUS_COLORS.get(status, 'gray')}[{status.upper()}]"
    if is_admin(user):
        header += f" | 👤 {engineer}"

    with st.expander(header, expanded=(status != "delivered")):
        # Progress bar
        st.progress(progress_pct)

        # Status timeline
        status_line = ""
        for i, s in enumerate(ORDER_STATUSES):
            if i == status_idx:
                status_line += f" **→ {s.upper()} ←** "
            elif i < status_idx:
                status_line += f" ~~{s}~~ >"
            else:
                status_line += f" {s} >"
        st.markdown(status_line.rstrip(">").rstrip())

        # Details
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Order ID:** `{order_id}`")
            st.markdown(f"**Submitted:** {created}")
            st.markdown(f"**Engineer:** {engineer}")
        with col2:
            st.markdown(f"**Layers:** {order.get('Layers', 'N/A')}")
            st.markdown(f"**Thickness:** {order.get('Thickness', 'N/A')}")
            st.markdown(f"**Solder Mask:** {order.get('SolderMask', 'N/A')}")
        with col3:
            eta = order.get("ETA", "")
            vendor = order.get("VendorOrderNum", "")
            smt_route = order.get("SMTRoute", "")
            st.markdown(f"**ETA:** {eta or 'Pending'}")
            st.markdown(f"**Vendor Order #:** {vendor or 'Pending'}")
            st.markdown(f"**SMT Route:** {smt_route or 'N/A'}")

        # Recipient
        recipient = order.get("Recipient", "")
        if recipient:
            st.markdown(f"**Recipient:** {recipient}")

        # Notes from admin
        notes = order.get("Notes", "")
        if notes:
            st.markdown(f"**Notes:** {notes}")

        # File link
        drive_link = order.get("DriveFileLink", "")
        if drive_link:
            st.markdown(f"📁 [View uploaded files on Google Drive]({drive_link})")
