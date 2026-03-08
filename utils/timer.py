import asyncio
from typing import Callable, Coroutine, Any


async def run_timer(seconds: int, callback: Callable[[], Coroutine[Any, Any, None]]):
    """Ожидает указанное количество секунд, затем вызывает callback."""
    await asyncio.sleep(seconds)
    await callback()
