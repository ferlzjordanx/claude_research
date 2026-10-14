"""Show how an index changes a query plan (PostgreSQL only).

APP_DATABASE_URL=postgresql+psycopg://... python -m scripts.explain_demo
"""

from __future__ import annotations

from sqlalchemy import text

from app.config import get_settings
from app.db import make_engine

QUERY = """
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT id, total, created_at FROM demo_orders
WHERE customer_id = 4242
ORDER BY created_at DESC
LIMIT 20
"""


def main() -> None:
    engine = make_engine(get_settings())
    if engine.dialect.name != "postgresql":
        raise SystemExit("This demo needs PostgreSQL (APP_DATABASE_URL).")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS demo_orders"))
        conn.execute(
            text(
                "CREATE TABLE demo_orders (id bigserial PRIMARY KEY,"
                " customer_id int NOT NULL, total numeric(12,2) NOT NULL,"
                " created_at timestamptz NOT NULL)"
            )
        )
        # 500k rows, 10k customers: realistic enough to see the effect.
        conn.execute(
            text(
                "INSERT INTO demo_orders (customer_id, total, created_at)"
                " SELECT (random()*10000)::int,"
                " (random()*500)::numeric(12,2),"
                " now() - (random() * interval '365 days')"
                " FROM generate_series(1, 500000)"
            )
        )
        conn.execute(text("ANALYZE demo_orders"))
        print("--- BEFORE index ---")
        for row in conn.execute(text(QUERY)):
            print(row[0])
        conn.execute(
            text(
                "CREATE INDEX ix_demo_customer_created"
                " ON demo_orders (customer_id, created_at DESC)"
            )
        )
        conn.execute(text("ANALYZE demo_orders"))
        print("--- AFTER index ---")
        for row in conn.execute(text(QUERY)):
            print(row[0])
        conn.execute(text("DROP TABLE demo_orders"))


if __name__ == "__main__":
    main()
