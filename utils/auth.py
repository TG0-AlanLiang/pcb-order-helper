"""User authentication and role-based access control."""
from __future__ import annotations

import streamlit as st

from config import ALLOWED_USERS, IS_LOCAL


def _get_cloud_email() -> str:
    """Get email from Streamlit Cloud auth, trying multiple API versions."""
    # Streamlit >= 1.37: st.context.user
    try:
        ctx = getattr(st, "context", None)
        if ctx:
            user_info = getattr(ctx, "user", None)
            if user_info:
                email = ""
                if isinstance(user_info, dict):
                    email = user_info.get("email", "")
                else:
                    email = getattr(user_info, "email", "")
                if email:
                    return email.lower().strip()
    except Exception:
        pass

    # Streamlit < 1.37: st.experimental_user
    try:
        exp_user = getattr(st, "experimental_user", None)
        if exp_user:
            email = ""
            if isinstance(exp_user, dict):
                email = exp_user.get("email", "")
            else:
                email = getattr(exp_user, "email", "")
            if email:
                return email.lower().strip()
    except Exception:
        pass

    return ""


def _prompt_email_login() -> str | None:
    """Show a simple email selector for Cloud deployment without OAuth."""
    st.markdown("### 👤 Select Your Account")
    st.markdown("Choose your name to continue:")

    # Build unique name list
    names_seen = {}
    for email, info in ALLOWED_USERS.items():
        name = info["name"]
        if name not in names_seen:
            names_seen[name] = {"email": email, "role": info["role"]}

    name_list = ["-- Select --"] + sorted(names_seen.keys())
    selected = st.selectbox("Who are you?", name_list, label_visibility="collapsed")

    if selected != "-- Select --":
        user_info = names_seen[selected]
        # Store in session state
        st.session_state["auth_email"] = user_info["email"]
        return user_info["email"]

    # Check if already selected
    if "auth_email" in st.session_state:
        return st.session_state["auth_email"]

    return None


def get_current_user() -> dict | None:
    """Get the currently logged-in user.

    Returns dict with {email, name, role} or None if not authorized.
    - Local dev mode: returns admin user (Alan)
    - Cloud with OAuth: reads user email from Streamlit auth
    - Cloud without OAuth: shows name selector
    """
    if IS_LOCAL:
        return {"email": "alan@tg0.com.hk", "name": "Alan", "role": "admin"}

    # Try Cloud OAuth first
    email = _get_cloud_email()

    # If no OAuth email, use session state (from name selector)
    if not email:
        email = st.session_state.get("auth_email", "")

    if not email:
        return None

    user_info = ALLOWED_USERS.get(email)
    if user_info is None:
        return None

    return {"email": email, "name": user_info["name"], "role": user_info["role"]}


def require_auth() -> dict:
    """Require authentication. Shows login prompt if not authenticated."""
    user = get_current_user()
    if user is None:
        _prompt_email_login()
        # Check again after selector
        user = get_current_user()
        if user is None:
            st.stop()
    return user


def require_role(role: str) -> dict:
    """Require a specific role."""
    user = require_auth()
    if user["role"] != role and user["role"] != "admin":
        st.error(f"This page requires '{role}' access. Your role: '{user['role']}'")
        st.stop()
    return user


def is_admin(user: dict) -> bool:
    """Check if user has admin role."""
    return user.get("role") == "admin"


def is_logistics(user: dict) -> bool:
    """Check if user has logistics role."""
    return user.get("role") == "logistics"
