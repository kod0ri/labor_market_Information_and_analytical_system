import asyncio
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


async def fetch_html(
    session: aiohttp.ClientSession, url: str, retries: int = 3
) -> Optional[str]:
    timeout_settings = ClientTimeout(total=15)
    for attempt in range(retries):
        try:
            async with session.get(url, headers=HEADERS, timeout=timeout_settings) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                elif response.status == 404:
                    return None
                else:
                    response.raise_for_status()
        except Exception as e:
            if attempt == retries - 1:
                print(f"   ❌ Помилка мережі ({url}): {e}")
                return None
            await asyncio.sleep(2 ** attempt)
    return None
