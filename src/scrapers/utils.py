import asyncio
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def parse_card_links(list_html: str, path_prefix: str) -> dict[str, str]:
    """
    Витягує {external_id: absolute_url} з картки-списку work.ua.

    Спільне для вакансій і резюме: сторінки мають однакову розмітку
    (`div.card-hover` з посиланням), відрізняється лише префікс шляху
    (`/jobs/` чи `/resumes/`). external_id — третій сегмент шляху
    (`/jobs/<id>/...`). Повертає лише посилання з потрібним префіксом.
    """
    soup = BeautifulSoup(list_html, "lxml")
    result: dict[str, str] = {}
    for card in soup.find_all("div", class_="card-hover"):
        link_tag = card.find("a", href=True)
        if not link_tag:
            continue
        href = link_tag.get("href")
        if isinstance(href, str) and href.startswith(path_prefix):
            parts = href.split("/")
            if len(parts) > 2:
                result[parts[2]] = f"https://www.work.ua{href}"
    return result


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
