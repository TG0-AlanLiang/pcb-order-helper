"""Check BOM components against stock inventory."""
from __future__ import annotations

import pandas as pd


def check_stock(bom_df: pd.DataFrame, stock_data: list[dict], pcb_quantity: int = 1) -> pd.DataFrame:
    """Compare BOM components against stock inventory.

    Args:
        bom_df: Parsed BOM DataFrame with at least MPN and Quantity columns.
        stock_data: List of dicts from Google Sheet Stock tab, each with
                     'Component MPN', 'Current Stock', etc.
        pcb_quantity: Number of PCBs to assemble (multiplier for BOM quantities).

    Returns:
        DataFrame with stock status for each component.
    """
    # Build stock lookup by MPN
    stock_lookup = {}
    for row in stock_data:
        mpn = str(row.get("Component MPN", "")).strip()
        if mpn:
            try:
                stock_qty = int(float(row.get("Current Stock", 0) or 0))
            except (ValueError, TypeError):
                stock_qty = 0
            stock_lookup[mpn.lower()] = {
                "mpn": mpn,
                "stock_qty": stock_qty,
                "location": row.get("Jimmy's location", ""),
                "note": row.get("Note", ""),
            }

    results = []
    for _, bom_row in bom_df.iterrows():
        mpn = str(bom_row.get("MPN", "")).strip()
        needed = int(bom_row.get("Quantity", 0)) * pcb_quantity
        lcsc = str(bom_row.get("LCSC", "")).strip()

        result = {
            "Comment": bom_row.get("Comment", ""),
            "Description": bom_row.get("Description", ""),
            "Designator": bom_row.get("Designator", ""),
            "Quantity_Per_Board": bom_row.get("Quantity", 0),
            "Total_Needed": needed,
            "MPN": mpn,
            "LCSC": lcsc,
            "Package": bom_row.get("Package", ""),
            "In_Stock": 0,
            "Stock_Status": "Unknown",
            "Shortfall": 0,
        }

        if mpn and mpn.lower() in stock_lookup:
            stock_info = stock_lookup[mpn.lower()]
            result["In_Stock"] = stock_info["stock_qty"]
            if stock_info["stock_qty"] >= needed:
                result["Stock_Status"] = "In Stock (Sufficient)"
                result["Shortfall"] = 0
            else:
                result["Stock_Status"] = "In Stock (Insufficient)"
                result["Shortfall"] = needed - stock_info["stock_qty"]
        elif mpn:
            result["Stock_Status"] = "Not In Stock"
            result["Shortfall"] = needed
        else:
            result["Stock_Status"] = "No MPN"
            result["Shortfall"] = needed

        # Tag LCSC availability
        if lcsc:
            result["Has_LCSC"] = True
        else:
            result["Has_LCSC"] = False

        results.append(result)

    return pd.DataFrame(results)


def suggest_smt_route(stock_result_df: pd.DataFrame, pcb_quantity: int) -> dict:
    """Suggest SMT route based on stock check results.

    Returns dict with recommendation and reasoning.
    """
    total_parts = len(stock_result_df)
    if total_parts == 0:
        return {"route": "N/A", "reason": "No components in BOM"}

    has_lcsc_count = stock_result_df["Has_LCSC"].sum() if "Has_LCSC" in stock_result_df.columns else 0
    lcsc_ratio = has_lcsc_count / total_parts

    reasons = []

    # Decision logic
    if lcsc_ratio > 0.8 and total_parts <= 20:
        route = "JLC SMT"
        reasons.append(f"{has_lcsc_count}/{total_parts} parts have LCSC numbers ({lcsc_ratio:.0%})")
        reasons.append(f"Component count is manageable ({total_parts} unique parts)")
    elif pcb_quantity > 100:
        route = "Aoxingda (奥兴达)"
        reasons.append(f"Quantity is {pcb_quantity} (>100), suitable for production run")
        reasons.append("Recommend 天佳/鹏创达 for BOM quoting")
    elif lcsc_ratio < 0.5 or total_parts > 30:
        route = "Xinhai (新海)"
        reasons.append(f"Only {has_lcsc_count}/{total_parts} parts have LCSC numbers ({lcsc_ratio:.0%})")
        reasons.append("Too many parts without LCSC for JLC SMT")
        reasons.append("Recommend 天佳/鹏创达 for BOM quoting")
    else:
        route = "JLC SMT or Xinhai (新海)"
        reasons.append(f"{has_lcsc_count}/{total_parts} parts have LCSC numbers ({lcsc_ratio:.0%})")
        reasons.append("Borderline - check JLC part availability before deciding")

    return {
        "route": route,
        "reasons": reasons,
        "lcsc_ratio": lcsc_ratio,
        "total_parts": total_parts,
        "has_lcsc": int(has_lcsc_count),
    }
