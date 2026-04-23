import time
from typing import Callable, TypeVar

from openai import RateLimitError

T = TypeVar("T")

_RETRY_DELAYS = [10, 20, 40]


def call_with_retry(fn: Callable[[], T]) -> T:
    """Call fn, retrying on 429 RateLimitError with exponential backoff."""
    for i, delay in enumerate(_RETRY_DELAYS):
        try:
            return fn()
        except RateLimitError:
            print(f"[llm] rate limit hit, retrying in {delay}s (attempt {i + 1}/{len(_RETRY_DELAYS)})...")
            time.sleep(delay)
    return fn()
