import os
import json
import time
import psycopg2
from google import genai
from google.genai import types
from dotenv import load_dotenv

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
    ], // Список навичок з їх категоріями (Hard або Soft). Якщо немає - [].
    "experience_level": "Middle", // Junior, Middle, Senior, Lead. Якщо не зрозуміло - null.
    "employment_type": "Remote", // Remote, Office, Part-time. Якщо не зрозуміло - null.
    "min_salary": 20000, 
    "max_salary": 40000, 
    "currency": "UAH",
    "company_industry": "IT", // Сфера діяльності компанії (Fintech, E-commerce тощо), якщо зрозуміло з тексту. Інакше - null.
    "website_url": "https://example.com", // Якщо в тексті є посилання на сайт компанії. Інакше - null.
    "region": "Київська область" // Виведи область для вказаного міста (наприклад, для Львова -> Львівська область).
}
"""

def connect_to_db():
    try:
        return psycopg2.connect(
            dbname=os.getenv("DB_NAME", "core_postgres"),
            user=os.getenv("DB_USER", "admin_denis"),
            password=os.getenv("DB_PASSWORD", "passs"),
            host="localhost",
            port="5432"
        )
    except Exception as e:
        print(f"❌ Помилка підключення: {e}")
        return None

def get_or_create_source(cursor, source_name, source_url):
    cursor.execute("""
        INSERT INTO dictionaries.sources (name, url) 
        VALUES (%s, %s) ON CONFLICT (name) DO NOTHING;
    """, (source_name, source_url))
    cursor.execute("SELECT id FROM dictionaries.sources WHERE name = %s;", (source_name,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_or_create_company(cursor, name, industry, website):
    if not name: return None
    cursor.execute("""
        INSERT INTO dictionaries.companies (name, industry, website_url) 
        VALUES (%s, %s, %s) 
        ON CONFLICT (name) DO UPDATE 
        SET industry = COALESCE(dictionaries.companies.industry, EXCLUDED.industry),
            website_url = COALESCE(dictionaries.companies.website_url, EXCLUDED.website_url)
        RETURNING id;
    """, (name, industry, website))
    result = cursor.fetchone()
    if result: return result[0]
    cursor.execute("SELECT id FROM dictionaries.companies WHERE name = %s;", (name,))
    result = cursor.fetchone()
    return result[0] if result else None

def get_or_create_location(cursor, city_name, region):
    if not city_name: return None
    cursor.execute("SELECT id FROM dictionaries.locations WHERE city_name = %s LIMIT 1;", (city_name,))
    result = cursor.fetchone()
    if result: return result[0]
    
    cursor.execute("""
        INSERT INTO dictionaries.locations (city_name, region) 
        VALUES (%s, %s) RETURNING id;
    """, (city_name, region))
    result = cursor.fetchone()
    return result[0] if result else None

def get_or_create_skill(cursor, name, category):
    if not name: return None
    cursor.execute("""
        INSERT INTO dictionaries.skills (name, category) 
        VALUES (%s, %s) ON CONFLICT (name) DO NOTHING;
    """, (name, category))
    cursor.execute("SELECT id FROM dictionaries.skills WHERE name = %s;", (name,))
    result = cursor.fetchone()
    return result[0] if result else None

def process_vacancies():
    conn = connect_to_db()
    if not conn:
        return
    cursor = conn.cursor()

    # Створюємо джерело
    source_id = get_or_create_source(cursor, 'work.ua', 'https://www.work.ua')
    if not source_id:
        print("❌ Не вдалося створити джерело work.ua")
        return

    # Беремо вакансії зі staging (5 полів: id, external_id, raw_html, raw_json, created_at)
    cursor.execute("""
        SELECT s.id, s.external_id, s.raw_html, s.raw_json, s.created_at 
        FROM staging.raw_vacancies s
        LEFT JOIN core.vacancies c ON s.external_id = c.external_id
        WHERE s.raw_html IS NOT NULL AND s.raw_html != '' AND c.id IS NULL
        LIMIT 3;
    """)
    vacancies = cursor.fetchall()
    
    if not vacancies:
        print("⚠️ Немає нових вакансій для обробки.")
        return

    print(f"🚀 Починаємо обробку {len(vacancies)} вакансій...\n")

    for vac_id, external_id, raw_html, raw_json, scraped_at in vacancies:
        title = raw_json.get('title', 'Невідома посада')
        company_name = raw_json.get('company', '')
        location_name = raw_json.get('location', '')
        raw_salary = raw_json.get('salary', '') 
        
        print(f"Обробляємо: [{external_id}] {title}")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                prompt = f"Текст вакансії:\n{raw_html}\n\nВказана зарплата: {raw_salary}"
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        response_mime_type="application/json",
                        temperature=0.1 
                    )
                )
                
                ai_data = json.loads(response.text)
                
                # --- ЗБЕРЕЖЕННЯ В БАЗУ ---
                try:
                    comp_id = get_or_create_company(cursor, company_name, ai_data.get('company_industry'), ai_data.get('website_url'))
                    loc_id = get_or_create_location(cursor, location_name, ai_data.get('region'))
                    
                    # 11 колонок і РІВНО 11 плейсхолдерів %s
                    cursor.execute("""
                        INSERT INTO core.vacancies 
                        (source_id, external_id, company_id, location_id, title, 
                         experience_level, employment_type, min_salary, max_salary, currency, published_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id;
                    """, (
                        source_id, external_id, comp_id, loc_id, title, 
                        ai_data.get('experience_level'), ai_data.get('employment_type'),
                        ai_data.get('min_salary'), ai_data.get('max_salary'), ai_data.get('currency'),
                        scraped_at
                    ))
                    new_vacancy_id = cursor.fetchone()[0]
                    
                    skills = ai_data.get('skills', [])
                    for skill_obj in skills:
                        if isinstance(skill_obj, dict):
                            skill_name = skill_obj.get('name')
                            skill_category = skill_obj.get('category')
                        else:
                            skill_name = str(skill_obj)
                            skill_category = 'Hard'
                            
                        skill_id = get_or_create_skill(cursor, skill_name, skill_category)
                        if skill_id:
                            cursor.execute("""
                                INSERT INTO core.vacancy_skills (vacancy_id, skill_id)
                                VALUES (%s, %s) ON CONFLICT DO NOTHING;
                            """, (new_vacancy_id, skill_id))
                            
                    conn.commit()
                    print(f"   💾 Успішно! Збережено у БД (Дата: {scraped_at.strftime('%Y-%m-%d')})\n")
                except Exception as db_error:
                    print(f"   ❌ Помилка запису в БД: {db_error}")
                    conn.rollback()
                break 
                
            except Exception as e:
                error_msg = str(e)
                if "503" in error_msg or "429" in error_msg or "UNAVAILABLE" in error_msg:
                    if attempt < max_retries - 1:
                        print(f"   ⚠️ Сервер зайнятий. Чекаємо 5 секунд...")
                        time.sleep(5)
                else:
                    print(f"   ❌ Непередбачена помилка: {error_msg}\n")
                    break
        time.sleep(2)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    process_vacancies()