"""Quick Supabase/Postgres connectivity + schema check for the TradeXBot backend.

Run from the backend/ directory:

    python scripts/check_db.py

It verifies that:
  1. DATABASE_URL is set to something other than the local default,
  2. the backend can open a connection and run a query,
  3. the expected tables (users, transactions, referrals) exist,
  4. (best effort) reports row counts.

Exits with code 0 on success, 1 on any failure — handy for CI or a pre-start gate.
"""

import sys
from pathlib import Path

# Allow running as `python scripts/check_db.py` from the backend/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.core.config import settings  # noqa: E402

EXPECTED_TABLES = ["users", "transactions", "referrals"]
LOCAL_DEFAULT = "postgresql+psycopg://tradexbot:tradexbot@localhost:5432/tradexbot"


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    print("TradeXBot - database connection check\n")

    url = settings.DATABASE_URL
    if not url:
        fail("DATABASE_URL is empty. Set it in backend/.env (Supabase Session pooler URI).")
    if url == LOCAL_DEFAULT:
        fail(
            "DATABASE_URL is still the local default. Set it to your Supabase connection "
            "string in backend/.env (Project Settings -> Database -> Connection string)."
        )

    # Show a redacted target so the user can confirm host/db without leaking the password.
    safe = make_url(url)
    host = safe.host or "?"
    print(f"  * Target: {safe.drivername} -> {host}:{safe.port or '?'} / {safe.database or '?'}")
    if "supabase" not in (host or ""):
        print("  ! Host does not look like Supabase - continuing anyway.")

    kwargs: dict = {"pool_pre_ping": True}
    if settings.DB_USE_NULL_POOL:
        from sqlalchemy.pool import NullPool

        kwargs["poolclass"] = NullPool

    try:
        engine = create_engine(url, **kwargs)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("  [OK] Connection OK")

            inspector = inspect(conn)
            existing = set(inspector.get_table_names())
            missing = [t for t in EXPECTED_TABLES if t not in existing]
            if missing:
                fail(
                    f"Connected, but missing table(s): {', '.join(missing)}. "
                    "Run db/schema.sql in the Supabase SQL Editor, or start the app "
                    "once with AUTO_CREATE_TABLES=true."
                )
            print(f"  [OK] Tables present: {', '.join(EXPECTED_TABLES)}")

            for table in EXPECTED_TABLES:
                count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
                print(f"      - {table}: {count} row(s)")

    except SQLAlchemyError as exc:
        # Surface the root cause (auth, DNS, SSL, pooler mode) without the full traceback.
        fail(f"Database error: {exc.__class__.__name__}: {str(exc).splitlines()[0]}")

    print("\nAll checks passed. Backend can reach Supabase.")
    sys.exit(0)


if __name__ == "__main__":
    main()
