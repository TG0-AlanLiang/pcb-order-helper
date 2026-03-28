"""Parse Slack PCB order messages into structured Order objects."""
from __future__ import annotations

import re
from utils.models import Order


def parse_slack_message(text: str) -> Order:
    """Parse a Slack PCB order message into an Order object.

    Handles formats like:
        Hey @Alan, please order PCB for ProjectName_revB
        1. Number of layers: 4
        2. PCB Type: Rigid
        ...
    """
    order = Order(raw_message=text)

    # Extract PCB name from first line or numbered items
    # Try "for the <name>" pattern
    name_match = re.search(r"(?:for|order)\s+(?:this\s+)?(?:PCB\s+)?(?:for\s+)?(?:the\s+)?(\S+[\w_\-]+)", text, re.IGNORECASE)
    if name_match:
        order.pcb_name = name_match.group(1).strip(" ,.")

    # Parse numbered fields (flexible format)
    lines = text.strip().split("\n")
    for line in lines:
        line_clean = line.strip()
        # Remove leading number+dot or bullet
        line_clean = re.sub(r"^\d+[\.\)]\s*", "", line_clean)

        lower = line_clean.lower()

        # Layers
        if "layer" in lower:
            m = re.search(r"(\d+)", line_clean)
            if m:
                order.layers = int(m.group(1))

        # PCB Type
        elif "pcb type" in lower or "type" in lower and ("rigid" in lower or "flex" in lower or "fpc" in lower):
            if "flex" in lower or "fpc" in lower:
                order.pcb_type = "FPC"
            else:
                order.pcb_type = "Rigid"

        # Thickness
        elif "thickness" in lower:
            m = re.search(r"([\d\.]+\s*mm)", line_clean, re.IGNORECASE)
            if m:
                order.thickness = m.group(1).replace(" ", "")

        # Solder mask colour
        elif "solder" in lower or "mask" in lower or "colour" in lower or "color" in lower:
            for color in ["Green", "Black", "White", "Blue", "Red", "Yellow", "Purple", "Matte Black", "Matte Green"]:
                if color.lower() in lower:
                    order.solder_mask_color = color
                    break

        # Quantity
        elif "quantity" in lower and "pcb" not in lower.split("quantity")[0][-5:]:
            m = re.search(r"(\d+)", line_clean)
            if m:
                order.quantity = int(m.group(1))

        # Priority
        elif "priority" in lower:
            if "urgent" in lower:
                order.priority = "URGENT"
            else:
                order.priority = "Normal"

        # Test by engineer
        elif "test" in lower:
            if "yes" in lower:
                order.test_by_engineer = "Yes"
            else:
                order.test_by_engineer = "No"

        # Recipient
        elif "recipient" in lower:
            # Extract names after the colon
            m = re.search(r"recipient[:\s]+(.+)", line_clean, re.IGNORECASE)
            if m:
                order.recipient = m.group(1).strip()

    # Extract engineer name from @mention
    mention_match = re.search(r"@(\w+(?:\s+\w+)?)", text)
    if mention_match:
        # The first @mention is usually directed at Alan, second might be engineer
        mentions = re.findall(r"@(\w+(?:\s+\w+)?)", text)
        # The message sender is the engineer (not Alan)
        for m in mentions:
            if "alan" not in m.lower():
                order.engineer = m
                break

    # Auto-detect FPC from PCB name
    if "flex" in order.pcb_name.lower() or "fpc" in order.pcb_name.lower():
        order.pcb_type = "FPC"

    return order
