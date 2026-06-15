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
    if " в " not in title:
        return title.strip(), None, None
    position, _, rest = title.rpartition(" в ")
    company, location = rest, None
    if "," in rest:
        company, location = (p.strip() for p in rest.split(",", 1))
    return position.strip() or title.strip(), (company or None), (location or None)


def _parse_feed(xml_text: str) -> list[dict]:
    items: list[dict] = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        description = item.findtext("description") or ""
        if not link or not description:
            continue
        m = _ID_RE.search(link)
        external_id = m.group(1) if m else link
        raw_title = (item.findtext("title") or "").strip()
        title, company, location = _parse_title(raw_title)
        items.append({
            "external_id": str(external_id)[:100],
            "raw_html": description,
            "raw_json": {"title": title, "company": company or "", "location": location or "", "url": link},
        })
    return items


async def main() -> None:
    await AsyncDatabasePool.initialize()
    print(f"📰 Збір вакансій з DOU.ua RSS ({len(_CATEGORIES)} категорій)...")
    inserted = 0

    async with aiohttp.ClientSession() as session:
        for category in _CATEGORIES:
            url = f"{_BASE}?category={category}"
            xml_text = await fetch_html(session, url)
            if not xml_text:
                continue
            try:
                items = await asyncio.to_thread(_parse_feed, xml_text)
            except ET.ParseError as exc:
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
                        "dou.ua", it["external_id"], category,
                        it["raw_html"], json.dumps(it["raw_json"], ensure_ascii=False),
                    )
                    if new_id:
                        inserted += 1

    print(f"✅ DOU.ua: +{inserted} нових вакансій у чергу на LLM-обробку.")


if __name__ == "__main__":
    asyncio.run(main())
