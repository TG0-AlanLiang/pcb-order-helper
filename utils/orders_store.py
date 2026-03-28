"""CRUD operations for the Orders tab in Google Sheet."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import gspread
import streamlit as st

from config import GOOGLE_SHEET_ID, TAB_ORDERS, ORDERS_HEADERS
from utils.models import Order, generate_checklist


def _get_orders_worksheet(client: gspread.Client) -> gspread.Worksheet:
    """Get or create the Orders worksheet."""
    ss = client.open_by_key(GOOGLE_SHEET_ID)
    try:
        return ss.worksheet(TAB_ORDERS)
    except gspread.exceptions.WorksheetNotFound:
        ws = ss.add_worksheet(title=TAB_ORDERS, rows=1000, cols=len(ORDERS_HEADERS))
        ws.insert_row(ORDERS_HEADERS, index=1)
        return ws


def _parse_rows(ws: gspread.Worksheet) -> list[dict]:
    """Parse all rows into list of dicts."""
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        return []
    headers = all_values[0]
    records = []
    for row in all_values[1:]:
        record = {}
        for i, header in enumerate(headers):
            if i < len(row) and header:
                record[header] = row[i]
        records.append(record)
    return records


@st.cache_data(ttl=30, show_spinner=False)
def _fetch_all_orders_cached(_sheet_id: str, _tab: str) -> list[dict]:
    """Cached fetch - internal, do not call directly."""
    from utils.google_client import get_gspread_client
    client = get_gspread_client()
    if not client:
        return []
    ws = _get_orders_worksheet(client)
    return _parse_rows(ws)


def fetch_all_orders() -> list[dict]:
    """Fetch all orders from the Orders tab (cached 30s)."""
    return _fetch_all_orders_cached(GOOGLE_SHEET_ID, TAB_ORDERS)


def fetch_orders_by_engineer(email: str) -> list[dict]:
    """Fetch orders for a specific engineer email."""
    all_orders = fetch_all_orders()
    email_lower = email.lower().strip()
    return [o for o in all_orders if o.get("EngineerEmail", "").lower().strip() == email_lower]


def fetch_order_by_id(order_id: str) -> dict | None:
    """Find a single order by OrderID."""
    for o in fetch_all_orders():
        if o.get("OrderID") == order_id:
            return o
    return None


def _clear_cache():
    """Clear the orders cache so next read gets fresh data."""
    _fetch_all_orders_cached.clear()


def create_order(client: gspread.Client, order_data: dict) -> str:
    """Create a new order in the Orders tab.

    Args:
        client: authenticated gspread client
        order_data: dict with keys matching Order dataclass fields + engineer info

    Returns:
        The generated OrderID
    """
    order_id = str(uuid.uuid4())[:8]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build Order object for checklist generation
    order = Order(
        pcb_name=order_data.get("pcb_name", ""),
        layers=order_data.get("layers", 2),
        pcb_type=order_data.get("pcb_type", "Rigid"),
        thickness=order_data.get("thickness", "1.6mm"),
        solder_mask_color=order_data.get("solder_mask_color", "Green"),
        quantity=order_data.get("quantity", 5),
        priority=order_data.get("priority", "Normal"),
        test_by_engineer=order_data.get("test_by_engineer", "No"),
        recipient=order_data.get("recipient", ""),
        engineer=order_data.get("engineer_name", ""),
        needs_smt=order_data.get("needs_smt", False),
    )
    checklist = generate_checklist(order)
    checklist_json = json.dumps(checklist, ensure_ascii=False)

    row = [
        order_id,                                       # OrderID
        now,                                            # CreatedAt
        order_data.get("engineer_email", ""),            # EngineerEmail
        order_data.get("engineer_name", ""),             # EngineerName
        "new",                                          # Status
        order.pcb_name,                                 # PCBName
        str(order.layers),                              # Layers
        order.pcb_type,                                 # PCBType
        order.thickness,                                # Thickness
        order.solder_mask_color,                        # SolderMask
        str(order.quantity),                            # Quantity
        order.priority,                                 # Priority
        order.recipient,                                # Recipient
        "Yes" if order.needs_smt else "No",             # NeedsSMT
        "",                                             # SMTRoute
        "",                                             # VendorOrderNum
        "",                                             # ETA
        order_data.get("notes", ""),                    # Notes
        order_data.get("drive_file_link", ""),           # DriveFileLink
        checklist_json,                                 # ChecklistJSON
        order.test_by_engineer,                         # TestByEngineer
    ]

    ws = _get_orders_worksheet(client)
    ws.insert_row(row, index=2, value_input_option="USER_ENTERED")
    _clear_cache()
    return order_id


def update_order(client: gspread.Client, order_id: str, updates: dict):
    """Update specific fields of an order by OrderID.

    Args:
        client: authenticated gspread client
        order_id: the OrderID to update
        updates: dict of {column_header: new_value}
    """
    ws = _get_orders_worksheet(client)
    all_values = ws.get_all_values()
    if len(all_values) < 2:
        return

    headers = all_values[0]

    # Find the row with matching OrderID
    for row_idx, row in enumerate(all_values[1:], start=2):  # 1-indexed, skip header
        if row[0] == order_id:
            for col_name, value in updates.items():
                if col_name in headers:
                    col_idx = headers.index(col_name) + 1  # 1-indexed
                    ws.update_cell(row_idx, col_idx, value)
            _clear_cache()
            return


def update_checklist(client: gspread.Client, order_id: str, checklist: list[dict]):
    """Update the checklist JSON for an order."""
    checklist_json = json.dumps(checklist, ensure_ascii=False)
    update_order(client, order_id, {"ChecklistJSON": checklist_json})
