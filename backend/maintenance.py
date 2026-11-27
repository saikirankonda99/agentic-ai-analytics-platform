"""Run bounded data-retention sweeps once or as a supervised service."""
from __future__ import annotations

import argparse
import json
import signal
import threading

from backend.data_lifecycle import run_retention
from backend.logging import get_logger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Run one sweep and exit (for cron and deployment checks).")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between sweeps; minimum 60.")
    args = parser.parse_args()
    if args.interval < 60:
        parser.error("--interval must be at least 60 seconds")
    stopped = threading.Event()
    for name in ("SIGINT", "SIGTERM"):
        signal.signal(getattr(signal, name), lambda *_: stopped.set())
    logger = get_logger(__name__)
    while not stopped.is_set():
        try:
            counts = run_retention()
            if args.once:
                print(json.dumps({"status": "ok", "deleted_or_pruned": counts}))
                return 0
            logger.info("retention_completed counts=%s", counts)
        except Exception as exc:
            logger.error("retention_failed error_type=%s", type(exc).__name__)
            if args.once:
                return 1
        stopped.wait(args.interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
