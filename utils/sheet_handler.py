"""Google Sheets read/write handler using gspread with Service Account."""
from __future__ import annotations

from typing import Optional

import gspread
import streamlit as st
from gspread.utils import rowcol_to_a1

from config import (
    GOOGLE_SHEET_ID,
    TAB_ALL_COMPONENTS,
    TAB_PCB_DELIVERY,
    TAB_STOCK,
)
from utils.google_client import with_worksheet


def get_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    """Open the PCB tracking spreadsheet (prefer google_client.get_spreadsheet)."""
    from utils.google_client import get_spreadsheet as _cached
    return _cached()


# --- Cache invalidation helpers ---

def _invalidate_pcb_delivery_cache():
    fetch_pcb_delivery.clear()


def _invalidate_components_cache():
    fetch_all_components.clear()


def _invalidate_stock_cache():
    fetch_stock_data.clear()
    fetch_stock_values.clear()


# --- Stock operations ---

@st.cache_data(ttl=120, show_spinner=False)
def fetch_stock_data(_client_id: str = "") -> list[dict]:
    """Fetch all stock data from the Stock tab. Cached 2 minutes."""
    result = with_worksheet(TAB_STOCK, lambda ws: ws.get_all_records())
    return result if result is not None else []


@st.cache_data(ttl=120, show_spinner=False)
def fetch_stock_values(_client_id: str = "") -> list[list]:
    """Raw 2D values of the Stock tab (headers + rows). Cached 2 minutes.

    Used by the Stock page, which needs raw values (Stock tab has duplicate /
    blank header cells that break get_all_records()).
    """
    result = with_worksheet(TAB_STOCK, lambda ws: ws.get_all_values())
    return result if result is not None else []


def add_stock_entry(client: gspread.Client, mpn: str, specs: str = "",
                    project: str = "", note: str = ""):
    """Add a new MPN entry to the Stock tab.

    Only writes to unprotected columns (A, B, F, G, H) to avoid
    hitting protected columns C:D.
    """
    def _do(ws: gspread.Worksheet):
        # Find next empty row in column A (1 round trip)
        col_a = ws.col_values(1)
        next_row = len(col_a) + 1
        # Write only to unprotected cells, in ONE batch_update (1 round trip).
        # A:B = MPN + Specs; G:H = Project + Note. Skip C,D (protected) and
        # E,F (formulas).
        ws.batch_update([
            {"range": f"A{next_row}:B{next_row}", "values": [[mpn, specs]]},
            {"range": f"G{next_row}:H{next_row}", "values": [[project, note]]},
        ], value_input_option="USER_ENTERED")

    with_worksheet(TAB_STOCK, _do)
    _invalidate_stock_cache()


# --- AllComponents operations ---

@st.cache_data(ttl=60, show_spinner=False)
def fetch_all_components(_client=None) -> list[dict]:
    """Fetch all records from AllComponents tab. Cached 60s."""
    all_values = with_worksheet(TAB_ALL_COMPONENTS, lambda ws: ws.get_all_values())
    if not all_values or len(all_values) < 3:
        return []
    headers = all_values[1]  # Row 2 is headers
    data = all_values[2:]    # Row 3+ is data
    records = []
    for row in data:
        record = {}
        for i, header in enumerate(headers):
            if i < len(row) and header:
                record[header] = row[i]
        records.append(record)
    return records


def get_next_component_id(client: gspread.Client) -> int:
    """Get the next available ID for AllComponents."""
    records = fetch_all_components()
    if not records:
        return 1
    max_id = 0
    for r in records:
        try:
            rid = int(r.get("ID", 0))
            max_id = max(max_id, rid)
        except (ValueError, TypeError):
            pass
    return max_id + 1


def update_component_cells(client: gspread.Client, component_id: int,
                           updates: dict):
    """Update multiple cells of one AllComponents row in a single batch write.

    Args:
        client: authenticated gspread client
        component_id: the ID value in column A
        updates: dict of {column_name: value}, where column_name matches
                 (or is contained in) the row-2 header text

    Does 2 round trips total (1 fetch + 1 batch_update) regardless of how
    many fields are updated.
    """
    if not updates:
        return

    def _do(ws: gspread.Worksheet):
        # 1 round trip: column A (find row by ID) + row 2 (headers for fuzzy match)
        col_a, header_rows = ws.batch_get(["A:A", "2:2"])
        if not header_rows:
            raise ValueError("AllComponents tab has no data")
        headers = header_rows[0]  # Row 2 is headers

        # Resolve each column name to a 1-indexed column number
        def _resolve_col(name: str):
            for i, h in enumerate(headers):
                if h.strip().startswith(name) or name in h:
                    return i + 1
            return None

        col_map = {name: _resolve_col(name) for name in updates}
        missing = [n for n, c in col_map.items() if c is None]
        if missing:
            raise ValueError(f"Columns not found: {missing}")

        # Find row by ID (column A, data starts at row 3).
        # col_a includes rows 1,2 at indices 0,1 -> sheet row = i + 1
        for i, cell in enumerate(col_a):
            row_idx = i + 1
            if row_idx < 3:
                continue
            try:
                if int(cell[0] if cell else "") == component_id:
                    data = [
                        {"range": rowcol_to_a1(row_idx, col_map[name]),
                         "values": [[value]]}
                        for name, value in updates.items()
                    ]
                    ws.batch_update(data, value_input_option="USER_ENTERED")  # 1 round trip
                    _invalidate_components_cache()
                    return
            except (ValueError, IndexError):
                continue

        raise ValueError(f"Component ID {component_id} not found")

    with_worksheet(TAB_ALL_COMPONENTS, _do)


def update_component_cell(client: gspread.Client, component_id: int,
                          column_name: str, value: str):
    """Update a single cell in AllComponents (thin wrapper over the batch version)."""
    update_component_cells(client, component_id, {column_name: value})


def add_component_rows(client: gspread.Client, rows: list[list]):
    """Add multiple rows to AllComponents tab (inserted at top, below headers).

    AllComponents has row 1 = role labels, row 2 = headers, data from row 3.
    Records are in descending order, so new rows go to row 3.
    """
    if not rows:
        return
    # Single insert_rows call instead of N insert_row round trips.
    with_worksheet(TAB_ALL_COMPONENTS,
                   lambda ws: ws.insert_rows(rows, row=3, value_input_option="USER_ENTERED"))
    _invalidate_components_cache()


# --- PCB Delivery operations ---

@st.cache_data(ttl=60, show_spinner=False)
def fetch_pcb_delivery(_client=None) -> list[dict]:
    """Fetch all records from PCB Delivery tab. Cached 60s."""
    all_values = with_worksheet(TAB_PCB_DELIVERY, lambda ws: ws.get_all_values())
    if not all_values or len(all_values) < 2:
        return []
    headers = all_values[0]
    data = all_values[1:]
    records = []
    for row in data:
        record = {}
        for i, header in enumerate(headers):
            if i < len(row) and header:
                record[header] = row[i]
        records.append(record)
    return records


def get_next_delivery_number(client: gspread.Client) -> int:
    """Get the next available Number for PCB Delivery."""
    records = fetch_pcb_delivery()
    if not records:
        return 1
    max_num = 0
    for r in records:
        try:
            rnum = int(r.get("Number", 0))
            max_num = max(max_num, rnum)
        except (ValueError, TypeError):
            pass
    return max_num + 1


def add_delivery_row(client: gspread.Client, row: list):
    """Add a row to PCB Delivery tab (inserted at top, below header).

    PCB Delivery has row 1 = headers, data from row 2.
    Records are in descending order, so new rows go to row 2.
    """
    with_worksheet(TAB_PCB_DELIVERY,
                   lambda ws: ws.insert_row(row, index=2, value_input_option="USER_ENTERED"))
    _invalidate_pcb_delivery_cache()


def update_delivery_cell(client: gspread.Client, delivery_number: int,
                         column_name: str, value: str):
    """Update a specific cell in PCB Delivery by delivery Number and column name.

    Args:
        client: authenticated gspread client
        delivery_number: the Number value in column A
        column_name: key from PCB_DELIVERY_COLS (e.g. "Jimmy Received")
        value: the new cell value
    """
    # Thin wrapper over the batch version (column letters are static).
    update_delivery_cells(client, delivery_number, {column_name: value})


def update_delivery_cells(client: gspread.Client, delivery_number: int,
                          updates: dict):
    """Update multiple cells of one PCB Delivery row in a single batch write.

    Args:
        client: authenticated gspread client
        delivery_number: the Number value in column A
        updates: dict of {column_name: value}, keys from PCB_DELIVERY_COLS

    Does 2 round trips total (1 fetch + 1 batch_update).
    """
    if not updates:
        return
    from config import PCB_DELIVERY_COLS

    # Resolve column letters -> 1-indexed numbers
    col_map = {}
    for name in updates:
        letter = PCB_DELIVERY_COLS.get(name)
        if not letter:
            raise ValueError(f"Unknown delivery column: {name}")
        col_map[name] = ord(letter.upper()) - ord("A") + 1

    def _do(ws: gspread.Worksheet):
        # Only column A is needed to find the row (column letters are static).
        col_a = ws.col_values(1)
        for row_idx, val in enumerate(col_a[1:], start=2):  # skip header
            try:
                if int(val) == delivery_number:
                    data = [
                        {"range": rowcol_to_a1(row_idx, col_map[name]),
                         "values": [[value]]}
                        for name, value in updates.items()
                    ]
                    ws.batch_update(data, value_input_option="USER_ENTERED")
                    _invalidate_pcb_delivery_cache()
                    return
            except (ValueError, IndexError):
                continue
        raise ValueError(f"Delivery number {delivery_number} not found")

    with_worksheet(TAB_PCB_DELIVERY, _do)
