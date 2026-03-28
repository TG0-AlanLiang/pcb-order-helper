"""User authentication and role-based access control."""
from __future__ import annotations

import streamlit as st

from config import ALLOWED_USERS, IS_LOCAL


def get_current_user() -> dict | None:
    """Get the currently logged-in user.

    Returns dict with {email, name, role} or None if not authorized.
    - Cloud mode: reads st.experimental_user.email
    - Local dev mode: returns admin user (Alan)
    """
    if IS_LOCAL:
        return {"email": "alan@tg0.com.hk", "name": "Alan", "role": "admin"}

    try:
        email = st.experimental_user.get("email", "").lower().strip()
    except Exception:
        return None

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
        st.error("Access denied. Your Google account is not authorized to use this app.")
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
