"""Event-loop factory for uvicorn on Windows (psycopg's async mode needs the selector loop).

Run the API with:
    uvicorn shopsense_api.entrypoints.api:app --loop shopsense_api.entrypoints.loop:selector_loop
"""

import asyncio


def selector_loop() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
