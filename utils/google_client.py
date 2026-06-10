"""Google API client using Service Account for headless (Cloud) deployment."""
from __future__ import annotations

import json
import os
import threading
from typing import Callable, Optional

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_ID, SERVICE_ACCOUNT_FILE, IS_LOCAL

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_gspread_client: Optional[gspread.Client] = None
_drive_service = None

# Cached Spreadsheet/Worksheet handles. open_by_key() + worksheet() each cost an
# API round trip (~0.7s combined), so resolving them once per process matters.
_spreadsheet: Optional[gspread.Spreadsheet] = None
_worksheets: dict[str, gspread.Worksheet] = {}
_handles_lock = threading.Lock()


def _load_credentials() -> Optional[Credentials]:
    """Load service account credentials from file or Streamlit secrets."""
    # Try local file first
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    # Try Streamlit secrets (for Cloud deployment)
    try:
        import streamlit as st
        if "gcp_service_account" in st.secrets:
            sa_info = st.secrets["gcp_service_account"]
            # Convert AttrDict to regular dict and ensure proper types
            sa_dict = dict(sa_info)
            # private_key may have literal \n that need to be actual newlines
            if "private_key" in sa_dict:
                sa_dict["private_key"] = sa_dict["private_key"].replace("\\n", "\n")
            return Credentials.from_service_account_info(sa_dict, scopes=SCOPES)
    except Exception as e:
        import streamlit as st
        st.error(f"Failed to load credentials from secrets: {e}")

    return None


def get_gspread_client() -> Optional[gspread.Client]:
    """Get authenticated gspread client using Service Account."""
    global _gspread_client
    if _gspread_client is not None:
        return _gspread_client

    creds = _load_credentials()
    if creds is None:
        return None

    _gspread_client = gspread.authorize(creds)
    return _gspread_client


def get_spreadsheet() -> Optional[gspread.Spreadsheet]:
    """Get the PCB tracking spreadsheet, resolving it via the API only once."""
    global _spreadsheet
    if _spreadsheet is not None:
        return _spreadsheet
    client = get_gspread_client()
    if client is None:
        return None
    with _handles_lock:
        if _spreadsheet is None:
            _spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    return _spreadsheet


def get_worksheet(tab: str,
                  create: Optional[Callable[[gspread.Spreadsheet], gspread.Worksheet]] = None
                  ) -> Optional[gspread.Worksheet]:
    """Get a worksheet handle by tab name, cached for the process lifetime.

    If the tab doesn't exist and `create` is given, it's called with the
    spreadsheet to build the tab (used for the auto-created Orders/Messages/
    Users tabs).
    """
    ws = _worksheets.get(tab)
    if ws is not None:
        return ws
    ss = get_spreadsheet()
    if ss is None:
        return None
    with _handles_lock:
        ws = _worksheets.get(tab)
        if ws is None:
            try:
                ws = ss.worksheet(tab)
            except gspread.exceptions.WorksheetNotFound:
                if create is None:
                    raise
                ws = create(ss)
            _worksheets[tab] = ws
    return ws


def invalidate_handles() -> None:
    """Drop cached Spreadsheet/Worksheet handles (e.g. after a tab rename)."""
    global _spreadsheet
    with _handles_lock:
        _spreadsheet = None
        _worksheets.clear()


def _is_stale_handle_error(e: Exception) -> bool:
    """A 400/404 APIError usually means the tab was renamed/deleted under us."""
    if isinstance(e, gspread.exceptions.WorksheetNotFound):
        return True
    if isinstance(e, gspread.exceptions.APIError):
        code = getattr(e, "code", None)
        if code is None:
            try:
                code = e.response.status_code
            except Exception:
                return False
        return code in (400, 404)
    return False


def with_worksheet(tab: str, fn: Callable[[gspread.Worksheet], object],
                   create: Optional[Callable] = None):
    """Run `fn(ws)` against a cached worksheet handle.

    On a stale-handle error (tab renamed/deleted since the handle was cached),
    drops all handles, re-resolves once and retries once. Quota/server errors
    (429/5xx) are NOT retried.
    """
    ws = get_worksheet(tab, create=create)
    if ws is None:
        return None
    try:
        return fn(ws)
    except (gspread.exceptions.WorksheetNotFound, gspread.exceptions.APIError) as e:
        if not _is_stale_handle_error(e):
            raise
        invalidate_handles()
        ws = get_worksheet(tab, create=create)
        if ws is None:
            raise
        return fn(ws)


def get_drive_service():
    """Get Google Drive API v3 service object."""
    global _drive_service
    if _drive_service is not None:
        return _drive_service

    creds = _load_credentials()
    if creds is None:
        return None

    from googleapiclient.discovery import build
    _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service
