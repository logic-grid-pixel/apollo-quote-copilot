"""Salesforce login with one retry on the org's spurious 504 upstream timeout."""

from __future__ import annotations

import time

import setup_quote_fields

RETRY_DELAY = 3.0
_sleep = time.sleep


def is_transient(exc: Exception) -> bool:
    text = str(exc).lower()
    return "504" in text or "upstream request timeout" in text


def connect(retries: int = 1, connect_fn=None):
    """Return a simple_salesforce client from .env, retrying transient login errors."""
    connect_fn = connect_fn or setup_quote_fields.connect
    for attempt in range(retries + 1):
        try:
            return connect_fn()
        except Exception as e:  # noqa: BLE001 - simple_salesforce raises several types
            if attempt >= retries or not is_transient(e):
                raise
            _sleep(RETRY_DELAY)
