"""Backup database contents to a JSON file."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import init_db, close_db
from app.db.repository import Repository
from scripts._db_utils import to_dict


async def main() -> None:
    out = os.getenv("BACKUP_FILE", "backup.json")
    await init_db()
    repo = Repository()
    data = {
        "feedback": [to_dict(x) for x in await repo.list_feedback(limit=100000)],
        "history": [to_dict(x) for x in await repo.list_history(limit=100000)],
        "vocabulary": [to_dict(x) for x in await repo.list_vocabulary(limit=100000)],
        "prompts": [to_dict(x) for x in await repo.list_prompts(limit=100000)],
    }
    Path(out).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    await close_db()
    print(f"Backup written to {out}")


if __name__ == "__main__":
    asyncio.run(main())