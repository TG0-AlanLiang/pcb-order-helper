"""Google Sheets read/write handler using gspread with Service Account."""
from __future__ import annotations

from typing import Optional

import gspread

from config import (
    GOOGLE_SHEET_ID,
    TAB_ALL_COMPONENTS,
    TAB_PCB_DELIVERY,
    TAB_STOCK,
)


def get_spreadsheet(client: gspread.Client) -> gspread.Spreadsheet:
    """Open the PCB tracking spreadsheet."""
    return client.open_by_key(GOOGLE_SHEET_ID)


# --- Stock operations ---

def fetch_stock_data(client: gspread.Client) -> list[dict]:
    """Fetch all stock data from the Stock tab."""
    sheet = get_spreadsheet(client)
    ws = sheet.worksheet(TAB_STOCK)
    records = ws.get_all_records()
    return records


def add_stock_entry(client: gspread.Client, mpn: str, specs: str = "",
                    project: str = "", note: str = ""):
    """Add a new MPN entry to the Stock tab (inserted at top, below header)."""
    sheet = get_spreadsheet(client)
    ws = sheet.worksheet(TAB_STOCK)
    ws.insert_row([mpn, specs, "", "", "", 0, project, note],
                  index=2, value_input_option="USER_ENTERED")


# --- AllComponents operations ---

def fetch_all_components(client: gspread.Client) -> list[dict]:
    """Fetch all records from AllComponents tab."""
    sheet = get_spreadsheet(client)
    ws = sheet.worksheet(TAB_ALL_COMPONENTS)
    all_values = ws.get_all_values()
    if len(all_values) < 3:
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
    records = fetch_all_components(client)
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


def add_component_rows(client: gspread.Client, rows: list[list]):
    """Add multiple rows to AllComponents tab (inserted at top, below headers).

    AllComponents has row 1 = role labels, row 2 = headers, data from row 3.
    Records are in descending order, so new rows go to row 3.
    """
    sheet = get_spreadsheet(client)
    ws = sheet.worksheet(TAB_ALL_COMPONENTS)
    for row in rows:
        ws.insert_row(row, index=3, value_input_option="USER_ENTERED")


# --- PCB Delivery operations ---

def fetch_pcb_delivery(client: gspread.Client) -> list[dict]:
    """Fetch all records from PCB Delivery tab."""
    sheet = get_spreadsheet(client)
    ws = sheet.worksheet(TAB_PCB_DELIVERY)
    all_values = ws.get_all_values()
    if len(all_values) < 2:
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
    records = fetch_pcb_delivery(client)
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
    sheet = get_spreadsheet(client)
    ws = sheet.worksheet(TAB_PCB_DELIVERY)
    ws.insert_row(row, index=2, value_input_option="USER_ENTERED")
