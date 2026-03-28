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
    category: str = "general"  # general, smt, fpc, sourcing, jlc_smt


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
    """Generate a dynamic checklist based on order type."""
    items = []

    def add(text: str, category: str = "general"):
        items.append(asdict(ChecklistItem(
            id=str(uuid.uuid4())[:8],
            text=text,
            category=category,
        )))

    # Universal items
    add("Place bare board order")
    add("Reply ETA on Slack")
    add("Update AllComponents sheet")
    add("Update PCB Delivery sheet")

    # SMT items
    if order.needs_smt:
        add("BOM preparation complete", "smt")
        add("SMT route decided (JLC / Xinhai / Aoxingda)", "smt")

    # FPC specific
    if order.pcb_type.upper() == "FPC" or "flex" in order.pcb_name.lower():
        add("Translate stiffener/process notes to Chinese", "fpc")

    # SMT external vendor items
    if order.needs_smt:
        add("Supplier quote received (if external SMT)", "smt")
        add("Order placed", "smt")

    # EQ handling
    add("Handle JLCPCB EQ (if any)")

    # Sourcing items
    add("Special part sourcing (if needed)", "sourcing")
    add("Ship parts to Jimmy + tracking number (if needed)", "sourcing")
    add("Register tracking in JLCPCB system (if JLC SMT + external parts)", "sourcing")
    add("Add MPN to Stock sheet (special sourcing only)", "sourcing")

    return items
