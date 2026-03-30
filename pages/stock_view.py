"""Stock View - Browse and search component stock levels."""
import streamlit as st
import pandas as pd

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_auth
from utils.google_client import get_gspread_client
from utils.sheet_handler import fetch_stock_data


user = require_auth()

st.title("📦 Stock Inventory")

client = get_gspread_client()
if not client:
    st.error("Cannot connect to Google Sheets.")
    st.stop()

# Fetch raw data for better column control
from config import GOOGLE_SHEET_ID
ss = client.open_by_key(GOOGLE_SHEET_ID)
ws = ss.worksheet("Stock")
all_values = ws.get_all_values()

if len(all_values) < 2:
    st.info("No stock data found.")
    st.stop()

headers = all_values[0]
data = all_values[1:]

# Build dataframe with clean column names
df = pd.DataFrame(data, columns=headers)

# Keep only useful columns
display_cols = []
col_mapping = {}
for h in headers:
    if "Component MPN" in h:
        display_cols.append(h)
        col_mapping[h] = "MPN"
    elif h == "Specs":
        display_cols.append(h)
        col_mapping[h] = "Specs"
    elif "Current Stock" in h:
        display_cols.append(h)
        col_mapping[h] = "Current Stock"
    elif "Project" in h:
        display_cols.append(h)
        col_mapping[h] = "Project"
    elif h == "Note":
        display_cols.append(h)
        col_mapping[h] = "Note"
    elif "Jimmy" in h:
        display_cols.append(h)
        col_mapping[h] = "Jimmy Location"

df_display = df[display_cols].copy()
df_display.rename(columns=col_mapping, inplace=True)

# Convert stock to numeric for filtering
df_display["Current Stock"] = pd.to_numeric(df_display["Current Stock"], errors="coerce").fillna(0).astype(int)

# Remove empty MPN rows
df_display = df_display[df_display["MPN"].str.strip() != ""]

# --- Summary ---
total_mpns = len(df_display)
in_stock = len(df_display[df_display["Current Stock"] > 0])
out_of_stock = len(df_display[df_display["Current Stock"] <= 0])

col1, col2, col3 = st.columns(3)
col1.metric("Total MPNs", total_mpns)
col2.metric("In Stock", in_stock)
col3.metric("Out of Stock", out_of_stock)

st.markdown("---")

# --- Search & Filter ---
search_col, filter_col = st.columns([3, 1])
with search_col:
    search = st.text_input("🔍 Search MPN, Specs, Project, or Note", placeholder="Type to search...")
with filter_col:
    stock_filter = st.selectbox("Stock Level", ["All", "In Stock (>0)", "Out of Stock (0)"])

# Apply filters
filtered = df_display.copy()
if search:
    search_lower = search.lower()
    mask = (
        filtered["MPN"].str.lower().str.contains(search_lower, na=False) |
        filtered["Specs"].str.lower().str.contains(search_lower, na=False) |
        filtered["Project"].str.lower().str.contains(search_lower, na=False) |
        filtered["Note"].str.lower().str.contains(search_lower, na=False)
    )
    filtered = filtered[mask]

if stock_filter == "In Stock (>0)":
    filtered = filtered[filtered["Current Stock"] > 0]
elif stock_filter == "Out of Stock (0)":
    filtered = filtered[filtered["Current Stock"] <= 0]

st.markdown(f"**{len(filtered)} items** shown")

# --- Color-code stock levels ---
def highlight_stock(row):
    stock = row.get("Current Stock", 0)
    if stock > 0:
        return ["background-color: #d4edda"] * len(row)
    else:
        return ["background-color: #f8d7da"] * len(row)

st.dataframe(
    filtered.style.apply(highlight_stock, axis=1),
    height=600,
    hide_index=True,
)
