"""Parse Altium BOM Excel files with flexible column detection."""
from __future__ import annotations

import re
from typing import Optional

import pandas as pd


# Known column name variants for each field
COLUMN_VARIANTS = {
    "comment": ["comment", "comments", "comp comment"],
    "description": ["description", "desc", "part description"],
    "designator": ["designator", "designators", "reference", "ref des", "refdes"],
    "quantity": ["quantity", "qty", "count", "number"],
    "value": ["value", "val", "comp value"],
    "package": ["case/package", "package", "footprint", "case", "pcb footprint"],
    "mpn": ["mpn", "manufacturer part number", "manufacturer part", "mfr part", "mfg part number", "part number"],
    "lcsc": ["lcsc", "lcsc part", "lcsc part#", "jlc part #", "jlcpcb part #", "立创编号", "lcsc part number"],
    "manufacturer": ["manufacturer", "mfr", "mfg", "vendor"],
}


def _match_column(col_name: str, field: str) -> bool:
    """Check if a column name matches a known variant for a field."""
    col_lower = col_name.strip().lower()
    return col_lower in COLUMN_VARIANTS.get(field, [])


def _find_column(df_columns: list[str], field: str) -> Optional[str]:
    """Find the actual column name in the DataFrame that matches a field."""
    for col in df_columns:
        if _match_column(col, field):
            return col
    return None


def parse_bom(file_path: str) -> tuple[pd.DataFrame, dict[str, Optional[str]]]:
    """Parse an Altium BOM Excel file.

    Returns:
        (parsed_dataframe, column_mapping)
        where column_mapping shows which actual columns were found for each field.
    """
    # Read Excel, try to find the header row
    df_raw = pd.read_excel(file_path, header=None)

    # Find header row: look for a row that contains 'Comment' or 'Designator'
    header_row = 0
    for idx, row in df_raw.iterrows():
        row_str = " ".join(str(v).lower() for v in row.values if pd.notna(v))
        if "comment" in row_str or "designator" in row_str or "description" in row_str:
            header_row = idx
            break

    # Re-read with correct header
    df = pd.read_excel(file_path, header=header_row)

    # Drop completely empty columns
    df = df.dropna(axis=1, how="all")

    # Map columns
    col_mapping = {}
    for field in COLUMN_VARIANTS:
        col_mapping[field] = _find_column(df.columns.tolist(), field)

    # Build clean DataFrame with standardized columns
    clean_data = []
    for _, row in df.iterrows():
        entry = {}

        # Comment (often contains part info like "100nF" or MPN)
        if col_mapping["comment"]:
            entry["Comment"] = str(row[col_mapping["comment"]]) if pd.notna(row[col_mapping["comment"]]) else ""
        else:
            entry["Comment"] = ""

        # Description
        if col_mapping["description"]:
            entry["Description"] = str(row[col_mapping["description"]]) if pd.notna(row[col_mapping["description"]]) else ""
        else:
            entry["Description"] = ""

        # Designator
        if col_mapping["designator"]:
            entry["Designator"] = str(row[col_mapping["designator"]]) if pd.notna(row[col_mapping["designator"]]) else ""
        else:
            entry["Designator"] = ""

        # Quantity
        if col_mapping["quantity"]:
            try:
                entry["Quantity"] = int(float(row[col_mapping["quantity"]]))
            except (ValueError, TypeError):
                entry["Quantity"] = 0
        else:
            entry["Quantity"] = 0

        # Value
        if col_mapping["value"]:
            entry["Value"] = str(row[col_mapping["value"]]) if pd.notna(row[col_mapping["value"]]) else ""
        else:
            entry["Value"] = ""

        # Package
        if col_mapping["package"]:
            entry["Package"] = str(row[col_mapping["package"]]) if pd.notna(row[col_mapping["package"]]) else ""
        else:
            entry["Package"] = ""

        # MPN (optional)
        if col_mapping["mpn"]:
            entry["MPN"] = str(row[col_mapping["mpn"]]) if pd.notna(row[col_mapping["mpn"]]) else ""
        else:
            # Try to extract MPN from Comment (if it looks like a part number)
            entry["MPN"] = _extract_mpn_from_comment(entry["Comment"])

        # LCSC (optional)
        if col_mapping["lcsc"]:
            entry["LCSC"] = str(row[col_mapping["lcsc"]]) if pd.notna(row[col_mapping["lcsc"]]) else ""
        else:
            entry["LCSC"] = ""

        # Skip rows with no useful data
        if entry["Designator"] or entry["Comment"] or entry["Description"]:
            clean_data.append(entry)

    result_df = pd.DataFrame(clean_data)
    return result_df, col_mapping


def _extract_mpn_from_comment(comment: str) -> str:
    """Try to extract an MPN from the Comment field.

    MPNs typically look like alphanumeric strings with dashes,
    not simple values like '100nF' or '10k'.
    Returns empty string for generic passive component descriptions.
    """
    if not comment:
        return ""
    # Skip generic passive component descriptions
    # e.g., "Capacitor 100nF +/-5% 25V 0402", "Resistor 10k 0603"
    passive_keywords = ["capacitor", "resistor", "inductor", "ferrite", "fuse"]
    if any(comment.lower().startswith(kw) for kw in passive_keywords):
        return ""
    # Skip simple values like "100nF", "10k", "4.7uF"
    if re.match(r"^[\d\.]+\s*(pF|nF|uF|µF|ohm|Ω|k|M|R|H|uH|mH)\s*$", comment, re.IGNORECASE):
        return ""
    # Skip "Header" / "Connector" style generic descriptions with counts
    if re.match(r"^(header|connector|test\s*point|mounting\s*hole|jumper)\b", comment, re.IGNORECASE):
        return ""
    # Skip descriptions that contain common passive descriptors with tolerances
    if re.search(r"\+/-\d+%", comment):
        return ""
    # If it looks like a real part number (no spaces, or compact alphanumeric), keep it
    # Real MPNs: RCLAMP0524PATCT, TPS62063DSG, IQS7222A, ESP32-S3-WROOM-1
    if not re.search(r"\s", comment.strip()) and len(comment.strip()) > 3:
        return comment.strip()
    # If it contains a dash and alphanumeric chars, might be an MPN like ESP32-S3-WROOM-1
    if re.search(r"^[A-Z0-9][\w\-]+$", comment.strip(), re.IGNORECASE) and len(comment.strip()) > 4:
        return comment.strip()
    return ""


def summarize_bom(df: pd.DataFrame) -> dict:
    """Generate summary statistics for a parsed BOM."""
    total_unique = len(df)
    total_components = df["Quantity"].sum() if "Quantity" in df.columns else 0
    has_mpn = len(df[df["MPN"] != ""]) if "MPN" in df.columns else 0
    has_lcsc = len(df[df["LCSC"] != ""]) if "LCSC" in df.columns else 0

    return {
        "total_unique_parts": total_unique,
        "total_components": int(total_components),
        "parts_with_mpn": has_mpn,
        "parts_with_lcsc": has_lcsc,
        "parts_without_mpn": total_unique - has_mpn,
    }
