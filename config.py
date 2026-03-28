"""Configuration for PCB Order Helper."""
import os

# --- Environment detection ---
# PCB_LOCAL_DEV=1 → local mode (auto-login as admin)
# PCB_LOCAL_DEV=0 or not set on Linux → cloud mode (require Google OAuth)
# Windows always defaults to local mode unless explicitly set to 0
_is_windows = os.name == "nt"
IS_LOCAL = os.environ.get("PCB_LOCAL_DEV", "1" if _is_windows else "0") == "1"

# --- Google Sheets configuration ---
GOOGLE_SHEET_ID = os.environ.get("PCB_SHEET_ID", "1_RGsAnpA7kBrszeORo3LfTWh7QSM1-WbZF-XySe6s2I")
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")

# Google Drive shared folder for file uploads
DRIVE_FOLDER_ID = os.environ.get("PCB_DRIVE_FOLDER_ID", "1FkIGTEjPY9GsfR05BE3Fwt0rw6B4sBoL")

# Local download base path (admin only, local mode)
LOCAL_DOWNLOAD_BASE = r"C:\Users\yingf\OneDrive\Documents\Work_Related\PCB Order Follow up"

# --- Sheet tab names ---
TAB_ALL_COMPONENTS = "AllComponents"
TAB_STOCK = "Stock"
TAB_PCB_DELIVERY = "PCB Delivery"
TAB_ORDERS = "Orders"

# --- Order statuses ---
ORDER_STATUSES = ["new", "processing", "ordered", "shipped", "delivered"]
STATUS_COLORS = {
    "new": "gray",
    "processing": "blue",
    "ordered": "orange",
    "shipped": "violet",
    "delivered": "green",
}

# --- Column mappings for AllComponents (0-indexed from actual data row) ---
ALL_COMPONENTS_COLS = {
    "ID": "A",
    "Record Date": "B",
    "Priority": "C",
    "PCB Name": "D",
    "Components": "E",
    "Count": "F",
    "MPN": "G",
    "BOM Quantity": "H",
    "Order Quantity": "I",
    "Unit Price (CNY)": "J",
    "Category": "K",
    "JLC SMT Order": "L",
    "PCB Quantity": "M",
    "Supplier": "N",
    "Component Source": "O",
    "Status": "P",
    "Order Date": "Q",
    "ETD": "R",
    "Point of Contact": "S",
    "Notes": "T",
}

# Column mappings for PCB Delivery (must match actual Sheet headers)
PCB_DELIVERY_COLS = {
    "Number": "A",
    "Order date": "B",
    "Piority": "C",
    "PCB Name": "D",
    "vendor Order number": "E",
    "Photo": "F",
    "Recipient": "G",
    "Jimmy received check": "H",
    "Jimmy Shipp out remark": "I",
    "ETA (UK)": "J",
}

# Column mappings for Stock
STOCK_COLS = {
    "Component MPN": "A",
    "Specs": "B",
    "Current Stock": "F",
    "Project": "G",
    "Note": "H",
}

# --- Orders tab column headers (must match the Google Sheet) ---
ORDERS_HEADERS = [
    "OrderID", "CreatedAt", "EngineerEmail", "EngineerName", "Status",
    "PCBName", "Layers", "PCBType", "Thickness", "SolderMask",
    "Quantity", "Priority", "Recipient", "NeedsSMT", "SMTRoute",
    "VendorOrderNum", "ETA", "Notes", "DriveFileLink", "ChecklistJSON",
    "TestByEngineer",
]

# --- User configuration ---
# Two UK email domains are interchangeable: @tangi0.com ↔ @tg0.co.uk
# We list all known variants so users can log in with either.
ALLOWED_USERS = {
    # Admins
    "alan@tg0.com.hk":     {"name": "Alan",    "role": "admin"},
    "shaoze@tg0.co.uk":    {"name": "Shaoze",  "role": "admin"},
    "shaoze@tangi0.com":   {"name": "Shaoze",  "role": "admin"},
    # Logistics (Jimmy)
    "jimmy@tangi0.com":    {"name": "Jimmy",   "role": "logistics"},
    "jimmy@tg0.co.uk":     {"name": "Jimmy",   "role": "logistics"},
    # Engineers
    "berk@tg0.co.uk":      {"name": "Berk",    "role": "engineer"},
    "berk@tangi0.com":     {"name": "Berk",    "role": "engineer"},
    "joseph@tg0.co.uk":    {"name": "Joseph",  "role": "engineer"},
    "joseph@tangi0.com":   {"name": "Joseph",  "role": "engineer"},
    "wende@tangi0.com":    {"name": "Wende",   "role": "engineer"},
    "wende@tg0.co.uk":     {"name": "Wende",   "role": "engineer"},
    "mozmel@tangi0.com":   {"name": "Mozmel",  "role": "engineer"},
    "mozmel@tg0.co.uk":    {"name": "Mozmel",  "role": "engineer"},
}

# Data directory (kept for backward compat, will be phased out)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
