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
    CONSTRAINT uq_location UNIQUE (city_name, region, country)
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
