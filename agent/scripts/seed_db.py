"""Seed default vocabulary and prompts into the database."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import init_db, close_db
from app.db.repository import Repository


async def main() -> None:
    await init_db()
    repo = Repository()

    # vocabulary
    vocab_path = Path(__file__).resolve().parents[1] / "app" / "prompts" / "vocabulary.json"
    if vocab_path.exists():
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
        words = data.get("words", data if isinstance(data, list) else [])
        for item in words:
            if isinstance(item, str):
                await repo.upsert_vocabulary(item)
            elif isinstance(item, dict):
                w = item.get("word") or item.get("text")
                if w:
                    await repo.upsert_vocabulary(w, tags=item.get("tags", []), metadata=item.get("metadata", {}))

    # prompt
    prompt_path = Path(__file__).resolve().parents[1] / "app" / "prompts" / "system_prompt.txt"
    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8")
        await repo.create_prompt(name="default", template=template, active=True, version="seed")

    await close_db()
    print("Database seeded.")


if __name__ == "__main__":
    asyncio.run(main())