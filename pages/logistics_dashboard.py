"""Logistics Dashboard - Jimmy's dedicated page for receiving and shipping PCBs."""
import streamlit as st
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import fetch_pcb_delivery, update_delivery_cell
from utils.orders_store import fetch_all_orders


def _get(d: dict, key: str, default: str = "") -> str:
    """Get value from dict, trying exact key first then stripped key match."""
    val = d.get(key, None)
    if val is not None:
        return str(val).strip()
    # Try matching with stripped keys (handles trailing spaces in Sheet headers)
    for k, v in d.items():
        if k.strip() == key.strip():
            return str(v).strip()
    return default


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

# --- Categorize ---
pending_receipt = [d for d in deliveries if not _get(d, "Jimmy received check")]
ready_to_ship = [d for d in deliveries
                 if _get(d, "Jimmy received check")
                 and not _get(d, "Jimmy Shipp out remark")]
shipped = [d for d in deliveries
           if _get(d, "Jimmy received check")
           and _get(d, "Jimmy Shipp out remark")]

# --- Summary metrics ---
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
    for i, d in enumerate(pending_receipt[:20]):
        num = _get(d, "Number", "?")
        pcb = _get(d, "PCB Name", "N/A")
        vendor = _get(d, "vendor Order number")
        priority = _get(d, "Piority", "Normal")
        order_date = _get(d, "Order date")
        recipient = _get(d, "Recipient")

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
                if st.button("✅ Mark Received", key=f"recv_{num}_{i}"):
                    try:
                        today = datetime.now().strftime("%Y-%m-%d")
                        update_delivery_cell(client, int(num), "Jimmy received check", today)
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
    for i, d in enumerate(ready_to_ship):
        num = _get(d, "Number", "?")
        pcb = _get(d, "PCB Name", "N/A")
        received = _get(d, "Jimmy received check")
        recipient = _get(d, "Recipient")
        priority = _get(d, "Piority", "Normal")

        priority_icon = "🔴" if priority == "URGENT" else "🟢"

        with st.expander(f"{priority_icon} **#{num}** — {pcb} | Received: {received} | To: {recipient}", expanded=True):
            remark = st.text_area(
                "Shipping remark (tracking number, destination, notes)",
                key=f"logship_remark_{num}_{i}",
                placeholder="e.g. SF1562763341561\n5 to 杭州临平区乔司街道天\nThe rest to UK Shaoze",
                height=100,
            )
            if st.button("📦 Mark Shipped", key=f"logship_btn_{num}_{i}", type="primary"):
                if remark.strip():
                    try:
                        update_delivery_cell(client, int(num), "Jimmy Shipp out remark", remark.strip())
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
    for i, d in enumerate(shipped[:10]):
        num = _get(d, "Number", "?")
        pcb = _get(d, "PCB Name", "N/A")
        received = _get(d, "Jimmy received check")
        remark = _get(d, "Jimmy Shipp out remark")
        recipient = _get(d, "Recipient")

        with st.expander(f"✅ #{num} — {pcb} | To: {recipient}", expanded=False):
            st.markdown(f"**Received:** {received}")
            st.markdown(f"**Ship Remark:** {remark}")

# ============================================================
# D. COMPONENT TRACKING (from AllComponents tab)
# ============================================================
st.markdown("---")
st.header("🔄 Component Tracking")
st.caption("Components from AllComponents that still need action")

from utils.sheet_handler import fetch_all_components, update_component_cell

components = fetch_all_components(client)

# Filter: only show components with active statuses
ACTIVE_STATUSES = {"To Order", "Ordered", "In Transit"}
active_components = [
    c for c in components
    if c.get("Status", "").strip() in ACTIVE_STATUSES
]

ALL_STATUSES = ["To Order", "Ordered", "In Transit", "Recieved", "DeliveredToVendor", "From Stock", "Cancelled"]
SOURCES = ["", "From Stock", "From UK", "LCSC", "Taobao", "DigiKey", "Mouser", "Supplier"]

if not active_components:
    st.success("No pending components!")
else:
    st.markdown(f"**{len(active_components)} components** need attention")

    for target_status in ["To Order", "Ordered", "In Transit"]:
        group = [c for c in active_components if c.get("Status", "").strip() == target_status]
        if not group:
            continue

        status_icons = {"To Order": "🔴", "Ordered": "🟠", "In Transit": "🚚"}
        icon = status_icons.get(target_status, "⚪")

        st.markdown(f"### {icon} {target_status} ({len(group)})")
        for idx, c in enumerate(group):
            cid = c.get("ID", "?")
            pcb = c.get("PCB Name", "").strip() if c.get("PCB Name") else "N/A"
            mpn = c.get("MPN", "").strip() if c.get("MPN") else "N/A"
            comp = c.get("Components", "").strip() if c.get("Components") else ""
            supplier = c.get("Supplier & Obj", "").strip() if c.get("Supplier & Obj") else ""
            notes = c.get("Notes", "").strip() if c.get("Notes") else ""
            source = c.get("Component cource", "").strip() if c.get("Component cource") else ""
            bom_qty = ""
            order_qty = ""
            for k, v in c.items():
                if "BOM" in k:
                    bom_qty = v
                if "Order Quantity" in k:
                    order_qty = v
            poc = c.get("Point of contact", "").strip() if c.get("Point of contact") else ""

            with st.expander(f"**#{cid}** — {pcb} | `{mpn}` | BOM: {bom_qty} | Order: {order_qty}", expanded=False):
                # Info row
                ic1, ic2 = st.columns(2)
                with ic1:
                    st.markdown(f"**MPN:** `{mpn}` {f'({comp})' if comp else ''}")
                    st.markdown(f"**Supplier:** {supplier or 'N/A'}")
                    st.markdown(f"**Contact:** {poc or 'N/A'}")
                with ic2:
                    st.markdown(f"**BOM Qty:** {bom_qty} | **Order Qty:** {order_qty}")
                    st.markdown(f"**Current Status:** {target_status}")
                    st.markdown(f"**Source:** {source or 'N/A'}")

                # Editable fields
                st.markdown("---")
                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    current_status_idx = ALL_STATUSES.index(target_status) if target_status in ALL_STATUSES else 0
                    new_status = st.selectbox(
                        "Update Status",
                        ALL_STATUSES,
                        index=current_status_idx,
                        key=f"comp_status_{cid}_{idx}",
                    )
                with ec2:
                    current_source_idx = SOURCES.index(source) if source in SOURCES else 0
                    new_source = st.selectbox(
                        "Component Source",
                        SOURCES,
                        index=current_source_idx,
                        key=f"comp_source_{cid}_{idx}",
                    )
                with ec3:
                    new_notes = st.text_input(
                        "Notes",
                        value=notes,
                        key=f"comp_notes_{cid}_{idx}",
                    )

                if st.button("💾 Save Changes", key=f"comp_save_{cid}_{idx}", type="primary"):
                    try:
                        changes = 0
                        if new_status != target_status:
                            update_component_cell(client, int(cid), "Status", new_status)
                            changes += 1
                        if new_source != source:
                            update_component_cell(client, int(cid), "Component cource", new_source)
                            changes += 1
                        if new_notes != notes:
                            update_component_cell(client, int(cid), "Notes", new_notes)
                            changes += 1
                        if changes > 0:
                            st.success(f"#{cid} updated!")
                            st.rerun()
                        else:
                            st.info("No changes to save.")
                    except Exception as e:
                        st.error(f"Failed: {e}")
