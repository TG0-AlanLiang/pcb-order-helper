"""Google API client using Service Account for headless (Cloud) deployment."""
from __future__ import annotations

import json
import os
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import SERVICE_ACCOUNT_FILE, IS_LOCAL

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_gspread_client: Optional[gspread.Client] = None
_drive_service = None


def _load_credentials() -> Optional[Credentials]:
    """Load service account credentials from file or Streamlit secrets."""
    # Try local file first
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    # Try Streamlit secrets (for Cloud deployment)
    try:
        import streamlit as st
        sa_info = st.secrets.get("gcp_service_account")
        if sa_info:
            return Credentials.from_service_account_info(dict(sa_info), scopes=SCOPES)
    except Exception:
        pass

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
