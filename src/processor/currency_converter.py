import asyncio
import aiohttp
from src.db.database import AsyncDatabasePool

_ALLOWED_TABLES: dict[str, str] = {
    "core.vacancies": "core.vacancies",
    "core.resumes": "core.resumes",
}


async def get_conversion_rates() -> dict[str, float]:
    try:
        url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

        usd_rate = next((item["rate"] for item in data if item["cc"] == "USD"), None)
        eur_rate = next((item["rate"] for item in data if item["cc"] == "EUR"), None)

        if not usd_rate:
            raise ValueError("Не вдалося знайти курс USD у відповіді НБУ")

        if eur_rate is not None:
            print(f"📊 Поточний курс НБУ: 1 USD = {usd_rate:.2f} UAH, 1 EUR = {eur_rate:.2f} UAH")
            eur_multiplier = eur_rate / usd_rate
        else:
            print(f"📊 Поточний курс НБУ: 1 USD = {usd_rate:.2f} UAH, EUR — не знайдено, використовуємо резервне значення")
            eur_multiplier = 43.0 / 40.0

        return {"USD": 1.0, "UAH": 1.0 / usd_rate, "EUR": eur_multiplier}

    except Exception as e:
        print(f"⚠️ Помилка отримання курсів НБУ: {e}. Використовуємо резервні значення.")
        return {"USD": 1.0, "UAH": 1.0 / 40.0, "EUR": 43.0 / 40.0}


async def process_table(conn, table_name: str, rates: dict[str, float]) -> int:
    safe_table = _ALLOWED_TABLES.get(table_name)
    if safe_table is None:
        raise ValueError(f"Невідома таблиця: {table_name!r}. Дозволені: {list(_ALLOWED_TABLES)}")

    records = await conn.fetch(f"""
        SELECT id, min_salary, max_salary, currency
        FROM {safe_table}
        WHERE currency IS NOT NULL
          AND (min_salary IS NOT NULL OR max_salary IS NOT NULL)
          AND (min_salary_usd_eq IS NULL AND max_salary_usd_eq IS NULL);
    """)

    if not records:
        print(f"✨ Немає нових записів для конвертації у таблиці {table_name}.")
        return 0

    updates: list[tuple] = []
    for record in records:
        raw_currency = record["currency"]

        if not raw_currency or not raw_currency.strip():
            continue

        currency = raw_currency.upper().strip()
        multiplier = rates.get(currency)

        if multiplier is None:
            continue

        min_sal = record["min_salary"]
        max_sal = record["max_salary"]
        min_usd = int(float(min_sal) * multiplier) if min_sal is not None else None
        max_usd = int(float(max_sal) * multiplier) if max_sal is not None else None
        updates.append((min_usd, max_usd, record["id"]))

    if updates:
        await conn.executemany(
            f"""
            UPDATE {safe_table}
            SET min_salary_usd_eq = $1, max_salary_usd_eq = $2
            WHERE id = $3;
            """,
            updates,
        )

    return len(updates)


async def run_conversion() -> None:
    print("🚀 Починаємо процес нормалізації зарплат...")
    rates = await get_conversion_rates()

    async with AsyncDatabasePool.get_connection() as conn:
        async with conn.transaction():
            vacancies_updated = await process_table(conn, "core.vacancies", rates)
            resumes_updated = await process_table(conn, "core.resumes", rates)
            print(f"✅ Готово! Оновлено вакансій: {vacancies_updated}, резюме: {resumes_updated}")


if __name__ == "__main__":
    async def _main():
        await AsyncDatabasePool.initialize()
        try:
            await run_conversion()
        finally:
            await AsyncDatabasePool.close_all()

    asyncio.run(_main())
