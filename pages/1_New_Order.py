"""New Order page - Parse Slack messages and create orders (Admin tool)."""
import streamlit as st
import json

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_role
from utils.slack_parser import parse_slack_message
from utils.models import Order
from utils.google_client import get_gspread_client
from utils.orders_store import create_order

user = require_role("admin")

st.title("💬 New Order (Slack)")
st.markdown("Parse Slack order messages and create order records.")

# --- Slack Message Parser ---
st.header("1. Paste Slack Order Message")

sample_msg = """Hey @Alan Liang, please can we order this PCB for the JHT2_Left_revB

1. Number of layers: 4
2. PCB Type: Rigid
3. PCB thickness: 1.6mm
4. Solder mask colour: Green
5. Quantity of the PCB: 15
6. Priority: Normal
7. Test by Alan: No
8. PCB Recipient: Joe/Alejandro"""

slack_text = st.text_area(
    "Paste Slack message here:",
    height=250,
    placeholder=sample_msg,
)

if slack_text:
    order = parse_slack_message(slack_text)

    st.header("2. Parsed Order Details")
    st.markdown("Review and edit the parsed fields:")

    col1, col2 = st.columns(2)
    with col1:
        order.pcb_name = st.text_input("PCB Name", value=order.pcb_name)
        order.layers = st.number_input("Layers", value=order.layers, min_value=1, max_value=32)
        order.pcb_type = st.selectbox("PCB Type", ["Rigid", "FPC"], index=0 if order.pcb_type == "Rigid" else 1)
        order.thickness = st.text_input("Thickness", value=order.thickness)
        order.engineer = st.text_input("Engineer (requester)", value=order.engineer)

    with col2:
        colors = ["Green", "Black", "White", "Blue", "Red", "Yellow", "Purple", "Matte Black", "Matte Green"]
        order.solder_mask_color = st.selectbox(
            "Solder Mask Color",
            colors,
            index=colors.index(order.solder_mask_color) if order.solder_mask_color in colors else 0,
        )
        order.quantity = st.number_input("Quantity", value=order.quantity, min_value=1)
        order.priority = st.selectbox("Priority", ["Normal", "URGENT"], index=0 if order.priority == "Normal" else 1)
        order.test_by_engineer = st.selectbox("Test by Engineer", ["No", "Yes"], index=0 if order.test_by_engineer == "No" else 1)
        order.recipient = st.text_input("Recipient", value=order.recipient)

    order.needs_smt = st.checkbox("Needs SMT (assembly)", value=order.needs_smt)

    # FPC warning
    if order.pcb_type == "FPC" or "flex" in order.pcb_name.lower():
        st.info("FPC detected - SMT must be done at JLCPCB")

    # --- Create Order ---
    st.header("3. Create Order")

    if st.button("Create Order", type="primary"):
        client = get_gspread_client()
        if not client:
            st.error("Cannot connect to Google Sheets.")
            st.stop()

        order_data = {
            "pcb_name": order.pcb_name,
            "layers": order.layers,
            "pcb_type": order.pcb_type,
            "thickness": order.thickness,
            "solder_mask_color": order.solder_mask_color,
            "quantity": order.quantity,
            "priority": order.priority,
            "test_by_engineer": order.test_by_engineer,
            "recipient": order.recipient,
            "needs_smt": order.needs_smt,
            "engineer_email": user["email"],
            "engineer_name": order.engineer or user["name"],
            "notes": f"Created from Slack message by {user['name']}",
        }

        order_id = create_order(client, order_data)
        st.success(f"Order created: **{order.pcb_name}** (ID: {order_id})")
        st.balloons()
        st.info("Go to **All Orders** or **Process Order** to manage this order.")

else:
    st.markdown("---")
    st.markdown("**Example Slack message format:**")
    st.code(sample_msg)
