"""Message store for order-level messaging via Google Sheet Messages tab."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import gspread
import streamlit as st

from config import GOOGLE_SHEET_ID

TAB_MESSAGES = "Messages"


def _get_messages_worksheet(client: gspread.Client) -> gspread.Worksheet:
    ss = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        return ss.worksheet(TAB_MESSAGES)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=TAB_MESSAGES, rows=2000, cols=5)
        ws.update(values=[["MessageID", "OrderID", "Timestamp", "Author", "Content"]], range_name="A1:E1")
        return ws


@st.cache_data(ttl=15, show_spinner=False)
def _fetch_messages_cached(_sheet_id: str) -> list[dict]:
    from utils.google_client import get_gspread_client
    client = get_gspread_client()
    if not client:
        return []
    ws = _get_messages_worksheet(client)
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        return []
    headers = all_values[0]
    return [
        {headers[i]: row[i] for i in range(min(len(headers), len(row)))}
        for row in all_values[1:]
        if any(cell.strip() for cell in row)
    ]


def fetch_messages_for_order(order_id: str) -> list[dict]:
    messages = _fetch_messages_cached(GOOGLE_SHEET_ID)
    return [m for m in messages if m.get("OrderID") == order_id]


def fetch_unread_messages(user_name: str) -> list[dict]:
    """Get messages NOT authored by this user (i.e. messages from others on their orders)."""
    messages = _fetch_messages_cached(GOOGLE_SHEET_ID)
    return [m for m in messages if m.get("Author", "") != user_name]


def send_message(client: gspread.Client, order_id: str, author: str, content: str):
    ws = _get_messages_worksheet(client)
    msg_id = str(uuid.uuid4())[:8]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    col_a = ws.col_values(1)
    next_row = len(col_a) + 1
    ws.update(
        values=[[msg_id, order_id, now, author, content]],
        range_name=f"A{next_row}:E{next_row}",
    )
    _fetch_messages_cached.clear()
