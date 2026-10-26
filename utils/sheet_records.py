"""Read Sheets records without losing identifiers to display formatting."""
from decimal import Decimal


def cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return format(Decimal(str(value)), "f").removesuffix(".0")
    return str(value)


def read_records(ws) -> list[dict]:
    # Dates stay readable, while numeric IDs use their full stored values.
    values = ws.get_all_values(
        value_render_option="UNFORMATTED_VALUE",
        date_time_render_option="FORMATTED_STRING",
    )
    if len(values) < 2:
        return []
    headers = values[0]
    return [
        {header: cell_text(row[i]) for i, header in enumerate(headers)
         if header and i < len(row)}
        for row in values[1:]
        if any(cell_text(value).strip() for value in row)
    ]
