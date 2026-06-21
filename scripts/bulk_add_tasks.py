#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import (  # noqa: E402
    CategoryCreate,
    ItemCreate,
    SessionLocal,
    add_category_tasks_bulk,
    add_custom_item_tasks_bulk,
    create_category_record,
    create_item_record,
    find_category_by_identifier,
    find_item_by_identifier,
    initialize_database,
)


def parse_task_lines(path: Path) -> list[tuple[str, str]]:
    tasks: list[tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        title, separator, description = line.partition("|")
        tasks.append((title.strip(), description.strip() if separator else ""))
    return tasks


def normalize_inline_tasks(values: list[str]) -> list[tuple[str, str]]:
    tasks: list[tuple[str, str]] = []
    for value in values:
        title, separator, description = value.partition("|")
        title = title.strip()
        if title:
            tasks.append((title, description.strip() if separator else ""))
    return tasks


def require_category(db, identifier: str):
    category = find_category_by_identifier(db, identifier)
    if category is None:
        raise SystemExit(f"Category not found: {identifier}")
    return category


def require_item(db, identifier: str):
    item = find_item_by_identifier(db, identifier)
    if item is None:
        raise SystemExit(f"Item not found: {identifier}")
    return item


def seed_demo(db) -> None:
    category = find_category_by_identifier(db, "Venue Launch")
    if category is None:
        category = create_category_record(
            db,
            CategoryCreate(
                name="Venue Launch",
                description="Sample category for checking the tracker UI",
                start_date="2026-05-08",
                end_date="2026-05-15",
                required_fields_schema=[
                    {"name": "Priority", "type": "number"},
                    {"name": "Event Date", "type": "date"},
                    {"name": "Owner", "type": "text"},
                ],
            ),
        )
    elif category.start_date is None or category.end_date is None:
        category.start_date = category.start_date or "2026-05-08"
        category.end_date = category.end_date or "2026-05-15"
        db.commit()

    baseline_tasks = [
        ("Confirm venue availability", "Call the venue coordinator"),
        ("Collect attendee estimate", "Use the latest registration count"),
        ("Review accessibility needs", "Check parking, ramps, and seating"),
    ]
    add_category_tasks_bulk(db, category, baseline_tasks, sync_existing_items=True)

    item = find_item_by_identifier(db, "North Hall Product Mixer")
    if item is None:
        item = create_item_record(
            db,
            ItemCreate(
                name="North Hall Product Mixer",
                category_id=category.id,
                custom_data={
                    "Priority": 1,
                    "Event Date": "2026-05-22",
                    "Owner": "Siva",
                },
            ),
        )

    custom_tasks = [
        ("Send catering headcount update", ""),
        ("Prepare VIP welcome list", ""),
        ("Print backup check-in sheets", ""),
    ]
    add_custom_item_tasks_bulk(db, item, custom_tasks)
    print(f"Demo data ready: category={category.name!r}, item={item.name!r}")


def collect_tasks(args) -> list[tuple[str, str]]:
    tasks: list[tuple[str, str]] = []
    if args.file:
        tasks.extend(parse_task_lines(Path(args.file)))
    tasks.extend(normalize_inline_tasks(args.tasks))
    if not tasks and not args.seed_demo:
        raise SystemExit("No tasks provided. Pass task titles or --file tasks.txt.")
    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bulk add Event Roster tasks to a category or item."
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--category", help="Category id or exact category name for baseline tasks")
    target.add_argument("--item", help="Item id or exact item name for custom item tasks")
    parser.add_argument("--file", help="Text file with one task per line. Use Title | Description.")
    parser.add_argument(
        "--sync-existing-items",
        action="store_true",
        help="When adding category tasks, also add missing baseline tasks to existing items.",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Create a sample category, item, baseline tasks, and custom tasks.",
    )
    parser.add_argument("tasks", nargs="*", help="Task titles, optionally Title | Description")
    args = parser.parse_args()

    initialize_database()
    with SessionLocal() as db:
        if args.seed_demo:
            seed_demo(db)
            return

        tasks = collect_tasks(args)
        if args.category:
            category = require_category(db, args.category)
            count = add_category_tasks_bulk(
                db, category, tasks, sync_existing_items=args.sync_existing_items
            )
            print(f"Added {count} baseline task(s) to category {category.name!r}.")
            if args.sync_existing_items:
                print("Existing items were synced with any missing baseline tasks.")
            return

        if args.item:
            item = require_item(db, args.item)
            count = add_custom_item_tasks_bulk(db, item, tasks)
            print(f"Added {count} custom task(s) to item {item.name!r}.")
            return

        raise SystemExit("Choose --category, --item, or --seed-demo.")


if __name__ == "__main__":
    main()
