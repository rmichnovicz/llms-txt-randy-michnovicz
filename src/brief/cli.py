from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from brief.crawl.runner import crawl
from brief.db import Database
from brief.store import Store
from brief.worker import run_forever, run_once


def main() -> int:
    parser = argparse.ArgumentParser(description="Brief source pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Apply pending Postgres migrations")
    worker = commands.add_parser("worker", help="Run durable crawl jobs")
    worker.add_argument("--once", action="store_true")
    commands.add_parser("schedule", help="Enqueue due daily refreshes, then exit")
    crawl_parser = commands.add_parser("crawl", help="Inspect a crawl without a database or model")
    crawl_parser.add_argument("url")
    crawl_parser.add_argument("--max-pages", type=int, default=None)
    crawl_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if args.command == "crawl":
        result = asyncio.run(crawl(args.url, max_pages=args.max_pages))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result.as_dict(), indent=2) + "\n")
        print(f"Extracted {len(result.sources)} sources; {len(result.warnings)} warnings; truncated={result.truncated}")
        return 0 if result.sources else 1
    database = Database()
    if args.command == "migrate":
        database.migrate()
        print("Migrations applied")
    elif args.command == "schedule":
        print(f"Scheduled {Store(database).schedule_due()} checks")
    elif args.command == "worker":
        from brief.model import OpenAIGenerator

        generator = OpenAIGenerator() if os.environ.get("OPENAI_API_KEY") else None
        asyncio.run(
            run_once(Store(database), generator=generator)
            if args.once
            else run_forever(Store(database), generator=generator)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
