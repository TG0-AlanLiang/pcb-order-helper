"""Submit Order - EE-facing form to submit a new PCB order."""
import streamlit as st

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.orders_store import create_order
from utils.drive_handler import upload_file


user = require_auth()

st.title("📋 Submit New PCB Order")
st.markdown(f"Submitting as: **{user['name']}** ({user['email']})")

# ============================================================
# PCB Name + Type (these control downstream options)
# ============================================================
st.subheader("1. Basic Info")
col_a, col_b = st.columns(2)
with col_a:
    pcb_name = st.text_input("PCB Name *", placeholder="e.g. EZ1_Main_revC")
with col_b:
    pcb_type = st.selectbox("PCB Type *", ["Rigid", "FPC"],
                            help="Select first — options below change based on type")

# ============================================================
# Specifications (dynamic based on PCB type)
# ============================================================
st.subheader("2. PCB Specifications")

if pcb_type == "Rigid":
    col1, col2 = st.columns(2)
    with col1:
        layers = st.selectbox("Layers", [1, 2, 4, 6, 8, 10, 12], index=1)
        thickness = st.selectbox("Thickness",
            ["0.4mm", "0.6mm", "0.8mm", "1.0mm", "1.2mm", "1.6mm", "2.0mm", "2.5mm", "3.0mm"],
            index=5)
        solder_mask = st.selectbox("Solder Mask Color",
            ["Green", "Red", "Yellow", "Blue", "White", "Black", "Matte Black", "JLC Purple"])
        surface_finish = st.selectbox("Surface Finish",
            ["HASL (Lead)", "Lead-free HASL", "ENIG (Immersion Gold)"],
            index=0)
    with col2:
        min_drill = st.selectbox("Min Hole Size",
            ["0.3mm (Free)", "0.25mm", "0.2mm", "0.15mm", "0.1mm"],
            index=0)
        via_covering = st.selectbox("Via Covering",
            ["Tented (Solder mask plug)", "Untented (Open window)",
             "Resin plug + cap plating", "Resin plug + open window"],
            index=0)
        silkscreen = st.selectbox("Silkscreen Color", ["White", "Black"], index=0)
        impedance = st.selectbox("Impedance Control",
            ["No requirement (Free)", "+/-20% (Free)", "+/-10%"],
            index=0)

    # Rigid-specific notes
    extra_specs = f"Surface: {surface_finish} | Min Drill: {min_drill} | Via: {via_covering} | Impedance: {impedance}"

else:  # FPC
    col1, col2 = st.columns(2)
    with col1:
        layers = st.selectbox("Layers", [1, 2, 4], index=1)
        thickness = st.selectbox("Thickness",
            ["0.11mm", "0.12mm", "0.20mm"],
            index=0)
        copper_type = st.selectbox("Copper Type",
            ["ED (Electrodeposited)", "RA (Rolled Annealed)"],
            index=0,
            help="RA copper is more flexible, recommended for dynamic flex areas")
        coverlay_color = st.selectbox("Coverlay Color",
            ["Yellow", "Black", "White"],
            index=0)
    with col2:
        surface_finish = st.selectbox("Surface Finish",
            ["ENIG (Immersion Gold)", "HASL (Lead)", "Lead-free HASL"],
            index=0)
        stiffener = st.selectbox("Stiffener",
            ["None", "PI Stiffener", "FR4 Stiffener", "Steel Stiffener", "3M Adhesive Tape"],
            index=0)
        emi_shield = st.selectbox("EMI Shielding",
            ["None", "Double-sided (Black) 18um", "Single-sided (Black) 18um"],
            index=0)
        impedance = st.selectbox("Impedance Control",
            ["No requirement (Free)", "+/-20% (Free)", "+/-10%"],
            index=0)

    # Build FPC specs string
    fpc_parts = [f"Copper: {copper_type}", f"Coverlay: {coverlay_color}", f"Surface: {surface_finish}"]
    if stiffener != "None":
        fpc_parts.append(f"Stiffener: {stiffener}")
    if emi_shield != "None":
        fpc_parts.append(f"EMI: {emi_shield}")
    if impedance != "No requirement (Free)":
        fpc_parts.append(f"Impedance: {impedance}")
    extra_specs = " | ".join(fpc_parts)

    # Solder mask = coverlay color for FPC
    solder_mask = coverlay_color

# ============================================================
# Quantity & Priority
# ============================================================
st.subheader("3. Order Details")
col3, col4 = st.columns(2)
with col3:
    quantity = st.number_input("Quantity", min_value=1, max_value=10000, value=5)
    priority = st.selectbox("Priority", ["Normal", "URGENT"])
with col4:
    test_by_engineer = st.selectbox("Test by Engineer?", ["No", "Yes"])
    recipient = st.text_input("Recipient *", placeholder="e.g. Send all to Berk")

# ============================================================
# SMT & Notes
# ============================================================
st.subheader("4. Assembly & Notes")
col5, col6 = st.columns(2)
with col5:
    needs_smt = st.checkbox("Needs SMT (Assembly)")
with col6:
    notes = st.text_area("Notes (optional)",
                         placeholder="Any special requirements, process notes, stiffener details...",
                         height=100)

# Show spec summary
with st.expander("Spec Summary (auto-generated)"):
    st.markdown(f"**Type:** {pcb_type} | **Layers:** {layers} | **Thickness:** {thickness}")
    st.markdown(f"**Solder Mask:** {solder_mask} | **Qty:** {quantity} | **Priority:** {priority}")
    st.markdown(f"**Details:** {extra_specs}")

# ============================================================
# File Upload
# ============================================================
st.subheader("5. Upload Gerber/Design Files")
uploaded_file = st.file_uploader(
    "Upload .rar or .zip file",
    type=["rar", "zip", "7z"],
    help="Include Gerber files, BOM (if SMT), and pick & place files",
)

# ============================================================
# Submit
# ============================================================
st.markdown("---")
if st.button("Submit Order", type="primary", key="submit_order_btn"):
    if not pcb_name.strip():
        st.error("PCB Name is required!")
        st.stop()
    if not recipient.strip():
        st.error("Recipient is required!")
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

    # Build full notes with extra specs
    full_notes = extra_specs
    if notes.strip():
        full_notes = f"{extra_specs}\n---\n{notes.strip()}"

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
                "notes": full_notes,
                "engineer_email": user["email"],
                "engineer_name": user["name"],
                "drive_file_link": drive_link,
            }
            order_id = create_order(client, order_data)
            st.success(f"Order submitted! Order ID: **{order_id}**")
            st.balloons()
            st.info("Go to **My Orders** to track progress.")
        except Exception as e:
            st.error(f"Failed to create order: {e}")
