-- Сирі вакансії
CREATE TABLE staging.raw_vacancies (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name VARCHAR(100),       -- Назва сайту звідки взяли
    external_id VARCHAR(100),       -- ID на сайті-донорі
    search_category VARCHAR(100),   -- Категорія пошуку
    raw_html TEXT,                  -- Оригінальний HTML або опис
    raw_json JSONB,                 -- Якщо парсили через API, зберігаємо весь JSON
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_name, external_id)
);

-- Сирі резюме
CREATE TABLE staging.raw_resumes (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_name VARCHAR(100),
    external_id VARCHAR(100),
    raw_text TEXT,
    raw_json JSONB,
    parsed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_name, external_id)
);