"""
Адаптер RSS-фідів DOU.ua (найбільша українська IT-спільнота).

На відміну від API-джерел, цінність DOU — у багатому НЕструктурованому описі
вакансії (скіли, зарплата, досвід, англійська сховані у тексті). Тому DOU йде
ШТАТНИМ LLM-шляхом: пишемо опис у staging.raw_vacancies (raw_html=опис), а далі
його обробляє nlp_vacancies (Groq), як і work.ua.

Фід: https://jobs.dou.ua/vacancies/feeds/?category=<Категорія>  → RSS 2.0
Елементи: title ("Посада в Компанія, локація"), link, description (HTML), pubDate.
"""

import asyncio
import json
import re
import xml.etree.ElementTree as ET

import aiohttp

from src.db.database import AsyncDatabasePool
from src.scrapers.utils import fetch_html

_BASE = "https://jobs.dou.ua/vacancies/feeds/"
_CATEGORIES = [
    "Python", "Java", "JavaScript", "C++", "C#/.NET", "PHP", "Ruby", "Golang",
    "QA", "DevOps", "Data Science", "Android", "iOS", "Front End", "Node.js",
]

_ID_RE = re.compile(r"/vacancies/(\d+)/")


def _parse_title(title: str) -> tuple[str, str | None, str | None]:
    """'Posada в Company, location' → (title, company, location). Best-effort."""
    if " в " not in title:                     # заголовок не в очікуваному форматі - повертаємо як є
        return title.strip(), None, None
    position, _, rest = title.rpartition(" в ")   # ділимо по ОСТАННЬОМУ " в " (посада може містити прийменник)
    company, location = rest, None
    if "," in rest:                                 # "Компанія, Місто" - розділяємо ще й локацію
        company, location = (p.strip() for p in rest.split(",", 1))
    return position.strip() or title.strip(), (company or None), (location or None)


def _parse_feed(xml_text: str, feed_category: str) -> list[dict]:
    """Розбирає один RSS-фід (одна технологічна категорія DOU) у список
    записів, готових під INSERT у staging.raw_vacancies."""
    items: list[dict] = []
    root = ET.fromstring(xml_text)      # парсимо RSS 2.0 XML у дерево елементів
    for item in root.iter("item"):      # кожен <item> - одна вакансія у фіді
        link = (item.findtext("link") or "").strip()             # URL сторінки вакансії на DOU
        description = item.findtext("description") or ""          # HTML-опис - те, що піде на LLM-обробку
        if not link or not description:      # без посилання чи опису запис марний - пропускаємо
            continue
        m = _ID_RE.search(link)                          # намагаємось витягти числовий id з /vacancies/<id>/
        external_id = m.group(1) if m else link           # фолбек - увесь link, якщо формат не збігся
        raw_title = (item.findtext("title") or "").strip()   # "Посада в Компанія, Місто"
        title, company, location = _parse_title(raw_title)    # розбираємо заголовок на 3 частини (best-effort)
        items.append({
            "external_id": str(external_id)[:100],
            "raw_html": description,
            "raw_json": {"title": title, "company": company or "", "location": location or "", "url": link,
                         "dou_feed": feed_category},
        })
    return items


async def main() -> None:
    """Проходить усі 15 технологічних фідів DOU.ua послідовно - фіди дрібні
    (десятки записів кожен), тож паралелізація тут не потрібна на відміну
    від work.ua/robota.ua з їхньою багатосторінковою пагінацією."""
    await AsyncDatabasePool.initialize()
    print(f"📰 Збір вакансій з DOU.ua RSS ({len(_CATEGORIES)} категорій)...")
    inserted = 0

    async with aiohttp.ClientSession() as session:
        for category in _CATEGORIES:                     # послідовно, один запит на технологічну категорію
            url = f"{_BASE}?category={category}"           # напр. .../feeds/?category=Python
            xml_text = await fetch_html(session, url)       # той самий fetch_html, що й у work.ua-скраперах
            if not xml_text:
                continue
            try:
                items = await asyncio.to_thread(_parse_feed, xml_text, category)   # парсинг XML - у окремому потоці
            except ET.ParseError as exc:            # фід прийшов пошкодженим/не-XML
                print(f"   ⚠️ {category}: не вдалось розпарсити RSS ({exc})")
                continue

            for it in items:
                async with AsyncDatabasePool.get_connection() as conn:
                    new_id = await conn.fetchval(
                        """
                        INSERT INTO staging.raw_vacancies
                            (source_name, external_id, search_category, raw_html, raw_json)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (source_name, external_id) DO NOTHING
                        RETURNING id;
                        """,
                        # search_category = канонічна мітка ринку (DOU — суто IT-борд);
                        # конкретний технологічний фід лежить у raw_json.dou_feed.
                        "dou.ua", it["external_id"], "IT",
                        it["raw_html"], json.dumps(it["raw_json"], ensure_ascii=False),
                    )
                    if new_id:
                        inserted += 1

    print(f"✅ DOU.ua: +{inserted} нових вакансій у чергу на LLM-обробку.")


if __name__ == "__main__":
    asyncio.run(main())
