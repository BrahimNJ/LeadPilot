"""CSV downloads that are safe to open in a spreadsheet."""

import csv
import io
from collections.abc import Iterable, Sequence

from fastapi import Response

MAX_EXPORT_ROWS = 10_000
# A cell starting with one of these runs as a formula when the file is opened in a spreadsheet.
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> object:
    """Make text that a spreadsheet would run as a formula display as plain text instead."""
    if value is None:
        return ""
    if isinstance(value, str) and value.startswith(_FORMULA_STARTS):
        return "'" + value
    return value


def csv_response(
    columns: Sequence[str], rows: Iterable[Sequence[object]], filename: str
) -> Response:
    """A CSV attachment with a header row, every cell passed through `safe_cell`."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return Response(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
