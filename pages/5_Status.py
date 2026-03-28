"""Status page - System configuration and connection status."""
import streamlit as st
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.auth import require_role
from config import SERVICE_ACCOUNT_FILE, GOOGLE_SHEET_ID, DRIVE_FOLDER_ID, ALLOWED_USERS

require_role("admin")

st.title("⚙️ Status")

# --- Service Account status ---
st.header("Google API Connection")

col1, col2 = st.columns(2)
with col1:
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        st.success("Service Account JSON found")
    else:
        st.error("No service_account.json found")

with col2:
    if GOOGLE_SHEET_ID != "YOUR_GOOGLE_SHEET_ID_HERE":
        st.success(f"Sheet ID: `{GOOGLE_SHEET_ID[:20]}...`")
    else:
        st.error("Google Sheet ID not configured")

st.markdown(f"**Drive Folder ID:** `{DRIVE_FOLDER_ID}`")

# Test connection
st.header("Test Connection")
if st.button("Test Google Sheet Connection"):
    try:
        from utils.google_client import get_gspread_client
        client = get_gspread_client()
        if client:
            ss = client.open_by_key(GOOGLE_SHEET_ID)
            st.success(f"Connected to: **{ss.title}**")
            for ws in ss.worksheets():
                st.markdown(f"- **{ws.title}**: {ws.row_count} rows x {ws.col_count} cols")
        else:
            st.error("Failed to create client")
    except Exception as e:
        st.error(f"Connection failed: {e}")

if st.button("Test Google Drive Connection"):
    try:
        from utils.google_client import get_drive_service
        service = get_drive_service()
        if service:
            folder = service.files().get(fileId=DRIVE_FOLDER_ID, fields="name").execute()
            st.success(f"Connected to Drive folder: **{folder.get('name')}**")
        else:
            st.error("Failed to create Drive service")
    except Exception as e:
        st.error(f"Drive connection failed: {e}")

# Orders status
st.header("Orders Data")
from utils.orders_store import fetch_all_orders
orders = fetch_all_orders()
from config import ORDER_STATUSES
st.markdown(f"**{len(orders)} total orders**")
for status in ORDER_STATUSES:
    count = sum(1 for o in orders if o.get("Status") == status)
    if count > 0:
        st.markdown(f"- {status}: {count}")

# User configuration
st.header("Allowed Users")
admins = {k: v for k, v in ALLOWED_USERS.items() if v["role"] == "admin"}
engineers = {k: v for k, v in ALLOWED_USERS.items() if v["role"] == "engineer"}

st.markdown("**Admins:**")
seen = set()
for email, info in admins.items():
    if info["name"] not in seen:
        st.markdown(f"- {info['name']} ({email})")
        seen.add(info["name"])

st.markdown("**Engineers:**")
seen = set()
for email, info in engineers.items():
    if info["name"] not in seen:
        st.markdown(f"- {info['name']} ({email})")
        seen.add(info["name"])
