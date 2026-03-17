"""知识星球爬虫入口

使用方法:
1. 复制 .env.example 为 .env 并填写 Cookie 和 Group ID
2. pip install -r requirements.txt
3. python main.py
"""

from __future__ import annotations

import argparse
import logging
import sys

from zsxq_crawler.client import AuthError, RateLimitError, ZsxqClient
from zsxq_crawler.config import Config
from zsxq_crawler.crawler import Crawler
from zsxq_crawler.storage import Storage


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="知识星球爬虫")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--no-images", action="store_true", help="Skip image downloads")
    parser.add_argument("--no-files", action="store_true", help="Skip file downloads")
    parser.add_argument("--no-comments", action="store_true", help="Skip comment fetching")
    parser.add_argument("--max-pages", type=int, default=0, help="Max pages to crawl (0=unlimited)")
    parser.add_argument("--since", type=str, default="", help="Only crawl topics after this date (e.g. 2024-03-16)")
    args = parser.parse_args()

    setup_logging(args.verbose)

    config = Config.from_env()

    # Apply CLI overrides (create new Config with overrides)
    if args.no_images or args.no_files or args.no_comments or args.max_pages or args.since:
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
            max_pages=args.max_pages if args.max_pages else config.max_pages,
            since=args.since if args.since else config.since,
        )

    storage = Storage(config.output_dir, config.group_id)

    with ZsxqClient(config) as client:
        crawler = Crawler(config, client, storage)
        try:
            stats = crawler.run()
            print(f"\nDone! {stats['topics']} topics, {stats['images']} images, "
                  f"{stats['files']} files, {stats['comments']} comments")
        except AuthError as e:
            print(f"\nAuth error: {e}", file=sys.stderr)
            sys.exit(1)
        except RateLimitError as e:
            print(f"\nRate limited: {e}", file=sys.stderr)
            print("Try again later or increase ZSXQ_REQUEST_DELAY / ZSXQ_BATCH_PAUSE", file=sys.stderr)
            sys.exit(2)
        except KeyboardInterrupt:
            print("\nInterrupted. Progress has been saved.")
            sys.exit(0)


if __name__ == "__main__":
    main()
