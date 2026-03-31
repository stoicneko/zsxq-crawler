"""zsxq monitor — real-time content monitoring service.

Usage:
    python monitor.py                    # poll every 5 minutes
    python monitor.py --interval 60      # poll every 60 seconds
    python monitor.py --no-notify        # don't notify web app
    python monitor.py -v                 # verbose logging
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from zsxq_crawler.client import AuthError, ZsxqClient
from zsxq_crawler.config import Config
from zsxq_crawler.monitor import Monitor
from zsxq_crawler.storage import Storage


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="zsxq monitor — 实时监控更新")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Polling interval in seconds (default: 300)",
    )
    parser.add_argument("--no-images", action="store_true", help="Skip image downloads")
    parser.add_argument("--no-files", action="store_true", help="Skip file downloads")
    parser.add_argument("--no-comments", action="store_true", help="Skip comment fetching")
    parser.add_argument(
        "--notify-url",
        type=str,
        default=None,
        help="Web app reload URL (default: http://localhost:5000/api/reload)",
    )
    parser.add_argument("--no-notify", action="store_true", help="Disable web app notification")
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = Config.from_env()

    if args.no_images or args.no_files or args.no_comments:
        config = Config(
            cookie=config.cookie,
            group_id=config.group_id,
            request_delay=config.request_delay,
            batch_size=config.batch_size,
            batch_pause=config.batch_pause,
            download_images=config.download_images and not args.no_images,
            download_files=config.download_files and not args.no_files,
            crawl_comments=config.crawl_comments and not args.no_comments,
            output_dir=config.output_dir,
            max_pages=config.max_pages,
            since=config.since,
        )

    interval = args.interval if args.interval is not None else int(os.getenv("ZSXQ_MONITOR_INTERVAL", "300"))

    if args.no_notify:
        notify_url = None
    else:
        notify_url = args.notify_url or "http://localhost:5000/api/reload"

    reload_token = os.getenv("ZSXQ_RELOAD_TOKEN") or None
    storage = Storage(config.output_dir, config.group_id)

    with ZsxqClient(config) as client:
        monitor = Monitor(
            config,
            client,
            storage,
            interval=interval,
            notify_url=notify_url,
            reload_token=reload_token,
        )
        try:
            stats = monitor.run()
            print(f"\nMonitor stopped. {stats['polls']} polls, {stats['topics']} new topics crawled.")
        except AuthError as e:
            print(f"\nAuth error: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nMonitor stopped by user.")
            sys.exit(0)


if __name__ == "__main__":
    main()
