"""Submit Order - EE-facing form to submit a new PCB order."""
import streamlit as st

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.orders_store import create_order
from utils.drive_handler import upload_file


user = require_auth()

st.title("📋 Submit New PCB Order")
st.markdown(f"Submitting as: **{user['name']}** ({user['email']})")

with st.form("submit_order_form"):
    st.subheader("PCB Specifications")

    col1, col2 = st.columns(2)
    with col1:
        pcb_name = st.text_input("PCB Name *", placeholder="e.g. EZ1_Main_revC")
        layers = st.selectbox("Layers", [2, 4, 6, 8], index=0)
        pcb_type = st.selectbox("PCB Type", ["Rigid", "FPC"])
        thickness = st.selectbox(
            "Thickness",
            ["0.6mm", "0.8mm", "1.0mm", "1.2mm", "1.6mm", "2.0mm"],
            index=4,
        )
    with col2:
        solder_mask = st.selectbox(
            "Solder Mask Color",
            ["Green", "Black", "Blue", "Red", "White", "Yellow", "Purple", "Matte Black", "Matte Green"],
        )
        quantity = st.number_input("Quantity", min_value=1, max_value=1000, value=5)
        priority = st.selectbox("Priority", ["Normal", "URGENT"])
        test_by_engineer = st.selectbox("Test by Engineer?", ["No", "Yes"])

    st.subheader("Delivery & SMT")
    col3, col4 = st.columns(2)
    with col3:
        recipient = st.text_input("Recipient", placeholder="e.g. Send all to Berk")
        needs_smt = st.checkbox("Needs SMT (Assembly)")
    with col4:
        notes = st.text_area("Notes (optional)", placeholder="Any special requirements...")

    st.subheader("Upload Gerber/Design Files")
    uploaded_file = st.file_uploader(
        "Upload .rar or .zip file",
        type=["rar", "zip", "7z"],
        help="Upload your Gerber files, BOM, or design package",
    )

    submitted = st.form_submit_button("Submit Order", type="primary")

if submitted:
    if not pcb_name.strip():
        st.error("PCB Name is required!")
        st.stop()

    client = get_gspread_client()
    if not client:
        st.error("Cannot connect to Google Sheets. Contact admin.")
        st.stop()

    # Upload file to Google Drive if provided
    drive_link = ""
    if uploaded_file:
        with st.spinner("Uploading file to Google Drive..."):
            try:
                file_bytes = uploaded_file.read()
                drive_link = upload_file(
                    file_bytes=file_bytes,
                    filename=uploaded_file.name,
                    pcb_name=pcb_name.strip(),
                )
                st.success(f"File uploaded: {uploaded_file.name}")
            except Exception as e:
                st.error(f"File upload failed: {e}")
                st.info("Order will be created without file. Please upload later.")

    # Create order
    with st.spinner("Creating order..."):
        try:
            order_data = {
                "pcb_name": pcb_name.strip(),
                "layers": layers,
                "pcb_type": pcb_type,
                "thickness": thickness,
                "solder_mask_color": solder_mask,
                "quantity": quantity,
                "priority": priority,
                "test_by_engineer": test_by_engineer,
                "recipient": recipient.strip(),
                "needs_smt": needs_smt,
                "notes": notes.strip(),
                "engineer_email": user["email"],
                "engineer_name": user["name"],
                "drive_file_link": drive_link,
            }
            order_id = create_order(client, order_data)
            st.success(f"Order submitted successfully! Order ID: **{order_id}**")
            st.balloons()
            st.info("Go to **My Orders** to track progress.")
        except Exception as e:
            st.error(f"Failed to create order: {e}")
