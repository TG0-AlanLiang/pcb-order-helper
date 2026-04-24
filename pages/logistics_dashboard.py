"""Logistics Dashboard - Jimmy's dedicated page for managing deliveries and components."""
import re
import streamlit as st
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import fetch_pcb_delivery, update_delivery_cell, fetch_all_components, update_component_cell


def _get(d: dict, key: str, default: str = "") -> str:
    """Get value from dict, trying exact key first then stripped key match."""
    val = d.get(key, None)
    if val is not None:
        return str(val).strip()
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

# ============================================================
# FETCH DATA
# ============================================================
deliveries = fetch_pcb_delivery(client)
components = fetch_all_components(client)

# --- PCB Delivery categories ---
pending_receipt = [d for d in deliveries if not _get(d, "Jimmy received check")]
ready_to_ship = [d for d in deliveries
                 if _get(d, "Jimmy received check")
                 and not _get(d, "Jimmy Shipp out remark")]
shipped_pcbs = [d for d in deliveries
                if _get(d, "Jimmy received check")
                and _get(d, "Jimmy Shipp out remark")]

# --- Component categories (based on Notes, not Status) ---
# Unprocessed = Notes is empty (Jimmy hasn't acted yet)
# Shipped = Notes starts with SF (tracking number)
# Stored = Notes is not empty and not a tracking number
unprocessed_components = [c for c in components if not (c.get("Notes", "") or "").strip()]
shipped_components = [c for c in components
                      if re.match(r"^SF\d", (c.get("Notes", "") or "").strip())]
stored_components = [c for c in components
                     if (c.get("Notes", "") or "").strip()
                     and not re.match(r"^SF\d", (c.get("Notes", "") or "").strip())]

# Only show unprocessed that have a Supplier & Obj (i.e. need forwarding)
actionable_components = [c for c in unprocessed_components
                         if (c.get("Supplier & Obj", "") or "").strip()]

# --- Summary metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("PCB Pending", len(pending_receipt))
col2.metric("PCB Ready to Ship", len(ready_to_ship))
col3.metric("Components to Handle", len(actionable_components))
col4.metric("Components Shipped", len(shipped_components))

st.markdown("---")

# ============================================================
# A. PENDING RECEIPT (collapsible)
# ============================================================
with st.expander(f"📥 **Pending Receipt** ({len(pending_receipt)})", expanded=False):
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
# B. READY TO SHIP (collapsible)
# ============================================================
with st.expander(f"📤 **Ready to Ship** ({len(ready_to_ship)})", expanded=False):
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

            st.markdown(f"{priority_icon} **#{num}** — {pcb} | Received: {received} | To: {recipient}")
            remark = st.text_area(
                "Shipping remark",
                key=f"logship_remark_{num}_{i}",
                placeholder="e.g. SF1562763341561\n5 to 杭州临平区\nThe rest to UK Shaoze",
                height=80,
            )
            btn1, btn2 = st.columns(2)
            with btn1:
                if st.button("📦 Mark Shipped", key=f"logship_btn_{num}_{i}", type="primary"):
                    if remark.strip():
                        try:
                            update_delivery_cell(client, int(num), "Jimmy Shipp out remark", remark.strip())
                            st.success(f"#{num} shipped!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                    else:
                        st.warning("Enter shipping remark first.")
            with btn2:
                if st.button("📥 Keep in Stock", key=f"logstock_btn_{num}_{i}"):
                    try:
                        update_delivery_cell(client, int(num), "Jimmy Shipp out remark", "入库存 Keep in stock")
                        st.success(f"#{num} stocked!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed: {e}")
            st.divider()

# ============================================================
# C. COMPONENT TRACKING (collapsible) — based on Notes being empty
# ============================================================
with st.expander(f"🔄 **Component Tracking** ({len(actionable_components)})", expanded=False):
    if not actionable_components:
        st.success("No pending components!")
    else:
        st.caption("Components with Supplier & Obj set but Notes empty (not yet processed by Jimmy)")

        ALL_STATUSES = ["To Order", "Ordered", "In Transit", "Recieved", "DeliveredToVendor", "From Stock", "Cancelled"]
        SOURCES = ["", "From Stock", "From UK", "From JLC", "To Order"]

        for idx, c in enumerate(actionable_components):
            cid = c.get("ID", "?")
            pcb = (c.get("PCB Name", "") or "").strip() or "N/A"
            mpn = (c.get("MPN", "") or "").strip() or "N/A"
            supplier = (c.get("Supplier & Obj", "") or "").strip()
            status = c.get("Status", "").strip()
            source = (c.get("Component cource", "") or "").strip()
            notes = (c.get("Notes", "") or "").strip()
            registor = (c.get("Registor", "") or "").strip()

            bom_qty = ""
            order_qty = ""
            for k, v in c.items():
                if "BOM" in k:
                    bom_qty = v
                if "Order Quantity" in k:
                    order_qty = v

            reg_suffix = f" | by {registor}" if registor else ""
            with st.expander(f"**#{cid}** — {pcb} | `{mpn}` | → {supplier}{reg_suffix}", expanded=False):
                ic1, ic2 = st.columns(2)
                with ic1:
                    st.markdown(f"**MPN:** `{mpn}`")
                    st.markdown(f"**Destination:** {supplier}")
                    st.markdown(f"**BOM:** {bom_qty} | **Order:** {order_qty}")
                with ic2:
                    st.markdown(f"**Status:** {status}")
                    st.markdown(f"**Source:** {source or 'N/A'}")
                    if registor:
                        st.markdown(f"**Registered by:** {registor}")

                st.markdown("---")
                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    cur_idx = ALL_STATUSES.index(status) if status in ALL_STATUSES else 0
                    new_status = st.selectbox("Status", ALL_STATUSES, index=cur_idx, key=f"cs_{cid}_{idx}")
                with ec2:
                    src_idx = SOURCES.index(source) if source in SOURCES else 0
                    new_source = st.selectbox("Source", SOURCES, index=src_idx, key=f"csrc_{cid}_{idx}")
                with ec3:
                    new_notes = st.text_input("Notes (tracking# / storage)", value=notes, key=f"cn_{cid}_{idx}",
                                              placeholder="SF1558225393176 or keep in 储物箱")

                if st.button("💾 Save", key=f"csave_{cid}_{idx}", type="primary"):
                    try:
                        changes = 0
                        if new_status != status:
                            update_component_cell(client, int(cid), "Status", new_status)
                            changes += 1
                        if new_source != source:
                            update_component_cell(client, int(cid), "Component cource", new_source)
                            changes += 1
                        if new_notes != notes:
                            update_component_cell(client, int(cid), "Notes", new_notes)
                            changes += 1
                        if changes:
                            st.success(f"#{cid} updated!")
                            st.rerun()
                        else:
                            st.info("No changes.")
                    except Exception as e:
                        st.error(f"Failed: {e}")

# ============================================================
# D. RECENTLY SHIPPED COMPONENTS (collapsible)
# ============================================================
with st.expander(f"🚚 **Recently Shipped Components** ({len(shipped_components)})", expanded=False):
    if not shipped_components:
        st.info("No shipped components.")
    else:
        for c in shipped_components[:15]:
            cid = c.get("ID", "?")
            pcb = (c.get("PCB Name", "") or "").strip() or "N/A"
            mpn = (c.get("MPN", "") or "").strip() or "N/A"
            supplier = (c.get("Supplier & Obj", "") or "").strip()
            notes = (c.get("Notes", "") or "").strip()
            st.markdown(f"**#{cid}** — {pcb} | `{mpn}` | → {supplier} | 📦 {notes}")

# ============================================================
# E. RECENTLY SHIPPED PCBs (collapsible, at bottom)
# ============================================================
with st.expander(f"✅ **Recently Shipped PCBs** ({len(shipped_pcbs)})", expanded=False):
    if not shipped_pcbs:
        st.info("No shipped PCBs.")
    else:
        for i, d in enumerate(shipped_pcbs[:10]):
            num = _get(d, "Number", "?")
            pcb = _get(d, "PCB Name", "N/A")
            remark = _get(d, "Jimmy Shipp out remark")
            recipient = _get(d, "Recipient")
            st.markdown(f"**#{num}** — {pcb} | To: {recipient} | {remark}")
