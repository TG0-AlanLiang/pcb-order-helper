"""Data models for PCB Order Helper."""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ChecklistItem:
    """A single checklist item for a project."""
    id: str
    text: str
    done: bool = False
    category: str = "general"  # general, smt, fpc, sourcing


@dataclass
class Order:
    """Parsed order from Slack message or web form."""
    pcb_name: str = ""
    layers: int = 2
    pcb_type: str = "Rigid"  # Rigid / FPC
    thickness: str = "1.6mm"
    solder_mask_color: str = "Green"
    quantity: int = 5
    priority: str = "Normal"  # Normal / URGENT
    test_by_engineer: str = "No"
    recipient: str = ""
    engineer: str = ""
    needs_smt: bool = False
    raw_message: str = ""


def generate_checklist(order: Order) -> list[dict]:
    """Generate a dynamic checklist based on order type.

    Only includes manual action items. Auto-handled items
    (PCB Delivery write, Stock MPN add) are excluded.
    """
    items = []

    def add(text: str, category: str = "general"):
        items.append(asdict(ChecklistItem(
            id=str(uuid.uuid4())[:8],
            text=text,
            category=category,
        )))

    # Core items (manual actions only)
    add("Place bare board order on JLCPCB")
    add("Reply ETA on Slack")

    # SMT items
    if order.needs_smt:
        add("BOM preparation complete", "smt")
        add("Decide SMT route (JLC / Xinhai / Ausinter)", "smt")
        add("Get supplier quote (if external SMT)", "smt")
        add("Place SMT order", "smt")

    # FPC specific
    if order.pcb_type.upper() == "FPC" or "flex" in order.pcb_name.lower():
        add("Translate stiffener/process notes to Chinese", "fpc")

    # EQ handling
    add("Handle JLCPCB EQ (if any)")

    # Sourcing (only manual items)
    if order.needs_smt:
        add("Special part sourcing (if needed)", "sourcing")
        add("Ship parts to Jimmy + fill tracking number", "sourcing")
        add("Register tracking in JLCPCB system (if JLC SMT + external parts)", "sourcing")

    return items
