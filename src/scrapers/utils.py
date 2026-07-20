"""
Спільні низькорівневі утиліти для HTML-скраперів work.ua: HTTP-фетч із
ретраями та парсинг карток списку. Винесено окремо, бо і workua_vacancies.py,
і workua_resumes.py повторюють один і той самий алгоритм обходу сторінок
пагінації над однаковою HTML-розміткою.
"""

import asyncio
from typing import Optional

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup

# Підробний User-Agent браузера — work.ua віддає інший (урізаний або 403)
# HTML ботам без нього; це публічний, без автентифікації HTML-скрапінг.
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
    result: dict[str, str] = {}                            # накопичуємо {external_id: повний url}
    for card in soup.find_all("div", class_="card-hover"):  # кожна картка списку - один блок оголошення
        link_tag = card.find("a", href=True)                # перше посилання всередині картки
        if not link_tag:
            continue
        href = link_tag.get("href")                          # відносний шлях типу "/jobs/1234567/"
        if isinstance(href, str) and href.startswith(path_prefix):   # фільтруємо сторонні посилання в картці
            parts = href.split("/")            # "/jobs/1234567/" → ["", "jobs", "1234567", ""]
            if len(parts) > 2:
                result[parts[2]] = f"https://www.work.ua{href}"   # parts[2] = сам external_id
    return result


async def fetch_html(
    session: aiohttp.ClientSession, url: str, retries: int = 3
) -> Optional[str]:
    """Завантажує сторінку з ретраями; повертає None, якщо сторінка не існує
    (404) чи всі спроби вичерпані (мережева помилка/невідома HTTP-помилка)."""
    timeout_settings = ClientTimeout(total=15)   # 15с на весь запит - достатньо для звичайної HTML-сторінки
    for attempt in range(retries):               # до 3 спроб за замовчуванням
        try:
            async with session.get(url, headers=HEADERS, timeout=timeout_settings) as response:
                if response.status == 200:
                    return await response.text()      # успіх - повертаємо сирий HTML одразу
                elif response.status == 429:
                    # Rate-limit від work.ua - зростаюча пауза (5s, 10s, 15s),
                    # а не миттєвий повтор, який лише продовжив би бан.
                    await asyncio.sleep(5 * (attempt + 1))
                elif response.status == 404:
                    # Сторінки більше нема (видалене оголошення/кінець пагінації) -
                    # це не помилка, що варта ретраю, тому не йде в except нижче.
                    return None
                else:
                    response.raise_for_status()
        except Exception as e:
            if attempt == retries - 1:
                print(f"   ❌ Помилка мережі ({url}): {e}")
                return None
            # Експоненційний backoff між спробами (1s, 2s, 4s...)
            await asyncio.sleep(2 ** attempt)
    return None
