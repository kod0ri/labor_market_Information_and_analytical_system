import asyncio
import aiohttp
from src.db.database import AsyncDatabasePool

_ALLOWED_TABLES: dict[str, str] = {
    "core.vacancies": "core.vacancies",
    "core.resumes": "core.resumes",
}


async def get_conversion_rates() -> dict[str, float] | None:
    """
    Повертає множники валют → USD за курсом НБУ, або None, якщо авторитетний
    курс USD отримати не вдалося.

    Ключовий інваріант: НЕ фабрикуємо курс. Записи конвертуються лише реальним
    курсом; результат (min/max_salary_usd_eq) стає non-NULL і БІЛЬШЕ НЕ
    переоцінюється (partial-index виключає такі записи). Тому разовий збій НБУ з
    захардкодженим фолбеком назавжди спотворив би зарплатну аналітику — краще
    пропустити прогін і повторити наступного разу з реальним курсом.

    Якщо USD є, а EUR немає — конвертуємо лише USD/UAH; EUR-записи лишаються на
    наступний прогін (не вставляємо у словник, тож process_table їх пропустить).
    """
    try:
        url = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                response.raise_for_status()
                data = await response.json()

        usd_rate = next((item["rate"] for item in data if item["cc"] == "USD"), None)   # грн за 1 USD, або None
        eur_rate = next((item["rate"] for item in data if item["cc"] == "EUR"), None)   # грн за 1 EUR, або None

        if not usd_rate:                     # без USD рахувати нема від чого - весь прогін безглуздий
            print("⚠️ У відповіді НБУ немає курсу USD — пропускаємо конвертацію до наступного прогону.")
            return None

        rates = {"USD": 1.0, "UAH": 1.0 / usd_rate}   # множники ДО USD: USD*1=USD; UAH*(1/курс)=USD
        if eur_rate is not None:
            print(f"📊 Поточний курс НБУ: 1 USD = {usd_rate:.2f} UAH, 1 EUR = {eur_rate:.2f} UAH")
            rates["EUR"] = eur_rate / usd_rate     # крос-курс EUR→USD через проміжний UAH
        else:
            print(f"📊 Поточний курс НБУ: 1 USD = {usd_rate:.2f} UAH, EUR — не знайдено; EUR-записи відкладено на наступний прогін.")
        return rates

    except Exception as e:
        print(f"⚠️ Помилка отримання курсів НБУ: {e}. Пропускаємо конвертацію до наступного прогону.")
        return None


async def process_table(conn, table_name: str, rates: dict[str, float]) -> int:
    """Конвертує min/max_salary → *_usd_eq для однієї таблиці (vacancies/resumes).

    `table_name` іде у SQL через f-string (asyncpg не параметризує ідентифікатори
    таблиць) - _ALLOWED_TABLES тут не про SQL-injection від користувача (виклик
    завжди з двома жорстко заданими іменами з run_conversion нижче), а страховка
    від помилки виклику з довільним рядком.
    """
    safe_table = _ALLOWED_TABLES.get(table_name)
    if safe_table is None:
        raise ValueError(f"Невідома таблиця: {table_name!r}. Дозволені: {list(_ALLOWED_TABLES)}")

    # WHERE ...usd_eq IS NULL - обробляємо лише те, що ще не конвертовано;
    # уже сконвертований запис більше НІКОЛИ не потрапить сюди повторно
    # (курс "заморожується" на момент першої конвертації, див. docstring вище).
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

    updates: list[tuple] = []       # накопичуємо (min_usd, max_usd, id) для пакетного UPDATE нижче
    for record in records:
        raw_currency = record["currency"]     # валюта як записав LLM (уже нормалізована схемою VacancySchema)

        if not raw_currency or not raw_currency.strip():   # порожня валюта - нема що конвертувати
            continue

        currency = raw_currency.upper().strip()   # захист про всяк випадок, навіть якщо схема вже нормалізувала
        multiplier = rates.get(currency)          # множник ДО USD для цієї валюти

        if multiplier is None:      # валюта не UAH/USD/EUR (rates не містить ключа) - пропускаємо запис
            continue

        min_sal = record["min_salary"]     # сира мінімальна ЗП у вихідній валюті (може бути None)
        max_sal = record["max_salary"]     # сира максимальна ЗП у вихідній валюті (може бути None)
        min_usd = int(float(min_sal) * multiplier) if min_sal is not None else None   # конвертуємо, обрізаючи до цілого
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

    if not rates:
        print("⏭️ Курс НБУ недоступний — конвертацію пропущено, записи лишаються на наступний прогін.")
        return

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
