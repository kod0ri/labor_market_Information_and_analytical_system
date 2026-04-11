import requests
from bs4 import BeautifulSoup
import time
import psycopg2
from psycopg2.extras import Json
import os
from dotenv import load_dotenv

# 1. Завантажуємо змінні середовища з файлу .env
load_dotenv()

# Заголовки для імітації реального браузера (захист від блокування)
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
            host="localhost",
            port="5432"
        )
        return conn
    except Exception as e:
        print(f"❌ Помилка підключення до БД: {e}")
        return None

def parse_job_page(job_url):
    """Заходить на сторінку вакансії, дістає опис, зарплату, компанію та місто"""
    response = requests.get(job_url, headers=headers)
    if response.status_code != 200:
        return "", "", "", "" # Тепер повертаємо 4 значення
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1. Шукаємо опис
    description_div = soup.find('div', id='job-description')
    description = description_div.text.strip() if description_div else ""
    
    # 2. Шукаємо зарплату
    salary = ""
    for tag in soup.find_all(['b', 'span']):
        text = tag.text.strip()
        if 'грн' in text or '$' in text or '€' in text:
            if any(char.isdigit() for char in text):
                salary = text
                break

    # 3. Шукаємо компанію (шукаємо посилання, що веде на профіль роботодавця)
    company = ""
    company_tag = soup.find('a', href=lambda href: href and '/employers/' in href)
    if company_tag:
        # Іноді там є картинка логотипу, тому використовуємо get_text(strip=True)
        company = company_tag.get_text(strip=True)

    # 4. Шукаємо місто (іноді воно лежить у класі 'text-muted' поруч із компанією)
    # На Work.ua місто зазвичай йде після назви компанії або має іконку локації.
    # Найпростіший спосіб для сторінки вакансії - знайти текст із популярними містами або "Дистанційно"
    location = ""
    # Збираємо всі абзаци <p>, щоб знайти той, що описує локацію
    for p_tag in soup.find_all('p'):
        text = p_tag.get_text(strip=True)
        # Шукаємо ключові слова для локації або перевіряємо, чи є місто у тексті
        if 'Київ' in text or 'Львів' in text or 'Дистанційно' in text or 'Одеса' in text:
            # Обмежуємо довжину, щоб не схопити цілий абзац опису
            if len(text) < 50: 
                location = text
                break

    return description, salary, company, location

def run_scraper():
    # Підключення до БД
    conn = connect_to_db()
    if not conn:
        return
    cursor = conn.cursor()

    # 2. Словник категорій для парсингу: "Назва категорії": "Посилання"
    categories_to_scrape = {
        "IT": "https://www.work.ua/jobs-it/",
        "Marketing": "https://www.work.ua/jobs-marketing/",
        "Administration": "https://www.work.ua/jobs-administration/"
    }

    # Скільки сторінок парсити для КОЖНОЇ категорії (зараз стоїть 2 для тестування)
    max_pages = 2 
    total_saved = 0

    # 3. Основний цикл по категоріях
    for category_name, base_url in categories_to_scrape.items():
        print(f"\n{'='*50}")
        print(f"🚀 ПОЧИНАЄМО ПАРСИНГ КАТЕГОРІЇ: {category_name} ({base_url})")
        print(f"{'='*50}\n")
        
        # 4. Цикл пагінації (сторінки)
        for page in range(1, max_pages + 1):
            if page == 1:
                current_url = base_url
            else:
                current_url = f"{base_url}?page={page}"
                
            print(f"📄 Відкриваємо сторінку {page}...")
            
            response = requests.get(current_url, headers=headers)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                job_headers = soup.find_all('h2')
                
                # Якщо вакансій на сторінці більше немає - переходимо до наступної категорії
                if not job_headers:
                    print(f"⚠️ Вакансії у категорії '{category_name}' закінчилися.")
                    break 
                
                # 5. Перебираємо всі вакансії на сторінці
                for header in job_headers:
                    link_tag = header.find('a')
                    
                    if link_tag and '/jobs/' in link_tag.get('href', ''):
                        title = link_tag.text.strip()
                        href = link_tag.get('href')
                        job_id = href.split('/')[-2]
                        link = "https://www.work.ua" + href
                        
                        # Заходимо на сторінку самої вакансії
                        full_description, salary, company, location = parse_job_page(link)
                        
                        # Пакуємо додаткові дані в JSON (тепер тут є компанія і місто!)
                        raw_json_data = {
                            "title": title,
                            "url": link,
                            "salary": salary,
                            "company": company,
                            "location": location
                        }
                        
                        try:
                            # 6. SQL-запит для вставки даних у БД
                            insert_query = """
                                INSERT INTO staging.raw_vacancies 
                                (source_name, external_id, raw_html, raw_json, search_category)
                                VALUES (%s, %s, %s, %s, %s)
                                ON CONFLICT DO NOTHING;
                            """
                            cursor.execute(insert_query, (
                                "work.ua", 
                                job_id, 
                                full_description, 
                                Json(raw_json_data), 
                                category_name
                            ))
                            
                            # Перевіряємо, чи вакансія нова (не дублікат)
                            if cursor.rowcount > 0:
                                total_saved += 1
                                print(f"  ✅ Збережено: [{category_name}] {title} (ID: {job_id})")
                            else:
                                print(f"  ⏩ Пропущено (вже є в БД): {title}")
                                
                            conn.commit()
                        except Exception as e:
                            print(f"  ❌ Помилка БД: {e}")
                            conn.rollback()
                        
                        # 7. ОБОВ'ЯЗКОВА ПАУЗА (щоб сайт не заблокував IP)
                        time.sleep(1.5)
            else:
                print(f"❌ Помилка сторінки {page}. Код: {response.status_code}")
                break

    # Закриваємо з'єднання
    cursor.close()
    conn.close()
    print(f"\n🎉 Парсинг завершено! Усього додано нових вакансій: {total_saved}")

if __name__ == "__main__":
    run_scraper()