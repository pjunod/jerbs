#!/usr/bin/env python3
"""
update_run.py — jerbs criteria.json updater and lock guard

Usage:
    python3 update_run.py --check-lock
    python3 update_run.py --set-lock
    python3 update_run.py --clear-lock
    python3 update_run.py --add-ids id1 id2 ...
"""

import argparse
import json
import os
from datetime import date, datetime, timezone

CRITERIA_PATH = os.path.expanduser("~/.claude/jerbs/criteria.json")
LOCK_PATH = os.path.expanduser("~/.claude/jerbs/.running")


def check_lock():
    if os.path.exists(LOCK_PATH):
        print("LOCKED")
    else:
        print("CLEAR")


def set_lock():
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        f.write(datetime.now(timezone.utc).isoformat())
    print("Lock set.")


def clear_lock():
    if os.path.exists(LOCK_PATH):
        os.remove(LOCK_PATH)
    print("Lock cleared.")


def add_ids(new_ids):
    with open(CRITERIA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    existing = data.get("screened_message_ids", [])
    today = date.today().isoformat()

    # Migrate legacy plain-string entries to object format
    migrated = []
    for entry in existing:
        if isinstance(entry, str):
            migrated.append({"id": entry, "screened_at": "2000-01-01"})
        else:
            migrated.append(entry)

    existing_ids = {e["id"] for e in migrated}
    added = 0
    for new_id in new_ids:
        if new_id not in existing_ids:
            migrated.append({"id": new_id, "screened_at": today})
            existing_ids.add(new_id)
            added += 1

    data["screened_message_ids"] = migrated
    data["last_run_date"] = today

    with open(CRITERIA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Added {added} new IDs. Total: {len(migrated)}. last_run_date set to {today}.")


def main():
    parser = argparse.ArgumentParser(description="jerbs criteria updater and lock guard")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-lock", action="store_true", help="Print LOCKED or CLEAR")
    group.add_argument("--set-lock", action="store_true", help="Create the lock file")
    group.add_argument("--clear-lock", action="store_true", help="Remove the lock file")
    group.add_argument("--add-ids", nargs="+", metavar="ID", help="Add screened message IDs")
    args = parser.parse_args()

    if args.check_lock:
        check_lock()
    elif args.set_lock:
        set_lock()
    elif args.clear_lock:
        clear_lock()
    elif args.add_ids:
        add_ids(args.add_ids)


if __name__ == "__main__":
    main()
