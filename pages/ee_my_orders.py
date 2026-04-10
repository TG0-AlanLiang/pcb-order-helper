"""My Orders - EE view of their own submitted orders."""
import json

import streamlit as st

from utils.auth import require_auth, is_admin
from utils.google_client import get_gspread_client
from utils.orders_store import fetch_all_orders, fetch_orders_by_engineer, update_order
from utils.drive_handler import upload_file
from utils.message_store import fetch_messages_for_order, send_message
from config import ORDER_STATUSES, STATUS_COLORS


user = require_auth()

st.title("📦 My Orders")
st.markdown(f"Viewing orders for: **{user['name']}** ({user['email']})")

# Admin can see all orders here too
if is_admin(user):
    orders = fetch_all_orders()
    st.info(f"Admin view - showing all {len(orders)} orders")
else:
    orders = fetch_orders_by_engineer(user["email"])

if not orders:
    st.info("No orders found. Go to **Submit Order** to create one.")
    st.stop()

# Sort: non-delivered first, then by creation date descending
delivered = [o for o in orders if o.get("Status") == "delivered"]
active = [o for o in orders if o.get("Status") != "delivered"]
active.sort(key=lambda o: o.get("CreatedAt", ""), reverse=True)
delivered.sort(key=lambda o: o.get("CreatedAt", ""), reverse=True)
orders = active + delivered

client = get_gspread_client()

for order in orders:
    order_id = order.get("OrderID", "?")
    pcb_name = order.get("PCBName", "Unknown")
    status = order.get("Status", "new")
    priority = order.get("Priority", "Normal")
    created = order.get("CreatedAt", "")
    pcb_type = order.get("PCBType", "Rigid")
    quantity = order.get("Quantity", "")
    engineer = order.get("EngineerName", "")
    engineer_email = order.get("EngineerEmail", "")

    status_idx = ORDER_STATUSES.index(status) if status in ORDER_STATUSES else 0
    progress_pct = status_idx / (len(ORDER_STATUSES) - 1)

    priority_icon = "🔴" if priority == "URGENT" else "🟢"
    type_icon = "🔵 FPC" if pcb_type == "FPC" else "⬜ Rigid"

    header = f"{priority_icon} **{pcb_name}** | {type_icon} | Qty: {quantity} | :{STATUS_COLORS.get(status, 'gray')}[{status.upper()}]"
    if is_admin(user):
        header += f" | 👤 {engineer}"

    with st.expander(header, expanded=False):
        st.progress(progress_pct)

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

        recipient = order.get("Recipient", "")
        if recipient:
            st.markdown(f"**Recipient:** {recipient}")

        notes = order.get("Notes", "")
        if notes:
            st.markdown(f"**Notes:** {notes}")

        # File link
        drive_link = order.get("DriveFileLink", "")
        if drive_link:
            st.markdown(f"📁 [View uploaded files on Google Drive]({drive_link})")

        # --- Actions: Re-upload + Delete ---
        # Only owner or admin can act
        can_act = is_admin(user) or (engineer_email.lower() == user["email"].lower())

        if can_act:
            st.markdown("---")
            act1, act2 = st.columns(2)

            # Re-upload file
            with act1:
                new_file = st.file_uploader(
                    "Re-upload file",
                    type=["rar", "zip", "7z"],
                    key=f"reupload_{order_id}",
                )
                if new_file and st.button("📤 Upload", key=f"upload_btn_{order_id}"):
                    try:
                        file_bytes = new_file.read()
                        new_link = upload_file(
                            file_bytes=file_bytes,
                            filename=new_file.name,
                            pcb_name=pcb_name,
                        )
                        if client:
                            update_order(client, order_id, {"DriveFileLink": new_link})
                        st.success(f"File updated: {new_file.name}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

            # Delete order (only if status is "new")
            with act2:
                if status == "new":
                    st.warning("Delete this order?")
                    if st.button("🗑 Delete Order", key=f"delete_{order_id}"):
                        try:
                            if client:
                                update_order(client, order_id, {"Status": "cancelled"})
                            st.success(f"Order {order_id} cancelled.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                elif status != "delivered" and status != "cancelled":
                    st.caption("Order already in progress — contact Alan to cancel.")

        # --- Messages ---
        st.markdown("---")
        st.markdown("**💬 Messages**")
        messages = fetch_messages_for_order(order_id)
        if messages:
            for m in messages:
                author = m.get("Author", "")
                ts = m.get("Timestamp", "")
                content = m.get("Content", "")
                is_me = author == user["name"]
                prefix = "🟢" if is_me else "🔵"
                st.markdown(f"{prefix} **{author}** ({ts}): {content}")
        else:
            st.caption("No messages yet.")

        new_msg = st.text_input("Type a message...", key=f"msg_input_{order_id}",
                                placeholder="Ask a question or leave a note")
        if st.button("Send", key=f"msg_send_{order_id}"):
            if new_msg.strip() and client:
                send_message(client, order_id, user["name"], new_msg.strip())
                st.rerun()

        # --- Reorder button ---
        st.markdown("---")
        if st.button("🔄 Reorder (same specs)", key=f"reorder_{order_id}"):
            st.session_state["reorder_data"] = {
                "pcb_name": pcb_name,
                "pcb_type": pcb_type,
                "layers": order.get("Layers", "2"),
                "thickness": order.get("Thickness", "1.6mm"),
                "solder_mask": order.get("SolderMask", "Green"),
                "quantity": quantity,
                "priority": priority,
                "recipient": recipient,
                "needs_smt": order.get("NeedsSMT", "No") == "Yes",
                "notes": order.get("Notes", ""),
            }
            st.info("Order specs copied! Go to **Submit Order** to complete the reorder.")
            st.switch_page("pages/ee_submit_order.py")
