"""My Components - View components registered by the current user."""
import streamlit as st

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import fetch_all_components


user = require_auth()

st.title("🔩 My Components")
st.markdown(f"Components registered by: **{user['name']}**")

client = get_gspread_client()
if not client:
    st.error("Cannot connect to Google Sheets.")
    st.stop()

components = fetch_all_components(client)

# Filter by current user's name (Point of contact column)
my_components = [
    c for c in components
    if (c.get("Point of contact", "") or "").strip().lower() == user["name"].lower()
]

if not my_components:
    st.info("No components registered by you yet. Use **Register Component** to add one.")
    st.stop()

# Group: active first, then completed
ACTIVE = {"To Order", "Ordered", "In Transit"}
active = [c for c in my_components if c.get("Status", "").strip() in ACTIVE]
done = [c for c in my_components if c.get("Status", "").strip() not in ACTIVE]

status_icons = {
    "To Order": "🔴", "Ordered": "🟠", "In Transit": "🚚",
    "Recieved": "✅", "DeliveredToVendor": "✅", "From Stock": "📦", "Cancelled": "❌",
}

# Summary
col1, col2, col3 = st.columns(3)
col1.metric("Total", len(my_components))
col2.metric("Active", len(active))
col3.metric("Completed", len(done))

st.markdown("---")

# Filter
show = st.radio("Show", ["Active", "All", "Completed"], horizontal=True)
if show == "Active":
    display = active
elif show == "Completed":
    display = done[:20]
else:
    display = active + done[:20]

st.markdown(f"**{len(display)} items** shown")

for c in display:
    cid = c.get("ID", "?")
    pcb = (c.get("PCB Name", "") or "").strip() or "N/A"
    mpn = (c.get("MPN", "") or "").strip() or "N/A"
    comp = (c.get("Components", "") or "").strip()
    status = c.get("Status", "").strip()
    notes = (c.get("Notes", "") or "").strip()
    supplier = (c.get("Supplier & Obj", "") or "").strip()
    source = (c.get("Component cource", "") or "").strip()
    icon = status_icons.get(status, "⚪")
    is_active = status in ACTIVE

    # Get quantities
    bom_qty = ""
    order_qty = ""
    for k, v in c.items():
        if "BOM" in k:
            bom_qty = v
        if "Order Quantity" in k:
            order_qty = v

    with st.expander(f"{icon} **#{cid}** — {pcb} | `{mpn}` | {status}", expanded=is_active):
        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown(f"**MPN:** `{mpn}` {f'({comp})' if comp else ''}")
            st.markdown(f"**Status:** {status}")
            st.markdown(f"**Supplier:** {supplier or 'N/A'}")
            st.markdown(f"**Source:** {source or 'N/A'}")
        with ec2:
            st.markdown(f"**BOM Qty:** {bom_qty}")
            st.markdown(f"**Order Qty:** {order_qty}")
            st.markdown(f"**PCB:** {pcb}")
            if notes:
                st.markdown(f"**Notes:** {notes}")
