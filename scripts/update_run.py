#!/usr/bin/env python3
"""
update_run.py — jerbs criteria.json updater and lock guard

Usage:
    python3 update_run.py --check-lock
    python3 update_run.py --set-lock
    python3 update_run.py --clear-lock
    python3 update_run.py --add-ids id1 id2 ...
    python3 update_run.py --enable-scheduler job_id_biz job_id_offhours
    python3 update_run.py --disable-scheduler
    python3 update_run.py --set-rapid-mode job_id rapid_mode_until_iso
    python3 update_run.py --clear-rapid-mode job_id_biz job_id_offhours
"""

import argparse
import json
import os
from datetime import UTC, date, datetime

CRITERIA_PATH = os.path.expanduser("~/.claude/jerbs/criteria.json")
LOCK_PATH = os.path.expanduser("~/.claude/jerbs/.running")


def _load():
    with open(CRITERIA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data):
    with open(CRITERIA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def check_lock():
    print("LOCKED" if os.path.exists(LOCK_PATH) else "CLEAR")


def set_lock():
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        f.write(datetime.now(UTC).isoformat())
    print("Lock set.")


def clear_lock():
    if os.path.exists(LOCK_PATH):
        os.remove(LOCK_PATH)
    print("Lock cleared.")


def add_ids(new_ids):
    data = _load()
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
    _save(data)
    print(f"Added {added} new IDs. Total: {len(migrated)}. last_run_date set to {today}.")


def enable_scheduler(cron_job_ids):
    data = _load()
    data.setdefault("scheduler", {})["enabled"] = True
    data["scheduler"]["cron_jobs"] = cron_job_ids
    _save(data)
    print(f"Scheduler enabled. cron_jobs: {cron_job_ids}")


def disable_scheduler():
    data = _load()
    data.setdefault("scheduler", {})["enabled"] = False
    data["scheduler"]["cron_jobs"] = []
    _save(data)
    print("Scheduler disabled.")


def set_rapid_mode(cron_job_ids, rapid_mode_until):
    """Switch to rapid mode: store single job ID and expiry timestamp."""
    data = _load()
    sched = data.setdefault("scheduler", {})
    sched["cron_jobs"] = cron_job_ids
    sched["rapid_mode_until"] = rapid_mode_until
    _save(data)
    print(f"Rapid mode set. expires: {rapid_mode_until}")


def clear_rapid_mode(cron_job_ids):
    """Revert from rapid mode: store standard job IDs and clear expiry."""
    data = _load()
    sched = data.setdefault("scheduler", {})
    sched["cron_jobs"] = cron_job_ids
    sched["rapid_mode_until"] = None
    _save(data)
    print(f"Rapid mode cleared. cron_jobs: {cron_job_ids}")


def main():
    parser = argparse.ArgumentParser(description="jerbs criteria updater and lock guard")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check-lock", action="store_true", help="Print LOCKED or CLEAR")
    group.add_argument("--set-lock", action="store_true", help="Create the lock file")
    group.add_argument("--clear-lock", action="store_true", help="Remove the lock file")
    group.add_argument("--add-ids", nargs="+", metavar="ID", help="Add screened message IDs")
    group.add_argument(
        "--enable-scheduler",
        nargs="+",
        metavar="JOB_ID",
        help="Set scheduler enabled=true with given cron job IDs",
    )
    group.add_argument(
        "--disable-scheduler",
        action="store_true",
        help="Set scheduler enabled=false and clear cron_jobs",
    )
    group.add_argument(
        "--set-rapid-mode",
        nargs=2,
        metavar=("JOB_ID", "UNTIL_ISO"),
        help="Store rapid-mode cron job ID and expiry timestamp",
    )
    group.add_argument(
        "--clear-rapid-mode",
        nargs="+",
        metavar="JOB_ID",
        help="Revert to standard schedule with given cron job IDs",
    )
    args = parser.parse_args()

    if args.check_lock:
        check_lock()
    elif args.set_lock:
        set_lock()
    elif args.clear_lock:
        clear_lock()
    elif args.add_ids:
        add_ids(args.add_ids)
    elif args.enable_scheduler:
        enable_scheduler(args.enable_scheduler)
    elif args.disable_scheduler:
        disable_scheduler()
    elif args.set_rapid_mode:
        set_rapid_mode([args.set_rapid_mode[0]], args.set_rapid_mode[1])
    elif args.clear_rapid_mode:
        clear_rapid_mode(args.clear_rapid_mode)


if __name__ == "__main__":
    main()
