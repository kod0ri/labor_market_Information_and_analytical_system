import os
import json
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Імпортуємо наш пул з'єднань
from src.db.database import DatabasePool

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Оновлений Промпт
SYSTEM_INSTRUCTION = """
Ти професійний IT-аналітик та Data Engineer. Твоє завдання: проаналізувати текст вакансії.
Ти ПОВИНЕН повернути результат ВИКЛЮЧНО у форматі JSON за такою структурою:
{
    "skills": [
        {"name": "Python", "category": "Hard"}, 
        {"name": "Teamwork", "category": "Soft"}
    ],
    "experience_years": 2, // Досвід роботи в РОКАХ (число). Якщо вказано "від 1 року" -> 1. Якщо "Junior" -> 0. Якщо не зрозуміло - null.
    "english_level": "Intermediate", // Рівень англійської (Beginner, Pre-Intermediate, Intermediate, Upper-Intermediate, Advanced, Fluent). Якщо не вказано - null.
    "min_salary": 20000, 
    "max_salary": 40000, 
    "currency": "UAH", // UAH, USD, EUR
    "company_industry": "IT", 
    "website_url": "https://example.com", 
    "region": "Київська область" 
}
"""


def clean_json_response(text):
    """Очищає відповідь LLM від Markdown-обгорток"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def get_or_create_company(cursor, company_name_val, industry, website):
    if not company_name_val:
        return None
    cursor.execute(
        """
        INSERT INTO dictionaries.companies (name, industry, website_url) 
        VALUES (%s, %s, %s) 
        ON CONFLICT (name) DO UPDATE 
        SET industry = COALESCE(dictionaries.companies.industry, EXCLUDED.industry),
            website_url = COALESCE(dictionaries.companies.website_url, EXCLUDED.website_url)
        RETURNING id;
    """,
        (company_name_val, industry, website),
    )
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute(
        "SELECT id FROM dictionaries.companies WHERE name = %s;", (company_name_val,)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def get_or_create_location(cursor, city_name, region):
    if not city_name:
        return None
    cursor.execute(
        "SELECT id FROM dictionaries.locations WHERE city_name = %s LIMIT 1;",
        (city_name,),
    )
    result = cursor.fetchone()
    if result:
        return result[0]

    cursor.execute(
        """
        INSERT INTO dictionaries.locations (city_name, region) 
        VALUES (%s, %s) RETURNING id;
    """,
        (city_name, region),
    )
    result = cursor.fetchone()
    return result[0] if result else None


def get_or_create_skill(cursor, skill_name_val, category):
    if not skill_name_val:
        return None
    cursor.execute(
        """
        INSERT INTO dictionaries.skills (name, category) 
        VALUES (%s, %s) ON CONFLICT (name) DO NOTHING;
    """,
        (skill_name_val, category),
    )
    cursor.execute(
        "SELECT id FROM dictionaries.skills WHERE name = %s;", (skill_name_val,)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def process_vacancies():
    DatabasePool.initialize()

    with DatabasePool.get_connection() as conn:
        with conn.cursor() as cursor:
            # Вибираємо до 100 нових вакансій
            cursor.execute("""
                SELECT s.id, s.external_id, s.raw_html, s.raw_json 
                FROM staging.raw_vacancies s
                LEFT JOIN core.vacancies c ON s.id = c.staging_id
                WHERE s.raw_html IS NOT NULL AND s.raw_html != '' AND c.id IS NULL
                LIMIT 100;
            """)
            vacancies = cursor.fetchall()

            if not vacancies:
                print("⚠️ Немає нових вакансій для обробки.")
                return

            print(f"🚀 Починаємо обробку {len(vacancies)} вакансій...\n")

            for staging_id, external_id, raw_html, raw_json in vacancies:
                title = raw_json.get("title", "Невідома посада")
                company_name = raw_json.get("company", "")
                location_name = raw_json.get("location", "")
                raw_salary = raw_json.get("salary", "")

                print(f"Обробляємо: [{staging_id}] {title}")

                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        prompt = f"Текст вакансії:\n{raw_html}\n\nВказана зарплата: {raw_salary}"
                        response = client.models.generate_content(
                            model="gemini-2.5-flash-lite",
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=SYSTEM_INSTRUCTION,
                                response_mime_type="application/json",
                                temperature=0.1,
                            ),
                        )

                        clean_text = clean_json_response(response.text)
                        ai_data = json.loads(clean_text)

                        comp_name = str(company_name)[:200] if company_name else None
                        loc_name = str(location_name)[:99] if location_name else None

                        comp_id = get_or_create_company(
                            cursor,
                            comp_name,
                            ai_data.get("company_industry"),
                            ai_data.get("website_url"),
                        )
                        loc_id = get_or_create_location(
                            cursor, loc_name, ai_data.get("region")
                        )

                        cursor.execute(
                            """
                            INSERT INTO core.vacancies 
                            (staging_id, title, company_id, location_id, min_salary, max_salary, currency, experience_years, english_level)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id;
                        """,
                            (
                                staging_id,
                                str(title)[
                                    :200
                                ],  # Захист від занадто довгих заголовків
                                comp_id,
                                loc_id,
                                ai_data.get("min_salary"),
                                ai_data.get("max_salary"),
                                ai_data.get("currency"),
                                ai_data.get("experience_years"),
                                ai_data.get("english_level"),
                            ),
                        )
                        new_vacancy_id = cursor.fetchone()[0]

                        skills = ai_data.get("skills", [])
                        for skill_obj in skills:
                            if isinstance(skill_obj, dict):
                                skill_name = str(skill_obj.get("name", ""))[
                                    :99
                                ]  # ОБРІЗАЄМО ДО 100 СИМВОЛІВ
                                skill_category = str(skill_obj.get("category", "Hard"))[
                                    :49
                                ]
                            else:
                                skill_name = str(skill_obj)[:99]
                                skill_category = "Hard"

                            if skill_name:
                                skill_id = get_or_create_skill(
                                    cursor, skill_name, skill_category
                                )
                                if skill_id:
                                    cursor.execute(
                                        """
                                        INSERT INTO core.vacancy_skills (vacancy_id, skill_id)
                                        VALUES (%s, %s) ON CONFLICT DO NOTHING;
                                    """,
                                        (new_vacancy_id, skill_id),
                                    )

                        conn.commit()
                        print("   💾 Успішно! Збережено у БД\n")
                        time.sleep(15)
                        break

                    except Exception as e:
                        conn.rollback()  # <--- КРИТИЧНО ВАЖЛИВО! ВІДКАТ ЗЛАМАНОЇ ТРАНЗАКЦІЇ
                        error_msg = str(e)
                        print(f"   🔥 ДЕТАЛІ ПОМИЛКИ: {error_msg}")

                        if (
                            "429" in error_msg
                            or "503" in error_msg
                            or "quota" in error_msg.lower()
                            or "UNAVAILABLE" in error_msg
                        ):
                            if attempt < max_retries - 1:
                                wait_time = 30 * (attempt + 1)
                                print(
                                    f"   ⚠️ Ліміт API. Охолоджуємо сервер {wait_time} секунд..."
                                )
                                time.sleep(wait_time)
                            else:
                                print(
                                    "   ❌ Ліміт спроб вичерпано. Пропускаємо запис.\n"
                                )
                        else:
                            print("   ❌ Непередбачена помилка БД/Коду. Йдемо далі.\n")
                            break


if __name__ == "__main__":
    process_vacancies()
