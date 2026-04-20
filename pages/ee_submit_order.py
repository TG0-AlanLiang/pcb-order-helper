"""Submit Order - EE-facing form to submit a new PCB order."""
import streamlit as st

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.orders_store import create_order
from utils.drive_handler import upload_file


user = require_auth()

st.title("📋 Submit New PCB Order")
st.markdown(f"Submitting as: **{user['name']}** ({user['email']})")

# Check for reorder data
reorder = st.session_state.pop("reorder_data", {})
if reorder:
    st.success(f"Reordering: **{reorder.get('pcb_name', '')}** — review and update specs below.")

# ============================================================
# PCB Name + Type (these control downstream options)
# ============================================================
st.subheader("1. Basic Info")
col_a, col_b, col_c = st.columns(3)
with col_a:
    pcb_name = st.text_input("PCB Name *", value=reorder.get("pcb_name", ""),
                             placeholder="e.g. EZ1_Main_revC")
with col_b:
    type_options = ["Rigid", "FPC"]
    type_idx = type_options.index(reorder["pcb_type"]) if reorder.get("pcb_type") in type_options else 0
    pcb_type = st.selectbox("PCB Type *", type_options, index=type_idx,
                            help="Select first — options below change based on type")
with col_c:
    pcb_vendor = st.selectbox("PCB Vendor", ["JLCPCB", "JDB"],
                              help="JDB and JLCPCB share the same PCB options")

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
            ["ENIG (Immersion Gold)", "HASL (Lead)", "Lead-free HASL"],
            index=0)
    with col2:
        min_drill = st.selectbox("Min Drill / Via Size (inner/outer diameter)",
            ["0.3mm / 0.45mm (Free)", "0.25mm / 0.4mm", "0.2mm / 0.35mm",
             "0.15mm / 0.3mm", "0.1mm / 0.25mm"],
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
        copper_type = st.selectbox("Copper Type",
            ["ED (Electrodeposited)", "RA (Rolled Annealed)"],
            index=0,
            help="RA copper is more flexible. JLC: RA limited to 0.11mm. JDB: RA available on all thicknesses.")

        # Thickness depends on vendor + copper type
        if pcb_vendor == "JDB":
            # JDB: 0.10/0.13/0.20, all support RA
            thickness = st.selectbox("Thickness", ["0.10mm", "0.13mm", "0.20mm"], index=0,
                                     help="JDB thickness options")
        else:
            # JLC: RA only on 0.11mm
            if "RA" in copper_type:
                thickness = st.selectbox("Thickness", ["0.11mm"], index=0,
                                         help="JLC: RA copper only available in 0.11mm")
            else:
                thickness = st.selectbox("Thickness", ["0.11mm", "0.12mm", "0.20mm"], index=0)

        coverlay_color = st.selectbox("Coverlay Color",
            ["Yellow", "Black", "White"],
            index=0)
    with col2:
        # FPC can only use ENIG
        surface_finish = "ENIG (Immersion Gold)"
        st.selectbox("Surface Finish", ["ENIG (Immersion Gold)"], index=0,
                     disabled=True, help="FPC only supports ENIG")
        stiffeners = st.multiselect("Stiffeners (select multiple if needed)",
            ["PI Stiffener", "FR4 Stiffener", "Steel Stiffener", "3M Adhesive Tape"],
            default=[],
            help="You can select multiple stiffener types for different areas")
        stiffener_thickness = st.text_input("Stiffener Thickness",
            placeholder="e.g. 0.2mm, or 0.1mm + 0.2mm for multiple PI layers",
            help="You can input multiple thicknesses (e.g. for 0.1mm and 0.2mm PI stiffeners)")
        emi_shield = st.selectbox("EMI Shielding",
            ["None", "Double-sided (Black) 18um", "Single-sided (Black) 18um"],
            index=0)
        impedance = st.selectbox("Impedance Control",
            ["No requirement (Free)", "+/-20% (Free)", "+/-10%"],
            index=0)

    # Gold finger thickness control (optional)
    gold_finger_thickness = st.text_input(
        "Gold Finger Total Thickness (optional)",
        placeholder="e.g. 0.3mm (bare board + stiffener = target total)",
        help="If the board has a gold finger, specify the required total thickness (bare board + stiffener)."
    )

    # Build FPC specs string
    fpc_parts = [f"Copper: {copper_type}", f"Coverlay: {coverlay_color}", f"Surface: {surface_finish}"]
    if stiffeners:
        stiffener_str = " + ".join(stiffeners)
        if stiffener_thickness.strip():
            stiffener_str += f" ({stiffener_thickness.strip()})"
        fpc_parts.append(f"Stiffeners: {stiffener_str}")
    if gold_finger_thickness.strip():
        fpc_parts.append(f"Gold Finger Total: {gold_finger_thickness.strip()}")
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
    reorder_qty = int(reorder.get("quantity", 5) or 5)
    quantity = st.number_input("Quantity", min_value=1, max_value=10000, value=reorder_qty)
    pri_options = ["Normal", "URGENT"]
    pri_idx = pri_options.index(reorder["priority"]) if reorder.get("priority") in pri_options else 0
    priority = st.selectbox("Priority", pri_options, index=pri_idx)
with col4:
    test_by_engineer = st.selectbox("Test by Engineer?", ["No", "Yes"])
    recipient = st.text_input("Recipient *", value=reorder.get("recipient", ""),
                              placeholder="e.g. Send all to Berk")

# ============================================================
# SMT & Notes
# ============================================================
st.subheader("4. Assembly & Notes")
col5, col6 = st.columns(2)
with col5:
    needs_smt = st.checkbox("Needs SMT (Assembly)", value=reorder.get("needs_smt", False))
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
    full_notes = f"[Vendor: {pcb_vendor}] {extra_specs}"
    if notes.strip():
        full_notes = f"[Vendor: {pcb_vendor}] {extra_specs}\n---\n{notes.strip()}"

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
