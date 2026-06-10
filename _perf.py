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
_section("App fetchers (cold = clear+fetch, warm = cache hit)")

from utils.orders_store import _fetch_all_orders_cached
from utils.sheet_handler import (
    fetch_pcb_delivery, fetch_all_components, fetch_stock_data, fetch_stock_values,
)
from utils.message_store import _fetch_messages_cached
from utils.user_store import _fetch_users_cached
from config import GOOGLE_SHEET_ID, TAB_ORDERS


def timed(label, fn, clear_fn):
    clear_fn()  # cold
    t = time.time()
    res = fn()
    dt = time.time() - t
    n = len(res) if hasattr(res, "__len__") else "?"
    print(f"{label:32} cold {dt:6.2f}s   rows={n}")
    t = time.time()
    fn()
    print(f"{label:32} warm {time.time()-t:6.4f}s")


timed("Orders",        lambda: _fetch_all_orders_cached(GOOGLE_SHEET_ID, TAB_ORDERS), _fetch_all_orders_cached.clear)
timed("PCB Delivery",  lambda: fetch_pcb_delivery(),  fetch_pcb_delivery.clear)
timed("AllComponents", lambda: fetch_all_components(), fetch_all_components.clear)
timed("Stock (dicts)", lambda: fetch_stock_data(),    fetch_stock_data.clear)
timed("Stock (values)",lambda: fetch_stock_values(),  fetch_stock_values.clear)
timed("Messages",      lambda: _fetch_messages_cached(GOOGLE_SHEET_ID), _fetch_messages_cached.clear)
timed("Users",         lambda: _fetch_users_cached(GOOGLE_SHEET_ID),    _fetch_users_cached.clear)
