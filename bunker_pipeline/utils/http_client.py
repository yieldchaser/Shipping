#!/usr/bin/env python3
"""
Resilient HTTP Client for Bunker Scraping Pipeline
Implements:
- Desktop User-Agent rotation
- Requests Session pooling
- Exponential backoff with randomized jitter
- Rate limiting protection (1.5 - 2.5s jitter)
"""

import time
import random
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BunkerHttpClient")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.2478.80",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

class ResilientHttpClient:
    def __init__(self, min_delay: float = 1.5, max_delay: float = 2.5, max_retries: int = 4):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
        self.session = requests.Session()
        self._last_request_time = 0.0

    def _get_headers(self, custom_headers: dict = None) -> dict:
        ua = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        target_delay = random.uniform(self.min_delay, self.max_delay)
        if elapsed < target_delay:
            sleep_time = target_delay - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def get(self, url: str, params: dict = None, headers: dict = None, timeout: int = 15) -> requests.Response:
        full_headers = self._get_headers(headers)
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                response = self.session.get(url, params=params, headers=full_headers, timeout=timeout)
                if response.status_code == 200:
                    return response
                elif response.status_code in [429, 500, 502, 503, 504]:
                    backoff = (2 ** attempt) * random.uniform(1.0, 2.0)
                    logger.warning(f"HTTP {response.status_code} for {url}. Retrying in {backoff:.2f}s (Attempt {attempt+1}/{self.max_retries})...")
                    time.sleep(backoff)
                else:
                    logger.error(f"HTTP {response.status_code} for {url}: {response.text[:200]}")
                    return response
            except requests.RequestException as e:
                backoff = (2 ** attempt) * random.uniform(1.0, 2.0)
                logger.warning(f"Request exception {e} for {url}. Retrying in {backoff:.2f}s...")
                time.sleep(backoff)
        raise requests.RequestException(f"Failed to GET {url} after {self.max_retries} attempts.")

    def post(self, url: str, data: dict = None, json_payload: dict = None, headers: dict = None, timeout: int = 15) -> requests.Response:
        full_headers = self._get_headers(headers)
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                response = self.session.post(url, data=data, json=json_payload, headers=full_headers, timeout=timeout)
                if response.status_code == 200:
                    return response
                elif response.status_code in [429, 500, 502, 503, 504]:
                    backoff = (2 ** attempt) * random.uniform(1.0, 2.0)
                    logger.warning(f"HTTP {response.status_code} for {url}. Retrying in {backoff:.2f}s (Attempt {attempt+1}/{self.max_retries})...")
                    time.sleep(backoff)
                else:
                    logger.error(f"HTTP {response.status_code} for {url}: {response.text[:200]}")
                    return response
            except requests.RequestException as e:
                backoff = (2 ** attempt) * random.uniform(1.0, 2.0)
                logger.warning(f"Request exception {e} for {url}. Retrying in {backoff:.2f}s...")
                time.sleep(backoff)
        raise requests.RequestException(f"Failed to POST {url} after {self.max_retries} attempts.")

# Global client singleton
CLIENT = ResilientHttpClient()
