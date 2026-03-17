"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    cookie: str
    group_id: str
    request_delay: float
    batch_size: int
    batch_pause: float
    download_images: bool
    download_files: bool
    crawl_comments: bool
    output_dir: str
    max_pages: int  # 0 means no limit
    since: str  # ISO date string like "2024-03-16", empty means no limit

    @staticmethod
    def from_env() -> Config:
        cookie = os.getenv("ZSXQ_COOKIE", "")
        if not cookie:
            print("Error: ZSXQ_COOKIE is required. See .env.example")
            sys.exit(1)

        group_id = os.getenv("ZSXQ_GROUP_ID", "")
        if not group_id:
            print("Error: ZSXQ_GROUP_ID is required. See .env.example")
            sys.exit(1)

        return Config(
            cookie=cookie,
            group_id=group_id,
            request_delay=float(os.getenv("ZSXQ_REQUEST_DELAY", "3")),
            batch_size=int(os.getenv("ZSXQ_BATCH_SIZE", "15")),
            batch_pause=float(os.getenv("ZSXQ_BATCH_PAUSE", "180")),
            download_images=os.getenv("ZSXQ_DOWNLOAD_IMAGES", "true").lower() == "true",
            download_files=os.getenv("ZSXQ_DOWNLOAD_FILES", "true").lower() == "true",
            crawl_comments=os.getenv("ZSXQ_CRAWL_COMMENTS", "true").lower() == "true",
            output_dir=os.getenv("ZSXQ_OUTPUT_DIR", "output"),
            max_pages=int(os.getenv("ZSXQ_MAX_PAGES", "0")),
            since=os.getenv("ZSXQ_SINCE", ""),
        )
