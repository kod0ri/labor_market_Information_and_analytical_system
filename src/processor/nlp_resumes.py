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

# Промпт адаптовано під структуру таблиці core.resumes
SYSTEM_INSTRUCTION = """
Ти професійний HR-аналітик та Data Engineer. Твоє завдання: проаналізувати текст резюме кандидата.
Ти ПОВИНЕН повернути результат ВИКЛЮЧНО у форматі JSON за такою структурою:
{
    "title": "Python Developer", // Бажана посада кандидата. Якщо вказано кілька, вибери головну.
    "location_name": "Львів", // Місто проживання або "Дистанційно". Якщо не вказано - null.
    "region": "Львівська область", // Область для вказаного міста.
    "expected_salary": 2500, // Очікувана зарплата (лише число). Якщо не вказана - null.
    "currency": "USD", // Валюта (UAH, USD, EUR). Якщо не вказана - null.
    "experience_years": 3, // Загальний досвід роботи кандидата У РОКАХ (ціле число). Якщо немає - 0.
    "english_level": "Upper-Intermediate", // Рівень англійської (Beginner, Pre-Intermediate, Intermediate, Upper-Intermediate, Advanced, Fluent). Якщо не вказано - null.
    "skills": [
        {
            "name": "Python", 
            "category": "Hard" // Hard або Soft
        }
    ]
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


def process_resumes():
    DatabasePool.initialize()

    with DatabasePool.get_connection() as conn:
        with conn.cursor() as cursor:
            # Вибираємо до 100 нових резюме
            cursor.execute("""
                SELECT s.id, s.external_id, s.raw_text, s.raw_json 
                FROM staging.raw_resumes s
                LEFT JOIN core.resumes c ON s.id = c.staging_id
                WHERE s.raw_text IS NOT NULL AND s.raw_text != '' AND c.id IS NULL
                LIMIT 100;
            """)
            resumes = cursor.fetchall()

            if not resumes:
                print("⚠️ Немає нових резюме для обробки.")
                return

            print(f"🚀 Починаємо обробку {len(resumes)} резюме...\n")

            for staging_id, external_id, raw_text, raw_json in resumes:
                category = raw_json.get("category", "Невідома")
                print(f"Обробляємо: [Staging ID: {staging_id}] (Категорія: {category})")

                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        prompt = f"Текст резюме:\n{raw_text}"
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

                        loc_id = get_or_create_location(
                            cursor, ai_data.get("location_name"), ai_data.get("region")
                        )
                        salary = ai_data.get("expected_salary")

                        cursor.execute(
                            """
                            INSERT INTO core.resumes 
                            (staging_id, title, location_id, min_salary, max_salary, currency, experience_years, english_level)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id;
                        """,
                            (
                                staging_id,
                                ai_data.get("title", "Не вказано"),
                                loc_id,
                                salary,
                                salary,
                                ai_data.get("currency"),
                                ai_data.get("experience_years"),
                                ai_data.get("english_level"),
                            ),
                        )
                        new_resume_id = cursor.fetchone()[0]

                        skills = ai_data.get("skills", [])
                        for skill_obj in skills:
                            if isinstance(skill_obj, dict):
                                skill_name = skill_obj.get("name")
                                skill_category = skill_obj.get("category", "Hard")
                            else:
                                skill_name = str(skill_obj)
                                skill_category = "Hard"

                            skill_id = get_or_create_skill(
                                cursor, skill_name, skill_category
                            )
                            if skill_id:
                                cursor.execute(
                                    """
                                    INSERT INTO core.resume_skills (resume_id, skill_id)
                                    VALUES (%s, %s) ON CONFLICT DO NOTHING;
                                """,
                                    (new_resume_id, skill_id),
                                )

                        conn.commit()
                        pos = ai_data.get("title", "Невідомо")
                        exp = ai_data.get("experience_years", 0)

                        print(f"   💾 Успішно! Посада: {pos}, Досвід: {exp} років.\n")

                        # 1. ЖОРСТКИЙ ЛІМІТ: 15 секунд паузи після успіху
                        # (Це гарантує максимум 4 запити на хвилину, що вбереже токени)
                        time.sleep(15)
                        break

                    except Exception as e:
                        error_msg = str(e)
                        if (
                            "429" in error_msg
                            or "503" in error_msg
                            or "quota" in error_msg.lower()
                            or "UNAVAILABLE" in error_msg
                        ):
                            if attempt < max_retries - 1:
                                # 2. АГРЕСИВНЕ ОХОЛОДЖЕННЯ: 30с, 60с, 90с...
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
                            print(f"   ❌ Непередбачена помилка: {error_msg}\n")
                            break


if __name__ == "__main__":
    process_resumes()
