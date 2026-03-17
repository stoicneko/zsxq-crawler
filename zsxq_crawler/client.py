"""HTTP client for the zsxq API with retry and rate limiting."""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from typing import Any
from urllib.parse import urlencode

import httpx

from zsxq_crawler.config import Config

logger = logging.getLogger(__name__)

API_BASE = "https://api.zsxq.com/v2"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


class RateLimitError(Exception):
    """Raised when the API returns error code 1059 (rate limited)."""


class AuthError(Exception):
    """Raised when the API returns 401 (unauthorized)."""


def _compute_signature(path: str, timestamp: str) -> str:
    """Compute X-Signature for the API request.

    Algorithm: SHA1("{url_path} {timestamp} zsxqapi2020")
    """
    raw = f"{path} {timestamp} zsxqapi2020"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class ZsxqClient:
    """Low-level HTTP client for the zsxq API."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._request_count = 0
        self._client = httpx.Client(timeout=30.0)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ZsxqClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _headers(self, path: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        return {
            "Cookie": self._config.cookie,
            "Origin": "https://wx.zsxq.com",
            "Referer": "https://wx.zsxq.com/",
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "X-Timestamp": timestamp,
            "X-Version": "2.83.0",
            "X-Signature": _compute_signature(path, timestamp),
            "X-Request-Id": uuid.uuid4().hex[:32],
        }

    def _rate_limit_wait(self) -> None:
        """Enforce rate limiting between requests."""
        self._request_count += 1

        if self._request_count == 1:
            return  # No wait on first request

        # Batch pause: every batch_size requests, take a long break
        if self._request_count % self._config.batch_size == 0:
            logger.info(
                "Batch pause: %d requests done, sleeping %.0fs...",
                self._request_count,
                self._config.batch_pause,
            )
            time.sleep(self._config.batch_pause)
        else:
            time.sleep(self._config.request_delay)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a GET request with retry logic.

        Returns the parsed JSON response body.
        Raises RateLimitError, AuthError, or httpx.HTTPError on failure.
        """
        url = f"{API_BASE}{path}"
        max_retries = 6
        delays = [2, 2, 2, 5, 5, 10]

        for attempt in range(max_retries + 1):
            self._rate_limit_wait()

            response = self._client.get(url, headers=self._headers(path), params=params)

            if response.status_code == 401:
                raise AuthError("Cookie expired or invalid. Please update ZSXQ_COOKIE.")

            if response.status_code == 429:
                if attempt < max_retries:
                    wait = delays[min(attempt, len(delays) - 1)]
                    logger.warning("HTTP 429 rate limited, retry %d/%d in %ds", attempt + 1, max_retries, wait)
                    time.sleep(wait)
                    continue
                raise RateLimitError("Rate limited after max retries")

            response.raise_for_status()
            data = response.json()

            if not data.get("succeeded"):
                code = data.get("code")
                logger.debug("API error response: %s", data)
                if code == 1059:
                    if attempt < max_retries:
                        wait = delays[min(attempt, len(delays) - 1)]
                        logger.warning("API code 1059, retry %d/%d in %ds", attempt + 1, max_retries, wait)
                        time.sleep(wait)
                        continue
                    raise RateLimitError(f"API error 1059 after max retries")
                raise RuntimeError(f"API error: code={code}, response={data}")

            return data

        raise RateLimitError("Exhausted retries")

    def download(self, url: str, dest_path: str) -> None:
        """Download a file from a URL to a local path."""
        self._rate_limit_wait()

        with self._client.stream("GET", url, headers=self._headers(""), follow_redirects=True) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
