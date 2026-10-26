"""Message store for order-level messaging via Google Sheet Messages tab."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import gspread

from config import GOOGLE_SHEET_ID
from utils import data_cache
from utils.google_client import with_worksheet
from utils.sheet_records import read_records

TAB_MESSAGES = "Messages"
_CACHE_KEY = "messages_raw_ids_v1"
_TTL = 30
_HEADERS = ["MessageID", "OrderID", "Timestamp", "Author", "Content"]


def _create_messages_ws(ss: gspread.Spreadsheet) -> gspread.Worksheet:
    ws = ss.add_worksheet(title=TAB_MESSAGES, rows=2000, cols=5)
    ws.update(values=[["MessageID", "OrderID", "Timestamp", "Author", "Content"]], range_name="A1:E1")
    return ws


def _on_messages_ws(fn):
    return with_worksheet(TAB_MESSAGES, fn, create=_create_messages_ws)


def _load_messages() -> list[dict]:
    return _on_messages_ws(read_records) or []


def fetch_all_messages() -> list[dict]:
    """All messages (cached 30s, write-through)."""
    return data_cache.get(_CACHE_KEY, _TTL, _load_messages)


def fetch_messages_for_order(order_id: str) -> list[dict]:
    return [m for m in fetch_all_messages() if m.get("OrderID") == order_id]


def fetch_unread_messages(user_name: str) -> list[dict]:
    """Get messages NOT authored by this user (i.e. messages from others on their orders)."""
    return [m for m in fetch_all_messages() if m.get("Author", "") != user_name]


def send_message(client: gspread.Client, order_id: str, author: str, content: str):
    from utils.orders_store import fetch_order_by_id, OrderIdentityError

    if fetch_order_by_id(order_id) is None:
        raise OrderIdentityError("Order not found. Refresh the page before sending a message.")
    msg_id = f"msg_{uuid.uuid4().hex}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    # append_row appends after the last data row in one API round trip
    _on_messages_ws(lambda ws: ws.append_row(
        [msg_id, order_id, now, author, content], value_input_option="RAW"))
    # write-through: append to the end (messages are chronological)
    data_cache.insert_row(_CACHE_KEY,
                          dict(zip(_HEADERS, [msg_id, order_id, now, author, content])),
                          top=False)
