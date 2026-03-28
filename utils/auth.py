"""User authentication and role-based access control."""
from __future__ import annotations

import streamlit as st

from config import ALLOWED_USERS, IS_LOCAL


def _get_cloud_email() -> str:
    """Get email from Streamlit Cloud auth, trying multiple API versions."""
    # Streamlit >= 1.37: st.context.user (preferred)
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


def get_current_user() -> dict | None:
    """Get the currently logged-in user.

    Returns dict with {email, name, role} or None if not authorized.
    - Cloud mode: reads user email from Streamlit auth
    - Local dev mode: returns admin user (Alan)
    """
    if IS_LOCAL:
        return {"email": "alan@tg0.com.hk", "name": "Alan", "role": "admin"}

    email = _get_cloud_email()

    if not email:
        return None

    user_info = ALLOWED_USERS.get(email)
    if user_info is None:
        return None

    return {"email": email, "name": user_info["name"], "role": user_info["role"]}


def require_auth() -> dict:
    """Require authentication. Shows error and stops if not authorized."""
    user = get_current_user()
    if user is None:
        email = _get_cloud_email()
        st.error("🔒 Access Denied")
        if email:
            st.markdown(f"Your account **{email}** is not authorized to use this app.")
        else:
            st.markdown("Your Google account is not authorized to use this app.")
            st.markdown("**Note:** The app owner must enable 'Require viewers to log in with Google' in Streamlit Cloud settings.")
        st.info("Contact Alan (alan@tg0.com.hk) to request access.")
        st.stop()
    return user


def require_role(role: str) -> dict:
    """Require a specific role. Shows error and stops if insufficient permissions."""
    user = require_auth()
    if user["role"] != role and user["role"] != "admin":
        st.error(f"This page requires '{role}' access. Your role: '{user['role']}'")
        st.stop()
    return user


def is_admin(user: dict) -> bool:
    """Check if user has admin role."""
    return user.get("role") == "admin"
