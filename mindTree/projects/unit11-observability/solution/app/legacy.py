"""A 'legacy' report renderer we cannot change: synchronous and slow.

It stands in for real-world blocking code: a PDF library, boto3, a
sync DB driver, requests.get(), heavy CPU work.
"""

import csv
import io
import time
from collections.abc import Sequence

from app.schemas import RevenueRow


def render_report(rows: Sequence[RevenueRow], delay: float) -> str:
    time.sleep(delay)  # blocks the calling thread for `delay` seconds
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["customer_id", "name", "order_count", "total"])
    for row in rows:
        writer.writerow(
            [row.customer_id, row.name, row.order_count, row.total_cents]
        )
    return buffer.getvalue()
