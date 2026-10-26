"""Run data retention cleanup."""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import init_db, close_db
from app.db.repository import Repository


async def main() -> None:
    days = int(os.getenv("DATA_RETENTION_DAYS", "30"))
    await init_db()
    repo = Repository()
    removed = await repo.cleanup_old_records(days=days)
    await close_db()
    print(f"Cleanup removed: {removed}")


if __name__ == "__main__":
    asyncio.run(main())