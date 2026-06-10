"""CRUD operations for the Orders tab in Google Sheet."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

import gspread
from gspread.utils import rowcol_to_a1

from config import GOOGLE_SHEET_ID, TAB_ORDERS, ORDERS_HEADERS
from utils import data_cache
from utils.google_client import with_worksheet
from utils.models import Order, generate_checklist

_CACHE_KEY = "orders"
_TTL = 60


def _create_orders_ws(ss: gspread.Spreadsheet) -> gspread.Worksheet:
    """Create the Orders worksheet (auto-create when missing)."""
    ws = ss.add_worksheet(title=TAB_ORDERS, rows=1000, cols=len(ORDERS_HEADERS))
    ws.insert_row(ORDERS_HEADERS, index=1)
    return ws


def _on_orders_ws(fn):
    """Run fn(ws) on the cached Orders worksheet handle."""
    return with_worksheet(TAB_ORDERS, fn, create=_create_orders_ws)


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


def _load_orders() -> list[dict]:
    result = _on_orders_ws(_parse_rows)
    return result if result is not None else []


def fetch_all_orders() -> list[dict]:
    """Fetch all orders from the Orders tab (cached 60s, write-through)."""
    return data_cache.get(_CACHE_KEY, _TTL, _load_orders, spinner="Loading orders…")


def fetch_orders_by_engineer(email: str) -> list[dict]:
    """Fetch orders for a specific engineer email."""
    all_orders = fetch_all_orders()
    email_lower = email.lower().strip()
    return [o for o in all_orders if o.get("EngineerEmail", "").lower().strip() == email_lower]


def fetch_orders_for_user(email: str, name: str) -> list[dict]:
    """Get orders where user is engineer OR reviewer."""
    all_orders = fetch_all_orders()
    email_lower = email.lower().strip()
    name_lower = name.lower().strip()
    return [o for o in all_orders
            if o.get("EngineerEmail", "").lower().strip() == email_lower
            or o.get("Reviewer", "").lower().strip() == name_lower]


def fetch_order_by_id(order_id: str) -> dict | None:
    """Find a single order by OrderID."""
    for o in fetch_all_orders():
        if o.get("OrderID") == order_id:
            return o
    return None


def _clear_cache():
    """Drop the orders cache so the next read refetches."""
    data_cache.invalidate(_CACHE_KEY)


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
        "",                                             # BareBoardCostCNY
        "",                                             # BOMCostCNY
        "",                                             # SMTCostCNY
        order_data.get("reviewer", ""),                  # Reviewer
        "",                                             # DeliveryNumber
    ]

    _on_orders_ws(lambda ws: ws.insert_row(row, index=2, value_input_option="USER_ENTERED"))
    # write-through: new order goes to the top (insert_row index=2)
    data_cache.insert_row(_CACHE_KEY, dict(zip(ORDERS_HEADERS, row)), top=True)
    return order_id


def update_order(client: gspread.Client, order_id: str, updates: dict):
    """Update specific fields of an order by OrderID.

    Args:
        client: authenticated gspread client
        order_id: the OrderID to update
        updates: dict of {column_header: new_value}
    """
    if not updates:
        return

    def _do(ws: gspread.Worksheet):
        # 1 round trip: column A (to find the row) + row 1 (live headers).
        # Always a fresh col-A read — create_order inserts at row 2 and shifts
        # every row, so row indices must never be cached.
        col_a, header_rows = ws.batch_get(["A:A", "1:1"])
        if not header_rows:
            return
        headers = header_rows[0]

        # col_a includes the header at index 0, so sheet row = i + 1
        row_idx = None
        for i, cell in enumerate(col_a):
            if (cell[0] if cell else "") == order_id:
                row_idx = i + 1
                break
        if row_idx is None:
            return

        # Build all cell writes, then send in ONE batch_update call
        data = []
        for col_name, value in updates.items():
            if col_name in headers:
                col_idx = headers.index(col_name) + 1  # 1-indexed
                data.append({
                    "range": rowcol_to_a1(row_idx, col_idx),
                    "values": [[value]],
                })
        if data:
            ws.batch_update(data, value_input_option="USER_ENTERED")  # 1 round trip
            # write-through: patch only the columns we actually wrote (these
            # keys are real Orders headers, so set them verbatim).
            written = {k: v for k, v in updates.items() if k in headers}
            data_cache.patch_rows(
                _CACHE_KEY,
                lambda r: r.get("OrderID") == order_id,
                written,
            )

    _on_orders_ws(_do)


def update_checklist(client: gspread.Client, order_id: str, checklist: list[dict]):
    """Update the checklist JSON for an order."""
    checklist_json = json.dumps(checklist, ensure_ascii=False)
    update_order(client, order_id, {"ChecklistJSON": checklist_json})


# --- Orders <-> PCB Delivery linkage ---

def _vendor_display(order: dict, vendor_num: str, smt_route: str) -> str:
    """Compose the PCB Delivery 'vendor Order number' value (order# + SMT route)."""
    needs_smt = order.get("NeedsSMT", "No") == "Yes"
    if needs_smt and smt_route:
        return f"{vendor_num}; {smt_route}" if vendor_num else smt_route
    return vendor_num


def sync_order_to_delivery(client: gspread.Client, order: dict,
                           vendor_num: str, smt_route: str, eta: str):
    """If this order is linked to a PCB Delivery row, push the latest
    vendor/SMT and ETA to that row. No-op if not yet linked (not ordered).
    """
    dn = (order.get("DeliveryNumber") or "").strip()
    if not dn:
        return
    from utils.sheet_handler import update_delivery_cells
    update_delivery_cells(client, int(dn), {
        "vendor Order number": _vendor_display(order, vendor_num, smt_route),
        "ETA (UK)": eta,
    })


def ensure_delivery_for_order(client: gspread.Client, order: dict,
                              vendor_num: str, smt_route: str, eta: str,
                              extra_order_updates: dict | None = None) -> int:
    """At 'ordered': create the PCB Delivery row if not already linked and
    store its Number back on the order; if already linked, just sync.
    Returns the delivery Number.

    extra_order_updates: extra Orders fields (e.g. {"Status": "ordered"}) to
    write together with DeliveryNumber so the status flip and the linkage land
    in ONE update_order call instead of two.
    """
    extra = extra_order_updates or {}
    dn = (order.get("DeliveryNumber") or "").strip()
    if dn:
        sync_order_to_delivery(client, order, vendor_num, smt_route, eta)
        if extra:
            update_order(client, order.get("OrderID", ""), extra)
        return int(dn)

    from utils.sheet_handler import get_next_delivery_number, add_delivery_row
    next_num = get_next_delivery_number(client)
    created = order.get("CreatedAt", "")
    order_date = created.split(" ")[0] if created else datetime.now().strftime("%Y-%m-%d")
    row = [
        next_num,
        order_date,
        order.get("Priority", "Normal"),
        order.get("PCBName", ""),
        _vendor_display(order, vendor_num, smt_route),
        "",  # Photo
        order.get("Recipient", ""),
        "",  # Jimmy received
        "",  # Jimmy ship remark
        eta,
        order.get("EngineerName", ""),  # Register
    ]
    add_delivery_row(client, row)
    update_order(client, order.get("OrderID", ""),
                 {"DeliveryNumber": str(next_num), **extra})
    return next_num
