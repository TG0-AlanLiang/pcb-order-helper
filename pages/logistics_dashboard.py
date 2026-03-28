"""Logistics Dashboard - Jimmy's dedicated page for receiving and shipping PCBs."""
import streamlit as st
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import fetch_pcb_delivery, update_delivery_cell
from utils.orders_store import fetch_all_orders


user = require_auth()

st.title("📦 Logistics Dashboard")
st.markdown(f"Welcome, **{user['name']}**")

client = get_gspread_client()
if not client:
    st.error("Cannot connect to Google Sheets.")
    st.stop()

# Fetch PCB Delivery data
deliveries = fetch_pcb_delivery(client)

if not deliveries:
    st.info("No delivery records found.")
    st.stop()

# --- Summary metrics ---
pending_receipt = [d for d in deliveries if not d.get("Jimmy received check", "").strip()]
ready_to_ship = [d for d in deliveries
                 if d.get("Jimmy received check", "").strip()
                 and not d.get("Jimmy Shipp out remark", "").strip()]
shipped = [d for d in deliveries
           if d.get("Jimmy received check", "").strip()
           and d.get("Jimmy Shipp out remark", "").strip()]

col1, col2, col3 = st.columns(3)
col1.metric("Pending Receipt", len(pending_receipt))
col2.metric("Ready to Ship", len(ready_to_ship))
col3.metric("Shipped", len(shipped))

st.markdown("---")

# ============================================================
# A. PENDING RECEIPT
# ============================================================
st.header("📥 Pending Receipt")

if not pending_receipt:
    st.success("All items received!")
else:
    for d in pending_receipt[:20]:  # Limit to recent 20
        num = d.get("Number", "?")
        pcb = d.get("PCB Name", "Unknown")
        vendor = d.get("vendor Order number", "")
        priority = d.get("Piority", "Normal")
        order_date = d.get("Order date", "")
        recipient = d.get("Recipient", "")

        priority_icon = "🔴" if priority == "URGENT" else "🟢"

        with st.container():
            c1, c2, c3 = st.columns([4, 3, 2])
            with c1:
                st.markdown(f"{priority_icon} **#{num}** — {pcb}")
                if vendor:
                    st.caption(f"Vendor: {vendor}")
            with c2:
                st.caption(f"Ordered: {order_date} | To: {recipient}")
            with c3:
                if st.button("✅ Mark Received", key=f"recv_{num}"):
                    try:
                        today = datetime.now().strftime("%Y-%m-%d")
                        update_delivery_cell(client, int(num), "Jimmy Received", today)
                        st.success(f"#{num} marked received!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
            st.divider()

# ============================================================
# B. READY TO SHIP
# ============================================================
st.header("📤 Ready to Ship")

if not ready_to_ship:
    st.success("Nothing waiting to ship!")
else:
    for d in ready_to_ship:
        num = d.get("Number", "?")
        pcb = d.get("PCB Name", "Unknown")
        received = d.get("Jimmy received check", "")
        recipient = d.get("Recipient", "")
        priority = d.get("Piority", "Normal")

        priority_icon = "🔴" if priority == "URGENT" else "🟢"

        with st.expander(f"{priority_icon} **#{num}** — {pcb} | Received: {received} | To: {recipient}", expanded=True):
            remark = st.text_area(
                "Shipping remark (tracking number, destination, notes)",
                key=f"ship_{num}",
                placeholder="e.g. SF1562763341561\n5 to 杭州临平区乔司街道天\nThe rest to UK Shaoze",
                height=100,
            )
            if st.button("📦 Mark Shipped", key=f"ship_btn_{num}", type="primary"):
                if remark.strip():
                    try:
                        update_delivery_cell(client, int(num), "Jimmy Ship Remark", remark.strip())
                        st.success(f"#{num} shipped!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
                else:
                    st.warning("Please enter shipping remark before marking as shipped.")

# ============================================================
# C. SHIPPED (Recent)
# ============================================================
st.header("✅ Recently Shipped")

if not shipped:
    st.info("No shipped items yet.")
else:
    # Show most recent 10
    for d in shipped[:10]:
        num = d.get("Number", "?")
        pcb = d.get("PCB Name", "Unknown")
        received = d.get("Jimmy received check", "")
        remark = d.get("Jimmy Shipp out remark", "")
        recipient = d.get("Recipient", "")

        with st.expander(f"✅ #{num} — {pcb} | To: {recipient}", expanded=False):
            st.markdown(f"**Received:** {received}")
            st.markdown(f"**Ship Remark:** {remark}")

# ============================================================
# D. MATERIAL TRANSFER (from Orders tab)
# ============================================================
st.markdown("---")
st.header("🔄 Material Transfer")
st.caption("Orders that need parts forwarded to SMT vendors")

orders = fetch_all_orders()
smt_orders = [o for o in orders
              if o.get("NeedsSMT") == "Yes"
              and o.get("Status") in ("processing", "ordered")]

if not smt_orders:
    st.info("No material transfers pending.")
else:
    for o in smt_orders:
        order_id = o.get("OrderID", "?")
        pcb = o.get("PCBName", "Unknown")
        smt_route = o.get("SMTRoute", "Not decided")
        engineer = o.get("EngineerName", "")
        status = o.get("Status", "")

        with st.container():
            mc1, mc2 = st.columns([3, 2])
            with mc1:
                st.markdown(f"**{pcb}** (Order: `{order_id}`)")
                st.markdown(f"Engineer: {engineer} | Status: {status.upper()}")
            with mc2:
                st.markdown(f"**SMT Route:** {smt_route or 'TBD'}")
                if smt_route:
                    st.caption(f"Forward parts to: {smt_route}")
                else:
                    st.caption("Waiting for Alan to decide SMT route")
            st.divider()
