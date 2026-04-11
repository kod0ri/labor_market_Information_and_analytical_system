import requests
from bs4 import BeautifulSoup
import time
import json
import psycopg2
from psycopg2.extras import Json
import os
from dotenv import load_dotenv

# 1. Завантажуємо змінні з файлу .env (який лежить на рівень вище)
# Припускаємо, що скрипт запускається з кореневої папки project
load_dotenv()

url = "https://www.work.ua/jobs-kyiv-python/"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def connect_to_db():
    """Підключення до локальної бази даних PostgreSQL"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME", "core_postgres"),
            user=os.getenv("DB_USER", "admin_denis"),
            password=os.getenv("DB_PASSWORD", "passs"),
            host="localhost", # Оскільки ми запускаємо Python локально, а не в Docker
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"❌ Помилка підключення до БД: {e}")
        return None

def parse_job_page(job_url):
    """Заходить на сторінку, дістає опис і зарплату"""
    response = requests.get(job_url, headers=headers)
    if response.status_code != 200:
        return "", ""
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Шукаємо опис
    description_div = soup.find('div', id='job-description')
    description = description_div.text.strip() if description_div else ""
    
    # Шукаємо зарплату (зазвичай вона виділена тегом <b> або <span> і містить "грн", "$", "€")
    salary = ""
    for tag in soup.find_all(['b', 'span']):
        text = tag.text.strip()
        if 'грн' in text or '$' in text or '€' in text:
            # Перевіряємо, чи це справді схоже на зарплату (є цифри)
            if any(char.isdigit() for char in text):
                salary = text
                break # Знайшли зарплату - зупиняємо пошук
                
    return description, salary

def run_scraper():
    # Підключаємося до БД
    conn = connect_to_db()
    if not conn:
        return
    cursor = conn.cursor()

    print(f"Відправляємо запит на: {url}")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("✅ Головна сторінка завантажена! Починаємо збір...\n")
        soup = BeautifulSoup(response.text, 'html.parser')
        job_headers = soup.find_all('h2')
        
        count = 1
        for header in job_headers:
            link_tag = header.find('a')
            
            if link_tag and '/jobs/' in link_tag.get('href', ''):
                title = link_tag.text.strip()
                href = link_tag.get('href')
                job_id = href.split('/')[-2]
                link = "https://www.work.ua" + href
                
                print(f"[{count}] Парсимо: {title}")
                full_description, salary = parse_job_page(link)
                
                print(f"    💰 Зарплата: {salary if salary else 'Не вказана'}")
                
                # Формуємо JSON з додатковими даними
                raw_json_data = {
                    "title": title,
                    "url": link,
                    "salary": salary
                }
                
                # Записуємо в таблицю staging.raw_vacancies
                try:
                    insert_query = """
                        INSERT INTO staging.raw_vacancies 
                        (source_name, external_id, raw_html, raw_json)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING;
                    """
                    cursor.execute(insert_query, (
                        "work.ua", 
                        job_id, 
                        full_description, 
                        Json(raw_json_data)
                    ))
                    conn.commit() # Зберігаємо зміни в БД
                    print("    💾 Записано в базу!")
                except Exception as e:
                    print(f"    ❌ Помилка запису в БД: {e}")
                    conn.rollback()
                
                count += 1
                if count > 5: # Збільшив ліміт до 5 для тесту
                    print("\n🛑 Тестовий прогін завершено.")
                    break
                
                time.sleep(1.5)
                
    else:
        print(f"❌ Помилка завантаження. Код статусу: {response.status_code}")

    # Закриваємо з'єднання
    cursor.close()
    conn.close()
    print("🔌 Відключено від БД.")

if __name__ == "__main__":
    run_scraper()