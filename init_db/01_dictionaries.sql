-- Джерела (Work.ua, Robota.ua, Djinni тощо)
CREATE TABLE dictionaries.sources (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    url VARCHAR(255)
);

-- Локації
CREATE TABLE dictionaries.locations (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city_name VARCHAR(100) NOT NULL,
    region VARCHAR(100),
    country VARCHAR(100) NOT NULL DEFAULT 'Ukraine',
    is_remote BOOLEAN DEFAULT FALSE
);


-- Компанії
CREATE TABLE dictionaries.companies (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    industry VARCHAR(150),
    website_url VARCHAR(255)
);

-- Канонічні навички (Python, SQL, React)
CREATE TABLE dictionaries.skills (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50) -- 'Hard', 'Soft'
);

-- Синоніми навичок для обробки тексту (NLP)
CREATE TABLE dictionaries.skill_synonyms (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    skill_id INTEGER NOT NULL REFERENCES dictionaries.skills(id) ON DELETE CASCADE,
    synonym VARCHAR(100) NOT NULL UNIQUE
);

-- ==========================================
-- ІНДЕКСИ (Створюються лише після таблиць!)
-- ==========================================
CREATE INDEX idx_locations_city ON dictionaries.locations(city_name);
CREATE INDEX idx_companies_name ON dictionaries.companies(name);
CREATE INDEX idx_skills_name ON dictionaries.skills(name);

CREATE UNIQUE INDEX uq_location_idx ON dictionaries.locations (
    city_name, 
    COALESCE(region, ''), 
    country
);