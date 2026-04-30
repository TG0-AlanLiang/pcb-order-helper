"""Order History - Admin view of delivered/completed orders."""
import json
from datetime import datetime

import streamlit as st

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_role
from utils.google_client import get_gspread_client
from utils.orders_store import fetch_all_orders
from config import STATUS_COLORS, CNY_TO_GBP


user = require_role("admin")

st.title("📚 Order History")
st.caption("Delivered and cancelled orders")

all_orders = fetch_all_orders()
history = [o for o in all_orders if o.get("Status") in ("delivered", "cancelled")]

if not history:
    st.info("No delivered or cancelled orders yet.")
    st.stop()

# Helpers
def _to_f(v):
    try: return float(str(v).strip()) if str(v).strip() else 0.0
    except (ValueError, TypeError): return 0.0

# Calc total cost across history
total_cost_cny = sum(
    _to_f(o.get("BareBoardCostCNY")) + _to_f(o.get("BOMCostCNY")) + _to_f(o.get("SMTCostCNY"))
    for o in history
)
total_cost_gbp = total_cost_cny * CNY_TO_GBP

# Summary
col1, col2, col3 = st.columns(3)
col1.metric("Delivered", sum(1 for o in history if o.get("Status") == "delivered"))
col2.metric("Cancelled", sum(1 for o in history if o.get("Status") == "cancelled"))
col3.metric("Total Cost", f"£{total_cost_gbp:,.0f}", help=f"¥{total_cost_cny:,.0f} CNY (rate: 1 CNY = {CNY_TO_GBP} GBP)")

st.markdown("---")

# Filters
fc1, fc2, fc3 = st.columns(3)
with fc1:
    status_filter = st.selectbox("Status", ["all", "delivered", "cancelled"])
with fc2:
    engineers = sorted(set(o.get("EngineerName", "") for o in history if o.get("EngineerName")))
    engineer_filter = st.selectbox("Engineer", ["all"] + engineers)
with fc3:
    search = st.text_input("Search PCB Name", placeholder="Type to filter...")

filtered = history
if status_filter != "all":
    filtered = [o for o in filtered if o.get("Status") == status_filter]
if engineer_filter != "all":
    filtered = [o for o in filtered if o.get("EngineerName") == engineer_filter]
if search:
    s = search.lower()
    filtered = [o for o in filtered if s in o.get("PCBName", "").lower()]

filtered.sort(key=lambda o: o.get("CreatedAt", ""), reverse=True)

st.markdown(f"**{len(filtered)} orders** shown")
st.markdown("---")

for order in filtered:
    order_id = order.get("OrderID", "?")
    pcb_name = order.get("PCBName", "Unknown")
    status = order.get("Status", "")
    engineer = order.get("EngineerName", "")
    created = order.get("CreatedAt", "")
    pcb_type = order.get("PCBType", "Rigid")
    quantity = order.get("Quantity", "")
    priority = order.get("Priority", "Normal")

    priority_icon = "🔴" if priority == "URGENT" else "🟢"
    type_icon = "🔵 FPC" if pcb_type == "FPC" else "⬜ Rigid"
    status_color = STATUS_COLORS.get(status, "gray")

    header = (
        f"{priority_icon} **{pcb_name}** | {type_icon} | Qty: {quantity} | "
        f"👤 {engineer} | :{status_color}[{status.upper()}] | {created}"
    )

    with st.expander(header, expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**ID:** `{order_id}`")
            st.markdown(f"**Engineer:** {engineer}")
            st.markdown(f"**Recipient:** {order.get('Recipient', 'N/A')}")
            st.markdown(f"**Submitted:** {created}")
        with c2:
            st.markdown(f"**Layers:** {order.get('Layers', 'N/A')}")
            st.markdown(f"**Thickness:** {order.get('Thickness', 'N/A')}")
            st.markdown(f"**Solder Mask:** {order.get('SolderMask', 'N/A')}")
            st.markdown(f"**Needs SMT:** {order.get('NeedsSMT', 'No')}")
        with c3:
            st.markdown(f"**SMT Route:** {order.get('SMTRoute', 'N/A')}")
            st.markdown(f"**Vendor Order #:** {order.get('VendorOrderNum', 'N/A')}")
            st.markdown(f"**ETA:** {order.get('ETA', 'N/A')}")

        # Cost
        bare_c = _to_f(order.get("BareBoardCostCNY"))
        bom_c = _to_f(order.get("BOMCostCNY"))
        smt_c = _to_f(order.get("SMTCostCNY"))
        order_total_cny = bare_c + bom_c + smt_c
        if order_total_cny > 0:
            order_total_gbp = order_total_cny * CNY_TO_GBP
            st.markdown(f"💰 **Cost:** Bare ¥{bare_c:.0f} + BOM ¥{bom_c:.0f} + SMT ¥{smt_c:.0f} = **¥{order_total_cny:,.2f} CNY (£{order_total_gbp:,.2f} GBP)**")

        drive_link = order.get("DriveFileLink", "")
        if drive_link:
            st.markdown(f"📁 [View files on Drive]({drive_link})")

        notes = order.get("Notes", "")
        if notes:
            st.markdown(f"**Notes:** {notes}")
