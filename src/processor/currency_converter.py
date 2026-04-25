import aiohttp
from src.db.database import AsyncDatabasePool


async def get_conversion_rates():
    """Отримує актуальні курси валют від НБУ асинхронно."""
    try:
        url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
        async with aiohttp.ClientSession() as session:
            timeout = aiohttp.ClientTimeout(total=10)
            async with session.get(url, timeout=timeout) as response:
                response.raise_for_status()
                data = await response.json()

        usd_rate = next((item["rate"] for item in data if item["cc"] == "USD"), None)
        eur_rate = next((item["rate"] for item in data if item["cc"] == "EUR"), None)

        if not usd_rate:
            raise ValueError("Не вдалося знайти курс USD")

        print(
            f"📊 Поточний курс НБУ: 1 USD = {usd_rate:.2f} UAH, 1 EUR = {eur_rate:.2f} UAH"
        )
        return {"USD": 1.0, "UAH": 1.0 / usd_rate, "EUR": eur_rate / usd_rate}
    except Exception as e:
        print(
            f"⚠️ Помилка отримання курсів: {e}. Використовуємо резервні статичні значення."
        )
        return {"USD": 1.0, "UAH": 1.0 / 40.0, "EUR": 43.0 / 40.0}


async def process_table(conn, table_name, rates):
    """Оновлює колонки _eq (які вже є в базі за замовчуванням)."""
    # Змінили min_salary_usd на min_salary_usd_eq
    records = await conn.fetch(f"""
        SELECT id, min_salary, max_salary, currency 
        FROM {table_name} 
        WHERE currency IS NOT NULL 
          AND (min_salary IS NOT NULL OR max_salary IS NOT NULL)
          AND min_salary_usd_eq IS NULL;
    """)

    if not records:
        print(f"✨ Немає нових записів для конвертації у таблиці {table_name}.")
        return 0

    updates = []
    for record in records:
        record_id = record["id"]
        min_sal = record["min_salary"]
        max_sal = record["max_salary"]
        currency = record["currency"].upper().strip()

        multiplier = rates.get(currency)
        if not currency:
            continue

        min_usd = int(float(min_sal) * multiplier) if min_sal is not None else None
        max_usd = int(float(max_sal) * multiplier) if max_sal is not None else None

        updates.append((min_usd, max_usd, record_id))

    if updates:
        # Пишемо у правильні колонки з суфіксом _eq
        await conn.executemany(
            f"""
            UPDATE {table_name}
            SET min_salary_usd_eq = $1, max_salary_usd_eq = $2
            WHERE id = $3;
        """,
            updates,
        )

    return len(updates)


async def run_conversion():
    print("🚀 Починаємо процес нормалізації зарплат...")
    rates = await get_conversion_rates()

    async with AsyncDatabasePool.get_connection() as conn:
        async with conn.transaction():
            # Ми ПРИБРАЛИ ensure_columns_exist(), бо правильні колонки вже є
            vacancies_updated = await process_table(conn, "core.vacancies", rates)
            resumes_updated = await process_table(conn, "core.resumes", rates)

            print(
                f"✅ Готово! Оновлено вакансій: {vacancies_updated}, Оновлено резюме: {resumes_updated}"
            )

if __name__ == "__main__":
    import asyncio
    async def _main():
        await AsyncDatabasePool.initialize()
        try:
            await run_conversion()
        finally:
            await AsyncDatabasePool.close_all()
    asyncio.run(_main())
