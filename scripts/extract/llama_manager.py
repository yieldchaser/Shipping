"""
LlamaCloud / LlamaParse Multi-Account Key Pool Manager

Manages automatic failover across multiple LlamaCloud / LlamaParse accounts.
Detects quota exhaustion, HTTP 429, payment required, and automatically swaps to the next key.
Persists active key index and usage tracking in data/extracted/.llama_key_state.json.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Available key pool provided by user
KEY_POOL: List[Dict[str, str]] = [
    {
        "id": "account_1",
        "name": "Account 1 (Default / .env)",
        "api_key": "llx-AVMBvb0UULqQGzWhFFJScQpwhrTM8hSVMZvjz4PEGQ9utg1P",
        "email": "primary",
        "project_id": "fc67f8bc-f3cb-4769-9bc5-f0632726b792",
    },
    {
        "id": "account_2",
        "name": "Account 2 (Active pool)",
        "api_key": "llx-hM8tERqfFZk1JGzLdPcuSgcaBctblBqm76nIieMxIx6AnAgB",
        "email": "account2",
        "project_id": "43ad4139-373b-42d6-9938-f0e24487de99",
    },
    {
        "id": "account_3",
        "name": "Account 3 (Prateek)",
        "api_key": "llx-Eu4wULlrO9ZW39sfKGtdJ0FvtJT43JCFb9osFkpvMu9ET0gV",
        "email": "prateek",
        "project_id": "acc6b00f-986b-4b43-99db-81fc89a65477",
    },
    {
        "id": "account_4",
        "name": "Account 4 (Killer Biller)",
        "api_key": "llx-1aX1giQjhw4vnnC9rS88Jz8IIwUsep76k1ytmU0z2VOAdpOw",
        "email": "killer_biller",
        "project_id": "3ed8d533-8d30-425b-b773-da0e5425c264",
    },
    {
        "id": "account_5",
        "name": "Account 5 (Prateek Upadhyay)",
        "api_key": "llx-3gIntWgNcRfQ8JldOC2Fb1LjK7PRkuap8th9WCSxvMaVuqRw",
        "email": "puwork09@gmail.com",
        "project_id": "27afb5f9-fca9-4b0b-bc0c-9cc43a131e7d",
    },
    {
        "id": "account_6",
        "name": "Account 6 (Kumar Ravindra)",
        "api_key": "llx-87GMiUy5mtvFe4aOQ3BaQO4zBfki7Vr0g00QyQkgKodvxqYf",
        "email": "kumarravindra.bas@gmail.com",
        "project_id": "7c5fe4f8-5512-4fab-b78a-942ccbde4a1d",
    },
    {
        "id": "account_7",
        "name": "Account 7 (Saumya Kumar)",
        "api_key": "llx-g8p7UzojxIQocFBeWgvRDUpaQR6U56RK3nWniAtWuBksFjiD",
        "email": "kumarsaumya25@gmail.com",
        "project_id": "62189908-9595-4d62-bbaf-f1f056bb7c27",
    },
    {
        "id": "account_8",
        "name": "Account 8 (Amitesh Anand)",
        "api_key": "llx-PZfPrjiaGq7viHwYsEAa1tUnpt4t7qrPmwX1tMhVPv1W6ljB",
        "email": "anandamitesh5@gmail.com",
        "project_id": "07fafe1c-7341-4f1f-8df3-5a37599421e0",
    },
    {
        "id": "account_9",
        "name": "Account 9 (HIMANSHU)",
        "api_key": "llx-iPBWeHFR8uLLFnGW4UNb8UWfMpxc3yO8ZZXTGE5vYA4ULhz9",
        "email": "himanshhuuu11@gmail.com",
        "project_id": "545bc7b7-3b47-4bbb-82f7-9882873494ff",
    },
    {
        "id": "account_10",
        "name": "Account 10",
        "api_key": "llx-QTsgfH9db023z5wEayqYPA69IBQb89fTddzd59M9K88qCKSx",
        "email": "account_10",
        "project_id": "account_10_proj",
    },
    {
        "id": "account_11",
        "name": "Account 11",
        "api_key": "llx-ktqDvk0yiATER6mECOrOfeppPgi9Oos6g76sDyk7MKFZXmtn",
        "email": "account_11",
        "project_id": "account_11_proj",
    },
]

STATE_FILE = Path("data/extracted/.llama_key_state.json")


def _load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "current_key_idx": 0,
        "exhausted_keys": [],
        "total_calls": 0,
        "key_usage": {k["id"]: 0 for k in KEY_POOL},
    }


def _save_state(state: Dict[str, Any]):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


import threading

_lock = threading.Lock()


class KeyManager:
    """Manages active key selection and automatic rotation upon quota errors."""

    def __init__(self):
        self.state = _load_state()

    def get_current_key(self) -> str:
        with _lock:
            idx = self.state.get("current_key_idx", 0)
            exhausted = set(self.state.get("exhausted_keys", []))
            
            # If current is exhausted, find next available
            while idx < len(KEY_POOL) and KEY_POOL[idx]["id"] in exhausted:
                idx += 1
                
            if idx >= len(KEY_POOL):
                raise RuntimeError(
                    "ALL LlamaParse API keys in the pool are exhausted! "
                    "Please provide a new key to continue."
                )
                
            if idx != self.state.get("current_key_idx", 0):
                self.state["current_key_idx"] = idx
                _save_state(self.state)
                
            return KEY_POOL[idx]["api_key"]

    def get_current_account_info(self) -> Dict[str, str]:
        with _lock:
            idx = self.state.get("current_key_idx", 0)
            return KEY_POOL[min(idx, len(KEY_POOL) - 1)]

    def record_success(self, num_pages: int = 1, used_key: Optional[str] = None):
        with _lock:
            self.state = _load_state()
            used_id = None
            if used_key:
                for k in KEY_POOL:
                    if k["api_key"] == used_key or k["id"] == used_key:
                        used_id = k["id"]
                        break
            if not used_id:
                idx = self.state.get("current_key_idx", 0)
                used_id = KEY_POOL[min(idx, len(KEY_POOL) - 1)]["id"]
            self.state["total_calls"] = self.state.get("total_calls", 0) + 1
            usage = self.state.setdefault("key_usage", {})
            usage[used_id] = usage.get(used_id, 0) + num_pages
            _save_state(self.state)

    def mark_key_exhausted(self, reason: str = "quota_exceeded", failed_key: Optional[str] = None):
        with _lock:
            self.state = _load_state()
            exhausted = self.state.setdefault("exhausted_keys", [])
            
            failed_id = None
            if failed_key:
                for k in KEY_POOL:
                    if k["api_key"] == failed_key or k["id"] == failed_key:
                        failed_id = k["id"]
                        break
            if not failed_id:
                idx = self.state.get("current_key_idx", 0)
                failed_id = KEY_POOL[min(idx, len(KEY_POOL) - 1)]["id"]
                
            if failed_id not in exhausted:
                logger.warning(f"Key {failed_id} marked exhausted: {reason}")
                exhausted.append(failed_id)
                
            # Rotate to next non-exhausted key
            idx = 0
            while idx < len(KEY_POOL) and KEY_POOL[idx]["id"] in set(exhausted):
                idx += 1
                
            self.state["current_key_idx"] = idx
            _save_state(self.state)
            
            if idx >= len(KEY_POOL):
                raise RuntimeError(
                    f"ALL {len(KEY_POOL)} LlamaParse API keys are exhausted! Last reason: {reason}"
                )
                
            logger.info(f"Swapped to active key: {KEY_POOL[idx]['name']}")
            return KEY_POOL[idx]["api_key"]


manager = KeyManager()


def get_active_parser(tier: str = "agentic", version: str = "latest", **kwargs):
    """
    Creates a LlamaParse parser instance using the active API key from the pool.
    """
    from llama_parse import LlamaParse

    api_key = manager.get_current_key()
    result_type = kwargs.pop("result_type", "markdown")
    return LlamaParse(
        api_key=api_key,
        tier=tier,
        version=version,
        result_type=result_type,
        verbose=False,
        **kwargs
    )


def execute_with_auto_rotate(parse_fn, max_retries: int = 10, **kwargs):
    """
    Executes a parsing function. If a 429 / quota error occurs,
    automatically rotates the key and retries seamlessly.
    """
    for attempt in range(max_retries):
        try:
            return parse_fn(manager.get_current_key())
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ["429", "402", "quota", "payment required", "credit", "limit exceeded", "exhausted", "empty result", "empty or truncated output"]):
                logger.warning(f"Quota / payment error detected: {e}. Rotating API key...")
                try:
                    manager.mark_key_exhausted(reason=str(e))
                except RuntimeError as re:
                    raise re
            else:
                raise e
    raise RuntimeError("Max retries exceeded across available keys.")
