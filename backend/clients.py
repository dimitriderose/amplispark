"""Singleton Gemini client.

Provides a lazy-initialised ``genai.Client`` so every agent shares one
connection pool instead of creating a fresh client at import time.
"""

import threading

from google import genai
from backend.config import GOOGLE_API_KEY

_client = None
_lock = threading.Lock()


def get_genai_client() -> genai.Client:
    global _client
    with _lock:
        if _client is None:
            _client = genai.Client(api_key=GOOGLE_API_KEY)
    return _client
