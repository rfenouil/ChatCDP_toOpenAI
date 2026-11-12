import asyncio


async def with_retry(coro_factory, attempts=3, backoff=1.0, retry_on=(TimeoutError, RuntimeError)):
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return await coro_factory()
        except retry_on as exc:
            last_exc = exc
            if attempt == attempts:
                raise
            await asyncio.sleep(backoff * attempt)
    raise last_exc
