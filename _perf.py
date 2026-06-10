"""Measure cold/warm fetch latencies for each Sheet tab.

Read-only by default. Run: python _perf.py
"""
import time

from utils.google_client import get_gspread_client, get_spreadsheet, get_worksheet


def _section(title):
    print(f"\n=== {title} ===")


# --- Auth + handle resolution (the ~0.7s/call we now pay only once) ---
_section("Handle resolution (once per process)")

t0 = time.time()
client = get_gspread_client()
print(f"get_gspread_client (auth):           {time.time()-t0:6.2f}s")

t0 = time.time()
ss = get_spreadsheet()
print(f"get_spreadsheet (cold open_by_key):  {time.time()-t0:6.2f}s")

t0 = time.time()
ss = get_spreadsheet()
print(f"get_spreadsheet (warm handle):       {time.time()-t0:6.4f}s")

for tab in ("Orders", "PCB Delivery", "AllComponents", "Stock", "Messages", "Users"):
    t0 = time.time()
    get_worksheet(tab)
    print(f"get_worksheet {tab:14} (cold):  {time.time()-t0:6.2f}s")

for tab in ("Orders", "PCB Delivery", "AllComponents", "Stock", "Messages", "Users"):
    t0 = time.time()
    get_worksheet(tab)
    print(f"get_worksheet {tab:14} (warm):  {time.time()-t0:6.4f}s")


# --- Warm-handle reads (1 round trip each, no open_by_key/worksheet overhead) ---
_section("Reads on cached handle (1 round trip each)")

for tab in ("Orders", "PCB Delivery", "AllComponents", "Stock", "Messages", "Users"):
    ws = get_worksheet(tab)
    t0 = time.time()
    vals = ws.get_all_values()
    print(f"{tab:16} get_all_values  {time.time()-t0:6.2f}s   rows={len(vals)}")


# --- App-level cached fetchers (cold then warm) ---
_section("App fetchers (cold = invalidate+fetch, warm = cache hit)")

from utils import data_cache
from utils.orders_store import fetch_all_orders
from utils.sheet_handler import (
    fetch_pcb_delivery, fetch_all_components, fetch_stock_data, fetch_stock_values,
)
from utils.message_store import fetch_all_messages
from utils.user_store import fetch_allowed_users


def timed(label, fn):
    data_cache.invalidate()  # cold (drop all tabs)
    t = time.time()
    res = fn()
    dt = time.time() - t
    n = len(res) if hasattr(res, "__len__") else "?"
    print(f"{label:32} cold {dt:6.2f}s   rows={n}")
    t = time.time()
    fn()
    print(f"{label:32} warm {time.time()-t:6.4f}s")


timed("Orders",        fetch_all_orders)
timed("PCB Delivery",  fetch_pcb_delivery)
timed("AllComponents", fetch_all_components)
timed("Stock (dicts)", fetch_stock_data)
timed("Stock (values)",fetch_stock_values)
timed("Messages",      fetch_all_messages)
timed("Users",         fetch_allowed_users)


# --- Write-through patch: a post-save rerun is a warm cache hit, not a refetch ---
_section("Write-through (patch keeps cache warm = no refetch)")

from utils.orders_store import _CACHE_KEY as ORDERS_KEY

fetch_all_orders()  # ensure warm
sample = fetch_all_orders()[0]
oid = sample.get("OrderID")
data_cache.patch_rows(ORDERS_KEY, lambda r: r.get("OrderID") == oid, {"Notes": "__sim__"})
t = time.time()
after = fetch_all_orders()  # should be instant + reflect the patch
dt = time.time() - t
patched = next((o for o in after if o.get("OrderID") == oid), {})
print(f"read after patch_rows: {dt:6.4f}s   Notes={patched.get('Notes')!r} (expect __sim__)")
