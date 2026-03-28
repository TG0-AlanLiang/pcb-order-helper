"""BOM Check page - Parse BOM files and check stock availability."""
import streamlit as st
import pandas as pd

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_role
from utils.bom_parser import parse_bom, summarize_bom
from utils.stock_checker import check_stock, suggest_smt_route
from utils.google_client import get_gspread_client
from utils.sheet_handler import fetch_stock_data

require_role("admin")

st.title("🔍 BOM Check")

# --- Upload BOM ---
st.header("1. Upload BOM File")
bom_file = st.file_uploader("Upload Altium BOM (.xlsx)", type=["xlsx", "xls", "csv"])

pcb_quantity = st.number_input("PCB Quantity (for total component calculation)", value=5, min_value=1)

if bom_file:
    # Save uploaded file temporarily
    temp_path = os.path.join(os.path.dirname(__file__), "..", "data", f"_temp_bom.xlsx")
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    with open(temp_path, "wb") as f:
        f.write(bom_file.getvalue())

    # Parse BOM
    try:
        bom_df, col_mapping = parse_bom(temp_path)
    except Exception as e:
        st.error(f"Failed to parse BOM: {e}")
        st.stop()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    # Show BOM summary
    st.header("2. BOM Summary")
    summary = summarize_bom(bom_df)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Unique Parts", summary["total_unique_parts"])
    col2.metric("Total Components", summary["total_components"])
    col3.metric("Parts with MPN", summary["parts_with_mpn"])
    col4.metric("Parts with LCSC", summary["parts_with_lcsc"])

    # Show detected columns
    with st.expander("Detected Column Mapping"):
        for field, col_name in col_mapping.items():
            st.markdown(f"- **{field}**: {col_name or '❌ Not found'}")

    # Show parsed BOM
    st.header("3. Parsed BOM")
    st.dataframe(bom_df, use_container_width=True, height=400)

    # --- Stock Check ---
    st.header("4. Stock Check")

    # Try Google Sheets connection
    stock_data = []
    client = get_gspread_client()
    if client:
        try:
            with st.spinner("Fetching stock data from Google Sheet..."):
                stock_data = fetch_stock_data(client)
            st.success(f"Loaded {len(stock_data)} stock entries from Google Sheet")
        except Exception as e:
            st.warning(f"Could not fetch stock data: {e}")
    else:
        st.warning("Google Sheets not configured. Stock check will show all items as 'Not In Stock'.")
        st.markdown("Configure `credentials.json` and `GOOGLE_SHEET_ID` in `config.py` to enable.")

    # Run stock check
    result_df = check_stock(bom_df, stock_data, pcb_quantity)

    # Color-code results
    def highlight_status(row):
        status = row.get("Stock_Status", "")
        if status == "In Stock (Sufficient)":
            return ["background-color: #d4edda"] * len(row)
        elif status == "In Stock (Insufficient)":
            return ["background-color: #fff3cd"] * len(row)
        elif status == "Not In Stock":
            return ["background-color: #f8d7da"] * len(row)
        return [""] * len(row)

    st.dataframe(
        result_df.style.apply(highlight_status, axis=1),
        use_container_width=True,
        height=500,
    )

    # Status breakdown
    st.subheader("Status Breakdown")
    status_counts = result_df["Stock_Status"].value_counts()
    for status, count in status_counts.items():
        if "Sufficient" in status:
            st.markdown(f"🟢 **{status}**: {count}")
        elif "Insufficient" in status:
            st.markdown(f"🟡 **{status}**: {count}")
        elif "Not In Stock" in status:
            st.markdown(f"🔴 **{status}**: {count}")
        else:
            st.markdown(f"⚪ **{status}**: {count}")

    # --- SMT Route Suggestion ---
    st.header("5. SMT Route Suggestion")
    suggestion = suggest_smt_route(result_df, pcb_quantity)
    st.markdown(f"### Recommended: **{suggestion['route']}**")
    for reason in suggestion.get("reasons", []):
        st.markdown(f"- {reason}")

    # --- Export ---
    st.header("6. Export")
    csv = result_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Download Stock Check Result (.csv)",
        csv,
        file_name="bom_stock_check.csv",
        mime="text/csv",
    )
