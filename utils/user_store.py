"""User management via Google Sheet Users tab."""
from __future__ import annotations

from typing import Optional

import gspread
import streamlit as st

from config import GOOGLE_SHEET_ID

TAB_USERS = "Users"

# Hardcoded fallback admin - prevents lockout if Sheet is empty/broken
FALLBACK_ADMIN = {"email": "alan@tg0.com.hk", "name": "Alan", "role": "admin"}


def _get_users_worksheet(client: gspread.Client) -> gspread.Worksheet:
    """Get or create the Users worksheet."""
    ss = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        return ss.worksheet(TAB_USERS)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=TAB_USERS, rows=50, cols=3)
        ws.update(values=[["Email", "Name", "Role"]], range_name="A1:C1")
        # Add fallback admin
        ws.update(values=[[FALLBACK_ADMIN["email"], FALLBACK_ADMIN["name"], FALLBACK_ADMIN["role"]]], range_name="A2:C2")
        return ws


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_users_cached(_sheet_id: str) -> dict:
    """Cached fetch of users from Sheet. Returns {email: {name, role}}."""
    from utils.google_client import get_gspread_client
    client = get_gspread_client()
    if not client:
        return {FALLBACK_ADMIN["email"]: {"name": FALLBACK_ADMIN["name"], "role": FALLBACK_ADMIN["role"]}}

    try:
        ws = _get_users_worksheet(client)
        all_values = ws.get_all_values()
        if len(all_values) < 2:
            return {FALLBACK_ADMIN["email"]: {"name": FALLBACK_ADMIN["name"], "role": FALLBACK_ADMIN["role"]}}

        users = {}
        for row in all_values[1:]:  # Skip header
            if len(row) >= 3 and row[0].strip():
                email = row[0].strip().lower()
                name = row[1].strip()
                role = row[2].strip().lower()
                if role not in ("admin", "engineer", "logistics"):
                    role = "engineer"
                users[email] = {"name": name, "role": role}

        # Always ensure fallback admin exists
        if FALLBACK_ADMIN["email"] not in users:
            users[FALLBACK_ADMIN["email"]] = {"name": FALLBACK_ADMIN["name"], "role": FALLBACK_ADMIN["role"]}

        return users
    except Exception:
        return {FALLBACK_ADMIN["email"]: {"name": FALLBACK_ADMIN["name"], "role": FALLBACK_ADMIN["role"]}}


def fetch_allowed_users() -> dict:
    """Get the allowed users dict (cached 60s)."""
    return _fetch_users_cached(GOOGLE_SHEET_ID)


def _clear_cache():
    _fetch_users_cached.clear()


def add_user(client: gspread.Client, email: str, name: str, role: str):
    """Add a user to the Users tab."""
    ws = _get_users_worksheet(client)
    col_a = ws.col_values(1)
    next_row = len(col_a) + 1
    ws.update(values=[[email.lower().strip(), name.strip(), role.lower().strip()]], range_name=f"A{next_row}:C{next_row}")
    _clear_cache()


def remove_user(client: gspread.Client, email: str):
    """Remove a user from the Users tab by email."""
    if email.lower().strip() == FALLBACK_ADMIN["email"]:
        raise ValueError("Cannot remove the primary admin account")

    ws = _get_users_worksheet(client)
    all_values = ws.get_all_values()
    target_email = email.lower().strip()

    for row_idx, row in enumerate(all_values[1:], start=2):
        if row[0].strip().lower() == target_email:
            ws.delete_rows(row_idx)
            _clear_cache()
            return

    raise ValueError(f"User {email} not found")


def update_user_role(client: gspread.Client, email: str, new_role: str):
    """Update a user's role."""
    ws = _get_users_worksheet(client)
    all_values = ws.get_all_values()
    target_email = email.lower().strip()

    for row_idx, row in enumerate(all_values[1:], start=2):
        if row[0].strip().lower() == target_email:
            ws.update_cell(row_idx, 3, new_role.lower().strip())
            _clear_cache()
            return

    raise ValueError(f"User {email} not found")
