"""Submit Order - EE-facing form to submit a new PCB order."""
import re

import streamlit as st

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.orders_store import create_order
from utils.drive_handler import upload_file


user = require_auth()


def _option_index(options, value, default=0):
    """Return the option index for saved reorder values, falling back safely."""
    try:
        return options.index(value)
    except ValueError:
        return default


def _int_value(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _vendor_from_reorder(reorder: dict) -> str:
    notes = reorder.get("notes", "")
    if "[Vendor: JDB]" in notes:
        return "JDB"
    return "JLCPCB"


def _field_from_notes(notes: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*([^|]+)", notes)
    return match.group(1).strip() if match else ""


def _size_from_notes(notes: str) -> tuple[float, float]:
    match = re.search(r"Size:\s*([0-9.]+)\s*x\s*([0-9.]+)\s*cm", notes)
    if not match:
        return 0.0, 0.0
    try:
        return float(match.group(1)), float(match.group(2))
    except ValueError:
        return 0.0, 0.0


def _stiffener_defaults(notes: str, options: list[str]) -> list[str]:
    stiffener_text = _field_from_notes(notes, "Stiffeners")
    return [option for option in options if option in stiffener_text]


def _stiffener_thickness_from_notes(notes: str) -> str:
    stiffener_text = _field_from_notes(notes, "Stiffeners")
    match = re.search(r"\(([^)]+)\)", stiffener_text)
    return match.group(1).strip() if match else ""


def _manual_notes_from_notes(notes: str) -> str:
    """Keep only the engineer-written note section from a stored order note."""
    if "\n---\n" not in notes:
        return ""
    return notes.split("\n---\n", 1)[1].strip()


st.title("📋 Submit New PCB Order")
st.markdown(f"Submitting as: **{user['name']}** ({user['email']})")

# Keep reorder data across Streamlit reruns. Do not pop it here: changing any
# widget (including Quantity) reruns the page, and a one-shot pop resets the
# rest of the form back to blank/default values.
reorder = st.session_state.get("reorder_data", {})
if reorder:
    st.success(f"Reordering: **{reorder.get('pcb_name', '')}** — review and update specs below.")
    if reorder.get("source_order_id"):
        st.caption(f"Copied from previous order `{reorder['source_order_id']}`.")
    if st.button("Start blank order instead", key="clear_reorder_draft"):
        st.session_state.pop("reorder_data", None)
        st.rerun()

previous_notes = reorder.get("notes", "").strip()
previous_drive_link = reorder.get("drive_file_link", "").strip()
default_board_length, default_board_width = _size_from_notes(previous_notes)
default_manual_notes = _manual_notes_from_notes(previous_notes)

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
    vendor_options = ["JLCPCB", "JDB"]
    pcb_vendor = st.selectbox("PCB Vendor", vendor_options,
                              index=_option_index(vendor_options, _vendor_from_reorder(reorder)),
                              help="JDB and JLCPCB share the same PCB options")

# Board dimensions
dim1, dim2 = st.columns(2)
with dim1:
    board_length = st.number_input("Board Length (cm) *", min_value=0.0, max_value=100.0,
                                   value=default_board_length, step=0.01, format="%.2f",
                                   help="Longest side of the board in cm")
with dim2:
    board_width = st.number_input("Board Width (cm) *", min_value=0.0, max_value=100.0,
                                  value=default_board_width, step=0.01, format="%.2f",
                                  help="Shorter side of the board in cm")

# ============================================================
# Specifications (dynamic based on PCB type)
# ============================================================
st.subheader("2. PCB Specifications")

if pcb_type == "Rigid":
    col1, col2 = st.columns(2)
    with col1:
        layer_options = [1, 2, 4, 6, 8, 10, 12]
        layers = st.selectbox("Layers", layer_options,
                              index=_option_index(layer_options, _int_value(reorder.get("layers"), 2), 1))
        thickness_options = ["0.4mm", "0.6mm", "0.8mm", "1.0mm", "1.2mm", "1.6mm", "2.0mm", "2.5mm", "3.0mm"]
        thickness = st.selectbox("Thickness",
            thickness_options,
            index=_option_index(thickness_options, reorder.get("thickness", "1.6mm"), 5))
        solder_options = ["Green", "Red", "Yellow", "Blue", "White", "Black", "Matte Black", "JLC Purple"]
        solder_mask = st.selectbox("Solder Mask Color",
            solder_options,
            index=_option_index(solder_options, reorder.get("solder_mask", "Green")))
        surface_options = ["ENIG (Immersion Gold)", "HASL (Lead)", "Lead-free HASL"]
        surface_finish = st.selectbox("Surface Finish",
            surface_options,
            index=_option_index(surface_options, _field_from_notes(previous_notes, "Surface")))
    with col2:
        min_drill_options = ["0.3mm / 0.45mm (Free)", "0.25mm / 0.4mm", "0.2mm / 0.35mm",
                             "0.15mm / 0.3mm", "0.1mm / 0.25mm"]
        min_drill = st.selectbox("Min Drill / Via Size (inner/outer diameter)",
            min_drill_options,
            index=_option_index(min_drill_options, _field_from_notes(previous_notes, "Min Drill")))
        via_options = ["Tented (Solder mask plug)", "Untented (Open window)",
                       "Resin plug + cap plating", "Resin plug + open window"]
        via_covering = st.selectbox("Via Covering",
            via_options,
            index=_option_index(via_options, _field_from_notes(previous_notes, "Via")))
        silkscreen = st.selectbox("Silkscreen Color", ["White", "Black"], index=0)
        impedance_options = ["No requirement (Free)", "+/-20% (Free)", "+/-10%"]
        impedance = st.selectbox("Impedance Control",
            impedance_options,
            index=_option_index(impedance_options, _field_from_notes(previous_notes, "Impedance")))

    # Rigid-specific notes
    extra_specs = f"Surface: {surface_finish} | Min Drill: {min_drill} | Via: {via_covering} | Impedance: {impedance}"

else:  # FPC
    col1, col2 = st.columns(2)
    with col1:
        layer_options = [1, 2, 4]
        layers = st.selectbox("Layers", layer_options,
                              index=_option_index(layer_options, _int_value(reorder.get("layers"), 2), 1))
        copper_options = ["RA (Rolled Annealed)", "ED (Electrodeposited)"]
        copied_copper = _field_from_notes(previous_notes, "Copper")
        copper_type = st.selectbox("Copper Type",
            copper_options,
            index=_option_index(copper_options, copied_copper),
            help="RA (压延铜) is default — more flexible. JLC: RA limited to 0.11mm. JDB: RA available on all thicknesses.")

        # Thickness depends on vendor + copper type
        if pcb_vendor == "JDB":
            # JDB: 0.10/0.13/0.20, all support RA
            thickness_options = ["0.10mm", "0.13mm", "0.20mm"]
            thickness = st.selectbox("Thickness", thickness_options,
                                     index=_option_index(thickness_options, reorder.get("thickness", "0.10mm")),
                                     help="JDB thickness options")
        else:
            # JLC: RA only on 0.11mm
            if "RA" in copper_type:
                thickness = st.selectbox("Thickness", ["0.11mm"], index=0,
                                         help="JLC: RA copper only available in 0.11mm")
            else:
                thickness_options = ["0.11mm", "0.12mm", "0.20mm"]
                thickness = st.selectbox("Thickness", thickness_options,
                                         index=_option_index(thickness_options, reorder.get("thickness", "0.11mm")))

        coverlay_options = ["Yellow", "Black", "White"]
        coverlay_color = st.selectbox("Coverlay Color",
            coverlay_options,
            index=_option_index(coverlay_options, reorder.get("solder_mask", "Yellow")))
    with col2:
        # FPC can only use ENIG
        surface_finish = "ENIG (Immersion Gold)"
        st.selectbox("Surface Finish", ["ENIG (Immersion Gold)"], index=0,
                     disabled=True, help="FPC only supports ENIG")
        stiffener_options = ["PI Stiffener", "FR4 Stiffener", "Steel Stiffener", "3M Adhesive Tape"]
        stiffeners = st.multiselect("Stiffeners (select multiple if needed)",
            stiffener_options,
            default=_stiffener_defaults(previous_notes, stiffener_options),
            help="You can select multiple stiffener types for different areas")
        stiffener_thickness = st.text_input("Stiffener Thickness",
            value=_stiffener_thickness_from_notes(previous_notes),
            placeholder="e.g. 0.2mm, or 0.1mm + 0.2mm for multiple PI layers",
            help="You can input multiple thicknesses (e.g. for 0.1mm and 0.2mm PI stiffeners)")
        silkscreen_on_stiffener = st.checkbox("Print silkscreen on stiffener (补强上印丝印)",
            value=("[silkscreen on stiffener]" in previous_notes) if reorder else True,
            help="Default ON — usually needed unless you have a specific reason to exclude")
        emi_options = ["None", "Double-sided (Black) 18um", "Single-sided (Black) 18um"]
        copied_emi = _field_from_notes(previous_notes, "EMI")
        emi_shield = st.selectbox("EMI Shielding",
            emi_options,
            index=_option_index(emi_options, copied_emi))
        impedance_options = ["No requirement (Free)", "+/-20% (Free)", "+/-10%"]
        copied_impedance = _field_from_notes(previous_notes, "Impedance")
        impedance = st.selectbox("Impedance Control",
            impedance_options,
            index=_option_index(impedance_options, copied_impedance))

    # Gold finger thickness control (optional)
    gold_finger_thickness = st.text_input(
        "Gold Finger Total Thickness (optional)",
        value=_field_from_notes(previous_notes, "Gold Finger Total"),
        placeholder="e.g. 0.3mm (bare board + stiffener = target total)",
        help="If the board has a gold finger, specify the required total thickness (bare board + stiffener)."
    )

    # Build FPC specs string
    fpc_parts = [f"Copper: {copper_type}", f"Coverlay: {coverlay_color}", f"Surface: {surface_finish}"]
    if stiffeners:
        stiffener_str = " + ".join(stiffeners)
        if stiffener_thickness.strip():
            stiffener_str += f" ({stiffener_thickness.strip()})"
        if silkscreen_on_stiffener:
            stiffener_str += " [silkscreen on stiffener]"
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
    test_options = ["No", "Yes"]
    test_by_engineer = st.selectbox("Test by Engineer?", test_options,
                                    index=_option_index(test_options, reorder.get("test_by_engineer", "No")))
    recipient = st.text_input("Recipient *", value=reorder.get("recipient", ""),
                              placeholder="e.g. Send all to Berk")

# Reviewer (second EE)
from utils.user_store import fetch_allowed_users
all_users = fetch_allowed_users()
# Build unique name list, excluding current user
reviewer_names = sorted({info["name"] for email, info in all_users.items() if info["name"] != user["name"]})
reviewer_options = ["-- Select --"] + reviewer_names
reviewer = st.selectbox("Reviewer (second EE who can answer EQs) *", reviewer_options,
                       index=_option_index(reviewer_options, reorder.get("reviewer", "-- Select --")),
                       help="Pick a colleague who reviewed/will help review this design. They can also answer EQs.")

# ============================================================
# SMT & Notes
# ============================================================
st.subheader("4. Assembly & Notes")
col5, col6 = st.columns(2)
with col5:
    needs_smt = st.checkbox("Needs SMT (Assembly)", value=reorder.get("needs_smt", False))
with col6:
    notes = st.text_area("Notes (optional)",
                         value=default_manual_notes,
                         placeholder="Any special requirements, process notes, stiffener details...",
                         height=100)

# Prepend dimensions to extra_specs
if board_length > 0 and board_width > 0:
    dimensions_str = f"Size: {board_length:.2f} x {board_width:.2f} cm"
    extra_specs = f"{dimensions_str} | {extra_specs}"

# Show spec summary
with st.expander("Spec Summary (auto-generated)"):
    st.markdown(f"**Type:** {pcb_type} | **Layers:** {layers} | **Thickness:** {thickness}")
    st.markdown(f"**Size:** {board_length:.2f} x {board_width:.2f} cm")
    st.markdown(f"**Solder Mask:** {solder_mask} | **Qty:** {quantity} | **Priority:** {priority}")
    st.markdown(f"**Details:** {extra_specs}")

# ============================================================
# File Upload
# ============================================================
st.subheader("5. Upload Gerber/Design Files")
if previous_drive_link:
    st.info("This reorder will reuse the previous order's Drive folder unless you upload a new file.")
    st.markdown(f"📁 [Previous order Drive folder]({previous_drive_link})")
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
    if board_length <= 0 or board_width <= 0:
        st.error("Board dimensions (length & width) are required!")
        st.stop()
    if not recipient.strip():
        st.error("Recipient is required!")
        st.stop()
    if reviewer == "-- Select --":
        st.error("Reviewer is required! Pick a colleague who can help answer EQs.")
        st.stop()

    client = get_gspread_client()
    if not client:
        st.error("Cannot connect to Google Sheets. Contact admin.")
        st.stop()

    # Reorders reuse the previous Drive folder unless a new file is uploaded.
    drive_link = previous_drive_link
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
                "reviewer": reviewer,
            }
            order_id = create_order(client, order_data)
            st.session_state.pop("reorder_data", None)
            st.success(f"Order submitted! Order ID: **{order_id}**")
            st.balloons()
            st.info("Go to **My Orders** to track progress.")
        except Exception as e:
            st.error(f"Failed to create order: {e}")
