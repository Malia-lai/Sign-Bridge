"""Restore database contents from a JSON backup file."""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import init_db, close_db
from app.db.repository import Repository


def _parse_dt(value):
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


async def main() -> None:
    src = os.getenv("BACKUP_FILE", "backup.json")
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    await init_db()
    repo = Repository()
    for item in data.get("feedback", []):
        item = dict(item)
        item.pop("id", None)
        if "created_at" in item:
            item["created_at"] = _parse_dt(item["created_at"])
        await repo.create_feedback(**item)
    for item in data.get("history", []):
        item = dict(item)
        item.pop("id", None)
        if "created_at" in item:
            item["created_at"] = _parse_dt(item["created_at"])
        await repo.create_history(**item)
    for item in data.get("vocabulary", []):
        item = dict(item)
        item.pop("id", None)
        for key in ("created_at", "updated_at"):
            if key in item:
                item[key] = _parse_dt(item[key])
        await repo.upsert_vocabulary(item.get("word"), **{k: v for k, v in item.items() if k != "word"})
    for item in data.get("prompts", []):
        item = dict(item)
        item.pop("id", None)
        for key in ("created_at", "updated_at"):
            if key in item:
                item[key] = _parse_dt(item[key])
        await repo.create_prompt(**item)
    await close_db()
    print(f"Restored from {src}")


if __name__ == "__main__":
    asyncio.run(main())