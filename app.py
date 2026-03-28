"""PCB Order Helper - Main entry point with role-based navigation."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

st.set_page_config(page_title="PCB Order Helper", page_icon="📊", layout="wide")

from utils.auth import get_current_user, is_admin, _prompt_email_login

# --- Auth gate ---
user = get_current_user()

if user is None:
    # Show login selector - use hidden navigation to prevent auto-discovery
    login_page = st.Page(lambda: None, title="Login", icon="🔒")
    pg = st.navigation([login_page], position="hidden")

    st.title("📊 PCB Order Helper")
    _prompt_email_login()

    # Re-check after selection
    user = get_current_user()
    if user is None:
        st.stop()
    else:
        st.rerun()

# Store user in session state
st.session_state["user"] = user

# --- Build page list based on role ---
shared_pages = [
    st.Page("pages/ee_submit_order.py", title="Submit Order", icon="📋"),
    st.Page("pages/ee_my_orders.py", title="My Orders", icon="📦"),
]

translator_page = [
    st.Page("pages/4_Translator.py", title="Translator", icon="🌐"),
]

admin_pages = []
status_pages = []
if is_admin(user):
    admin_pages = [
        st.Page("pages/admin_all_orders.py", title="All Orders", icon="📊", default=True),
        st.Page("pages/admin_process_order.py", title="Process Order", icon="🔧"),
        st.Page("pages/1_New_Order.py", title="New Order (Slack)", icon="💬"),
        st.Page("pages/2_BOM_Check.py", title="BOM Check", icon="🔍"),
        st.Page("pages/3_Sheet_Update.py", title="Sheet Update", icon="📝"),
    ]
    status_pages = [
        st.Page("pages/5_Status.py", title="Status", icon="⚙️"),
    ]

# Navigation structure
if is_admin(user):
    pages = {
        "Admin": admin_pages,
        "Orders": shared_pages,
        "Tools": translator_page + status_pages,
    }
else:
    pages = {
        "Orders": shared_pages,
        "Tools": translator_page,
    }

pg = st.navigation(pages)

# Show user info in sidebar
with st.sidebar:
    st.markdown("---")
    role_badge = "🔑 Admin" if is_admin(user) else "👤 Engineer"
    st.markdown(f"{role_badge} **{user['name']}**")
    st.caption(user["email"])
    if st.button("Logout", type="secondary", use_container_width=True):
        del st.session_state["auth_email"]
        del st.session_state["user"]
        st.rerun()

pg.run()
