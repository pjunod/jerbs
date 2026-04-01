#!/usr/bin/env python3
"""
jerbs — local daemon for automated job email screening
Runs continuously, screening Gmail on a variable schedule and optionally
exporting results to a spreadsheet.

Usage:
    python jerbs.py                  # Run with saved criteria
    python jerbs.py --setup          # First-time setup wizard
    python jerbs.py --once           # Single run, then exit
    python jerbs.py --export         # Run once and export to xlsx
    python jerbs.py --send           # Enable auto-sending draft replies (careful!)
"""

import argparse
import json
import signal
import sys
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gmail_client import GmailClient
from scheduler import Scheduler
from screener import Screener
from setup_wizard import run_setup_wizard

CRITERIA_PATH = Path.home() / ".jerbs" / "criteria.json"
LOG_PATH = Path.home() / ".jerbs" / "jerbs.log"


def load_criteria(path: Path) -> dict:
    if not path.exists():
        print(f"\nNo criteria file found at {path}")
        print("Run with --setup to configure jerbs for the first time.\n")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def save_criteria(criteria: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(criteria, f, indent=2)


def log(msg: str, path: Path = LOG_PATH):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _log_result(result: dict, gmail: GmailClient, criteria: dict, send_mode: bool):
    """Log a single screening result and optionally send a draft reply."""
    verdict = result["verdict"]
    if verdict == "fail":
        return
    status = "INTERESTED" if verdict == "pass" else "MAYBE"
    log(f"  [{status}] {result.get('company', '?')} — {result.get('role', '?')}")
    if result.get("dealbreaker"):
        log(f"    Dealbreaker: {result['dealbreaker']}")
    if result.get("missing_fields"):
        log(f"    Missing: {', '.join(result['missing_fields'])}")
    if result.get("reply_draft"):
        log("    Draft reply generated.")
        if send_mode:
            _send_draft(gmail, result, criteria)


def run_screen(
    criteria: dict,
    gmail: GmailClient,
    screener: Screener,
    send_mode: bool = False,
    export: bool = False,
    interactive: bool = False,
) -> bool:
    """
    Run one full screening pass. Returns True if any draft replies were generated
    (triggers rapid mode in the scheduler).

    interactive=True streams results as each email is screened (for --once runs).
    interactive=False uses the Batch API when >3 emails (for daemon runs).
    """
    is_first = not criteria.get("screened_message_ids")
    lookback = 7 if is_first else criteria.get("search_settings", {}).get("lookback_days", 1)
    max_per_pass = (
        None if is_first else criteria.get("search_settings", {}).get("max_results_per_pass", 100)
    )

    log(f"Starting screen — lookback={lookback}d, max={max_per_pass or 'unlimited'}")

    def on_result(result: dict):
        _log_result(result, gmail, criteria, send_mode)

    results, had_drafts = screener.run(
        criteria=criteria,
        gmail=gmail,
        lookback_days=lookback,
        max_per_pass=max_per_pass,
        use_batch=not interactive,
        on_result=on_result if interactive else None,
    )

    if not results:
        log("No new emails to screen.")
        return False

    interested = [r for r in results if r["verdict"] == "pass"]
    maybe = [r for r in results if r["verdict"] == "maybe"]
    filtered = [r for r in results if r["verdict"] == "fail"]

    log(f"Results: {len(interested)} interested, {len(maybe)} maybe, {len(filtered)} filtered out")

    # In interactive mode results were already logged as they arrived; only log in batch/daemon mode.
    if not interactive:
        for r in results:
            _log_result(r, gmail, criteria, send_mode)

    if export:
        _export_results(results, criteria)

    criteria["last_run_date"] = datetime.now(UTC).strftime("%Y-%m-%d")
    new_ids = [r["message_id"] for r in results if r.get("message_id")]
    _update_screened_ids(criteria, new_ids)
    _prune_correspondence_log(criteria)
    save_criteria(criteria, CRITERIA_PATH)

    return had_drafts


def _send_draft(gmail: GmailClient, result: dict, criteria: dict):
    """Send a draft reply if send_mode is enabled."""
    thread_id = result.get("thread_id")
    draft = result.get("reply_draft")
    if not draft or not thread_id:
        return
    try:
        gmail.send_reply(
            thread_id=thread_id,
            body=draft,
            signature=criteria.get("reply_settings", {}).get("signature", ""),
        )
        log(f"    Sent reply to {result.get('company')} ({result.get('role')})")
    except Exception as e:
        log(f"    Failed to send reply: {e}")


def _export_results(results: list, criteria: dict):
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "shared" / "scripts"))
        from export_results import export_to_xlsx

        date_str = datetime.now().strftime("%Y-%m-%d")
        out = Path.home() / "Downloads" / f"jerbs_{date_str}.xlsx"
        export_to_xlsx({"run_date": date_str, "results": results}, str(out))
        log(f"Exported to {out}")
    except Exception as e:
        log(f"Export failed: {e}")


def _update_screened_ids(criteria: dict, new_ids: list[str]) -> None:
    """
    Migrate screened_message_ids to object format, add new IDs, and prune entries
    older than 60 days.

    Legacy format: list of plain strings — migrated to objects on first write.
    Object format: [{"id": "...", "screened_at": "YYYY-MM-DD"}, ...]
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    cutoff = (datetime.now(UTC) - timedelta(days=60)).strftime("%Y-%m-%d")

    existing: dict[str, str] = {}
    for entry in criteria.get("screened_message_ids", []):
        if isinstance(entry, dict):
            existing[entry["id"]] = entry["screened_at"]
        else:
            # Legacy string — assign today so it expires 60 days from migration
            existing[str(entry)] = today

    for msg_id in new_ids:
        if msg_id not in existing:
            existing[msg_id] = today

    criteria["screened_message_ids"] = [
        {"id": id_, "screened_at": sa} for id_, sa in existing.items() if sa >= cutoff
    ]


def _prune_correspondence_log(criteria: dict) -> None:
    """Prune closed correspondence log entries (replied_at set) older than 90 days."""
    log_path_str = criteria.get("correspondence_log_path", "~/.jerbs/correspondence.json")
    log_path = Path(log_path_str).expanduser()

    if not log_path.exists():
        return

    try:
        with open(log_path) as f:
            entries = json.load(f)

        cutoff = (datetime.now(UTC) - timedelta(days=90)).isoformat()
        pruned = [e for e in entries if not (e.get("replied_at") and e["replied_at"] < cutoff)]

        if len(pruned) < len(entries):
            with open(log_path, "w") as f:
                json.dump(pruned, f, indent=2)
            log(f"Pruned {len(entries) - len(pruned)} closed correspondence entries (>90 days old)")
    except Exception as e:
        log(f"Correspondence log pruning failed: {e}")


def print_summary(criteria: dict):
    comp = criteria.get("compensation", {})
    ids = criteria.get("screened_message_ids", [])
    last = criteria.get("last_run_date", "never")
    print(f"\n{'─' * 50}")
    print(f"  jerbs — {criteria.get('profile_name', 'My Job Search')}")
    print(f"{'─' * 50}")
    floor = comp.get("base_salary_floor")
    tc = comp.get("total_comp_target")
    print(f"  Base floor:    {f'${floor:,}' if isinstance(floor, int) else '?'}")
    print(f"  TC target:     {f'${tc:,}+' if isinstance(tc, int) else '?'}")
    print(f"  Last run:      {last}")
    print(f"  Screened IDs:  {len(ids)} emails on record")
    print(f"{'─' * 50}\n")


def main():
    parser = argparse.ArgumentParser(description="jerbs — automated job email screener")
    parser.add_argument("--setup", action="store_true", help="Run first-time setup wizard")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument(
        "--export", action="store_true", help="Export results to xlsx after each run"
    )
    parser.add_argument(
        "--send", action="store_true", help="Auto-send draft replies (use carefully)"
    )
    parser.add_argument("--criteria", default=str(CRITERIA_PATH), help="Path to criteria JSON file")
    args = parser.parse_args()

    criteria_path = Path(args.criteria)

    if args.setup:
        run_setup_wizard(criteria_path)
        print("\nSetup complete. Run `python jerbs.py` to start screening.\n")
        return

    criteria = load_criteria(criteria_path)
    print_summary(criteria)

    if args.send:
        print("⚠  Send mode enabled — draft replies will be sent automatically.")
        confirm = input("   Type 'yes' to confirm: ").strip().lower()
        if confirm != "yes":
            print("Cancelled.")
            return

    gmail = GmailClient()
    screener = Screener()

    if args.once:
        run_screen(
            criteria, gmail, screener, send_mode=args.send, export=args.export, interactive=True
        )
        return

    scheduler = Scheduler(
        biz_start_hour=criteria.get("search_settings", {}).get("biz_start_hour", 9),
        biz_end_hour=criteria.get("search_settings", {}).get("biz_end_hour", 17),
        timezone=criteria.get("search_settings", {}).get("timezone", "America/New_York"),
    )

    stop_event = threading.Event()

    def handle_signal(sig, frame):
        log("Shutting down jerbs...")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    log(
        f"jerbs daemon started. Biz hours: "
        f"{scheduler.biz_start}:00–{scheduler.biz_end}:00 {scheduler.tz_name}"
    )

    while not stop_event.is_set():
        interval = scheduler.current_interval()
        log(f"Waiting {interval // 60} min [{scheduler.current_mode()}]...")

        if stop_event.wait(timeout=interval):
            break

        criteria = load_criteria(criteria_path)
        had_drafts = run_screen(criteria, gmail, screener, send_mode=args.send, export=args.export)

        if had_drafts:
            scheduler.trigger_rapid()
            log("Draft replies generated — rapid mode active (5 min × 30 min)")

        scheduler.tick()

    log("jerbs stopped.")


if __name__ == "__main__":
    main()
