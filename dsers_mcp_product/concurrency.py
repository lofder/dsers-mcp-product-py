"""
Concurrency limiter using asyncio.Semaphore.
"""

import asyncio
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def p_limit(concurrency: int) -> Callable[[Callable[[], Awaitable[T]]], Awaitable[T]]:
    """Return a wrapper that limits concurrent async executions.

    Usage:
        limit = p_limit(5)
        results = await asyncio.gather(*[limit(task) for task in tasks])
    """
    sem = asyncio.Semaphore(concurrency)

    async def wrapper(fn: Callable[[], Awaitable[T]]) -> T:
        async with sem:
            return await fn()

    return wrapper  # type: ignore[return-value]
